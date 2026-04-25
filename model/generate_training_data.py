"""
Synthetic Training Data Generator for ZKTCA-Transformer
========================================================
Generates labeled sequences of network flow metadata that mimic
the behavioral signatures described in the spec document.

Each sample is a sequence of 32 flow events (a ~5-minute window)
encoded as 12-dimensional feature vectors.

Labels (multi-label):
  0 = benign
  1 = grooming (app switching)
  2 = bullying (burst from multiple sources)
  3 = night_abuse (persistent nocturnal activity)
  4 = exfiltration (large uploads to cloud)
"""

import numpy as np
import os
import json
from pathlib import Path

SEQUENCE_LENGTH = 32
FEATURE_DIM = 12
OUTPUT_DIR = Path(__file__).parent / "data"

# Port category mapping (same as analyzer.py)
PORT_GAMING = [19132, 27015, 25565, 30000]   # Minecraft, Steam, MC Java, generic game
PORT_CHAT = [443, 5222, 5223, 8443]           # TLS (Discord/Telegram/WhatsApp), XMPP
PORT_CLOUD = [443, 8080, 9000]                # Cloud storage endpoints
PORT_NORMAL = [80, 443, 8080, 53]             # Normal browsing

# Feature indices
F_DST_PORT_CAT = 0    # 0=other, 1=gaming, 2=chat, 3=cloud
F_PROTOCOL = 1        # 0=TCP(6), 1=UDP(17)
F_PACKETS = 2         # log-scaled
F_BYTES = 3           # log-scaled
F_DURATION = 4        # seconds
F_BYTES_RATIO = 5     # upload/download
F_IAT = 6             # inter-arrival time
F_HOUR_SIN = 7        # cyclic hour encoding
F_HOUR_COS = 8
F_UNIQUE_DST_5M = 9   # unique dest IPs in window
F_DST_ENTROPY = 10    # Shannon entropy
F_IS_NEW_DST = 11     # binary: new destination


def port_to_category(port):
    if port in PORT_GAMING:
        return 1.0
    elif port in PORT_CHAT:
        return 2.0
    elif port in PORT_CLOUD:
        return 3.0
    return 0.0


def cyclic_hour(hour):
    """Encode hour as sin/cos for cyclic continuity."""
    sin_h = np.sin(2 * np.pi * hour / 24.0)
    cos_h = np.cos(2 * np.pi * hour / 24.0)
    return sin_h, cos_h


def generate_benign(n_samples=2000):
    """Normal browsing: stable destinations, regular hours, balanced traffic."""
    sequences = []
    labels = []
    for _ in range(n_samples):
        seq = np.zeros((SEQUENCE_LENGTH, FEATURE_DIM))
        hour = np.random.choice([8, 9, 10, 11, 14, 15, 16, 17, 18, 19, 20])  # daytime
        hour_sin, hour_cos = cyclic_hour(hour)

        n_unique_dst = np.random.randint(2, 6)
        for i in range(SEQUENCE_LENGTH):
            port = np.random.choice(PORT_NORMAL)
            seq[i, F_DST_PORT_CAT] = port_to_category(port)
            seq[i, F_PROTOCOL] = 0.0 if np.random.rand() > 0.3 else 1.0  # mostly TCP
            seq[i, F_PACKETS] = np.log1p(np.random.randint(5, 200))
            seq[i, F_BYTES] = np.log1p(np.random.randint(500, 50000))
            seq[i, F_DURATION] = np.random.uniform(0.5, 120)
            seq[i, F_BYTES_RATIO] = np.random.uniform(0.3, 0.7)  # balanced
            seq[i, F_IAT] = np.random.uniform(0.1, 10.0)  # regular pacing
            seq[i, F_HOUR_SIN] = hour_sin + np.random.normal(0, 0.05)
            seq[i, F_HOUR_COS] = hour_cos + np.random.normal(0, 0.05)
            seq[i, F_UNIQUE_DST_5M] = n_unique_dst / 20.0  # normalized
            seq[i, F_DST_ENTROPY] = np.random.uniform(0.3, 0.7)
            seq[i, F_IS_NEW_DST] = 0.0 if np.random.rand() > 0.1 else 1.0

        sequences.append(seq)
        labels.append([1, 0, 0, 0, 0])  # benign only
    return sequences, labels


