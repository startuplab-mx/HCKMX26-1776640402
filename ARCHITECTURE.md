# 🏗️ Architecture & Setup Guide

Detailed architecture, data flow, deployment, and execution instructions for the ZKTCA Child Protection System.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Data Flow Pipeline](#data-flow-pipeline)
3. [Component Details](#component-details)
4. [Transformer Model Architecture](#transformer-model-architecture)
5. [How to Run](#how-to-run)
6. [Deployment to Raspberry Pi](#deployment-to-raspberry-pi)
7. [Grafana Dashboard Setup](#grafana-dashboard-setup)
8. [Legal Compliance Module](#legal-compliance-module)

---

## System Architecture

The system follows a **Sensor → Collector → Analyzer → Dashboard** pipeline with strict separation of concerns:

```
┌─────────────────┐     ┌──────────────────────────────────────────────┐
│   LAYER 1       │     │   LAYER 2 — RASPBERRY PI 5                  │
│   SENSOR        │     │                                              │
│   (Router)      │     │  ┌────────────┐   ┌────────────────────────┐│
│                 │     │  │  Syslog    │   │   ANALYSIS ENGINE      ││
│  ┌───────────┐  │ UDP │  │  Collector │   │                        ││
│  │ nf_conntrack│─┼─────┼─▶│  (Port    │──▶│  ┌──────────────────┐  ││
│  └─────┬─────┘  │     │  │   5140)   │   │  │  Rule Engine     │  ││
│        │        │     │  └────────────┘   │  │  • Grooming      │  ││
│  ┌─────▼─────┐  │     │                  │  │  • Bullying      │  ││
│  │  ulogd2   │  │     │                  │  │  • Night abuse   │  ││
│  │           │  │     │                  │  └────────┬─────────┘  ││
│  │ hash_en=0 │  │     │                  │           │            ││
│  │ NFCT+SYSLG│  │     │                  │  ┌────────▼─────────┐  ││
│  └───────────┘  │     │                  │  │  Transformer     │  ││
│                 │     │                  │  │  ONNX Runtime    │  ││
│  OpenWrt 23.05+ │     │                  │  │  (int8, 0.18MB)  │  ││
└─────────────────┘     │                  │  └────────┬─────────┘  ││
                        │                  │           │            ││
                        │                  │  ┌────────▼─────────┐  ││
                        │                  │  │  Risk Tagger     │  ││
                        │                  │  │  → Grafana       │  ││
                        │                  │  │  → Alerts        │  ││
                        │                  │  └──────────────────┘  ││
                        │                  └────────────────────────┘│
                        │                                            │
                        │  ┌────────────────────────────────────────┐│
                        │  │  LAYER 3 — VISUALIZATION               ││
                        │  │  Grafana + InfluxDB                    ││
                        │  │  • Risk Heatmaps (no URL logs)         ││
                        │  │  • Teachable Moments alerts            ││
                        │  │  • ARCO rights panel                   ││
                        │  └────────────────────────────────────────┘│
                        └──────────────────────────────────────────────┘
```

### Hardware Requirements

| Component | Specification | Purpose |
|---|---|---|
| Router | MediaTek MT7986A, 1GB RAM, OpenWrt 23.05+ | Network metadata extraction |
| Raspberry Pi | RPi 5, 8GB RAM, NVMe SSD 256GB | ML inference + data storage |
| Network | Gigabit Ethernet with VLAN support | Isolate children's traffic |

---

## Data Flow Pipeline

```
[Device Traffic]
      │
      ▼
[nf_conntrack]  ── Kernel tracks all TCP/UDP connections
      │
      ▼
[ulogd2]        ── Extracts metadata on NEW and DESTROY events
      │              (hash_enable=0 for separate events)
      ▼
[Syslog UDP]    ── Sends ZKTCA_METADATA formatted logs
      │              to Raspberry Pi port 5140
      ▼
[analyzer.py]   ── Parses metadata, extracts 12-dim features
      │
      ├──▶ [Rule Engine]       ── Static threshold checks
      │         │
      ├──▶ [Transformer]       ── Sliding window (32 events)
      │         │                  ONNX inference (<1ms)
      │         │
      ▼         ▼
[Risk Tags]  ── benign | grooming | bullying | night_abuse | exfiltration
      │
      ▼
[Grafana]    ── Risk heatmaps, teachable moments, ARCO panel
```

### Metadata Format (ZKTCA)

Each log line from the router follows this format:

```
ZKTCA_METADATA: src_ip=192.168.1.10 dst_ip=8.8.8.8 src_port=12345 dst_port=443 protocol=6 packets=15 bytes=25000 event=NEW
```

**What is captured** (metadata only):
- Source and destination IP addresses
- Source and destination ports
- Protocol number (6=TCP, 17=UDP)
- Packet count and byte count
- Connection event type (NEW / DESTROY)

**What is NOT captured** (privacy by design):
- ❌ No packet content / payload
- ❌ No URLs or domain names
- ❌ No SNI (Server Name Indication)
- ❌ No DNS queries
- ❌ No TLS decryption

---

## Component Details

### 1. Router Sensor (`ulogd.conf`)

The router runs OpenWrt with `ulogd2` configured to export connection tracking events:

```ini
[ct1]
hash_enable=0    # Critical: emit NEW and DESTROY separately

[syslog1]
facility=16      # local0
level=6          # informational
format="ZKTCA_METADATA: src_ip=%(src_ip)s dst_ip=%(dst_ip)s ..."
```

**Key setting:** `hash_enable=0` ensures each connection lifecycle (start → end) is logged as two separate events, allowing the analyzer to compute exact connection durations and Inter-Arrival Times (IAT).

### 2. Analysis Engine (`analyzer.py`)

The analyzer supports three operating modes:

| Mode | Flag | Description |
|---|---|---|
| **Rules** | `--mode rules` | Static thresholds only (lightweight, no ML) |
| **Transformer** | `--mode transformer` | ML-only classification via ONNX |
| **Hybrid** | `--mode hybrid` | Both engines in parallel (default) |

### 3. Grafana Dashboard (`grafana_dashboard.json`)

Privacy-preserving panels:
- **Risk Heatmap** — Geographic map of connections highlighting risky jurisdictions
- **Teachable Moments** — Alert table for parent-child dialogue opportunities
- **Night Activity** — Stat panel showing off-hours connection minutes

---

## Transformer Model Architecture

```
Input: (batch, 32, 12)
         │
    ┌────▼────┐
    │ Linear  │  12 → 64 (input projection)
    └────┬────┘
         │
    ┌────▼──────────────┐
    │ Positional        │  Learned embeddings (32 positions)
    │ Encoding          │
    └────┬──────────────┘
         │
    ┌────▼──────────────┐
    │ TransformerEncoder │  Layer 1: 4 heads, d=64, ff=128, GELU
    │ TransformerEncoder │  Layer 2: 4 heads, d=64, ff=128, GELU
    └────┬──────────────┘
         │
    ┌────▼────┐
    │  Mean   │  Pool over sequence dimension
    │ Pooling │
    └────┬────┘
         │
    ┌────▼──────────────┐
    │ Classification    │  LayerNorm → Linear(64,64) → GELU
    │ Head              │  → Dropout → Linear(64,5) → Sigmoid
    └────┬──────────────┘
         │
Output: (batch, 5)  →  [benign, grooming, bullying, night_abuse, exfiltration]
```

### Feature Vector (12 dimensions per flow event)

| # | Feature | Type | Description |
|---|---|---|---|
| 0 | `dst_port_cat` | Categorical | 0=other, 1=gaming, 2=chat, 3=cloud |
| 1 | `protocol` | Binary | 0=TCP, 1=UDP |
| 2 | `packets_log` | Numerical | log1p(packet count) |
| 3 | `bytes_log` | Numerical | log1p(byte count) |
| 4 | `duration` | Numerical | Connection duration in seconds |
| 5 | `bytes_ratio` | Numerical | Upload/download ratio |
| 6 | `iat` | Numerical | Inter-Arrival Time since last event |
| 7 | `hour_sin` | Numerical | sin(2π × hour/24) — cyclic encoding |
| 8 | `hour_cos` | Numerical | cos(2π × hour/24) — cyclic encoding |
| 9 | `unique_dst_5m` | Numerical | Unique dest IPs in 5-min window |
| 10 | `dst_entropy` | Numerical | Shannon entropy of destinations |
| 11 | `is_new_dst` | Binary | 1 if destination not in baseline |

### Platform Auto-Detection

The training script auto-detects the host OS and selects the best accelerator:

| OS | Accelerator | Backend |
|---|---|---|
| macOS (Apple Silicon) | Metal GPU | `torch.device("mps")` |
| Linux (NVIDIA GPU) | CUDA | `torch.device("cuda")` |
| Windows (NVIDIA GPU) | CUDA | `torch.device("cuda")` |
| Any (no GPU) | CPU | `torch.device("cpu")` |

Run `python3 model/platform_utils.py` to check your system:

```
=======================================================
  ZKTCA Platform Report
=======================================================
  OS:           macOS (Darwin)
  Architecture: arm64
  CUDA:         ❌ Not available
  MPS (Metal):  ✅ Available
  Device:       MPS
=======================================================
```

---

## How to Run

### Prerequisites

- Python 3.9+
- pip

### Step 1: Install Dependencies

```bash
cd theat_not_found
pip install -r requirements.txt
```

### Step 2: Generate Training Data

```bash
python3 model/generate_training_data.py
```

This creates 10,000 synthetic flow sequences across 5 risk categories in `model/data/`.

### Step 3: Train the Model

```bash
python3 model/train.py
```

The script will:
1. Print a platform report (OS, GPU availability)
2. Auto-select the best accelerator (MPS / CUDA / CPU)
3. Train for up to 50 epochs with early stopping
4. Save the best checkpoint to `model/models/best_model.pt`

### Step 4: Export to ONNX

```bash
python3 model/export_onnx.py
```

This exports the model to ONNX format and applies int8 quantization:
- `model/models/zktca_transformer.onnx` — Full precision (0.35 MB)
- `model/models/zktca_transformer_q8.onnx` — Quantized (0.18 MB)

### Step 5: Run the Analyzer

```bash
# Hybrid mode (rules + transformer, default)
python3 analyzer.py --mode hybrid

# Rules only
python3 analyzer.py --mode rules

# Transformer only
python3 analyzer.py --mode transformer
```

### Step 6: Test with Simulated Traffic

In a separate terminal:

```bash
python3 test_analyzer.py
```

This sends simulated grooming, bullying, and nocturnal activity patterns to the analyzer.

---

## Deployment to Raspberry Pi

### Transfer the quantized model

```bash
scp model/models/zktca_transformer_q8.onnx pi@raspberrypi:/home/pi/zktca/model/models/
scp analyzer.py pi@raspberrypi:/home/pi/zktca/
scp requirements.txt pi@raspberrypi:/home/pi/zktca/
```

### Install on RPi (aarch64)

```bash
ssh pi@raspberrypi
cd /home/pi/zktca
pip install onnxruntime numpy
python3 analyzer.py --mode transformer --port 5140
```

> **Note:** PyTorch is NOT required on the Raspberry Pi. Only `onnxruntime` and `numpy` are needed for inference.

---

## Grafana Dashboard Setup

### 1. Install Grafana on the Raspberry Pi

```bash
sudo apt install grafana
sudo systemctl enable grafana-server
sudo systemctl start grafana-server
```

### 2. Add InfluxDB as Data Source

Configure InfluxDB (or any time-series DB) to receive risk tags from `analyzer.py`.

### 3. Import the Dashboard

1. Open Grafana at `http://raspberrypi:3000`
2. Go to **Dashboards → Import**
3. Upload `grafana_dashboard.json`
4. Select the InfluxDB data source

---

## Legal Compliance Module

The system includes a built-in compliance module aligned with Mexican privacy law (SFP 2026):

### Privacy Notice

Generated automatically at system startup:

```
=== AVISO DE PRIVACIDAD SIMPLIFICADO (Ley Federal SFP 2026) ===
El presente sistema de telemetría de red procesa únicamente METADATOS
(tamaño de paquetes, tiempos de conexión y direcciones IP) con el fin
exclusivo de garantizar el Interés Superior del Menor protegiéndolo de
riesgos digitales.
NO SE INSPECCIONA NI DESENCRIPTA EL CONTENIDO DE LA NAVEGACIÓN.
Los metadatos se retendrán por un máximo de 30 días.
===============================================================
```

### ARCO Rights (programmatic API)

```python
from analyzer import LegalComplianceModule

# Download anonymized profile
LegalComplianceModule.execute_arco_download("192.168.1.100")

# Delete all data for a user
LegalComplianceModule.execute_arco_deletion("192.168.1.100")
```

### Data Minimization

- Metadata logs are automatically purged after **30 days**
- No content is ever stored — only flow-level statistics
- Grafana displays risk scores, never raw IP addresses or browsing history
