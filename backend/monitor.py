import threading
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union
import csv
from .utils import (
    ping_host,
    resolve_dns,
    get_wifi_signal,
    packet_loss_test,
    get_speedtest,
    check_connectivity,
)
from .models import MonitoringEvent, AggregatedStats


class NetworkMonitor:
    """Main monitoring class that runs network diagnostics periodically"""

    def __init__(self, interval_sec: int = 10, log_dir: str = "./logs"):
        self.interval_sec = interval_sec
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.running = False
        self.monitor_thread = None
        self.stop_event = threading.Event()
        self._lock = threading.Lock()  # B4: thread safety

        self.start_time = None
        self.events: List[MonitoringEvent] = []
        self.last_connectivity_state = None
        self.last_speedtest_time = 0.0
        self.speedtest_interval = 600  # 10 minutes

        # B2: accurate uptime tracking
        self.connected_since: Optional[float] = None
        self.total_downtime_sec: float = 0.0
        self.last_disconnect_time: Optional[float] = None

        # B7: alert thresholds and list
        self.alert_thresholds = {
            "latency_ms": 200.0,
            "packet_loss": 10.0,
        }
        self.alerts: List[dict] = []

        # B8: runtime config
        self.config = {
            "interval_sec": interval_sec,
            "speedtest_interval": 600,
            "alert_latency_ms": 200.0,
            "alert_packet_loss": 10.0,
        }

    def start(self):
        """Start monitoring in background thread"""
        if self.running:
            return

        self.running = True
        self.start_time = datetime.now()
        self.stop_event.clear()
        with self._lock:
            self.events = []
            self.alerts = []
        self.last_speedtest_time = time.time()
        self.connected_since = time.time()
        self.total_downtime_sec = 0.0
        self.last_disconnect_time = None

        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        """Stop monitoring gracefully"""
        self.running = False
        self.stop_event.set()

        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

        self._save_logs()

    def restart(self):
        """B9: Stop and restart monitoring"""
        if self.running:
            self.stop()
        self.start()

    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running and not self.stop_event.is_set():
            try:
                self._run_check()
            except Exception as e:
                print(f"Monitor loop error: {e}")
            # Wait for interval OR stop signal — whichever comes first
            self.stop_event.wait(timeout=self.interval_sec)

    def _append_event(self, event: MonitoringEvent):
        """B4: Thread-safe event append with B1 autosave every 50 events"""
        with self._lock:
            self.events.append(event)
            count = len(self.events)
        if count % 50 == 0:
            self._save_logs_atomic()

    def _run_check(self):
        """Execute one monitoring cycle"""
        timestamp = datetime.now()

        # 1. Check connectivity (ping multiple hosts)
        ping_results = {}
        for host in ["8.8.8.8", "1.1.1.1"]:
            success, latency, loss = ping_host(host, count=2, timeout=4)
            ping_results[host] = {
                "success": success,
                "latency_ms": latency,
                "packet_loss": loss,
            }

        # 2. Detect connectivity change
        current_connectivity = any(r["success"] for r in ping_results.values())
        if (
            self.last_connectivity_state is not None
            and self.last_connectivity_state != current_connectivity
        ):
            # B2: track downtime accurately
            now = time.time()
            if not current_connectivity:
                self.last_disconnect_time = now
                self.connected_since = None
            else:
                if self.last_disconnect_time is not None:
                    self.total_downtime_sec += now - self.last_disconnect_time
                self.last_disconnect_time = None
                self.connected_since = now

            event = MonitoringEvent(
                event_type="connection_change",
                success=current_connectivity,
                details={
                    "prev_state": (
                        "connected" if self.last_connectivity_state else "disconnected"
                    ),
                    "new_state": (
                        "connected" if current_connectivity else "disconnected"
                    ),
                },
                timestamp=timestamp,
            )
            self._append_event(event)

        self.last_connectivity_state = current_connectivity

        # 3. Log ping results
        for host, result in ping_results.items():
            event = MonitoringEvent(
                event_type="ping",
                success=result["success"],
                details={
                    "host": host,
                    "latency_ms": result["latency_ms"],
                    "packet_loss": result["packet_loss"],
                },
                timestamp=timestamp,
            )
            self._append_event(event)
            self._check_ping_alert(host, result)  # B7

        # 4. Check DNS
        dns_success, resolved_ip, dns_latency = resolve_dns("google.com")
        event = MonitoringEvent(
            event_type="dns",
            success=dns_success,
            details={
                "hostname": "google.com",
                "resolved_ip": resolved_ip,
                "latency_ms": dns_latency,
            },
            timestamp=timestamp,
        )
        self._append_event(event)

        # 5. Check WiFi signal
        signal_db, connection_status = get_wifi_signal()
        event = MonitoringEvent(
            event_type="wifi",
            success=connection_status != "N/A",
            details={
                "signal_strength_db": signal_db,
                "connection_status": connection_status,
            },
            timestamp=timestamp,
        )
        self._append_event(event)

        # 6. Periodic speedtest (every 10 minutes)
        current_time = time.time()
        if current_time - self.last_speedtest_time >= self.speedtest_interval:
            download, upload = None, None
            speedtest_success = False

            try:
                speedtest_success, download, upload = get_speedtest()
            except Exception as e:
                print(f"Speedtest failed: {e}")

            event = MonitoringEvent(
                event_type="speedtest",
                success=speedtest_success,
                details={"download_mbps": download, "upload_mbps": upload},
                timestamp=timestamp,
            )
            self._append_event(event)
            self.last_speedtest_time = current_time

    def _check_ping_alert(self, host: str, result: dict):
        """B7: Generate alert if ping exceeds thresholds"""
        if not result["success"]:
            return
        lat = result.get("latency_ms")
        loss = result.get("packet_loss")
        thresh = self.alert_thresholds
        if lat and lat > thresh["latency_ms"]:
            self._add_alert(
                "high_latency",
                f"{host}: {lat:.0f}ms exceeds {thresh['latency_ms']:.0f}ms threshold",
            )
        if loss and loss > thresh["packet_loss"]:
            self._add_alert(
                "high_packet_loss",
                f"{host}: {loss:.1f}% loss exceeds {thresh['packet_loss']:.1f}% threshold",
            )

    def _add_alert(self, alert_type: str, message: str):
        """B7: Add an alert to the alerts list"""
        alert = {
            "type": alert_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        with self._lock:
            self.alerts.append(alert)
            if len(self.alerts) > 100:
                self.alerts = self.alerts[-100:]

    def _write_events_json(self, path: Path):
        """Write current events snapshot to a JSON file"""
        with self._lock:
            events_snapshot = list(self.events)
        events_data = [
            {
                "event_type": e.event_type,
                "success": e.success,
                "details": e.details,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events_snapshot
        ]
        with open(path, "w") as f:
            json.dump(events_data, f, indent=2)

    def _save_logs(self):
        """Save events to timestamped JSON on stop"""
        try:
            log_file = (
                self.log_dir
                / f"network_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            self._write_events_json(log_file)
            print(f"Logs saved to {log_file}")
        except Exception as e:
            print(f"Error saving logs: {e}")

    def _save_logs_atomic(self):
        """B1: Autosave to session_current.json every 50 events"""
        try:
            self._write_events_json(self.log_dir / "session_current.json")
        except Exception as e:
            print(f"Error autosaving: {e}")

    def get_history(self, limit: Optional[int] = 100) -> List[dict]:
        """Get last N events as dictionaries (B4: thread-safe)"""
        with self._lock:
            evs = list(self.events)
        if limit is None:
            limit = len(evs)
        return [
            {
                "event_type": e.event_type,
                "success": e.success,
                "details": e.details,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in evs[-limit:]
        ]

    def get_chart_data(self, limit: int = 200) -> dict:
        """B3: Return structured chart data for frontend graphs"""
        with self._lock:
            evs = list(self.events[-limit:])

        ping_series: dict = {"8.8.8.8": [], "1.1.1.1": []}
        loss_series: dict = {"8.8.8.8": [], "1.1.1.1": []}
        speedtest_series: list = []

        for e in evs:
            ts = e.timestamp.isoformat()
            if e.event_type == "ping":
                host = e.details.get("host")
                if host in ping_series:
                    ping_series[host].append(
                        {"t": ts, "v": e.details.get("latency_ms")}
                    )
                    loss_series[host].append(
                        {"t": ts, "v": e.details.get("packet_loss")}
                    )
            elif e.event_type == "speedtest" and e.success:
                speedtest_series.append(
                    {
                        "t": ts,
                        "download": e.details.get("download_mbps"),
                        "upload": e.details.get("upload_mbps"),
                    }
                )

        return {
            "ping": ping_series,
            "packet_loss": loss_series,
            "speedtest": speedtest_series,
        }

    def get_alerts(self, limit: int = 50) -> List[dict]:
        """B7: Return recent alerts"""
        with self._lock:
            return list(self.alerts[-limit:])

    def get_log_files(self) -> List[dict]:
        """B10: List all saved log files"""
        files = []
        for pattern in ("*.json", "*.csv"):
            for f in sorted(self.log_dir.glob(pattern)):
                stat = f.stat()
                files.append(
                    {
                        "name": f.name,
                        "size_kb": round(stat.st_size / 1024, 1),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    }
                )
        return files

    def export_csv(self, filepath: Optional[Union[str, Path]] = None) -> str:
        """Export events to CSV and return filepath (B4: thread-safe)"""
        if filepath is None:
            filepath = (
                self.log_dir
                / f"network_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
        else:
            filepath = Path(filepath)

        try:
            with self._lock:
                events_snapshot = list(self.events)

            rows = []
            for event in events_snapshot:
                row = {
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type,
                    "success": event.success,
                }
                for key, value in event.details.items():
                    row[f"detail_{key}"] = value
                rows.append(row)

            if not rows:
                print("No events to export")
                return str(filepath)

            fieldnames = ["timestamp", "event_type", "success"]
            for row in rows:
                for key in row.keys():
                    if key not in fieldnames:
                        fieldnames.append(key)

            with open(filepath, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            print(f"CSV exported to {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"Error exporting CSV: {e}")
            return str(filepath)

    def get_stats(self) -> AggregatedStats:
        """B2: Calculate aggregated statistics with accurate uptime"""
        with self._lock:
            events_snapshot = list(self.events)

        if not events_snapshot or not self.start_time:
            return AggregatedStats(
                uptime_percent=0.0,
                total_disconnects=0,
                avg_latency_ms=None,
                total_events=0,
                monitoring_duration_sec=0,
            )

        monitoring_duration = (datetime.now() - self.start_time).total_seconds()

        # Count disconnects
        total_disconnects = sum(
            1
            for e in events_snapshot
            if e.event_type == "connection_change" and not e.success
        )

        # B2: accurate downtime using tracked wall-clock timestamps
        current_downtime = self.total_downtime_sec
        if self.last_disconnect_time is not None:
            current_downtime += time.time() - self.last_disconnect_time

        uptime_sec = max(0.0, monitoring_duration - current_downtime)
        uptime_percent = (
            min(100.0, (uptime_sec / monitoring_duration) * 100.0)
            if monitoring_duration > 0
            else 100.0
        )

        # Average ping latency (from events_snapshot, not self.events)
        latencies = [
            e.details["latency_ms"]
            for e in events_snapshot
            if e.event_type == "ping" and e.details.get("latency_ms") is not None
        ]
        avg_latency = sum(latencies) / len(latencies) if latencies else None

        return AggregatedStats(
            uptime_percent=uptime_percent,
            total_disconnects=total_disconnects,
            avg_latency_ms=avg_latency,
            total_events=len(events_snapshot),
            monitoring_duration_sec=int(monitoring_duration),
        )

    def get_status(self) -> dict:
        """Get current monitoring status (B4: thread-safe)"""
        with self._lock:
            event_count = len(self.events)
            last_ts = self.events[-1].timestamp.isoformat() if self.events else None
        uptime_sec = (
            int((datetime.now() - self.start_time).total_seconds())
            if self.start_time
            else 0
        )
        return {
            "running": self.running,
            "uptime_sec": uptime_sec,
            "events_count": event_count,
            "last_check": last_ts,
        }
