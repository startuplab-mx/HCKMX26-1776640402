# 🛡️ Threat Not Found — ZKTCA Child Protection System

> **Zero-Knowledge Traffic Classification Analysis** for behavioral risk detection at the router level.

A privacy-first child protection MVP that detects grooming, cyberbullying, nocturnal abuse, and data exfiltration using **only network metadata** — no content inspection, no DPI, no decryption.

---

## 🧩 Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         HOME NETWORK                                    │
│                                                                         │
│  ┌──────────────────┐        Syslog (UDP)        ┌───────────────────┐ │
│  │  📡 ROUTER       │ ─────────────────────────▶ │  🧠 RASPBERRY PI  │ │
│  │  (OpenWrt)       │   ZKTCA Metadata only      │  (Analyzer)       │ │
│  │                  │   • src/dst IP              │                   │ │
│  │  nf_conntrack    │   • ports                   │  ┌─────────────┐ │ │
│  │  + ulogd2        │   • bytes/packets           │  │ Rule Engine │ │ │
│  │                  │   • timestamps              │  └──────┬──────┘ │ │
│  │  hash_enable=0   │                             │         │        │ │
│  │  (NEW + DESTROY) │                             │  ┌──────▼──────┐ │ │
│  └──────────────────┘                             │  │ Transformer │ │ │
│         ▲                                         │  │ (ONNX int8) │ │ │
│         │                                         │  └──────┬──────┘ │ │
│  ┌──────┴──────┐                                  │         │        │ │
│  │ 📱 Devices  │                                  │  ┌──────▼──────┐ │ │
│  │ (children)  │                                  │  │  Risk Tags  │ │ │
│  └─────────────┘                                  │  └──────┬──────┘ │ │
│                                                   └─────────┼────────┘ │
│                                                             │          │
│                                                    ┌────────▼───────┐  │
│                                                    │  📊 GRAFANA    │  │
│                                                    │  Risk Heatmaps │  │
│                                                    │  (no URL logs) │  │
│                                                    └────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

| Principle | Implementation |
|---|---|
| **Zero-Knowledge** | Only flow metadata (IPs, ports, bytes, timestamps). No payload inspection. |
| **TLS 1.3 / ECH compatible** | Works with fully encrypted traffic — no need to break encryption. |
| **Privacy-first** | Grafana shows risk heatmaps, never browsing history. Logs auto-purge after 30 days. |
| **Mexican Law (SFP 2026)** | Built-in ARCO rights module, privacy notices, and *Interés Superior del Menor*. |
| **Edge AI** | Transformer model runs on Raspberry Pi 5 via ONNX Runtime (0.18 MB, <1ms inference). |

---

## 📁 Project Structure

```
theat_not_found/
├── README.md                        # This file
├── ARCHITECTURE.md                  # Detailed architecture & how-to-run guide
├── requirements.txt                 # Python dependencies
├── ulogd.conf                       # Router sensor configuration (OpenWrt)
├── analyzer.py                      # Main analysis engine (rules + transformer)
├── test_analyzer.py                 # Simulated traffic tests
├── grafana_dashboard.json           # Grafana dashboard model (risk heatmaps)
└── model/
    ├── platform_utils.py            # OS detection (macOS/Linux/Windows)
    ├── generate_training_data.py    # Synthetic dataset generator
    ├── transformer_model.py         # Transformer architecture (PyTorch)
    ├── train.py                     # Training script (MPS / CUDA / CPU)
    ├── export_onnx.py               # ONNX export + int8 quantization
    ├── data/                        # Generated training data (.npy)
    └── models/                      # Trained models (.pt, .onnx)
```

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate synthetic training data
python3 model/generate_training_data.py

# 3. Train the transformer (auto-detects GPU)
python3 model/train.py

# 4. Export to ONNX + quantize for Raspberry Pi
python3 model/export_onnx.py

# 5. Run the analyzer in hybrid mode
python3 analyzer.py --mode hybrid

# 6. (In another terminal) Send test traffic
python3 test_analyzer.py
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed setup, configuration, and deployment instructions.

---

## 🔍 Risk Detection

| Risk | What the model detects | How |
|---|---|---|
| **Grooming** | Gaming → encrypted chat transition | Port category shift within <5 min window |
| **Bullying** | Burst of traffic from many sources | >10 unique IPs, asymmetric download-heavy |
| **Night Abuse** | Persistent activity 11PM–4AM | Human-like IAT patterns in restricted hours |
| **Exfiltration** | Large uploads to cloud storage | >50MB upload ratio to unauthorized servers |

---

## ⚖️ Legal Compliance (Mexico 2026)

- **Aviso de Privacidad** — Auto-generated at system startup
- **Derechos ARCO** — Download/delete profile data via API
- **Data Minimization** — Metadata auto-purge after 30 days
- **Interés Superior del Menor** — Manual override for all blocking rules
- **SFP / Secretaría de Anticorrupción** — Aligned with post-INAI regulatory framework

---

## 🧠 Transformer Model

| Spec | Value |
|---|---|
| Architecture | 2-layer Encoder, 4 heads, d=64 |
| Parameters | 74,437 |
| Size (quantized) | 0.18 MB (int8) |
| Inference | <1ms (Mac), ~5ms (RPi 5 est.) |
| Validation F1 | 1.000 |
| Training | Auto-detects: MPS (Mac), CUDA (Linux/Win), CPU |

---

## 📄 License

See [LICENSE](LICENSE) file.
