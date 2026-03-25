#!/usr/bin/env python3
"""
NetCheck - Network Stability Monitor
Simple entry point to run the FastAPI server
"""

import sys
import os
import socket
import signal
import atexit
import time
import uvicorn
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

PID_FILE = Path(__file__).parent / "netcheck.pid"


def _kill_existing_instance() -> None:
    """Kill previous NetCheck process recorded in PID file."""
    if not PID_FILE.exists():
        return
    try:
        old_pid = int(PID_FILE.read_text().strip())
        if old_pid == os.getpid():
            return
        print(f"⚠️  Found old NetCheck process (PID {old_pid}) — terminating it...")
        os.kill(old_pid, signal.SIGTERM)
        # Wait up to 3 s for the old process to release the port
        for _ in range(30):
            time.sleep(0.1)
            try:
                os.kill(old_pid, 0)  # probe — raises if process is gone
            except (ProcessLookupError, OSError):
                break
        else:
            # Still alive on Unix — force kill
            if sys.platform != "win32":
                os.kill(old_pid, signal.SIGKILL)
        print(f"   PID {old_pid} terminated.")
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        pass  # Process already gone or unreadable PID
    finally:
        PID_FILE.unlink(missing_ok=True)


def _write_pid() -> None:
    PID_FILE.write_text(str(os.getpid()))


def _cleanup() -> None:
    """Remove PID file on any exit (normal, Ctrl-C, crash)."""
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    print("\n✅ NetCheck zatrzymany — port zwolniony.")


def _signal_handler(sig, frame) -> None:
    """Handle SIGINT / SIGTERM gracefully."""
    _cleanup()
    sys.exit(0)


def find_free_port(start: int = 8000, end: int = 8020) -> int:
    """Return the first free TCP port in range [start, end]."""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}-{end}")


def main():
    """Run the FastAPI server"""
    # 1. Kill any leftover instance that held the port
    _kill_existing_instance()

    # 2. Register cleanup for ALL exit paths (normal, exception, signal)
    atexit.register(_cleanup)
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # 3. Find a free port and record our PID
    port = find_free_port()
    _write_pid()

    print("=" * 60)
    print("🔗 NetCheck - Network Stability Monitor")
    print("=" * 60)
    print("\nStarting server...")
    print(f"📡 Server running at: http://127.0.0.1:{port}")
    print("🌐 Open your browser and navigate to the URL above")
    print("\n⚠️  Security: This is a local-only application")
    print("   - No data is sent externally")
    print("   - All logs are saved locally in ./logs/")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60 + "\n")

    if port != 8000:
        print(f"ℹ️  Port 8000 was busy — using port {port} instead.\n")

    # 4. Run the server
    uvicorn.run(
        "backend.app:app", host="127.0.0.1", port=port, reload=False, log_level="info"
    )


if __name__ == "__main__":
    main()
