# NetCheck — Network Stability Monitor

A lightweight, self-hosted tool for monitoring network connectivity over time. Runs a local web server, collects ping/DNS/WiFi/speed metrics every 10 seconds, streams results live to the browser, and saves everything to JSON logs on your machine.

---

## Features

| Category | Details |
|---|---|
| **Diagnostics** | Ping (8.8.8.8, 1.1.1.1), DNS resolution, WiFi signal strength, download/upload speed |
| **Alerting** | Configurable thresholds for high latency and packet loss |
| **Live UI** | SSE-driven dashboard — no page refreshes; sparkline timeline; event log |
| **Export** | One-click CSV export; raw JSON logs retained in `./logs/` |
| **Privacy** | Fully local — `localhost:8000` only, zero external data transmission |
| **Platform** | Windows · Linux · macOS |

---

## Requirements

- Python 3.8+
- pip

---

## Installation

```bash
git clone https://github.com/your-username/netcheck.git
cd netcheck

# Create and activate a virtual environment (recommended)
python -m venv venv

# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

---

## Running

```bash
python run.py          # Windows
python3 run.py         # Linux / macOS
```

Open **http://127.0.0.1:8000** in your browser.

---

## Usage

1. Click **▶ Start Monitoring** — the status indicator turns green.
2. Events appear in the log every ~10 seconds.
3. Click **��� Export CSV** at any time to download a spreadsheet.
4. Click **⏸ Stop Monitoring** to end the session — logs are saved automatically.

### Dashboard panels

| Panel | Description |
|---|---|
| **Status bar** | Online / Offline indicator with monitoring state |
| **Stats cards** | Uptime %, disconnect count, average latency, session duration |
| **Timeline** | Colour-coded sparkline — ��� connected · ��� disconnected |
| **Event log** | Last 100 events with type, status, and metric details |

### Event types

| Type | Interval | What it measures |
|---|---|---|
| `ping` | 10 s | Round-trip latency and packet loss to 8.8.8.8 / 1.1.1.1 |
| `dns` | 10 s | Resolution time for `google.com` |
| `wifi` | 10 s | Signal strength (dBm / %) and connection status |
| `speedtest` | 10 min | Download and upload throughput |
| `connection_change` | on change | Online ↔ Offline state transitions |

---

## REST API

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Serve web UI |
| `/api/start` | GET | Start monitoring |
| `/api/stop` | GET | Stop monitoring |
| `/api/status` | GET | Current running state |
| `/api/history` | GET | Event list (`?limit=N`) |
| `/api/stats` | GET | Aggregated statistics |
| `/api/events` | GET | Server-Sent Events stream |
| `/api/export` | POST | Download CSV or JSON |
| `/api/logs` | DELETE | Clear all in-memory logs |

---

## Logs & data format

Logs are written to `./logs/` as timestamped JSON files.

### JSON event schema

```json
{
  "event_type": "ping",
  "success": true,
  "timestamp": "2026-03-25T10:15:30.123456",
  "details": {
    "host": "8.8.8.8",
    "latency_ms": 18.4,
    "packet_loss": 0.0
  }
}
```

### CSV export columns

```
timestamp, event_type, success, detail_host, detail_latency_ms, detail_packet_loss
```

---

## Project structure

```
netcheck/
├── backend/
│   ├── app.py        # FastAPI application & REST endpoints
│   ├── monitor.py    # Monitoring loop, alerting, uptime tracking
│   ├── models.py     # Pydantic data models
│   └── utils.py      # ping, DNS, WiFi, speed-test helpers
├── frontend/
│   ├── index.html    # Dashboard markup
│   ├── style.css     # Dark-theme stylesheet
│   └── app.js        # SSE client, charts, UI logic
├── logs/             # JSON session logs (auto-created)
├── run.py            # Entry point (uvicorn launcher)
└── requirements.txt  # Python dependencies
```

---

## Tech stack

| Component | Library | Version |
|---|---|---|
| Web framework | FastAPI | 0.135 |
| ASGI server | uvicorn | 0.42 |
| Data validation | Pydantic | 2.x |
| Ping | ping3 | 5.1 |
| Speed test | speedtest-cli | 2.1 |
| DNS | dnspython | 2.8 |

---

## Performance

| Metric | Value |
|---|---|
| Monitoring interval | 10 s |
| Speed test interval | 10 min (background) |
| Events per hour | ~360–400 |
| Log size per hour | ~200–300 KB |
| CPU usage | ~1–2 % (idle between checks) |
| Memory | ~50–100 MB |

---

## Troubleshooting

**Port 8000 already in use**

Edit `run.py` and change the port number:
```python
uvicorn.run(..., port=8001)
```

**`Permission denied` on Linux / macOS**

ICMP ping requires elevated privileges on some systems:
```bash
sudo python3 run.py
```

**WiFi signal shows N/A**

Expected on Ethernet-only machines. On Linux, ensure `nmcli` or `iwconfig` is available.

**Speed test is slow / times out**

Speed tests run for 30–60 s by design to produce accurate results. They run in the background and do not block ping or DNS checks.

---

## Security & privacy

- Binds to `127.0.0.1` only — not accessible over the network.
- No data is sent to any external service.
- No analytics, telemetry, or tracking of any kind.
- Logs contain only technical network metrics (latency, signal strength, throughput) — no URLs, credentials, or personal data.
- Source code is fully auditable.

---

## License

MIT
