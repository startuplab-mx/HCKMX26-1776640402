"""
ZKTCA Realistic Traffic Simulator
===================================
Simulates a full 24-hour day of network activity across multiple
children's devices, mixing benign browsing with embedded risk patterns.

Generates enough events per device (40+) to fill the Transformer's
32-event sliding window and trigger ML-based risk classification.

Usage:
    python3 test_realistic.py                    # All scenarios, fast
    python3 test_realistic.py --scenario grooming # Single scenario
    python3 test_realistic.py --speed 0.5         # Slow for live demo
    python3 test_realistic.py --speed 0           # As fast as possible
"""

import socket
import time
import random
import argparse
from datetime import datetime, timedelta

# ==========================================
# Configuration
# ==========================================
CONFIG = {
    "host": "127.0.0.1",
    "port": 5140,
}

# ==========================================
# Realistic Service Database
# ==========================================
SERVICES = {
    # Benign / Normal
    "youtube":       {"ips": ["142.250.80.46", "142.250.80.78", "142.250.81.110"], "port": 443, "proto": 6},
    "google":        {"ips": ["142.250.217.100", "142.250.217.101"],               "port": 443, "proto": 6},
    "school_portal": {"ips": ["104.18.25.30", "104.18.25.31"],                     "port": 443, "proto": 6},
    "wikipedia":     {"ips": ["208.80.154.224"],                                   "port": 443, "proto": 6},
    "cdn_images":    {"ips": ["151.101.1.69", "151.101.65.69"],                    "port": 443, "proto": 6},
    "dns":           {"ips": ["8.8.8.8", "1.1.1.1"],                               "port": 53,  "proto": 17},
    # Gaming
    "minecraft":     {"ips": ["52.165.165.26", "52.165.165.27"],                   "port": 19132, "proto": 17},
    "roblox":        {"ips": ["128.116.0.54", "128.116.0.55"],                     "port": 443,   "proto": 6},
    "steam":         {"ips": ["155.133.248.50", "155.133.248.51"],                 "port": 27015, "proto": 17},
    # Chat / Encrypted (risk destinations)
    "discord":       {"ips": ["162.159.135.232", "162.159.128.233"],               "port": 443, "proto": 6},
    "telegram":      {"ips": ["149.154.167.50", "149.154.167.51"],                "port": 443, "proto": 6},
    "whatsapp":      {"ips": ["157.240.25.53", "157.240.25.54"],                  "port": 443, "proto": 6},
    # Social / Streaming
    "tiktok":        {"ips": ["161.117.197.20", "161.117.197.21"],                "port": 443, "proto": 6},
    "instagram":     {"ips": ["157.240.1.35", "157.240.1.36"],                    "port": 443, "proto": 6},
    "netflix":       {"ips": ["54.74.73.31", "54.74.73.32"],                      "port": 443, "proto": 6},
    # Cloud storage (exfiltration targets)
    "gdrive":        {"ips": ["142.251.33.65", "142.251.33.66"],                  "port": 443, "proto": 6},
    "mega":          {"ips": ["66.203.127.12", "66.203.127.13"],                  "port": 443, "proto": 6},
}

# ==========================================
# Device Profiles
# ==========================================
DEVICES = {
    "sofia": {
        "ip": "192.168.1.100",
        "name": "Sofía, 12 años",
        "risk": None,
        "description": "Uso normal — escuela, YouTube y juegos casuales",
    },
    "diego": {
        "ip": "192.168.1.101",
        "name": "Diego, 14 años",
        "risk": "grooming",
        "description": "Sesión de juegos que migra a chat cifrado",
    },
    "valentina": {
        "ip": "192.168.1.102",
        "name": "Valentina, 10 años",
        "risk": "bullying",
        "description": "Pico de tráfico entrante desde múltiples IPs",
    },
    "mateo": {
        "ip": "192.168.1.103",
        "name": "Mateo, 16 años",
        "risk": "night_abuse+exfiltration",
        "description": "Actividad nocturna persistente y subida masiva de archivos",
    },
    "carlos": {
        "ip": "192.168.1.104",
        "name": "Carlos, 15 años",
        "risk": "recruitment",
        "description": "Reclutamiento criminal: redes sociales → grupo cifrado + media pesada",
    },
}

