import subprocess
import platform
import re
import socket
import json
from typing import Optional, Tuple
import time
import os


def ping_host(
    host: str, count: int = 4, timeout: int = 5
) -> Tuple[bool, Optional[float], float]:
    """
    Ping a host and return (success, avg_latency_ms, packet_loss_percent)
    """
    try:
        system = platform.system()

        if system == "Windows":
            cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), host]
        else:  # Linux, macOS
            cmd = ["ping", "-c", str(count), "-W", str(timeout * 1000), host]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 5
        )

        if result.returncode != 0:
            return False, None, 100.0

        # Parse output for latency and packet loss
        output = result.stdout

        # Extract average latency
        latency_ms = None
        if system == "Windows":
            # Windows: "Average = 25ms"
            match = re.search(r"Average[^=]*=\s*([\d.]+)ms", output)
            if match:
                latency_ms = float(match.group(1))
        else:
            # Linux/macOS: "min/avg/max/stddev = x/y/z/w ms"
            match = re.search(r"min/avg/max/stddev\s*=\s*[\d.]+/([\d.]+)/", output)
            if match:
                latency_ms = float(match.group(1))

        # Extract packet loss
        packet_loss = 0.0
        if system == "Windows":
            match = re.search(r"\(([0-9.]+)%\s*loss\)", output)
            if match:
                packet_loss = float(match.group(1))
        else:
            match = re.search(r"([\d.]+)%\s*packet loss", output)
            if match:
                packet_loss = float(match.group(1))

        success = packet_loss < 100.0
        return success, latency_ms, packet_loss

    except Exception as e:
        print(f"Ping error: {e}")
        return False, None, 100.0


def get_speedtest() -> Tuple[bool, Optional[float], Optional[float]]:
    """
    B6: Run speedtest using --json for more reliable parsing.
    Returns (success, download_mbps, upload_mbps). Slow (~30-60s).
    """
    try:
        result = subprocess.run(
            ["speedtest-cli", "--json"], capture_output=True, text=True, timeout=120
        )

        if result.returncode != 0:
            return False, None, None

        data = json.loads(result.stdout.strip())
        download = data["download"] / 1_000_000  # bits/s → Mbps
        upload = data["upload"] / 1_000_000
        return True, round(download, 2), round(upload, 2)

    except Exception as e:
        print(f"Speedtest error: {e}")

    return False, None, None


def resolve_dns(
    hostname: str = "google.com",
) -> Tuple[bool, Optional[str], Optional[float]]:
    """
    Resolve DNS and return (success, resolved_ip, latency_ms)
    """
    try:
        start_time = time.time()
        ip = socket.gethostbyname(hostname)
        latency_ms = (time.time() - start_time) * 1000
        return True, ip, latency_ms
    except Exception as e:
        print(f"DNS error: {e}")
        return False, None, None


def get_wifi_signal_windows() -> Tuple[Optional[float], str]:
    """
    Windows only: Get WiFi signal strength using netsh
    Returns (signal_strength_db, connection_status)
    """
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True
        )

        if result.returncode != 0:
            return None, "N/A"

        output = result.stdout

        # Extract signal strength
        signal_db = None
        match = re.search(r"Signal\s*:\s*([\d]+)\s*%", output)
        if match:
            signal_percent = int(match.group(1))
            # Convert percentage to dBm (rough approximation: -100 to 0 dBm)
            signal_db = -100 + (signal_percent / 100.0) * 50

        # Extract connection status
        status = "N/A"
        if "connected" in output.lower():
            status = "connected"
        elif "disconnected" in output.lower():
            status = "disconnected"

        return signal_db, status

    except Exception as e:
        print(f"WiFi signal error (Windows): {e}")
        return None, "N/A"


def get_wifi_signal_linux() -> Tuple[Optional[float], str]:
    """
    Linux: Get WiFi signal strength using iwconfig or nmcli
    Returns (signal_strength_db, connection_status)
    """
    try:
        # Try nmcli first (NetworkManager)
        result = subprocess.run(
            ["nmcli", "device", "wifi", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            # Parse for signal strength
            match = re.search(r"(\d+)\s+Mbit/s", result.stdout)
            if match:
                return None, "connected"

        # Fallback: iwconfig
        result = subprocess.run(["iwconfig"], capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            output = result.stdout
            match = re.search(r"Signal level[=:]?\s*([+-]?\d+)\s*dBm", output)
            if match:
                signal_db = float(match.group(1))
                status = "connected" if signal_db > -100 else "weak"
                return signal_db, status

        return None, "N/A"

    except Exception as e:
        print(f"WiFi signal error (Linux): {e}")
        return None, "N/A"


def get_wifi_signal_macos() -> Tuple[Optional[float], str]:
    """
    macOS: Get WiFi signal strength using airport
    Returns (signal_strength_db, connection_status)
    """
    try:
        airport_path = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"

        if not os.path.exists(airport_path):
            return None, "N/A"

        result = subprocess.run(
            [airport_path, "-I"], capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            output = result.stdout
            match = re.search(r"rssi:\s*([+-]?\d+)", output)
            if match:
                signal_db = float(match.group(1))
                status = "connected" if signal_db > -100 else "weak"
                return signal_db, status

        return None, "N/A"

    except Exception as e:
        print(f"WiFi signal error (macOS): {e}")
        return None, "N/A"


def get_wifi_signal() -> Tuple[Optional[float], str]:
    """
    Cross-platform WiFi signal detection
    Returns (signal_strength_db, connection_status)
    """
    system = platform.system()

    if system == "Windows":
        return get_wifi_signal_windows()
    elif system == "Linux":
        return get_wifi_signal_linux()
    elif system == "Darwin":
        return get_wifi_signal_macos()
    else:
        return None, "N/A"


def packet_loss_test(host: str = "8.8.8.8", count: int = 10) -> float:
    """
    Test packet loss percentage
    Returns percentage (0-100)
    """
    try:
        _, _, loss = ping_host(host, count=count, timeout=5)
        return loss
    except Exception as e:
        print(f"Packet loss test error: {e}")
        return 100.0


def check_connectivity() -> bool:
    """
    Quick check if there's any internet connectivity
    Returns True if at least one public DNS resolves
    """
    for host in ["8.8.8.8", "1.1.1.1"]:
        success, _, _ = ping_host(host, count=1, timeout=3)
        if success:
            return True

    return False
