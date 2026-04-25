import socketserver
import logging
import json
import time
import argparse
import math
import numpy as np
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ==========================================
# Configuración del MVP ZKTCA
# ==========================================
SYSLOG_HOST = "0.0.0.0"
SYSLOG_PORT = 5140  # Puerto alternativo para evitar requerir root

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Estructuras de estado en memoria (Para el MVP, en producción usar InfluxDB/Redis)
session_state = defaultdict(list)
bullying_state = defaultdict(set)
night_activity_state = defaultdict(float)

# Diccionario mock de reputación y categorización de puertos/servicios
PORT_CATEGORIES = {
    19132: "Public_Gaming",  # Minecraft
    27015: "Public_Gaming",  # Steam
    25565: "Public_Gaming",  # Minecraft Java
    30000: "Public_Gaming",  # Generic game
    443: "Encrypted_Traffic",  # TLS (Telegram, Discord, etc.)
    5222: "Encrypted_Traffic",  # XMPP
    5223: "Encrypted_Traffic",  # XMPP TLS
    8443: "Encrypted_Traffic",  # Alt HTTPS
}

# Port to numeric category for transformer features
PORT_CAT_NUMERIC = {
    19132: 1.0, 27015: 1.0, 25565: 1.0, 30000: 1.0,  # gaming
    443: 2.0, 5222: 2.0, 5223: 2.0, 8443: 2.0,  # chat/encrypted
    8080: 3.0, 9000: 3.0,  # cloud
}

CLASS_NAMES = ["benign", "grooming", "bullying", "night_abuse", "exfiltration"]

# ==========================================
# Motor de Cumplimiento Legal (SFP 2026)
# ==========================================
class LegalComplianceModule:
    @staticmethod
    def generate_privacy_notice():
        notice = """
        === AVISO DE PRIVACIDAD SIMPLIFICADO (Ley Federal SFP 2026) ===
        El presente sistema de telemetría de red procesa únicamente METADATOS 
        (tamaño de paquetes, tiempos de conexión y direcciones IP) con el fin 
        exclusivo de garantizar el Interés Superior del Menor protegiéndolo de 
        riesgos digitales. 
        NO SE INSPECCIONA NI DESENCRIPTA EL CONTENIDO DE LA NAVEGACIÓN.
        Los metadatos se retendrán por un máximo de 30 días.
        ===============================================================
        """
        logging.info("Generando Aviso de Privacidad para Onboarding del Tutor.")
        print(notice)
        return True

    @staticmethod
    def execute_arco_download(user_ip):
        logging.info(f"[DERECHOS ARCO - DESCARGA] Generando perfil anonimizado para la IP {user_ip}.")
        return {"user": user_ip, "status": "Downloaded", "data": "Anonimized metadata summary..."}

    @staticmethod
    def execute_arco_deletion(user_ip):
        logging.info(f"[DERECHOS ARCO - ELIMINACIÓN] Purgando todos los registros de la IP {user_ip}.")
        if user_ip in session_state:
            del session_state[user_ip]
        if user_ip in bullying_state:
            del bullying_state[user_ip]
        return True


# ==========================================
# Motor de Reglas (Análisis de Riesgo)
# ==========================================
class RiskAnalyzer:
    @staticmethod
    def check_grooming(src_ip, current_time, dst_port):
        """
        Detección de Grooming (App Switching):
        Transición de Public_Gaming a Encrypted_Traffic en < 5 minutos.
        """
        category = PORT_CATEGORIES.get(dst_port, "Unknown")
        history = session_state[src_ip]

        history.append((current_time, category))

        # Mantener solo los últimos 10 eventos
        if len(history) > 10:
            history.pop(0)

        # Analizar transiciones
        gaming_time = None
        for timestamp, cat in history:
            if cat == "Public_Gaming":
                gaming_time = timestamp
            elif cat == "Encrypted_Traffic" and gaming_time is not None:
                diff = timestamp - gaming_time
                if diff < 300:  # 5 minutos
                    logging.warning(f"🚨 ALERTA GROOMING: Cambio rápido de app (Juego -> Chat) detectado en la IP {src_ip}. (IAT: {diff}s)")
                    gaming_time = None  # Reset
                    return True
        return False

    @staticmethod
    def check_bullying(dst_ip, src_ip, event_type, bytes_transfered):
        """
        Detección de Acoso/Bullying:
        Picos repentinos de tráfico entrante desde múltiples IPs no registradas.
        Simulamos que si dst_ip recibe de >3 IPs distintas en un corto lapso, es alerta.
        """
        if event_type == "NEW":
            bullying_state[dst_ip].add(src_ip)

            # Para el MVP, el umbral es bajo (3 IPs distintas). En prod: 10+
            if len(bullying_state[dst_ip]) > 3:
                logging.warning(f"🚨 ALERTA BULLYING/ACOSO: Pico de tráfico entrante asimétrico hacia {dst_ip} desde múltiples orígenes: {bullying_state[dst_ip]}")
                bullying_state[dst_ip].clear()  # Reset tras alerta
                return True
        return False

    @staticmethod
    def check_night_activity(src_ip, current_time, duration):
        """
        Detección de Uso Nocturno/Adicción:
        Actividad humana (conexiones > 30 mins) entre 11 PM y 4 AM.
        """
        now = datetime.fromtimestamp(current_time)
        if now.hour >= 23 or now.hour < 4:
            night_activity_state[src_ip] += duration
            # Si acumula más de 30 minutos (1800 segundos) de conexiones
            if night_activity_state[src_ip] > 1800:
                logging.warning(f"🚨 ALERTA USO NOCTURNO: Actividad persistente fuera de horario detectada en la IP {src_ip}.")
                night_activity_state[src_ip] = 0  # Reset
                return True
        return False