# ==========================================
# Syslog Sender
# ==========================================
_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send_event(src_ip, dst_ip, src_port, dst_port, proto, packets, bytes_val, event, timestamp):
    """Send a single ZKTCA metadata event to the analyzer."""
    msg = (
        f"ZKTCA_METADATA: src_ip={src_ip} dst_ip={dst_ip} "
        f"src_port={src_port} dst_port={dst_port} protocol={proto} "
        f"packets={packets} bytes={bytes_val} event={event} "
        f"timestamp={int(timestamp)}"
    )
    _sock.sendto(msg.encode(), (CONFIG["host"], CONFIG["port"]))


def send_flow(src_ip, service_name, timestamp, duration_s=None,
              packets=None, bytes_val=None, event="NEW", incoming=False,
              override_src_ip=None):
    """Send a flow event for a named service."""
    svc = SERVICES[service_name]
    dst_ip = random.choice(svc["ips"])
    dst_port = svc["port"]
    proto = svc["proto"]
    src_port = random.randint(30000, 65000)

    if packets is None:
        packets = random.randint(10, 500)
    if bytes_val is None:
        bytes_val = random.randint(1000, 100000)

    if incoming:
        # Swap src/dst to simulate inbound traffic
        actual_src = override_src_ip if override_src_ip else dst_ip
        send_event(actual_src, src_ip, dst_port, src_port, proto, packets, bytes_val, event, timestamp)
    else:
        send_event(src_ip, dst_ip, src_port, dst_port, proto, packets, bytes_val, event, timestamp)

    # If duration provided, also send a DESTROY event
    if duration_s and event == "NEW":
        send_event(src_ip, dst_ip, src_port, dst_port, proto,
                   packets * 3, bytes_val * 2, "DESTROY", timestamp + duration_s)


# ==========================================
# Scenario Generators
# ==========================================

def generate_sofia(base_time, speed_delay):
    """Sofia — Normal day, NO risk. Should produce ZERO alerts."""
    ip = DEVICES["sofia"]["ip"]
    events = []
    t = base_time.replace(hour=8, minute=0)  # Starts at 8 AM

    print(f"  📱 Sofía (192.168.1.100) — Uso normal escolar y recreativo")

    # Morning: school portal
    for i in range(8):
        send_flow(ip, "school_portal", t.timestamp(), duration_s=120)
        t += timedelta(minutes=random.randint(3, 8))
        time.sleep(speed_delay)
        events.append(("school", t))

    # DNS lookups throughout
    for _ in range(5):
        send_flow(ip, "dns", t.timestamp())
        t += timedelta(seconds=random.randint(10, 60))
        time.sleep(speed_delay)
        events.append(("dns", t))

    # Midday: YouTube
    t = base_time.replace(hour=13, minute=0)
    for i in range(10):
        send_flow(ip, "youtube", t.timestamp(), duration_s=random.randint(60, 300))
        t += timedelta(minutes=random.randint(1, 5))
        time.sleep(speed_delay)
        events.append(("youtube", t))

    # Afternoon: casual Roblox
    t = base_time.replace(hour=16, minute=0)
    for i in range(10):
        send_flow(ip, "roblox", t.timestamp(), duration_s=random.randint(30, 180))
        t += timedelta(minutes=random.randint(2, 6))
        time.sleep(speed_delay)
        events.append(("roblox", t))

    # Evening: Netflix
    t = base_time.replace(hour=20, minute=0)
    for i in range(8):
        send_flow(ip, "netflix", t.timestamp(), duration_s=random.randint(120, 600))
        t += timedelta(minutes=random.randint(3, 10))
        time.sleep(speed_delay)
        events.append(("netflix", t))

    # CDN images mixed in
    for _ in range(4):
        send_flow(ip, "cdn_images", t.timestamp())
        time.sleep(speed_delay)
        events.append(("cdn", t))

    return len(events) * 2  # NEW + DESTROY pairs


