"""
ONNX Export & Quantization for ZKTCA-Transformer
=================================================
Exports the trained PyTorch model to ONNX format and applies
int8 dynamic quantization for Raspberry Pi 5 deployment.

Usage:
    python model/export_onnx.py
"""

import torch
import numpy as np
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from transformer_model import ZKTCATransformer, count_parameters

MODELS_DIR = Path(__file__).parent / "models"
ONNX_PATH = MODELS_DIR / "zktca_transformer.onnx"
ONNX_Q8_PATH = MODELS_DIR / "zktca_transformer_q8.onnx"


def export_to_onnx():
    """Load best checkpoint and export to ONNX."""
    checkpoint_path = MODELS_DIR / "best_model.pt"
    if not checkpoint_path.exists():
        print(f"❌ No checkpoint found at {checkpoint_path}. Train the model first.")
        return False

    print("📦 Loading best model checkpoint...")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)

    model = ZKTCATransformer()
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    print(f"   Epoch: {checkpoint['epoch']}, Val F1: {checkpoint['val_f1']:.4f}")
    print(f"   Parameters: {count_parameters(model):,}")

    # Create dummy input matching expected shape
    dummy_input = torch.randn(1, 32, 12)

    # Export using legacy exporter for maximum compatibility with quantization
    print(f"\n🔄 Exporting to ONNX: {ONNX_PATH}")
    torch.onnx.export(
        model,
        dummy_input,
        str(ONNX_PATH),
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["flow_sequence"],
        output_names=["risk_logits"],
        dynamic_axes={
            "flow_sequence": {0: "batch_size"},
            "risk_logits": {0: "batch_size"},
        },
        dynamo=False,
    )

    # Verify ONNX model
    try:
        import onnx
        onnx_model = onnx.load(str(ONNX_PATH))
        onnx.checker.check_model(onnx_model)
        print(f"   ✅ ONNX model validated successfully")
    except ImportError:
        print(f"   ⚠️  onnx package not installed, skipping validation")
    except Exception as e:
        print(f"   ⚠️  ONNX validation warning: {e}")

    onnx_size = ONNX_PATH.stat().st_size / 1024 / 1024
    print(f"   Size: {onnx_size:.2f} MB")

    return True


def quantize_onnx():
    """Apply int8 dynamic quantization to the ONNX model."""
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType
    except ImportError:
        print("⚠️  onnxruntime.quantization not available. Skipping quantization.")
        print("   Install with: pip install onnxruntime")
        return False

    if not ONNX_PATH.exists():
        print(f"❌ ONNX model not found at {ONNX_PATH}")
        return False

    print(f"\n🔧 Quantizing to int8: {ONNX_Q8_PATH}")
    quantize_dynamic(
        model_input=str(ONNX_PATH),
        model_output=str(ONNX_Q8_PATH),
        weight_type=QuantType.QInt8,
    )

    q8_size = ONNX_Q8_PATH.stat().st_size / 1024 / 1024
    orig_size = ONNX_PATH.stat().st_size / 1024 / 1024
    ratio = (1 - q8_size / orig_size) * 100

    print(f"   ✅ Quantized model saved")
    print(f"   Original: {orig_size:.2f} MB → Quantized: {q8_size:.2f} MB ({ratio:.1f}% reduction)")

    return True


def verify_inference():
    """Test inference with ONNX Runtime on the quantized model."""
    try:
        import onnxruntime as ort
    except ImportError:
        print("⚠️  onnxruntime not available. Skipping inference test.")
        return False

    model_path = ONNX_Q8_PATH if ONNX_Q8_PATH.exists() else ONNX_PATH
    print(f"\n🧪 Testing inference with: {model_path.name}")

    session = ort.InferenceSession(str(model_path))

    # Generate random test input
    test_input = np.random.randn(1, 32, 12).astype(np.float32)

    # Time inference
    import time
    times = []
    for _ in range(100):
        start = time.perf_counter()
        outputs = session.run(None, {"flow_sequence": test_input})
        times.append(time.perf_counter() - start)

    logits = outputs[0]
    probs = 1 / (1 + np.exp(-logits))  # sigmoid

    avg_ms = np.mean(times) * 1000
    p95_ms = np.percentile(times, 95) * 1000

    print(f"   Output shape: {logits.shape}")
    print(f"   Sample probs: {[f'{p:.3f}' for p in probs[0]]}")
    print(f"   Latency (100 runs): avg={avg_ms:.2f}ms, p95={p95_ms:.2f}ms")

    # Save export metadata
    export_meta = {
        "onnx_size_mb": ONNX_PATH.stat().st_size / 1024 / 1024 if ONNX_PATH.exists() else None,
        "onnx_q8_size_mb": ONNX_Q8_PATH.stat().st_size / 1024 / 1024 if ONNX_Q8_PATH.exists() else None,
        "inference_avg_ms": avg_ms,
        "inference_p95_ms": p95_ms,
        "class_names": ["benign", "grooming", "bullying", "night_abuse", "exfiltration", "recruitment"],
    }
    with open(MODELS_DIR / "export_report.json", "w") as f:
        json.dump(export_meta, f, indent=2)
    print(f"   Report saved to {MODELS_DIR / 'export_report.json'}")

    return True


if __name__ == "__main__":
    if export_to_onnx():
        quantize_onnx()
        verify_inference()
