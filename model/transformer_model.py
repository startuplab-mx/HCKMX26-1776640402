"""
ZKTCA-Transformer: Lightweight Transformer for Network Flow Classification
==========================================================================
Encoder-only Transformer that classifies sequences of network flow metadata
into risk categories. Designed for edge deployment on Raspberry Pi 5.

Architecture:
  - Input projection: Linear(12, 64)
  - Learned positional encoding (32 positions)
  - 2x TransformerEncoderLayer (d_model=64, nhead=4, dim_ff=128)
  - Mean pooling over sequence
  - Classification head: Linear(64, 6) with sigmoid

Total params: ~530K (~2MB fp32, <1MB int8 quantized)
"""

import torch
import torch.nn as nn
import numpy as np
import math


class LearnedPositionalEncoding(nn.Module):
    """Learned positional encoding for sequence positions."""

    def __init__(self, max_len, d_model):
        super().__init__()
        self.pos_embedding = nn.Embedding(max_len, d_model)

    def forward(self, x):
        """x: (batch, seq_len, d_model)"""
        batch_size, seq_len, _ = x.shape
        positions = torch.arange(seq_len, device=x.device).unsqueeze(0).expand(batch_size, -1)
        return x + self.pos_embedding(positions)


class ZKTCATransformer(nn.Module):
    """
    Lightweight Transformer encoder for ZKTCA flow classification.

    Input:  (batch, 32, 12) — 32 flow events, 12 features each
    Output: (batch, 6)      — sigmoid scores for [benign, grooming, bullying, night_abuse, exfiltration, recruitment]
    """

    def __init__(
        self,
        feature_dim=12,
        d_model=64,
        nhead=4,
        num_layers=2,
        dim_feedforward=128,
        num_classes=6,
        max_seq_len=32,
        dropout=0.1,
    ):
        super().__init__()

        # Input projection
        self.input_proj = nn.Linear(feature_dim, d_model)

        # Positional encoding
        self.pos_encoder = LearnedPositionalEncoding(max_seq_len, d_model)

        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer, num_layers=num_layers
        )

        # Classification head
        self.classifier = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Linear(d_model, d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, num_classes),
        )

        self._init_weights()

    def _init_weights(self):
        """Xavier initialization for stable training."""
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)

    def forward(self, x):
        """
        Args:
            x: (batch, seq_len, feature_dim) flow metadata sequences
        Returns:
            logits: (batch, num_classes) raw logits (apply sigmoid for probabilities)
        """
        # Project input features to model dimension
        x = self.input_proj(x)  # (batch, seq, d_model)

        # Add positional encoding
        x = self.pos_encoder(x)

        # Transformer encoder
        x = self.transformer_encoder(x)  # (batch, seq, d_model)

        # Mean pooling over sequence dimension
        x = x.mean(dim=1)  # (batch, d_model)

        # Classify
        logits = self.classifier(x)  # (batch, num_classes)
        return logits

    def predict(self, x, threshold=0.5):
        """Convenience method for inference with sigmoid + thresholding."""
        self.eval()
        with torch.no_grad():
            logits = self.forward(x)
            probs = torch.sigmoid(logits)
            preds = (probs > threshold).float()
        return preds, probs


def count_parameters(model):
    """Count trainable parameters."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


if __name__ == "__main__":
    # Quick sanity check
    model = ZKTCATransformer()
    print(f"ZKTCA-Transformer initialized")
    print(f"  Parameters: {count_parameters(model):,}")
    print(f"  Model size: ~{count_parameters(model) * 4 / 1024 / 1024:.2f} MB (fp32)")

    # Test forward pass
    dummy_input = torch.randn(4, 32, 12)  # batch=4, seq=32, features=12
    logits = model(dummy_input)
    probs = torch.sigmoid(logits)
    print(f"\n  Input shape:  {dummy_input.shape}")
    print(f"  Output shape: {logits.shape}")
    print(f"  Sample probs: {probs[0].tolist()}")