def generate_diego(base_time, speed_delay):
    """Diego — Grooming scenario: gaming → encrypted chat migration."""
    ip = DEVICES["diego"]["ip"]
    events = 0
    print(f"  🎮 Diego (192.168.1.101) — Grooming: juego → chat cifrado")

    # Normal school morning
    t = base_time.replace(hour=9, minute=0)
    for i in range(6):
        send_flow(ip, "school_portal", t.timestamp(), duration_s=90)
        t += timedelta(minutes=random.randint(5, 10))
        time.sleep(speed_delay)
        events += 2

    # Afternoon: starts gaming (Minecraft) — this builds the baseline
    t = base_time.replace(hour=16, minute=0)
    for i in range(12):
        send_flow(ip, "minecraft", t.timestamp(), duration_s=random.randint(10, 60))
        t += timedelta(seconds=random.randint(15, 90))
        time.sleep(speed_delay)
        events += 2

    # ⚠️ GROOMING TRIGGER: abrupt switch to Discord/Telegram within 3 minutes
    t = base_time.replace(hour=16, minute=28)
    print(f"    ⚠️  16:28 — Transición rápida Minecraft → Discord")
    for i in range(8):
        send_flow(ip, "discord", t.timestamp(), duration_s=random.randint(60, 300))
        t += timedelta(seconds=random.randint(20, 90))
        time.sleep(speed_delay)
        events += 2

    # Continues chatting on Telegram (escalation)
    t = base_time.replace(hour=16, minute=45)
    for i in range(8):
        send_flow(ip, "telegram", t.timestamp(), duration_s=random.randint(120, 600))
        t += timedelta(minutes=random.randint(2, 8))
        time.sleep(speed_delay)
        events += 2

    # Some benign evening traffic
    t = base_time.replace(hour=19, minute=0)
    for i in range(5):
        send_flow(ip, "youtube", t.timestamp(), duration_s=180)
        t += timedelta(minutes=5)
        time.sleep(speed_delay)
        events += 2

    return events


def generate_valentina(base_time, speed_delay):
    """Valentina — Bullying: sudden burst of inbound traffic from many IPs."""
    ip = DEVICES["valentina"]["ip"]
    events = 0
    print(f"  👧 Valentina (192.168.1.102) — Bullying: pico de tráfico entrante")

    # Normal morning
    t = base_time.replace(hour=10, minute=0)
    for i in range(8):
        send_flow(ip, "youtube", t.timestamp(), duration_s=120)
        t += timedelta(minutes=random.randint(3, 8))
        time.sleep(speed_delay)
        events += 2

    # Normal social media
    t = base_time.replace(hour=13, minute=0)
    for i in range(6):
        send_flow(ip, "instagram", t.timestamp(), duration_s=60)
        t += timedelta(minutes=random.randint(2, 5))
        time.sleep(speed_delay)
        events += 2

    # ⚠️ BULLYING TRIGGER: 14:15 — flood of inbound connections from many unique IPs
    t = base_time.replace(hour=14, minute=15)
    print(f"    ⚠️  14:15 — Pico de tráfico desde 15 IPs distintas")
    bully_ips = [f"45.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}" for _ in range(15)]
    for i, bully_ip in enumerate(bully_ips):
        send_event(
            src_ip=bully_ip, dst_ip=ip,
            src_port=443, dst_port=random.randint(40000, 60000),
            proto=6,
            packets=random.randint(50, 500),
            bytes_val=random.randint(20000, 500000),
            event="NEW",
            timestamp=int((t + timedelta(seconds=i * 2)).timestamp())
        )
        time.sleep(speed_delay)
        events += 1

    # Normal afternoon after the burst
    t = base_time.replace(hour=15, minute=0)
    for i in range(6):
        send_flow(ip, "roblox", t.timestamp(), duration_s=120)
        t += timedelta(minutes=5)
        time.sleep(speed_delay)
        events += 2

    # Evening
    t = base_time.replace(hour=19, minute=30)
    for i in range(5):
        send_flow(ip, "netflix", t.timestamp(), duration_s=300)
        t += timedelta(minutes=10)
        time.sleep(speed_delay)
        events += 2

    return events


