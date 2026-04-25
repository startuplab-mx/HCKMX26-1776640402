"""
ZKTCA-Transformer Training Script
===================================
Trains the transformer model on synthetic ZKTCA flow data.
Auto-detects platform: MPS on macOS, CUDA on Linux/Windows, CPU fallback.

Usage:
    python model/train.py
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import json
import time
from pathlib import Path

# Import model and platform utils from same package
import sys
sys.path.insert(0, str(Path(__file__).parent))
from transformer_model import ZKTCATransformer, count_parameters
from platform_utils import get_device, print_platform_report

# ==========================================
# Configuration
# ==========================================
DATA_DIR = Path(__file__).parent / "data"
MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

BATCH_SIZE = 64
EPOCHS = 50
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
PATIENCE = 8  # early stopping patience
THRESHOLD = 0.5

CLASS_NAMES = ["benign", "grooming", "bullying", "night_abuse", "exfiltration"]


def compute_metrics(preds, targets, threshold=THRESHOLD):
    """Compute per-class and macro F1 score."""
    preds_bin = (preds > threshold).float()

    metrics = {}
    f1_scores = []

    for i, name in enumerate(CLASS_NAMES):
        tp = ((preds_bin[:, i] == 1) & (targets[:, i] == 1)).sum().float()
        fp = ((preds_bin[:, i] == 1) & (targets[:, i] == 0)).sum().float()
        fn = ((preds_bin[:, i] == 0) & (targets[:, i] == 1)).sum().float()

        precision = tp / (tp + fp + 1e-8)
        recall = tp / (tp + fn + 1e-8)
        f1 = 2 * precision * recall / (precision + recall + 1e-8)

        metrics[name] = {"precision": precision.item(), "recall": recall.item(), "f1": f1.item()}
        f1_scores.append(f1.item())

    metrics["macro_f1"] = np.mean(f1_scores)
    return metrics


def train():
    platform_info = print_platform_report()
    device = get_device()

    # Load data
    print("\n📂 Loading training data...")
    X = np.load(DATA_DIR / "X_train.npy")
    y = np.load(DATA_DIR / "y_train.npy")
    print(f"   X: {X.shape}, y: {y.shape}")

    # Train/validation split (80/20)
    n_total = len(X)
    n_train = int(0.8 * n_total)
    indices = np.random.permutation(n_total)

    X_train = torch.FloatTensor(X[indices[:n_train]])
    y_train = torch.FloatTensor(y[indices[:n_train]])
    X_val = torch.FloatTensor(X[indices[n_train:]])
    y_val = torch.FloatTensor(y[indices[n_train:]])

    train_ds = TensorDataset(X_train, y_train)
    val_ds = TensorDataset(X_val, y_val)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)

    print(f"   Train: {len(train_ds)}, Validation: {len(val_ds)}")

    # Initialize model
    model = ZKTCATransformer().to(device)
    print(f"\n🧠 Model initialized: {count_parameters(model):,} parameters")

    # Loss and optimizer
    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    # Training loop
    best_val_f1 = 0.0
    patience_counter = 0

    print(f"\n🚀 Starting training ({EPOCHS} epochs max, patience={PATIENCE})...\n")
    print(f"{'Epoch':>5} | {'Train Loss':>10} | {'Val Loss':>10} | {'Val F1':>8} | {'LR':>10} | {'Time':>6}")
    print("-" * 65)

    for epoch in range(1, EPOCHS + 1):
        epoch_start = time.time()

        # --- Training ---
        model.train()
        train_loss = 0.0
        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)

            optimizer.zero_grad()
            logits = model(batch_X)
            loss = criterion(logits, batch_y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            train_loss += loss.item()

        train_loss /= len(train_loader)

        # --- Validation ---
        model.eval()
        val_loss = 0.0
        all_preds = []
        all_targets = []

        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                logits = model(batch_X)
                loss = criterion(logits, batch_y)
                val_loss += loss.item()
                all_preds.append(torch.sigmoid(logits).cpu())
                all_targets.append(batch_y.cpu())

        val_loss /= len(val_loader)
        all_preds = torch.cat(all_preds)
        all_targets = torch.cat(all_targets)
        metrics = compute_metrics(all_preds, all_targets)
        val_f1 = metrics["macro_f1"]

        scheduler.step()
        elapsed = time.time() - epoch_start
        lr = optimizer.param_groups[0]["lr"]

        print(f"{epoch:5d} | {train_loss:10.4f} | {val_loss:10.4f} | {val_f1:8.4f} | {lr:10.6f} | {elapsed:5.1f}s")

        # Early stopping
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            patience_counter = 0
            # Save best model
            checkpoint = {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_f1": val_f1,
                "val_loss": val_loss,
                "metrics": metrics,
            }
            torch.save(checkpoint, MODELS_DIR / "best_model.pt")
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print(f"\n⏹️  Early stopping at epoch {epoch} (no improvement for {PATIENCE} epochs)")
                break

    # Final report
    print(f"\n{'=' * 65}")
    print(f"✅ Training complete!")
    print(f"   Best validation F1: {best_val_f1:.4f}")
    print(f"   Model saved to: {MODELS_DIR / 'best_model.pt'}")

    # Load best and print per-class metrics
    best = torch.load(MODELS_DIR / "best_model.pt", map_location="cpu", weights_only=False)
    print(f"\n📊 Per-class metrics (best epoch {best['epoch']}):")
    for name in CLASS_NAMES:
        m = best["metrics"][name]
        print(f"   {name:15s}  P={m['precision']:.3f}  R={m['recall']:.3f}  F1={m['f1']:.3f}")
    print(f"   {'MACRO':15s}  F1={best['metrics']['macro_f1']:.3f}")

    # Save training metadata
    train_meta = {
        "best_epoch": best["epoch"],
        "best_val_f1": best_val_f1,
        "best_val_loss": best["val_loss"],
        "per_class_metrics": best["metrics"],
        "device_used": str(device),
        "total_params": count_parameters(model),
        "platform": platform_info,
    }
    with open(MODELS_DIR / "training_report.json", "w") as f:
        json.dump(train_meta, f, indent=2)


if __name__ == "__main__":
    train()
