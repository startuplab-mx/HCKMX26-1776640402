"""
ZKTCA Enhanced Training Data Generator (v3)
============================================
Generates 70K+ labeled sequences with 6 risk categories:
- More samples per class (8K base + 2K variants)
- Multi-label combinations (grooming+night, recruitment+night)
- Hard negatives (benign gaming, benign nocturnal, benign group chat)
- Gaussian noise augmentation
- Criminal recruitment detection (new in v3)
"""

import numpy as np
import json, argparse
from pathlib import Path

SEQ_LEN = 32
FEAT_DIM = 12
OUTPUT_DIR = Path(__file__).parent / "data"

# Feature indices
F_PORT_CAT, F_PROTO, F_PKT, F_BYTES, F_DUR, F_RATIO = 0, 1, 2, 3, 4, 5
F_IAT, F_HSIN, F_HCOS, F_UDST, F_ENTR, F_NEWDST = 6, 7, 8, 9, 10, 11

def cyclic_hour(h):
    return np.sin(2*np.pi*h/24), np.cos(2*np.pi*h/24)

def fill_baseline(seq, i, hour_sin, hour_cos, port_cat=0.0):
    seq[i, F_PORT_CAT] = port_cat
    seq[i, F_PROTO] = 0.0 if np.random.rand() > 0.3 else 1.0
    seq[i, F_PKT] = np.log1p(np.random.randint(5, 200))
    seq[i, F_BYTES] = np.log1p(np.random.randint(500, 50000))
    seq[i, F_DUR] = np.random.uniform(0.5, 120)
    seq[i, F_RATIO] = np.random.uniform(0.3, 0.7)
    seq[i, F_IAT] = np.random.uniform(0.1, 10.0)
    seq[i, F_HSIN] = hour_sin + np.random.normal(0, 0.05)
    seq[i, F_HCOS] = hour_cos + np.random.normal(0, 0.05)
    seq[i, F_UDST] = np.random.randint(2, 6) / 20.0
    seq[i, F_ENTR] = np.random.uniform(0.3, 0.7)
    seq[i, F_NEWDST] = float(np.random.rand() < 0.1)

def augment(seq, noise=0.03):
    """Add Gaussian noise for data augmentation."""
    return seq + np.random.normal(0, noise, seq.shape).astype(np.float32)

# ── Generators ──────────────────────────────────────────

def gen_benign(n):
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice([8,9,10,11,14,15,16,17,18,19,20])
        hs, hc = cyclic_hour(h)
        for i in range(SEQ_LEN):
            fill_baseline(seq, i, hs, hc)
        seqs.append(seq); labs.append([1,0,0,0,0,0])
    return seqs, labs

def gen_benign_gaming(n):
    """Hard negative: gaming all session, NO switch to chat."""
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice([14,15,16,17,18,19,20])
        hs, hc = cyclic_hour(h)
        for i in range(SEQ_LEN):
            seq[i, F_PORT_CAT] = 1.0
            seq[i, F_PROTO] = 1.0
            seq[i, F_PKT] = np.log1p(np.random.randint(50, 500))
            seq[i, F_BYTES] = np.log1p(np.random.randint(1000, 20000))
            seq[i, F_DUR] = np.random.uniform(10, 300)
            seq[i, F_RATIO] = np.random.uniform(0.4, 0.6)
            seq[i, F_IAT] = np.random.uniform(0.05, 2.0)
            seq[i, F_HSIN] = hs + np.random.normal(0, 0.05)
            seq[i, F_HCOS] = hc + np.random.normal(0, 0.05)
            seq[i, F_UDST] = np.random.randint(1, 4) / 20.0
            seq[i, F_ENTR] = np.random.uniform(0.2, 0.5)
            seq[i, F_NEWDST] = float(np.random.rand() < 0.05)
        seqs.append(seq); labs.append([1,0,0,0,0,0])
    return seqs, labs