def generate_mateo(base_time, speed_delay):
    """Mateo — Night abuse + exfiltration: late-night activity and large uploads."""
    ip = DEVICES["mateo"]["ip"]
    events = 0
    print(f"  🌙 Mateo (192.168.1.103) — Uso nocturno + exfiltración de datos")

    # Normal daytime
    t = base_time.replace(hour=11, minute=0)
    for i in range(8):
        send_flow(ip, "google", t.timestamp(), duration_s=60)
        t += timedelta(minutes=random.randint(5, 15))
        time.sleep(speed_delay)
        events += 2

    # Afternoon gaming
    t = base_time.replace(hour=15, minute=0)
    for i in range(6):
        send_flow(ip, "steam", t.timestamp(), duration_s=random.randint(60, 300))
        t += timedelta(minutes=random.randint(5, 10))
        time.sleep(speed_delay)
        events += 2

    # Evening YouTube
    t = base_time.replace(hour=20, minute=0)
    for i in range(5):
        send_flow(ip, "youtube", t.timestamp(), duration_s=180)
        t += timedelta(minutes=5)
        time.sleep(speed_delay)
        events += 2

    # ⚠️ NIGHT ABUSE TRIGGER: 1:00 AM — persistent TikTok/Instagram with human IAT
    t = (base_time + timedelta(days=1)).replace(hour=1, minute=0)
    print(f"    ⚠️  01:00 — Actividad persistente (TikTok/Instagram)")
    for i in range(12):
        svc = random.choice(["tiktok", "instagram"])
        # Long sessions with human-like spacing
        send_flow(ip, svc, t.timestamp(), duration_s=random.randint(180, 1800))
        t += timedelta(seconds=random.randint(30, 180))  # Human IAT
        time.sleep(speed_delay)
        events += 2

    # ⚠️ EXFILTRATION TRIGGER: 2:10 AM — massive uploads to cloud storage
    t = (base_time + timedelta(days=1)).replace(hour=2, minute=10)
    print(f"    ⚠️  02:10 — Carga masiva de datos a almacenamiento en la nube")
    for i in range(5):
        svc = random.choice(["gdrive", "mega"])
        dst_ip = random.choice(SERVICES[svc]["ips"])
        src_port = random.randint(40000, 60000)
        # Massive upload: >50MB per flow, high packet count
        send_event(ip, dst_ip, src_port, 443, 6,
                   packets=random.randint(5000, 20000),
                   bytes_val=random.randint(50_000_000, 200_000_000),
                   event="NEW", timestamp=int(t.timestamp()))
        t += timedelta(seconds=random.randint(10, 30))
        time.sleep(speed_delay)
        events += 1

    # More late-night browsing to pad the window
    t = (base_time + timedelta(days=1)).replace(hour=2, minute=30)
    for i in range(5):
        send_flow(ip, "tiktok", t.timestamp(), duration_s=600)
        t += timedelta(minutes=5)
        time.sleep(speed_delay)
        events += 2

    return events


def generate_carlos(base_time, speed_delay):
    """Carlos — Criminal recruitment: social media → encrypted group chat + large inbound media."""
    ip = DEVICES["carlos"]["ip"]
    events = 0
    print(f"  🔫 Carlos (192.168.1.104) — Reclutamiento criminal")

    # Normal morning school
    t = base_time.replace(hour=9, minute=0)
    for i in range(6):
        send_flow(ip, "school_portal", t.timestamp(), duration_s=90)
        t += timedelta(minutes=random.randint(5, 10))
        time.sleep(speed_delay)
        events += 2

    # Afternoon: normal TikTok / Instagram (contact surface)
    t = base_time.replace(hour=15, minute=0)
    for i in range(8):
        svc = random.choice(["tiktok", "instagram"])
        send_flow(ip, svc, t.timestamp(), duration_s=random.randint(30, 120))
        t += timedelta(minutes=random.randint(2, 5))
        time.sleep(speed_delay)
        events += 2

    # ⚠️ RECRUITMENT TRIGGER: 17:30 — migration to encrypted group + large downloads
    t = base_time.replace(hour=17, minute=30)
    print(f"    ⚠️  17:30 — Migración a grupo cifrado (Telegram)")

    # Encrypted group chat with large inbound media (propaganda videos)
    for i in range(10):
        svc = random.choice(["telegram", "discord"])
        dst_ip = random.choice(SERVICES[svc]["ips"])
        src_port = random.randint(40000, 60000)
        # Large INBOUND media: 5-50 MB per flow (recruitment videos/propaganda)
        send_event(dst_ip, ip, 443, src_port, 6,
                   packets=random.randint(500, 5000),
                   bytes_val=random.randint(5_000_000, 50_000_000),
                   event="NEW", timestamp=int(t.timestamp()))
        t += timedelta(seconds=random.randint(30, 120))
        time.sleep(speed_delay)
        events += 1

    # More group chat activity (text messages interspersed)
    print(f"    ⚠️  18:00 — Actividad sostenida en grupo cifrado")
    t = base_time.replace(hour=18, minute=0)
    for i in range(8):
        svc = random.choice(["telegram", "discord"])
        send_flow(ip, svc, t.timestamp(), duration_s=random.randint(60, 600))
        t += timedelta(minutes=random.randint(2, 8))
        time.sleep(speed_delay)
        events += 2

    # Evening: some benign traffic
    t = base_time.replace(hour=20, minute=0)
    for i in range(4):
        send_flow(ip, "youtube", t.timestamp(), duration_s=180)
        t += timedelta(minutes=5)
        time.sleep(speed_delay)
        events += 2

    return events