# ==========================================
# Transformer Tagger (ONNX Runtime)
# ==========================================
class TransformerTagger:
    """
    ZKTCA-Transformer inference engine using ONNX Runtime.
    Maintains a sliding window of 32 flow events per source IP
    and runs the transformer model for risk classification.
    """

    SEQUENCE_LENGTH = 32
    FEATURE_DIM = 12
    THRESHOLD = 0.5

    def __init__(self, model_path=None):
        self.session = None
        self.windows = defaultdict(list)  # per-IP sliding windows
        self.last_event_time = defaultdict(float)  # for IAT calculation
        self.dst_ip_history = defaultdict(set)  # for entropy & unique count
        self.baseline_ips = defaultdict(set)  # known IPs per source

        if model_path is None:
            model_path = Path(__file__).parent / "model" / "models" / "zktca_transformer_q8.onnx"
            if not model_path.exists():
                model_path = Path(__file__).parent / "model" / "models" / "zktca_transformer.onnx"

        if model_path.exists():
            try:
                import onnxruntime as ort
                self.session = ort.InferenceSession(str(model_path))
                logging.info(f"🧠 Transformer cargado: {model_path.name}")
            except ImportError:
                logging.warning("⚠️  onnxruntime no instalado. Transformer deshabilitado.")
            except Exception as e:
                logging.warning(f"⚠️  Error cargando modelo ONNX: {e}")
        else:
            logging.warning(f"⚠️  Modelo ONNX no encontrado en {model_path}. Transformer deshabilitado.")

    @property
    def available(self):
        return self.session is not None

    def _extract_features(self, metadata, current_time):
        """Convert raw metadata dict to a 12-dim feature vector."""
        dst_port = int(metadata.get("dst_port", 0))
        protocol = int(metadata.get("protocol", 6))
        packets = int(metadata.get("packets", 0))
        bytes_val = int(metadata.get("bytes", 0))
        src_ip = metadata.get("src_ip", "")
        dst_ip = metadata.get("dst_ip", "")
        event = metadata.get("event", "NEW")

        # Feature 0: Port category
        port_cat = PORT_CAT_NUMERIC.get(dst_port, 0.0)

        # Feature 1: Protocol (0=TCP, 1=UDP)
        proto = 0.0 if protocol == 6 else 1.0

        # Feature 2: Packets (log-scaled)
        packets_log = math.log1p(packets)

        # Feature 3: Bytes (log-scaled)
        bytes_log = math.log1p(bytes_val)

        # Feature 4: Duration (mock for MVP)
        duration = min(bytes_val / 1000, 3600) if event == "DESTROY" else 0.0

        # Feature 5: Bytes ratio (mock — would need up/down separation)
        bytes_ratio = 0.5  # default balanced; in prod, compute from conntrack counters

        # Feature 6: IAT (inter-arrival time)
        iat = 0.0
        if self.last_event_time[src_ip] > 0:
            iat = current_time - self.last_event_time[src_ip]
        self.last_event_time[src_ip] = current_time

        # Features 7-8: Cyclic hour encoding
        hour = datetime.fromtimestamp(current_time).hour
        hour_sin = math.sin(2 * math.pi * hour / 24.0)
        hour_cos = math.cos(2 * math.pi * hour / 24.0)

        # Feature 9: Unique destination IPs in window (normalized)
        self.dst_ip_history[src_ip].add(dst_ip)
        unique_dst = len(self.dst_ip_history[src_ip]) / 20.0

        # Feature 10: Destination entropy (Shannon)
        dst_entropy = 0.0
        if len(self.dst_ip_history[src_ip]) > 1:
            # Simplified: use count diversity
            n = len(self.dst_ip_history[src_ip])
            dst_entropy = min(math.log2(n) / 5.0, 1.0)

        # Feature 11: Is new destination
        is_new = 0.0
        if dst_ip not in self.baseline_ips[src_ip]:
            is_new = 1.0
            self.baseline_ips[src_ip].add(dst_ip)

        return [port_cat, proto, packets_log, bytes_log, duration,
                bytes_ratio, iat, hour_sin, hour_cos, unique_dst,
                dst_entropy, is_new]

    def process_event(self, metadata, current_time):
        """
        Process a single flow event: extract features, update sliding window,
        and run inference when the window is full.

        Returns:
            dict with risk tags and probabilities, or None if window not full yet.
        """
        if not self.available:
            return None

        src_ip = metadata.get("src_ip", "unknown")
        features = self._extract_features(metadata, current_time)

        # Add to sliding window
        window = self.windows[src_ip]
        window.append(features)

        # Keep only last SEQUENCE_LENGTH events
        if len(window) > self.SEQUENCE_LENGTH:
            window.pop(0)

        # Only run inference when we have a full window
        if len(window) < self.SEQUENCE_LENGTH:
            return None

        # Prepare input tensor
        input_array = np.array([window], dtype=np.float32)  # (1, 32, 12)

        # Run inference
        outputs = self.session.run(None, {"flow_sequence": input_array})
        logits = outputs[0][0]  # (5,)

        # Sigmoid
        probs = 1.0 / (1.0 + np.exp(-logits))

        # Build result
        result = {}
        alerts = []
        for i, name in enumerate(CLASS_NAMES):
            result[name] = float(probs[i])
            if name != "benign" and probs[i] > self.THRESHOLD:
                alerts.append((name, float(probs[i])))

        if alerts:
            for alert_name, alert_prob in alerts:
                emoji = {"grooming": "🎯", "bullying": "👊", "night_abuse": "🌙", "exfiltration": "📤"}.get(alert_name, "⚠️")
                logging.warning(
                    f"{emoji} TRANSFORMER [{alert_name.upper()}]: Confianza {alert_prob:.1%} "
                    f"para IP {src_ip} | Scores: {', '.join(f'{n}={p:.2f}' for n, p in zip(CLASS_NAMES, probs))}"
                )

        return result