def gen_benign_night(n):
    """Hard negative: brief late-night activity (e.g., quick check), NOT abuse."""
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice([23, 0, 1])
        hs, hc = cyclic_hour(h)
        active = np.random.randint(3, 8)  # only a few events active
        for i in range(SEQ_LEN):
            if i < active:
                fill_baseline(seq, i, hs, hc)
                seq[i, F_DUR] = np.random.uniform(1, 30)  # short
                seq[i, F_IAT] = np.random.uniform(0.1, 3.0)  # fast, automated
            else:
                fill_baseline(seq, i, hs, hc)
                seq[i, F_PKT] = np.log1p(np.random.randint(1, 10))
                seq[i, F_BYTES] = np.log1p(np.random.randint(100, 1000))
                seq[i, F_DUR] = 0.0
        seqs.append(seq); labs.append([1,0,0,0,0,0])
    return seqs, labs

def gen_grooming(n):
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice([14,15,16,17,18,19,20,21])
        hs, hc = cyclic_hour(h)
        sw = np.random.randint(6, 26)
        for i in range(SEQ_LEN):
            if i < sw:
                seq[i, F_PORT_CAT] = 1.0; seq[i, F_PROTO] = 1.0
                seq[i, F_PKT] = np.log1p(np.random.randint(50, 500))
                seq[i, F_BYTES] = np.log1p(np.random.randint(1000, 20000))
                seq[i, F_DUR] = np.random.uniform(10, 300)
                seq[i, F_RATIO] = np.random.uniform(0.4, 0.6)
                seq[i, F_IAT] = np.random.uniform(0.05, 2.0)
            else:
                seq[i, F_PORT_CAT] = 2.0; seq[i, F_PROTO] = 0.0
                seq[i, F_PKT] = np.log1p(np.random.randint(10, 100))
                seq[i, F_BYTES] = np.log1p(np.random.randint(200, 5000))
                seq[i, F_DUR] = np.random.uniform(30, 600)
                seq[i, F_RATIO] = np.random.uniform(0.3, 0.5)
                seq[i, F_IAT] = np.random.uniform(1.0, 30.0)
            seq[i, F_HSIN] = hs + np.random.normal(0, 0.05)
            seq[i, F_HCOS] = hc + np.random.normal(0, 0.05)
            seq[i, F_UDST] = np.random.randint(2, 8) / 20.0
            seq[i, F_ENTR] = np.random.uniform(0.4, 0.8)
            seq[i, F_NEWDST] = 1.0 if i == sw else float(np.random.rand() < 0.15)
        seqs.append(seq); labs.append([0,1,0,0,0,0])
    return seqs, labs

def gen_grooming_gradual(n):
    """Variant: gradual transition (interleaved gaming+chat) instead of abrupt."""
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice([15,16,17,18,19,20])
        hs, hc = cyclic_hour(h)
        transition_start = np.random.randint(8, 16)
        for i in range(SEQ_LEN):
            if i < transition_start:
                seq[i, F_PORT_CAT] = 1.0; seq[i, F_PROTO] = 1.0
            elif i < transition_start + 8:
                seq[i, F_PORT_CAT] = np.random.choice([1.0, 2.0])
                seq[i, F_PROTO] = 0.0 if seq[i, F_PORT_CAT] == 2.0 else 1.0
            else:
                seq[i, F_PORT_CAT] = 2.0; seq[i, F_PROTO] = 0.0
            seq[i, F_PKT] = np.log1p(np.random.randint(10, 400))
            seq[i, F_BYTES] = np.log1p(np.random.randint(500, 15000))
            seq[i, F_DUR] = np.random.uniform(10, 400)
            seq[i, F_RATIO] = np.random.uniform(0.3, 0.6)
            seq[i, F_IAT] = np.random.uniform(0.5, 15.0)
            seq[i, F_HSIN] = hs + np.random.normal(0, 0.05)
            seq[i, F_HCOS] = hc + np.random.normal(0, 0.05)
            seq[i, F_UDST] = np.random.randint(2, 8) / 20.0
            seq[i, F_ENTR] = np.random.uniform(0.4, 0.8)
            seq[i, F_NEWDST] = float(np.random.rand() < 0.2)
        seqs.append(seq); labs.append([0,1,0,0,0,0])
    return seqs, labs