# ==========================================
# Report Generator
# ==========================================
def print_report(event_counts, start_time):
    total = sum(event_counts.values())
    elapsed = time.time() - start_time

    print()
    print("═" * 58)
    print("  ZKTCA Realistic Traffic Simulation — Report")
    print("═" * 58)
    print(f"  Simulated period:  24 hours")
    print(f"  Wall-clock time:   {elapsed:.1f} seconds")
    print(f"  Total events sent: {total}")
    print(f"  Devices simulated: {len(event_counts)}")
    print()

    for key, dev in DEVICES.items():
        count = event_counts.get(key, 0)
        risk_label = dev["risk"] if dev["risk"] else "NONE (control)"
        icon = "✅" if dev["risk"] else "❌"
        print(f"  {icon} {dev['name']:20s} ({dev['ip']})  {count:3d} events  risk={risk_label}")

    print()
    print("  Expected alerts from analyzer:")
    print("    🎯 GROOMING      — Diego (192.168.1.101) @ ~16:28")
    print("    👊 BULLYING      — Valentina (192.168.1.102) @ ~14:15")
    print("    🌙 NIGHT ABUSE   — Mateo (192.168.1.103) @ ~01:00")
    print("    📤 EXFILTRATION  — Mateo (192.168.1.103) @ ~02:10")
    print("    🔫 RECRUITMENT   — Carlos (192.168.1.104) @ ~17:30")
    print("    ✅ NO ALERTS     — Sofía (192.168.1.100) — control limpio")
    print("═" * 58)


# ==========================================
# Main
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="ZKTCA Realistic Traffic Simulator")
    parser.add_argument("--scenario", choices=["all", "grooming", "bullying", "night", "recruitment", "benign"],
                        default="all", help="Scenario to simulate (default: all)")
    parser.add_argument("--speed", type=float, default=0.02,
                        help="Delay between events in seconds. 0=fastest, 0.5=slow demo (default: 0.02)")
    parser.add_argument("--host", type=str, default=CONFIG["host"])
    parser.add_argument("--port", type=int, default=CONFIG["port"])
    args = parser.parse_args()

    CONFIG["host"] = args.host
    CONFIG["port"] = args.port

    # Base time: today at midnight
    base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    print()
    print("🔬 ZKTCA Realistic Traffic Simulator")
    print("─" * 45)
    print(f"   Target:   {args.host}:{args.port}")
    print(f"   Scenario: {args.scenario}")
    print(f"   Speed:    {args.speed}s delay per event")
    print(f"   Base date: {base_time.strftime('%Y-%m-%d')}")
    print("─" * 45)
    print()

    event_counts = {}
    wall_start = time.time()

    scenarios = {
        "benign":      ("sofia",     generate_sofia),
        "grooming":    ("diego",     generate_diego),
        "bullying":    ("valentina", generate_valentina),
        "night":       ("mateo",     generate_mateo),
        "recruitment": ("carlos",    generate_carlos),
    }

    if args.scenario == "all":
        for key, (dev_key, gen_fn) in scenarios.items():
            event_counts[dev_key] = gen_fn(base_time, args.speed)
    else:
        dev_key, gen_fn = scenarios[args.scenario]
        event_counts[dev_key] = gen_fn(base_time, args.speed)

    print_report(event_counts, wall_start)


if __name__ == "__main__":
    main()