# ==========================================
# Ingesta Syslog (Receptor UDP)
# ==========================================
# Global references set in main
_analyzer_mode = "rules"
_transformer_tagger = None


class SyslogUDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = bytes.decode(self.request[0].strip())
        current_time = time.time()

        # Parseo simple del formato de ulogd.conf
        if "ZKTCA_METADATA" in data:
            try:
                metadata = {}
                parts = data.split("ZKTCA_METADATA:")[1].strip().split()
                for part in parts:
                    k, v = part.split("=")
                    metadata[k] = v

                src_ip = metadata.get("src_ip")
                dst_ip = metadata.get("dst_ip")
                dst_port = int(metadata.get("dst_port", 0))
                event = metadata.get("event")
                bytes_t = int(metadata.get("bytes", 0))

                # Use embedded timestamp if present (for simulated/virtual clock),
                # otherwise fall back to wall-clock time
                if "timestamp" in metadata and metadata["timestamp"].isdigit():
                    current_time = float(metadata["timestamp"])

                # Mock duration calculation for DESTROY events
                duration = 0
                if event == "DESTROY":
                    duration = min(bytes_t / 1000, 3600)

                # --- Rules engine ---
                if _analyzer_mode in ("rules", "hybrid"):
                    RiskAnalyzer.check_grooming(src_ip, current_time, dst_port)
                    RiskAnalyzer.check_bullying(dst_ip, src_ip, event, bytes_t)
                    if event == "DESTROY":
                        RiskAnalyzer.check_night_activity(src_ip, current_time, duration)

                # --- Transformer engine ---
                if _analyzer_mode in ("transformer", "hybrid") and _transformer_tagger:
                    _transformer_tagger.process_event(metadata, current_time)

            except Exception as e:
                logging.error(f"Error parseando metadatos: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZKTCA Analyzer - Motor de Análisis de Protección Infantil")
    parser.add_argument("--mode", choices=["rules", "transformer", "hybrid"], default="hybrid",
                        help="Modo de análisis: rules (solo reglas), transformer (solo ML), hybrid (ambos)")
    parser.add_argument("--model", type=str, default=None,
                        help="Ruta al modelo ONNX (por defecto: model/models/zktca_transformer_q8.onnx)")
    parser.add_argument("--host", type=str, default=SYSLOG_HOST)
    parser.add_argument("--port", type=int, default=SYSLOG_PORT)
    args = parser.parse_args()

    _analyzer_mode = args.mode
    model_path = Path(args.model) if args.model else None

    logging.info(f"Iniciando Motor de Análisis ZKTCA (Raspberry Pi MVP)...")
    logging.info(f"Modo: {_analyzer_mode.upper()}")
    LegalComplianceModule.generate_privacy_notice()

    if _analyzer_mode in ("transformer", "hybrid"):
        _transformer_tagger = TransformerTagger(model_path)
        if not _transformer_tagger.available:
            if _analyzer_mode == "transformer":
                logging.error("❌ Modo transformer seleccionado pero el modelo no está disponible. Abortando.")
                exit(1)
            else:
                logging.warning("⚠️  Transformer no disponible, usando solo motor de reglas.")
                _analyzer_mode = "rules"

    server = socketserver.UDPServer((args.host, args.port), SyslogUDPHandler)
    logging.info(f"Escuchando logs Syslog UDP en {args.host}:{args.port}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Apagando motor de análisis...")