def gen_bullying(n):
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice(range(8, 22))
        hs, hc = cyclic_hour(h)
        bs = np.random.randint(4, 16)
        be = min(bs + np.random.randint(6, 18), SEQ_LEN)
        for i in range(SEQ_LEN):
            if bs <= i < be:
                seq[i, F_PORT_CAT] = 2.0; seq[i, F_PROTO] = 0.0
                seq[i, F_PKT] = np.log1p(np.random.randint(100, 1000))
                seq[i, F_BYTES] = np.log1p(np.random.randint(10000, 500000))
                seq[i, F_DUR] = np.random.uniform(1, 30)
                seq[i, F_RATIO] = np.random.uniform(0.05, 0.2)
                seq[i, F_IAT] = np.random.uniform(0.01, 0.5)
                seq[i, F_UDST] = np.random.randint(10, 30) / 20.0
                seq[i, F_ENTR] = np.random.uniform(0.8, 1.0)
                seq[i, F_NEWDST] = float(np.random.rand() > 0.3)
            else:
                fill_baseline(seq, i, hs, hc)
            seq[i, F_HSIN] = hs + np.random.normal(0, 0.05)
            seq[i, F_HCOS] = hc + np.random.normal(0, 0.05)
        seqs.append(seq); labs.append([0,0,1,0,0,0])
    return seqs, labs

def gen_bullying_mild(n):
    """Variant: fewer sources (5-10), lower volume — subtler bullying."""
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice(range(8, 22))
        hs, hc = cyclic_hour(h)
        bs = np.random.randint(8, 20)
        be = min(bs + np.random.randint(4, 10), SEQ_LEN)
        for i in range(SEQ_LEN):
            if bs <= i < be:
                seq[i, F_PORT_CAT] = 2.0; seq[i, F_PROTO] = 0.0
                seq[i, F_PKT] = np.log1p(np.random.randint(30, 300))
                seq[i, F_BYTES] = np.log1p(np.random.randint(5000, 100000))
                seq[i, F_DUR] = np.random.uniform(5, 60)
                seq[i, F_RATIO] = np.random.uniform(0.1, 0.3)
                seq[i, F_IAT] = np.random.uniform(0.1, 2.0)
                seq[i, F_UDST] = np.random.randint(5, 12) / 20.0
                seq[i, F_ENTR] = np.random.uniform(0.6, 0.9)
                seq[i, F_NEWDST] = float(np.random.rand() > 0.4)
            else:
                fill_baseline(seq, i, hs, hc)
            seq[i, F_HSIN] = hs + np.random.normal(0, 0.05)
            seq[i, F_HCOS] = hc + np.random.normal(0, 0.05)
        seqs.append(seq); labs.append([0,0,1,0,0,0])
    return seqs, labs

def gen_night(n):
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice([23, 0, 1, 2, 3])
        hs, hc = cyclic_hour(h)
        for i in range(SEQ_LEN):
            seq[i, F_PORT_CAT] = np.random.choice([0.0, 2.0])
            seq[i, F_PROTO] = 0.0
            seq[i, F_PKT] = np.log1p(np.random.randint(20, 300))
            seq[i, F_BYTES] = np.log1p(np.random.randint(2000, 100000))
            seq[i, F_DUR] = np.random.uniform(60, 1800)
            seq[i, F_RATIO] = np.random.uniform(0.3, 0.6)
            seq[i, F_IAT] = np.random.uniform(1.0, 30.0)
            seq[i, F_HSIN] = hs + np.random.normal(0, 0.1)
            seq[i, F_HCOS] = hc + np.random.normal(0, 0.1)
            seq[i, F_UDST] = np.random.randint(1, 4) / 20.0
            seq[i, F_ENTR] = np.random.uniform(0.2, 0.5)
            seq[i, F_NEWDST] = float(np.random.rand() < 0.05)
        seqs.append(seq); labs.append([0,0,0,1,0,0])
    return seqs, labs

