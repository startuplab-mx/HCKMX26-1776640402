"""
ZKTCA Platform Detection Module
================================
Detects the host OS and selects the optimal compute backend
for training and inference.

Supported platforms:
  - macOS  → Apple MPS (Metal Performance Shaders)
  - Linux  → NVIDIA CUDA (if available)
  - Windows → NVIDIA CUDA (if available)
  - Fallback → CPU on any platform
"""

import platform
import sys
import logging

logger = logging.getLogger(__name__)


def get_platform_info():
    """
    Detect the current OS and available hardware accelerators.

    Returns:
        dict with keys: os_name, os_version, arch, python_version,
                        cuda_available, mps_available, recommended_device
    """
    os_name = platform.system()        # 'Darwin', 'Linux', 'Windows'
    os_version = platform.version()
    arch = platform.machine()          # 'arm64', 'x86_64', 'AMD64'
    python_ver = platform.python_version()

    info = {
        "os_name": os_name,
        "os_friendly": {"Darwin": "macOS", "Linux": "Linux", "Windows": "Windows"}.get(os_name, os_name),
        "os_version": os_version,
        "arch": arch,
        "python_version": python_ver,
        "cuda_available": False,
        "cuda_version": None,
        "cuda_device_name": None,
        "mps_available": False,
        "recommended_device": "cpu",
    }

    # Check for PyTorch backends
    try:
        import torch

        # --- CUDA (Linux / Windows) ---
        if torch.cuda.is_available():
            info["cuda_available"] = True
            info["cuda_version"] = torch.version.cuda
            info["cuda_device_name"] = torch.cuda.get_device_name(0)

        # --- MPS (macOS Apple Silicon) ---
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            info["mps_available"] = True

    except ImportError:
        logger.warning("PyTorch not installed — cannot detect GPU backends.")

    # Determine recommended device based on OS
    if os_name in ("Linux", "Windows") and info["cuda_available"]:
        info["recommended_device"] = "cuda"
    elif os_name == "Darwin" and info["mps_available"]:
        info["recommended_device"] = "mps"
    else:
        info["recommended_device"] = "cpu"

    return info


def get_device():
    """
    Select the best available PyTorch device based on the detected platform.

    Returns:
        torch.device — the optimal device for this machine.
    """
    import torch

    info = get_platform_info()
    device_name = info["recommended_device"]

    # Build a user-friendly log message
    os_label = info["os_friendly"]
    icons = {"cuda": "🟢", "mps": "🍎", "cpu": "💻"}
    icon = icons.get(device_name, "💻")

    if device_name == "cuda":
        gpu_name = info["cuda_device_name"] or "Unknown GPU"
        cuda_ver = info["cuda_version"] or "?"
        logger.info(f"{icon} [{os_label}] Using NVIDIA CUDA — {gpu_name} (CUDA {cuda_ver})")
    elif device_name == "mps":
        logger.info(f"{icon} [{os_label}] Using Apple MPS (Metal Performance Shaders) — {info['arch']}")
    else:
        logger.info(f"{icon} [{os_label}] Using CPU — no GPU acceleration detected")

    return torch.device(device_name)


def print_platform_report():
    """Print a formatted platform report to stdout."""
    info = get_platform_info()

    print("=" * 55)
    print("  ZKTCA Platform Report")
    print("=" * 55)
    print(f"  OS:           {info['os_friendly']} ({info['os_name']})")
    print(f"  Version:      {info['os_version'][:60]}")
    print(f"  Architecture: {info['arch']}")
    print(f"  Python:       {info['python_version']}")
    print(f"  CUDA:         {'✅ ' + (info['cuda_device_name'] or '') + ' (CUDA ' + (info['cuda_version'] or '?') + ')' if info['cuda_available'] else '❌ Not available'}")
    print(f"  MPS (Metal):  {'✅ Available' if info['mps_available'] else '❌ Not available'}")
    print(f"  Device:       {info['recommended_device'].upper()}")
    print("=" * 55)

    return info


if __name__ == "__main__":
    print_platform_report()
