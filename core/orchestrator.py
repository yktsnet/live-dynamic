import subprocess
import sys
from pathlib import Path


_APP_ROOT = Path(__file__).resolve().parents[1]


def _run_script(path: Path) -> int:
    return subprocess.run([sys.executable, str(path)], check=False).returncode


def run_pipeline() -> int:
    build_signal_code = _run_script(_APP_ROOT / "core" / "build_signal.py")
    if build_signal_code != 0:
        return build_signal_code

    sender_gate_code = _run_script(_APP_ROOT / "core" / "sender_gate.py")
    if sender_gate_code != 0:
        return sender_gate_code

    return 0


def main() -> int:
    return run_pipeline()


if __name__ == "__main__":
    raise SystemExit(main())