def generate_grooming(n_samples=2000):
    """
    Grooming pattern: starts with gaming traffic, then abruptly switches
    to encrypted chat within the same window (< 5 minutes).
    """
    sequences = []
    labels = []
    for _ in range(n_samples):
        seq = np.zeros((SEQUENCE_LENGTH, FEATURE_DIM))
        hour = np.random.choice([14, 15, 16, 17, 18, 19, 20, 21])
        hour_sin, hour_cos = cyclic_hour(hour)

        # Switch point: somewhere in the middle of the sequence
        switch_point = np.random.randint(8, 24)

        for i in range(SEQUENCE_LENGTH):
            if i < switch_point:
                # Gaming phase
                port = np.random.choice(PORT_GAMING)
                seq[i, F_DST_PORT_CAT] = 1.0  # gaming
                seq[i, F_PROTOCOL] = 1.0  # UDP typical for games
                seq[i, F_PACKETS] = np.log1p(np.random.randint(50, 500))
                seq[i, F_BYTES] = np.log1p(np.random.randint(1000, 20000))
                seq[i, F_DURATION] = np.random.uniform(10, 300)
                seq[i, F_BYTES_RATIO] = np.random.uniform(0.4, 0.6)
                seq[i, F_IAT] = np.random.uniform(0.05, 2.0)
            else:
                # Chat phase (abrupt switch)
                seq[i, F_DST_PORT_CAT] = 2.0  # chat/encrypted
                seq[i, F_PROTOCOL] = 0.0  # TCP for chat
                seq[i, F_PACKETS] = np.log1p(np.random.randint(10, 100))
                seq[i, F_BYTES] = np.log1p(np.random.randint(200, 5000))
                seq[i, F_DURATION] = np.random.uniform(30, 600)
                seq[i, F_BYTES_RATIO] = np.random.uniform(0.3, 0.5)
                seq[i, F_IAT] = np.random.uniform(1.0, 30.0)  # human typing rhythm

            seq[i, F_HOUR_SIN] = hour_sin + np.random.normal(0, 0.05)
            seq[i, F_HOUR_COS] = hour_cos + np.random.normal(0, 0.05)
            seq[i, F_UNIQUE_DST_5M] = np.random.randint(2, 8) / 20.0
            seq[i, F_DST_ENTROPY] = np.random.uniform(0.4, 0.8)
            seq[i, F_IS_NEW_DST] = 1.0 if i == switch_point else (0.0 if np.random.rand() > 0.15 else 1.0)

        sequences.append(seq)
        labels.append([0, 1, 0, 0, 0])  # grooming
    return sequences, labels