def gen_exfil(n):
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice(range(8, 23))
        hs, hc = cyclic_hour(h)
        es = np.random.randint(4, 20)
        ee = min(es + np.random.randint(3, 12), SEQ_LEN)
        for i in range(SEQ_LEN):
            if es <= i < ee:
                seq[i, F_PORT_CAT] = 3.0; seq[i, F_PROTO] = 0.0
                seq[i, F_PKT] = np.log1p(np.random.randint(500, 5000))
                seq[i, F_BYTES] = np.log1p(np.random.randint(1000000, 50000000))
                seq[i, F_DUR] = np.random.uniform(10, 120)
                seq[i, F_RATIO] = np.random.uniform(0.7, 0.95)
                seq[i, F_IAT] = np.random.uniform(0.01, 1.0)
                seq[i, F_UDST] = np.random.randint(1, 3) / 20.0
                seq[i, F_ENTR] = np.random.uniform(0.1, 0.3)
                seq[i, F_NEWDST] = float(np.random.rand() > 0.5)
            else:
                fill_baseline(seq, i, hs, hc)
            seq[i, F_HSIN] = hs + np.random.normal(0, 0.05)
            seq[i, F_HCOS] = hc + np.random.normal(0, 0.05)
        seqs.append(seq); labs.append([0,0,0,0,1,0])
    return seqs, labs

# ── Multi-label combinations ───────────────────────────

def gen_grooming_night(n):
    """Grooming that happens at night (gaming→chat at 1AM)."""
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice([23, 0, 1, 2])
        hs, hc = cyclic_hour(h)
        sw = np.random.randint(8, 20)
        for i in range(SEQ_LEN):
            if i < sw:
                seq[i, F_PORT_CAT] = 1.0; seq[i, F_PROTO] = 1.0
                seq[i, F_PKT] = np.log1p(np.random.randint(50, 500))
                seq[i, F_BYTES] = np.log1p(np.random.randint(1000, 20000))
                seq[i, F_DUR] = np.random.uniform(30, 600)
                seq[i, F_RATIO] = np.random.uniform(0.4, 0.6)
                seq[i, F_IAT] = np.random.uniform(0.1, 3.0)
            else:
                seq[i, F_PORT_CAT] = 2.0; seq[i, F_PROTO] = 0.0
                seq[i, F_PKT] = np.log1p(np.random.randint(10, 100))
                seq[i, F_BYTES] = np.log1p(np.random.randint(200, 5000))
                seq[i, F_DUR] = np.random.uniform(60, 1800)
                seq[i, F_RATIO] = np.random.uniform(0.3, 0.5)
                seq[i, F_IAT] = np.random.uniform(1.0, 30.0)
            seq[i, F_HSIN] = hs + np.random.normal(0, 0.1)
            seq[i, F_HCOS] = hc + np.random.normal(0, 0.1)
            seq[i, F_UDST] = np.random.randint(2, 6) / 20.0
            seq[i, F_ENTR] = np.random.uniform(0.3, 0.7)
            seq[i, F_NEWDST] = float(np.random.rand() < 0.15)
        seqs.append(seq); labs.append([0,1,0,1,0,0])  # grooming + night
    return seqs, labs

