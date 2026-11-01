"""Report the local environment used for the EG-VQA reproduction.

Reads versions only; it does not install or modify anything. The output is JSON
so it can be archived under experiments/env_report.json.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional


PACKAGES = [
    "torch",
    "torchvision",
    "transformers",
    "accelerate",
    "vllm",
    "qwen_vl_utils",
    "sentence_transformers",
    "datasets",
    "pyarrow",
    "numpy",
    "scipy",
    "cv2",
    "PIL",
    "pytest",
    "openai",
    "ray",
    "omegaconf",
]


def package_version(name: str) -> Optional[str]:
    try:
        module = __import__(name)
    except Exception:
        return None
    return getattr(module, "__version__", "unknown")


def torch_report() -> Dict[str, Any]:
    report: Dict[str, Any] = {"installed": False}
    try:
        import torch
    except Exception as exc:
        report["error"] = str(exc)
        return report

    report.update(
        {
            "installed": True,
            "version": torch.__version__,
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_version": getattr(torch.version, "cuda", None),
            "cudnn_version": torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None,
            "device_count": torch.cuda.device_count(),
            "devices": [],
        }
    )
    for index in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(index)
        report["devices"].append(
            {
                "index": index,
                "name": props.name,
                "total_memory_gb": round(props.total_memory / 1024**3, 2),
                "capability": f"{props.major}.{props.minor}",
            }
        )
    return report


def nvidia_smi() -> Optional[str]:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        return subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        ).stdout.strip()
    except Exception:
        return None


def git_commit(path: Path) -> Optional[str]:
    if not (path / ".git").exists():
        return None
    try:
        return subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        ).stdout.strip() or None
    except Exception:
        return None


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report = {
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
            "conda_prefix": __import__("os").environ.get("CONDA_PREFIX"),
        },
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "cpu_count": __import__("os").cpu_count(),
        "torch": torch_report(),
        "nvidia_smi": nvidia_smi(),
        "packages": {name: package_version(name) for name in PACKAGES},
        "official_repo_commit": git_commit(root / "official_repo"),
        "disk": {
            str(location): {
                "total_gb": round(shutil.disk_usage(location).total / 1024**3, 1),
                "free_gb": round(shutil.disk_usage(location).free / 1024**3, 1),
            }
            for location in sorted({Path.home(), root}, key=str)
            if Path(location).exists()
        },
    }
    output = root / "experiments" / "env_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nSaved to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