def generate_bullying(n_samples=2000):
    """
    Bullying pattern: sudden burst of inbound traffic from many unique
    source IPs, asymmetric (more download than upload).
    """
    sequences = []
    labels = []
    for _ in range(n_samples):
        seq = np.zeros((SEQUENCE_LENGTH, FEATURE_DIM))
        hour = np.random.choice(range(8, 22))
        hour_sin, hour_cos = cyclic_hour(hour)

        # Burst starts at some point
        burst_start = np.random.randint(4, 16)
        burst_end = min(burst_start + np.random.randint(8, 16), SEQUENCE_LENGTH)

        for i in range(SEQUENCE_LENGTH):
            if burst_start <= i < burst_end:
                # Burst phase: many sources, high volume, asymmetric
                seq[i, F_DST_PORT_CAT] = 2.0  # chat/encrypted
                seq[i, F_PROTOCOL] = 0.0
                seq[i, F_PACKETS] = np.log1p(np.random.randint(100, 1000))
                seq[i, F_BYTES] = np.log1p(np.random.randint(10000, 500000))
                seq[i, F_DURATION] = np.random.uniform(1, 30)
                seq[i, F_BYTES_RATIO] = np.random.uniform(0.05, 0.2)  # very asymmetric
                seq[i, F_IAT] = np.random.uniform(0.01, 0.5)  # very fast bursts
                seq[i, F_UNIQUE_DST_5M] = np.random.randint(10, 30) / 20.0  # many sources
                seq[i, F_DST_ENTROPY] = np.random.uniform(0.8, 1.0)  # high entropy
                seq[i, F_IS_NEW_DST] = 1.0 if np.random.rand() > 0.3 else 0.0
            else:
                # Normal baseline
                seq[i, F_DST_PORT_CAT] = 0.0
                seq[i, F_PROTOCOL] = 0.0
                seq[i, F_PACKETS] = np.log1p(np.random.randint(5, 50))
                seq[i, F_BYTES] = np.log1p(np.random.randint(500, 5000))
                seq[i, F_DURATION] = np.random.uniform(1, 60)
                seq[i, F_BYTES_RATIO] = np.random.uniform(0.3, 0.7)
                seq[i, F_IAT] = np.random.uniform(0.5, 5.0)
                seq[i, F_UNIQUE_DST_5M] = np.random.randint(2, 5) / 20.0
                seq[i, F_DST_ENTROPY] = np.random.uniform(0.3, 0.6)
                seq[i, F_IS_NEW_DST] = 0.0

            seq[i, F_HOUR_SIN] = hour_sin + np.random.normal(0, 0.05)
            seq[i, F_HOUR_COS] = hour_cos + np.random.normal(0, 0.05)

        sequences.append(seq)
        labels.append([0, 0, 1, 0, 0])  # bullying
    return sequences, labels


def generate_night_abuse(n_samples=2000):
    """
    Night abuse: persistent connections with human-like IAT patterns
    between 23:00 and 04:00.
    """
    sequences = []
    labels = []
    for _ in range(n_samples):
        seq = np.zeros((SEQUENCE_LENGTH, FEATURE_DIM))
        hour = np.random.choice([23, 0, 1, 2, 3])
        hour_sin, hour_cos = cyclic_hour(hour)

        for i in range(SEQUENCE_LENGTH):
            seq[i, F_DST_PORT_CAT] = np.random.choice([0.0, 2.0])
            seq[i, F_PROTOCOL] = 0.0
            seq[i, F_PACKETS] = np.log1p(np.random.randint(20, 300))
            seq[i, F_BYTES] = np.log1p(np.random.randint(2000, 100000))
            seq[i, F_DURATION] = np.random.uniform(60, 1800)  # long sessions
            seq[i, F_BYTES_RATIO] = np.random.uniform(0.3, 0.6)
            seq[i, F_IAT] = np.random.uniform(1.0, 30.0)  # human-like, irregular
            seq[i, F_HOUR_SIN] = hour_sin + np.random.normal(0, 0.1)
            seq[i, F_HOUR_COS] = hour_cos + np.random.normal(0, 0.1)
            seq[i, F_UNIQUE_DST_5M] = np.random.randint(1, 4) / 20.0
            seq[i, F_DST_ENTROPY] = np.random.uniform(0.2, 0.5)
            seq[i, F_IS_NEW_DST] = 0.0 if np.random.rand() > 0.05 else 1.0

        sequences.append(seq)
        labels.append([0, 0, 0, 1, 0])  # night_abuse
    return sequences, labels