def gen_night_exfil(n):
    """Exfiltration at night (uploading photos at 2AM)."""
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice([0, 1, 2, 3])
        hs, hc = cyclic_hour(h)
        es = np.random.randint(10, 22)
        ee = min(es + np.random.randint(4, 10), SEQ_LEN)
        for i in range(SEQ_LEN):
            seq[i, F_HSIN] = hs + np.random.normal(0, 0.1)
            seq[i, F_HCOS] = hc + np.random.normal(0, 0.1)
            if es <= i < ee:
                seq[i, F_PORT_CAT] = 3.0; seq[i, F_PROTO] = 0.0
                seq[i, F_PKT] = np.log1p(np.random.randint(500, 5000))
                seq[i, F_BYTES] = np.log1p(np.random.randint(1000000, 50000000))
                seq[i, F_DUR] = np.random.uniform(30, 300)
                seq[i, F_RATIO] = np.random.uniform(0.7, 0.95)
                seq[i, F_IAT] = np.random.uniform(0.5, 5.0)
            else:
                seq[i, F_PORT_CAT] = np.random.choice([0.0, 2.0])
                seq[i, F_PROTO] = 0.0
                seq[i, F_PKT] = np.log1p(np.random.randint(20, 200))
                seq[i, F_BYTES] = np.log1p(np.random.randint(2000, 50000))
                seq[i, F_DUR] = np.random.uniform(60, 900)
                seq[i, F_RATIO] = np.random.uniform(0.3, 0.6)
                seq[i, F_IAT] = np.random.uniform(2.0, 30.0)
            seq[i, F_UDST] = np.random.randint(1, 4) / 20.0
            seq[i, F_ENTR] = np.random.uniform(0.2, 0.5)
            seq[i, F_NEWDST] = float(np.random.rand() < 0.1)
        seqs.append(seq); labs.append([0,0,0,1,1,0])  # night + exfil
    return seqs, labs

def gen_recruitment(n):
    """Criminal recruitment: social media → encrypted group chat + large inbound media."""
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice([15,16,17,18,19,20,21,22])
        hs, hc = cyclic_hour(h)
        # Phase 1: social media browsing (first ~10 events)
        phase1_end = np.random.randint(6, 14)
        # Phase 2: encrypted group activity + large downloads
        for i in range(SEQ_LEN):
            seq[i, F_HSIN] = hs + np.random.normal(0, 0.05)
            seq[i, F_HCOS] = hc + np.random.normal(0, 0.05)
            if i < phase1_end:
                # Social media phase (TikTok, Instagram)
                seq[i, F_PORT_CAT] = 0.0  # general web
                seq[i, F_PROTO] = 0.0
                seq[i, F_PKT] = np.log1p(np.random.randint(10, 200))
                seq[i, F_BYTES] = np.log1p(np.random.randint(1000, 50000))
                seq[i, F_DUR] = np.random.uniform(5, 120)
                seq[i, F_RATIO] = np.random.uniform(0.2, 0.5)  # download-heavy (watching)
                seq[i, F_IAT] = np.random.uniform(0.5, 10.0)
                seq[i, F_UDST] = np.random.randint(2, 5) / 20.0
                seq[i, F_ENTR] = np.random.uniform(0.3, 0.6)
                seq[i, F_NEWDST] = float(np.random.rand() < 0.1)
            else:
                # Encrypted group + large media downloads
                seq[i, F_PORT_CAT] = 2.0  # chat/encrypted
                seq[i, F_PROTO] = 0.0  # TCP
                seq[i, F_PKT] = np.log1p(np.random.randint(100, 2000))
                # Large inbound media (recruitment videos/propaganda): 5-50MB
                seq[i, F_BYTES] = np.log1p(np.random.randint(500000, 50000000))
                seq[i, F_DUR] = np.random.uniform(30, 600)
                seq[i, F_RATIO] = np.random.uniform(0.05, 0.25)  # very download-heavy
                seq[i, F_IAT] = np.random.uniform(1.0, 20.0)
                # Many unique IPs in group (cooperative, not hostile)
                seq[i, F_UDST] = np.random.randint(8, 20) / 20.0
                seq[i, F_ENTR] = np.random.uniform(0.6, 0.9)
                seq[i, F_NEWDST] = float(np.random.rand() < 0.4)
        seqs.append(seq); labs.append([0,0,0,0,0,1])
    return seqs, labs

