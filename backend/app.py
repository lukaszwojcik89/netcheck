from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
import asyncio
from pathlib import Path
import json
from datetime import datetime
from .monitor import NetworkMonitor


# Global monitor instance
monitor = NetworkMonitor(interval_sec=10, log_dir="./logs")

# Create FastAPI app
app = FastAPI(title="NetCheck - Network Stability Monitor")

# Mount frontend static files
frontend_dir = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
async def root():
    """Serve index.html"""
    return FileResponse(frontend_dir / "index.html", media_type="text/html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon to suppress 404 in logs"""
    from fastapi.responses import Response

    # fmt: off
    ico = bytes([0,0,1,0,1,0,1,1,0,0,1,0,24,0,40,0,0,0,1,0,0,0,2,0,0,0,1,0,24,0,0,0,0,0,12,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,255,255,255,0,0,0])
    # fmt: on
    return Response(content=ico, media_type="image/x-icon")


@app.get("/api/start")
async def start_monitoring():
    """Start network monitoring"""
    try:
        monitor.start()
        return {
            "status": "started",
            "message": "Network monitoring started",
            "running": monitor.running,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stop")
async def stop_monitoring():
    """Stop network monitoring"""
    try:
        monitor.stop()
        return {
            "status": "stopped",
            "message": "Network monitoring stopped",
            "running": monitor.running,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/restart")
async def restart_monitoring():
    """B9: Restart monitoring (stop + start)"""
    try:
        monitor.restart()
        return {"status": "restarted", "running": monitor.running}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_status():
    """Get current monitoring status"""
    return monitor.get_status()


@app.get("/api/history")
async def get_history(limit: int = 100):
    """Get last N monitoring events"""
    return {
        "events": monitor.get_history(limit=limit),
        "total_count": len(monitor.events),
    }


@app.get("/api/stats")
async def get_stats():
    """Get aggregated statistics"""
    stats = monitor.get_stats()
    return stats.dict()


@app.get("/api/chart-data")
async def get_chart_data(limit: int = 200):
    """B3: Structured time-series data for frontend charts"""
    return monitor.get_chart_data(limit=limit)


@app.get("/api/alerts")
async def get_alerts(limit: int = 50):
    """B7: Return recent threshold alerts"""
    return {"alerts": monitor.get_alerts(limit=limit)}


@app.post("/api/alerts/config")
async def configure_alerts(latency_ms: float = 200.0, packet_loss: float = 10.0):
    """B7: Update alert thresholds"""
    monitor.alert_thresholds["latency_ms"] = latency_ms
    monitor.alert_thresholds["packet_loss"] = packet_loss
    monitor.config["alert_latency_ms"] = latency_ms
    monitor.config["alert_packet_loss"] = packet_loss
    return {"status": "ok", "thresholds": monitor.alert_thresholds}


@app.get("/api/config")
async def get_config():
    """B8: Return current runtime config"""
    return monitor.config


@app.post("/api/config")
async def update_config(
    interval_sec: int = 10,
    speedtest_interval: int = 600,
):
    """B8: Update runtime config (takes effect on next restart)"""
    monitor.config["interval_sec"] = interval_sec
    monitor.config["speedtest_interval"] = speedtest_interval
    monitor.interval_sec = interval_sec
    monitor.speedtest_interval = speedtest_interval
    return {"status": "ok", "config": monitor.config}


@app.get("/api/logs/files")
async def list_log_files():
    """B10: List all saved log files"""
    return {"files": monitor.get_log_files()}


@app.post("/api/export")
async def export_logs(format: str = "csv"):
    """Export logs to file (csv or json)"""
    try:
        if format == "csv":
            filepath = monitor.export_csv()
            return FileResponse(
                path=filepath,
                filename=f"network_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                media_type="text/csv",
            )
        elif format == "json":
            export_path = (
                Path("./logs")
                / f"network_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            export_path.parent.mkdir(parents=True, exist_ok=True)

            with open(export_path, "w") as f:
                json.dump(monitor.get_history(limit=9999), f, indent=2)

            return FileResponse(
                path=export_path,
                filename=export_path.name,
                media_type="application/json",
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/logs")
async def clear_logs():
    """Clear monitoring logs and events"""
    try:
        with monitor._lock:
            monitor.events = []
            monitor.alerts = []
        log_dir = Path("./logs")
        for log_file in log_dir.glob("*.json"):
            log_file.unlink()
        for log_file in log_dir.glob("*.csv"):
            log_file.unlink()

        return {"status": "cleared", "message": "All logs cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/events")
async def stream_events():
    """B5: SSE stream with heartbeat every 2.5s"""

    async def event_generator():
        last_count = len(monitor.events)
        heartbeat_counter = 0

        while monitor.running:
            current_count = len(monitor.events)

            if current_count > last_count:
                new_events = monitor.events[last_count:current_count]
                for event in new_events:
                    event_dict = {
                        "event_type": event.event_type,
                        "success": event.success,
                        "details": event.details,
                        "timestamp": event.timestamp.isoformat(),
                    }
                    yield f"data: {json.dumps(event_dict)}\n\n"
                last_count = current_count

            heartbeat_counter += 1
            if heartbeat_counter >= 5:  # every 5 × 0.5s = 2.5s
                yield 'data: {"type":"heartbeat"}\n\n'
                heartbeat_counter = 0

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown — stop monitor and flush logs to disk."""
    if monitor.running:
        monitor.stop()
    # Flush any buffered events even if monitor was already stopped
    try:
        with monitor._lock:
            monitor._save_logs_atomic()
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