def generate_exfiltration(n_samples=2000):
    """
    Media exfiltration: large upload spikes to cloud storage,
    very high bytes_ratio (more upload than download).
    """
    sequences = []
    labels = []
    for _ in range(n_samples):
        seq = np.zeros((SEQUENCE_LENGTH, FEATURE_DIM))
        hour = np.random.choice(range(8, 23))
        hour_sin, hour_cos = cyclic_hour(hour)

        exfil_start = np.random.randint(4, 20)
        exfil_end = min(exfil_start + np.random.randint(4, 10), SEQUENCE_LENGTH)

        for i in range(SEQUENCE_LENGTH):
            if exfil_start <= i < exfil_end:
                # Exfiltration phase: massive uploads
                seq[i, F_DST_PORT_CAT] = 3.0  # cloud
                seq[i, F_PROTOCOL] = 0.0
                seq[i, F_PACKETS] = np.log1p(np.random.randint(500, 5000))
                seq[i, F_BYTES] = np.log1p(np.random.randint(1000000, 50000000))  # >1MB
                seq[i, F_DURATION] = np.random.uniform(10, 120)
                seq[i, F_BYTES_RATIO] = np.random.uniform(0.7, 0.95)  # upload-heavy
                seq[i, F_IAT] = np.random.uniform(0.01, 1.0)
                seq[i, F_UNIQUE_DST_5M] = np.random.randint(1, 3) / 20.0
                seq[i, F_DST_ENTROPY] = np.random.uniform(0.1, 0.3)  # few destinations
                seq[i, F_IS_NEW_DST] = 1.0 if np.random.rand() > 0.5 else 0.0
            else:
                # Normal baseline
                seq[i, F_DST_PORT_CAT] = 0.0
                seq[i, F_PROTOCOL] = 0.0
                seq[i, F_PACKETS] = np.log1p(np.random.randint(5, 100))
                seq[i, F_BYTES] = np.log1p(np.random.randint(500, 10000))
                seq[i, F_DURATION] = np.random.uniform(1, 60)
                seq[i, F_BYTES_RATIO] = np.random.uniform(0.3, 0.6)
                seq[i, F_IAT] = np.random.uniform(0.5, 5.0)
                seq[i, F_UNIQUE_DST_5M] = np.random.randint(2, 5) / 20.0
                seq[i, F_DST_ENTROPY] = np.random.uniform(0.3, 0.6)
                seq[i, F_IS_NEW_DST] = 0.0

            seq[i, F_HOUR_SIN] = hour_sin + np.random.normal(0, 0.05)
            seq[i, F_HOUR_COS] = hour_cos + np.random.normal(0, 0.05)

        sequences.append(seq)
        labels.append([0, 0, 0, 0, 1])  # exfiltration
    return sequences, labels


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating synthetic ZKTCA training data...")
    all_sequences = []
    all_labels = []

    generators = [
        ("benign", generate_benign),
        ("grooming", generate_grooming),
        ("bullying", generate_bullying),
        ("night_abuse", generate_night_abuse),
        ("exfiltration", generate_exfiltration),
    ]

    for name, gen_fn in generators:
        seqs, labs = gen_fn(n_samples=2000)
        all_sequences.extend(seqs)
        all_labels.extend(labs)
        print(f"  ✅ {name}: {len(seqs)} sequences")

    # Shuffle
    indices = np.random.permutation(len(all_sequences))
    all_sequences = [all_sequences[i] for i in indices]
    all_labels = [all_labels[i] for i in indices]

    # Convert to numpy arrays
    X = np.array(all_sequences, dtype=np.float32)
    y = np.array(all_labels, dtype=np.float32)

    # Save
    np.save(OUTPUT_DIR / "X_train.npy", X)
    np.save(OUTPUT_DIR / "y_train.npy", y)

    print(f"\n📊 Dataset saved to {OUTPUT_DIR}")
    print(f"   X shape: {X.shape}  (samples, seq_len, features)")
    print(f"   y shape: {y.shape}  (samples, classes)")
    print(f"   Total samples: {len(X)}")

    # Save metadata for reproducibility
    meta = {
        "sequence_length": SEQUENCE_LENGTH,
        "feature_dim": FEATURE_DIM,
        "classes": ["benign", "grooming", "bullying", "night_abuse", "exfiltration"],
        "samples_per_class": 2000,
        "total_samples": len(X),
        "feature_names": [
            "dst_port_cat", "protocol", "packets_log", "bytes_log",
            "duration", "bytes_ratio", "iat", "hour_sin", "hour_cos",
            "unique_dst_5m", "dst_entropy", "is_new_dst"
        ]
    }
    with open(OUTPUT_DIR / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"   Metadata saved to {OUTPUT_DIR / 'metadata.json'}")


if __name__ == "__main__":
    main()