def gen_recruitment_gradual(n):
    """Variant: gradual engagement over time, interleaved social + group."""
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice([16,17,18,19,20,21])
        hs, hc = cyclic_hour(h)
        transition = np.random.randint(8, 16)
        for i in range(SEQ_LEN):
            seq[i, F_HSIN] = hs + np.random.normal(0, 0.05)
            seq[i, F_HCOS] = hc + np.random.normal(0, 0.05)
            if i < transition:
                seq[i, F_PORT_CAT] = 0.0
            elif i < transition + 6:
                seq[i, F_PORT_CAT] = np.random.choice([0.0, 2.0])  # mixed
            else:
                seq[i, F_PORT_CAT] = 2.0
            seq[i, F_PROTO] = 0.0
            seq[i, F_PKT] = np.log1p(np.random.randint(50, 1500))
            # Gradually increasing download sizes
            base_bytes = 50000 if i < transition else np.random.randint(500000, 30000000)
            seq[i, F_BYTES] = np.log1p(base_bytes)
            seq[i, F_DUR] = np.random.uniform(10, 400)
            seq[i, F_RATIO] = np.random.uniform(0.1, 0.35)  # download-heavy
            seq[i, F_IAT] = np.random.uniform(0.5, 15.0)
            seq[i, F_UDST] = np.random.randint(5, 15) / 20.0
            seq[i, F_ENTR] = np.random.uniform(0.5, 0.85)
            seq[i, F_NEWDST] = float(np.random.rand() < 0.3)
        seqs.append(seq); labs.append([0,0,0,0,0,1])
    return seqs, labs

def gen_recruitment_night(n):
    """Multi-label: recruitment activity happening at night."""
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice([23, 0, 1, 2])
        hs, hc = cyclic_hour(h)
        phase1_end = np.random.randint(6, 12)
        for i in range(SEQ_LEN):
            seq[i, F_HSIN] = hs + np.random.normal(0, 0.1)
            seq[i, F_HCOS] = hc + np.random.normal(0, 0.1)
            if i < phase1_end:
                seq[i, F_PORT_CAT] = 0.0
                seq[i, F_PKT] = np.log1p(np.random.randint(10, 200))
                seq[i, F_BYTES] = np.log1p(np.random.randint(2000, 80000))
                seq[i, F_RATIO] = np.random.uniform(0.2, 0.5)
            else:
                seq[i, F_PORT_CAT] = 2.0
                seq[i, F_PKT] = np.log1p(np.random.randint(100, 2000))
                seq[i, F_BYTES] = np.log1p(np.random.randint(500000, 40000000))
                seq[i, F_RATIO] = np.random.uniform(0.05, 0.25)
            seq[i, F_PROTO] = 0.0
            seq[i, F_DUR] = np.random.uniform(30, 900)
            seq[i, F_IAT] = np.random.uniform(1.0, 30.0)
            seq[i, F_UDST] = np.random.randint(5, 18) / 20.0
            seq[i, F_ENTR] = np.random.uniform(0.5, 0.9)
            seq[i, F_NEWDST] = float(np.random.rand() < 0.3)
        seqs.append(seq); labs.append([0,0,0,1,0,1])  # night + recruitment
    return seqs, labs

def gen_benign_group_chat(n):
    """Hard negative: group chat (e.g., school project) — should NOT trigger recruitment."""
    seqs, labs = [], []
    for _ in range(n):
        seq = np.zeros((SEQ_LEN, FEAT_DIM))
        h = np.random.choice([10,11,14,15,16,17,18])
        hs, hc = cyclic_hour(h)
        for i in range(SEQ_LEN):
            seq[i, F_PORT_CAT] = 2.0  # encrypted chat
            seq[i, F_PROTO] = 0.0
            seq[i, F_PKT] = np.log1p(np.random.randint(10, 200))
            seq[i, F_BYTES] = np.log1p(np.random.randint(1000, 30000))  # small msgs
            seq[i, F_DUR] = np.random.uniform(5, 120)
            seq[i, F_RATIO] = np.random.uniform(0.35, 0.65)  # balanced (not download-heavy)
            seq[i, F_IAT] = np.random.uniform(1.0, 20.0)
            seq[i, F_HSIN] = hs + np.random.normal(0, 0.05)
            seq[i, F_HCOS] = hc + np.random.normal(0, 0.05)
            seq[i, F_UDST] = np.random.randint(3, 8) / 20.0
            seq[i, F_ENTR] = np.random.uniform(0.4, 0.7)
            seq[i, F_NEWDST] = float(np.random.rand() < 0.05)
        seqs.append(seq); labs.append([1,0,0,0,0,0])
    return seqs, labs

