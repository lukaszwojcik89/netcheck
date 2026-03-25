# 🔗 NetCheck - Network Stability Monitor

A simple, local web-based tool to monitor network connectivity and diagnose cable/connection issues over extended periods.

## Features

✅ **Real-time Monitoring**

- Ping to multiple DNS servers (8.8.8.8, 1.1.1.1)
- DNS resolution testing (google.com)
- Packet loss measurement
- WiFi signal strength (Windows/Linux/macOS)
- Periodic speed tests (every 10 minutes)

✅ **Web UI**

- Real-time status dashboard
- Live connection timeline (sparkline)
- Event log with detailed history
- Aggregated statistics (uptime %, disconnects, avg latency)

✅ **Data Export**

- CSV export for analysis
- JSON logs saved locally
- Full data control on your machine

✅ **Privacy & Security**

- 100% local operation (localhost:8000 only)
- No data sent externally
- No analytics or tracking
- Open source code you can audit

---

## Quick Start

### Prerequisites

- Python 3.8+
- Windows, Linux, or macOS

### Installation

1. **Clone or extract the project**

```bash
cd netcheck
```

1. **Create virtual environment** (recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

1. **Install dependencies**

```bash
pip install -r requirements.txt
```

### Running

```bash
# Windows
python run.py

# Linux/macOS
python3 run.py
```

Then open your browser to: **<http://127.0.0.1:8000>**

---

## Usage

### Starting Monitoring

1. Click **"▶ Start Monitoring"** button in the web UI
2. The status indicator will turn **🟢 green** and show "Monitoring Active"
3. Events will start appearing in the event log

### What's Being Monitored

- **PING**: Connection test to public DNS servers (8.8.8.8, 1.1.1.1)
- **DNS**: Domain name resolution test (google.com)
- **WiFi**: Signal strength and connection status
- **SPEED**: Download/upload speed test (runs every 10 minutes, can be slow)
- **CONN**: Connection state changes (online/offline transitions)

### Viewing Results

- **Real-time Dashboard**: Stats update every 2 seconds
  - Uptime percentage
  - Disconnect count
  - Average latency
  - Monitoring duration

- **Event Timeline**: Visual sparkline showing connection state history
  - 🟩 Green = Connected
  - 🟥 Red = Disconnected

- **Event Log**: Last 100 events with timestamps and details
  - Type, status, and metrics for each event
  - Scroll to see full history

### Exporting Data

1. Click **"📥 Export CSV"** to download events as spreadsheet
2. File available for analysis in Excel, Python, etc.

### Stopping Monitoring

Click **"⏸ Stop Monitoring"** button

- Logs are automatically saved to `./logs/` folder
- Data persists for future reference

### Clearing Logs

Click **"🗑 Clear Logs"** to remove all events

- ⚠️ This cannot be undone
- Useful for starting fresh test session

---

## Project Structure

```
netcheck/
├── backend/
│   ├── app.py           # FastAPI server & endpoints
│   ├── monitor.py       # Core monitoring logic
│   ├── models.py        # Pydantic data models
│   ├── utils.py         # Network diagnostic functions
│   └── __init__.py      # Package marker
├── frontend/
│   ├── index.html       # Web UI
│   ├── style.css        # Styling (dark theme)
│   └── app.js           # JavaScript (EventSource SSE)
├── logs/                # JSON/CSV logs (created on first run)
├── run.py              # Entry point
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

---

## Logs & Data

### Storage

- **JSON Logs**: `./logs/network_monitor_*.json`
- **CSV Exports**: `./logs/network_monitor_*.csv`
- All data stays on your machine

### JSON Log Format

```json
{
  "event_type": "ping",
  "success": true,
  "details": {
    "host": "8.8.8.8",
    "latency_ms": 25.5,
    "packet_loss": 0.0
  },
  "timestamp": "2024-03-24T14:30:45.123456"
}
```

### CSV Export Format

| timestamp | event_type | success | detail_host | detail_latency_ms | detail_packet_loss |
|-----------|-----------|---------|-------------|-------------------|-------------------|
| 2024-03-24T14:30:45 | ping | True | 8.8.8.8 | 25.5 | 0.0 |

---

## Troubleshooting

### "Permission denied" on Linux/macOS

Run with `sudo` for ping capability:

```bash
sudo python3 run.py
```

### Speed test is slow

- Speed tests take 30-60 seconds by design (accurate measurement)
- They run every 10 minutes in background
- Does not block other checks (ping/DNS run every 10s)
- Can be disabled by modifying `monitor.py`

### Port 8000 already in use

Edit `run.py` and change port:

```python
uvicorn.run(..., port=8001)  # or any unused port
```

### WiFi signal shows "N/A"

- Normal on Ethernet-only machines
- Linux may require `wmctrl` or `nmcli` package
- Windows uses native `netsh` command

### No internet = all pings fail

- This is expected and logged correctly
- Good for testing when disconnected intentionally
- Check event log to see failure reasons

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve web UI |
| `/api/start` | GET | Start monitoring |
| `/api/stop` | GET | Stop monitoring |
| `/api/status` | GET | Current status |
| `/api/history` | GET | Event history (limit param) |
| `/api/stats` | GET | Aggregated statistics |
| `/api/events` | GET | EventSource (SSE) stream |
| `/api/export` | POST | Export CSV/JSON |
| `/api/logs` | DELETE | Clear all logs |

---

## Performance & Specs

- **Monitoring Interval**: 10 seconds (ping, DNS, WiFi)
- **Speed Test Interval**: 10 minutes (background)
- **Typical Duration**: ~1 hour baseline test
- **Events per Hour**: ~360-400 (six per cycle × 60 cycles)
- **JSON Log Size**: ~200-300 KB for 1-hour session
- **CPU Impact**: Minimal (~1-2% idle between checks)
- **Memory**: ~50-100 MB process size

---

## Security Notes

✅ **What's NOT logged:**

- URLs you visit
- Passwords or tokens
- Private communication content
- Personally identifiable information (PII)

✅ **What IS logged:**

- Connectivity state (online/offline)
- Latency to public DNS servers
- DNS resolution results
- WiFi signal strength (technical metric)
- Download/upload speeds (technical metrics)

✅ **All data is LOCAL:**

- Nothing uploaded to cloud
- Nothing stored externally
- You control deletion & archival
- Fully auditable source code

---

## Limitations

- Local-only (not accessible from other machines by default)
- No authentication (assumes trusted environment)
- Speed tests require internet connectivity
- WiFi signal accuracy varies by platform
- Single-machine monitoring (no multi-device sync)

---

## Future Enhancements (v2)

- [ ] Historical graph comparison
- [ ] Email/Slack alerts
- [ ] Custom test targets
- [ ] HTTPS with self-signed cert
- [ ] Network interface selection
- [ ] Mobile app
- [ ] Database storage option

---

## License

Open source. Free to use and modify for personal use.

---

## Support

For issues or questions:

1. Check event logs in `./logs/`
2. Review browser console (F12 → Console tab)
3. Check terminal output when running `run.py`

---

**Happy monitoring! 🔗**
# netcheck