# ── Main ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=8000, help="Base samples per class")
    args = parser.parse_args()
    n = args.samples
    n_var = n // 4  # variant count

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating enhanced ZKTCA dataset ({n} base + variants per class)...\n")

    all_seqs, all_labs = [], []
    generators = [
        ("benign (normal)",       gen_benign,          n),
        ("benign (gaming only)",  gen_benign_gaming,   n_var),
        ("benign (brief night)",  gen_benign_night,    n_var),
        ("grooming (abrupt)",     gen_grooming,        n),
        ("grooming (gradual)",    gen_grooming_gradual,n_var),
        ("bullying (severe)",     gen_bullying,        n),
        ("bullying (mild)",       gen_bullying_mild,   n_var),
        ("night abuse",           gen_night,           n),
        ("exfiltration",          gen_exfil,           n),
        ("recruitment (rapid)",   gen_recruitment,     n),
        ("recruitment (gradual)", gen_recruitment_gradual, n_var),
        ("benign (group chat)",   gen_benign_group_chat, n_var),
        ("grooming + night",      gen_grooming_night,  n_var),
        ("night + exfiltration",  gen_night_exfil,     n_var),
        ("recruitment + night",   gen_recruitment_night, n_var),
    ]

    for name, fn, count in generators:
        s, l = fn(count)
        all_seqs.extend(s); all_labs.extend(l)
        print(f"  ✅ {name:25s} {count:5d} samples")

    # Augmented copies (noise)
    aug_seqs, aug_labs = [], []
    n_aug = len(all_seqs) // 5
    for idx in np.random.choice(len(all_seqs), n_aug, replace=False):
        aug_seqs.append(augment(all_seqs[idx]))
        aug_labs.append(all_labs[idx])
    all_seqs.extend(aug_seqs); all_labs.extend(aug_labs)
    print(f"  🔄 {'augmented (noise)':25s} {n_aug:5d} samples")

    # Shuffle
    idx = np.random.permutation(len(all_seqs))
    X = np.array([all_seqs[i] for i in idx], dtype=np.float32)
    y = np.array([all_labs[i] for i in idx], dtype=np.float32)

    np.save(OUTPUT_DIR / "X_train.npy", X)
    np.save(OUTPUT_DIR / "y_train.npy", y)

    print(f"\n📊 Dataset: {OUTPUT_DIR}")
    print(f"   X: {X.shape}  y: {y.shape}")
    print(f"   Total: {len(X)} samples")

    # Class distribution
    print(f"\n   Label distribution:")
    names = ["benign", "grooming", "bullying", "night_abuse", "exfiltration", "recruitment"]
    for i, nm in enumerate(names):
        cnt = int(y[:, i].sum())
        print(f"     {nm:15s}: {cnt:6d} ({cnt/len(y)*100:.1f}%)")
    multi = int((y.sum(axis=1) > 1).sum())
    print(f"     {'multi-label':15s}: {multi:6d} ({multi/len(y)*100:.1f}%)")

    meta = {"sequence_length": SEQ_LEN, "feature_dim": FEAT_DIM,
            "classes": names, "total_samples": len(X),
            "has_augmentation": True, "has_multi_label": True,
            "has_hard_negatives": True}
    with open(OUTPUT_DIR / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

if __name__ == "__main__":
    main()
