// ============================================================
// NetCheck — Frontend Application (v2)
// ============================================================

// Global state
let monitoring = {
    running: false,
    events: [],
    statsData: null,
    eventSource: null,
    statsUpdateInterval: null,
    chartUpdateInterval: null,
    alertsUpdateInterval: null,
    clockInterval: null,
    sparklineStates: [],
    charts: {
        latency: null,
        loss: null,
        speed: null,
    },
    latestPing: {
        "8.8.8.8": { latency: null, loss: null, success: null },
        "1.1.1.1": { latency: null, loss: null, success: null },
    },
    latestWifi: { db: null, status: "N/A" },
    eventFilter: { type: "", status: "" },
    allEventRows: [],       // Raw event data for re-filtering
    totalAlertCount: 0,
};

// ── Element refs ────────────────────────────────────────────
const btnStart    = document.getElementById("btnStart");
const btnStop     = document.getElementById("btnStop");
const btnRestart  = document.getElementById("btnRestart");
const btnExport   = document.getElementById("btnExport");
const btnClear    = document.getElementById("btnClear");
const btnDarkMode    = document.getElementById("btnDarkMode");
const statusDot      = document.getElementById("statusDot");
const statusText     = document.getElementById("statusText");
const eventTable     = document.getElementById("eventTable");
const sparklineEl    = document.getElementById("sparkline");
const filterType     = document.getElementById("filterType");
const filterStatus   = document.getElementById("filterStatus");
const inputInterval  = document.getElementById("inputInterval");
const inputSpeedInt  = document.getElementById("inputSpeedInterval");
const btnApplyConfig = document.getElementById("btnApplyConfig");

// ── Event Listeners ─────────────────────────────────────────
btnStart.addEventListener("click", startMonitoring);
btnStop.addEventListener("click", stopMonitoring);
btnRestart.addEventListener("click", restartMonitoring);
btnExport.addEventListener("click", exportLogs);
btnClear.addEventListener("click", clearLogs);
btnDarkMode.addEventListener("click", toggleDarkMode);
filterType.addEventListener("change", applyFilter);
filterStatus.addEventListener("change", applyFilter);
btnApplyConfig.addEventListener("click", applyConfig);

// ── Config: interval settings ───────────────────────────────
async function applyConfig() {
    const interval = parseInt(inputInterval.value, 10);
    const speedInterval = parseInt(inputSpeedInt.value, 10);
    const hint = document.getElementById("configHint");

    if (isNaN(interval) || interval < 5 || interval > 300) {
        hint.textContent = "Check interval must be 5–300 s";
        hint.style.color = "#ef4444";
        return;
    }
    if (isNaN(speedInterval) || speedInterval < 60 || speedInterval > 3600) {
        hint.textContent = "Speed interval must be 60–3600 s";
        hint.style.color = "#ef4444";
        return;
    }

    try {
        const params = new URLSearchParams({
            interval_sec: interval,
            speedtest_interval: speedInterval,
        });
        const response = await fetch(`/api/config?${params}`, { method: "POST" });
        if (response.ok) {
            hint.textContent = `✓ Saved (${interval}s / ${speedInterval}s). Restart to apply.`;
            hint.style.color = "#10b981";
            showToast(`Intervals updated: ${interval}s check, ${speedInterval}s speed test`, "success");
        } else {
            throw new Error("Server error");
        }
    } catch (err) {
        hint.textContent = "Failed to save";
        hint.style.color = "#ef4444";
        showToast("Config update failed: " + err.message, "error");
    }
}

// ── Load current config on page load ───────────────────────
async function loadConfig() {
    try {
        const response = await fetch("/api/config");
        if (!response.ok) return;
        const cfg = await response.json();
        if (cfg.interval_sec)       inputInterval.value = cfg.interval_sec;
        if (cfg.speedtest_interval) inputSpeedInt.value = cfg.speedtest_interval;
    } catch (_) {}
}

// ── Dark mode (F14) ─────────────────────────────────────────
function toggleDarkMode() {
    const html = document.documentElement;
    const isLight = html.getAttribute("data-theme") === "light";
    html.setAttribute("data-theme", isLight ? "dark" : "light");
    btnDarkMode.textContent = isLight ? "🌙" : "☀️";
}

// ── Clock (F11) ─────────────────────────────────────────────
function updateClock() {
    const now = new Date();
    document.getElementById("clock").textContent =
        now.toLocaleTimeString("pl-PL", { hour12: false });
}

function startClock() {
    updateClock();
    monitoring.clockInterval = setInterval(updateClock, 1000);
}

// ── Toast Notifications (F12) ────────────────────────────────
function showToast(message, type = "info", duration = 4000) {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("removing");
        toast.addEventListener("animationend", () => toast.remove());
    }, duration);
}

// ── Sound Alert (F13) ────────────────────────────────────────
function playAlert() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = "sine";
        osc.frequency.value = 880;
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.4);
    } catch (_) {
        // Web Audio not supported — silently skip
    }
}

// ── Start / Stop / Restart ──────────────────────────────────
async function startMonitoring() {
    try {
        const response = await fetch("/api/start");
        const data = await response.json();
        if (response.ok) {
            monitoring.running = true;
            updateControlsUI();
            setupEventStream();
            startStatsUpdate();
            startChartUpdate();
            startAlertsUpdate();
            updateStatusDisplay();
            showToast("Monitoring started", "success");
        }
    } catch (error) {
        console.error("Error starting monitoring:", error);
        showToast("Error starting monitoring: " + error.message, "error");
    }
}

async function stopMonitoring() {
    try {
        const response = await fetch("/api/stop");
        const data = await response.json();
        if (response.ok) {
            monitoring.running = false;
            updateControlsUI();
            closeStreams();
            updateStatusDisplay();
            showToast("Monitoring stopped", "warning");
        }
    } catch (error) {
        console.error("Error stopping monitoring:", error);
        showToast("Error stopping monitoring: " + error.message, "error");
    }
}

async function restartMonitoring() {
    try {
        const response = await fetch("/api/restart");
        if (response.ok) {
            monitoring.running = true;
            monitoring.events = [];
            monitoring.allEventRows = [];
            monitoring.sparklineStates = [];
            eventTable.innerHTML = "<div class='empty-state'>Restarted. Collecting new events…</div>";
            renderSparkline();
            setupEventStream();
            startStatsUpdate();
            startChartUpdate();
            startAlertsUpdate();
            updateControlsUI();
            updateStatusDisplay();
            showToast("Monitoring restarted", "info");
        }
    } catch (error) {
        showToast("Error restarting: " + error.message, "error");
    }
}

function closeStreams() {
    if (monitoring.eventSource) {
        monitoring.eventSource.close();
        monitoring.eventSource = null;
    }
    if (monitoring.statsUpdateInterval)  clearInterval(monitoring.statsUpdateInterval);
    if (monitoring.chartUpdateInterval)  clearInterval(monitoring.chartUpdateInterval);
    if (monitoring.alertsUpdateInterval) clearInterval(monitoring.alertsUpdateInterval);
}

// ── SSE Event Stream (B5: ignores heartbeat) ────────────────
function setupEventStream() {
    if (monitoring.eventSource) monitoring.eventSource.close();

    monitoring.eventSource = new EventSource("/api/events");

    monitoring.eventSource.onmessage = function (event) {
        const data = JSON.parse(event.data);

        // B5: ignore heartbeat events
        if (data.type === "heartbeat") return;

        monitoring.events.unshift(data);
        if (monitoring.events.length > 200) monitoring.events.pop();

        // Update live ping/wifi state
        updateLiveState(data);

        // Add to table with filter check
        addEventToTable(data);

        // Connection change toasts + sound (F12, F13)
        if (data.event_type === "connection_change") {
            if (data.success) {
                showToast("✅ Connection restored", "success");
            } else {
                showToast("❌ Connection lost!", "error");
                playAlert();
            }
        }

        updateSparkline(data);
    };

    monitoring.eventSource.onerror = function () {
        console.log("Event stream closed");
        if (monitoring.eventSource) monitoring.eventSource.close();
    };
}

// ── Live State Update (F4, F5) ──────────────────────────────
function updateLiveState(eventData) {
    if (eventData.event_type === "ping") {
        const host = eventData.details.host;
        if (host in monitoring.latestPing) {
            monitoring.latestPing[host] = {
                latency: eventData.details.latency_ms,
                loss: eventData.details.packet_loss,
                success: eventData.success,
            };
            renderPingCard(host);
        }
    }
    if (eventData.event_type === "wifi") {
        monitoring.latestWifi = {
            db: eventData.details.signal_strength_db,
            status: eventData.details.connection_status,
        };
        renderWifiCard();
    }
    if (eventData.event_type === "speedtest" && eventData.success) {
        const dl = eventData.details.download_mbps;
        const ul = eventData.details.upload_mbps;
        if (dl !== null && ul !== null) {
            document.getElementById("speedLatest").textContent =
                `Latest: ↓ ${dl.toFixed(2)} Mbps  ↑ ${ul.toFixed(2)} Mbps`;
        }
    }
}

// ── F4: Dual Ping Cards ──────────────────────────────────────
function renderPingCard(host) {
    const data = monitoring.latestPing[host];
    const idSuffix = host.replace(/\./g, "");
    const card = document.getElementById(`pingCard${idSuffix}`);
    const latEl = document.getElementById(`pingLatency${idSuffix}`);
    const lossEl = document.getElementById(`pingLoss${idSuffix}`);

    if (!card) return;

    card.className = "ping-card " + (data.success ? "online" : "offline");
    latEl.textContent = data.latency !== null ? `${data.latency.toFixed(1)} ms` : "—";
    lossEl.textContent = data.loss !== null ? `loss: ${data.loss.toFixed(1)}%` : "loss: —";
}

// ── F5: WiFi Bar ─────────────────────────────────────────────
function renderWifiCard() {
    const { db, status } = monitoring.latestWifi;
    const valEl = document.getElementById("wifiValue");
    const fillEl = document.getElementById("wifiFill");
    const statusEl = document.getElementById("wifiStatus");

    valEl.textContent = db !== null ? `${db.toFixed(0)} dBm` : "—";
    statusEl.textContent = status;

    // Convert dBm (-30 excellent → -90 terrible) to 0-100%
    let pct = 0;
    if (db !== null) {
        pct = Math.max(0, Math.min(100, (db + 90) / 60 * 100));
    }
    fillEl.style.width = pct + "%";
    fillEl.style.background =
        pct > 60 ? "linear-gradient(90deg, #22c55e, #86efac)" :
        pct > 30 ? "linear-gradient(90deg, #f59e0b, #fcd34d)" :
                   "linear-gradient(90deg, #ef4444, #fca5a5)";
}

// ── Add Event to Table (F8: filter, F9: highlight) ──────────
function addEventToTable(eventData, storeRow = true) {
    // Store raw for re-filtering (skip when rebuilding from existing data)
    if (storeRow) {
        monitoring.allEventRows.unshift(eventData);
        if (monitoring.allEventRows.length > 200) monitoring.allEventRows.pop();
    }

    // Check filter
    if (!passesFilter(eventData)) return;

    const emptyState = eventTable.querySelector(".empty-state");
    if (emptyState) emptyState.remove();

    if (!eventTable.querySelector(".event-table-header")) {
        const header = document.createElement("div");
        header.className = "event-table-header";
        header.innerHTML = `<div>Timestamp</div><div>Type</div><div>Status</div><div>Details</div>`;
        eventTable.appendChild(header);
    }

    const row = document.createElement("div");
    row.className = "event-row new-event";  // F9: highlight
    row.dataset.type   = eventData.event_type;
    row.dataset.status = eventData.success ? "success" : "failed";

    const timeStr = new Date(eventData.timestamp).toLocaleTimeString("pl-PL", {
        hour: "2-digit", minute: "2-digit", second: "2-digit",
    });

    row.innerHTML = `
        <div class="event-timestamp">${timeStr}</div>
        <div><span class="event-type ${eventData.event_type}">${formatEventType(eventData.event_type)}</span></div>
        <div class="event-status ${eventData.success ? "success" : "failed"}">${eventData.success ? "OK" : "FAIL"}</div>
        <div class="event-details">${formatEventDetails(eventData)}</div>
    `;

    const headerEl = eventTable.querySelector(".event-table-header");
    eventTable.insertBefore(row, headerEl ? headerEl.nextSibling : null);

    // Keep table size manageable
    const rows = eventTable.querySelectorAll(".event-row");
    if (rows.length > 150) rows[rows.length - 1].remove();

    // Update summary (F15)
    updateSummary();
}

// ── F8: Filter logic ─────────────────────────────────────────
function passesFilter(eventData) {
    const { type, status } = monitoring.eventFilter;
    if (type   && eventData.event_type !== type) return false;
    if (status === "success" && !eventData.success) return false;
    if (status === "failed"  &&  eventData.success) return false;
    return true;
}

function applyFilter() {
    monitoring.eventFilter.type   = filterType.value;
    monitoring.eventFilter.status = filterStatus.value;

    // Rebuild table WITHOUT re-storing rows (storeRow = false)
    eventTable.innerHTML = "";
    monitoring.allEventRows.forEach(e => addEventToTable(e, false));
    if (!eventTable.querySelector(".event-row")) {
        eventTable.innerHTML = "<div class='empty-state'>No events match the current filter.</div>";
    }
}

function formatEventType(type) {
    return {
        connection_change: "CONN",
        ping: "PING",
        dns: "DNS",
        wifi: "WiFi",
        speedtest: "SPEED",
        packet_loss: "LOSS",
    }[type] || type.toUpperCase();
}

function formatEventDetails(eventData) {
    const d = eventData.details;
    const parts = [];

    switch (eventData.event_type) {
        case "ping":
            if (d.latency_ms != null) parts.push(`${d.host}: ${d.latency_ms.toFixed(1)}ms`);
            if (d.packet_loss != null) parts.push(`loss: ${d.packet_loss.toFixed(1)}%`);
            break;
        case "dns":
            if (d.resolved_ip) parts.push(`${d.hostname} → ${d.resolved_ip}`);
            if (d.latency_ms)  parts.push(`${d.latency_ms.toFixed(1)}ms`);
            break;
        case "wifi":
            parts.push(d.connection_status);
            if (d.signal_strength_db != null) parts.push(`${d.signal_strength_db.toFixed(1)} dBm`);
            break;
        case "speedtest":
            if (d.download_mbps != null) parts.push(`↓ ${d.download_mbps.toFixed(2)} Mbps`);
            if (d.upload_mbps   != null) parts.push(`↑ ${d.upload_mbps.toFixed(2)} Mbps`);
            break;
        case "connection_change":
            parts.push(`${d.prev_state} → ${d.new_state}`);
            break;
        default:
            parts.push(JSON.stringify(d).substring(0, 60));
    }
    return parts.join(" | ") || "—";
}

// ── Sparkline ────────────────────────────────────────────────
function updateSparkline(eventData) {
    if (eventData.event_type === "connection_change") {
        monitoring.sparklineStates.push(eventData.success ? "online" : "offline");
    } else if (eventData.event_type === "ping" && monitoring.sparklineStates.length === 0) {
        monitoring.sparklineStates.push(eventData.success ? "online" : "offline");
    }
    if (monitoring.sparklineStates.length > 60) monitoring.sparklineStates.shift();
    renderSparkline();
}

function renderSparkline() {
    sparklineEl.innerHTML = "";
    if (monitoring.sparklineStates.length === 0) {
        sparklineEl.innerHTML = '<div style="color:#64748b;padding:20px;text-align:center;">No data yet</div>';
        return;
    }
    monitoring.sparklineStates.forEach(state => {
        const bar = document.createElement("div");
        bar.className = `sparkline-bar ${state}`;
        sparklineEl.appendChild(bar);
    });
}

// ── Stats Update ─────────────────────────────────────────────
async function updateStats() {
    try {
        const response = await fetch("/api/stats");
        const stats = await response.json();
        monitoring.statsData = stats;

        document.getElementById("statUptime").textContent =
            stats.uptime_percent.toFixed(1) + "%";
        document.getElementById("statDisconnects").textContent =
            stats.total_disconnects;
        document.getElementById("statLatency").textContent =
            stats.avg_latency_ms != null
                ? stats.avg_latency_ms.toFixed(1) + " ms"
                : "—";

        const m = Math.floor(stats.monitoring_duration_sec / 60);
        const s = stats.monitoring_duration_sec % 60;
        document.getElementById("statDuration").textContent =
            m > 0 ? `${m}m ${s}s` : `${s}s`;

        // F10: Uptime bar
        document.getElementById("uptimeBarFill").style.width =
            stats.uptime_percent.toFixed(1) + "%";

        // F15: summary total count
        document.getElementById("sumTotal").textContent = stats.total_events;
    } catch (error) {
        console.error("Error updating stats:", error);
    }
}

function startStatsUpdate() {
    updateStats();
    monitoring.statsUpdateInterval = setInterval(updateStats, 2000);
}

// ── F1-F3: Chart.js charts ───────────────────────────────────
function initCharts() {
    const chartDefaults = {
        responsive: true,
        maintainAspectRatio: true,
        animation: { duration: 500, easing: "easeOutQuart" },
        interaction: { mode: "index", intersect: false },
        plugins: {
            legend: {
                labels: {
                    color: "#64748b", font: { size: 11, family: "'Inter',sans-serif" },
                    usePointStyle: true, pointStyleWidth: 8, padding: 16,
                }
            },
            tooltip: {
                backgroundColor: "rgba(5,13,27,0.92)",
                titleColor: "#f1f5f9", bodyColor: "#94a3b8",
                borderColor: "rgba(14,165,233,0.35)", borderWidth: 1,
                padding: 10, cornerRadius: 10,
                bodyFont: { family: "'JetBrains Mono',monospace", size: 12 },
            }
        },
        scales: {
            x: {
                ticks: { color: "#334155", maxTicksLimit: 8, font: { size: 10 } },
                grid: { color: "rgba(255,255,255,0.045)", drawBorder: false },
                border: { display: false },
            },
            y: {
                ticks: { color: "#334155", font: { size: 10 } },
                grid: { color: "rgba(255,255,255,0.045)", drawBorder: false },
                border: { display: false },
            },
        },
    };

    // F1: Latency chart — line with gradient fill
    const latencyCtx = document.getElementById("latencyChart").getContext("2d");
    const gradC = latencyCtx.createLinearGradient(0, 0, 0, 280);
    gradC.addColorStop(0, "rgba(14,165,233,0.45)");
    gradC.addColorStop(1, "rgba(14,165,233,0.00)");
    const gradP = latencyCtx.createLinearGradient(0, 0, 0, 280);
    gradP.addColorStop(0, "rgba(168,85,247,0.40)");
    gradP.addColorStop(1, "rgba(168,85,247,0.00)");

    monitoring.charts.latency = new Chart(latencyCtx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                { label: "8.8.8.8", data: [], borderColor: "#0ea5e9", backgroundColor: gradC,
                  tension: 0.4, pointRadius: 3, pointHoverRadius: 6,
                  pointBackgroundColor: "#0ea5e9", pointBorderColor: "rgba(14,165,233,0.25)",
                  pointBorderWidth: 5, fill: true, borderWidth: 2.5 },
                { label: "1.1.1.1", data: [], borderColor: "#a855f7", backgroundColor: gradP,
                  tension: 0.4, pointRadius: 3, pointHoverRadius: 6,
                  pointBackgroundColor: "#a855f7", pointBorderColor: "rgba(168,85,247,0.25)",
                  pointBorderWidth: 5, fill: true, borderWidth: 2.5 },
            ],
        },
        options: { ...chartDefaults,
            scales: { ...chartDefaults.scales,
                y: { ...chartDefaults.scales.y, beginAtZero: true,
                     title: { display: true, text: "ms", color: "#475569", font: { size: 10 } } } } },
    });

    // F2: Packet loss chart — bar with rounded corners
    monitoring.charts.loss = new Chart(
        document.getElementById("lossChart").getContext("2d"), {
        type: "bar",
        data: {
            labels: [],
            datasets: [
                { label: "8.8.8.8 loss", data: [],
                  backgroundColor: "rgba(239,68,68,0.55)", borderColor: "rgba(239,68,68,0.85)",
                  borderWidth: 1, borderRadius: 4, borderSkipped: false },
                { label: "1.1.1.1 loss", data: [],
                  backgroundColor: "rgba(245,158,11,0.50)", borderColor: "rgba(245,158,11,0.85)",
                  borderWidth: 1, borderRadius: 4, borderSkipped: false },
            ],
        },
        options: { ...chartDefaults,
            scales: { ...chartDefaults.scales,
                y: { ...chartDefaults.scales.y, beginAtZero: true, max: 100,
                     title: { display: true, text: "%", color: "#475569", font: { size: 10 } } } } },
    });

    // F3: Speed chart — bar with gradient colors
    const speedCtx = document.getElementById("speedChart").getContext("2d");
    const gradDown = speedCtx.createLinearGradient(0, 0, 0, 220);
    gradDown.addColorStop(0, "rgba(16,185,129,0.90)");
    gradDown.addColorStop(1, "rgba(16,185,129,0.45)");
    const gradUp = speedCtx.createLinearGradient(0, 0, 0, 220);
    gradUp.addColorStop(0, "rgba(14,165,233,0.90)");
    gradUp.addColorStop(1, "rgba(14,165,233,0.45)");

    monitoring.charts.speed = new Chart(speedCtx, {
        type: "bar",
        data: {
            labels: [],
            datasets: [
                { label: "Download (Mbps)", data: [],
                  backgroundColor: gradDown, borderColor: "rgba(16,185,129,0.95)",
                  borderWidth: 1, borderRadius: 6, borderSkipped: false },
                { label: "Upload (Mbps)", data: [],
                  backgroundColor: gradUp, borderColor: "rgba(14,165,233,0.95)",
                  borderWidth: 1, borderRadius: 6, borderSkipped: false },
            ],
        },
        options: { ...chartDefaults,
            scales: { ...chartDefaults.scales,
                y: { ...chartDefaults.scales.y, beginAtZero: true,
                     title: { display: true, text: "Mbps", color: "#475569", font: { size: 10 } } } } },
    });
}

async function updateCharts() {
    try {
        const response = await fetch("/api/chart-data?limit=100");
        const data = await response.json();

        const s1 = data.ping["8.8.8.8"] || [];
        const s2 = data.ping["1.1.1.1"] || [];
        const l1 = data.packet_loss["8.8.8.8"] || [];
        const l2 = data.packet_loss["1.1.1.1"] || [];
        const sp = data.speedtest || [];

        // Use timestamps from 8.8.8.8 as shared x-axis labels for latency + loss
        const pingLabels = s1.map(p =>
            new Date(p.t).toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
        );

        // F1: latency
        monitoring.charts.latency.data.labels    = pingLabels;
        monitoring.charts.latency.data.datasets[0].data = s1.map(p => p.v);
        monitoring.charts.latency.data.datasets[1].data = s2.map(p => p.v);
        monitoring.charts.latency.update("none");

        // F2: packet loss
        monitoring.charts.loss.data.labels    = pingLabels;
        monitoring.charts.loss.data.datasets[0].data = l1.map(p => p.v);
        monitoring.charts.loss.data.datasets[1].data = l2.map(p => p.v);
        monitoring.charts.loss.update("none");

        // F3: speed
        if (sp.length > 0) {
            monitoring.charts.speed.data.labels    =
                sp.map(s => new Date(s.t).toLocaleTimeString("pl-PL",
                    { hour: "2-digit", minute: "2-digit" }));
            monitoring.charts.speed.data.datasets[0].data = sp.map(s => s.download);
            monitoring.charts.speed.data.datasets[1].data = sp.map(s => s.upload);
            monitoring.charts.speed.update("none");
        }

        // F15: type-specific counts from chart data
        document.getElementById("sumPing").textContent  = s1.length;
        document.getElementById("sumSpeed").textContent = sp.length;
    } catch (error) {
        console.error("Error updating charts:", error);
    }
}

function startChartUpdate() {
    updateCharts();
    monitoring.chartUpdateInterval = setInterval(updateCharts, 5000);
}

// ── B7: Alerts ───────────────────────────────────────────────
async function updateAlerts() {
    try {
        const response = await fetch("/api/alerts");
        const data = await response.json();
        const alerts = data.alerts || [];

        const section = document.getElementById("alertsSection");
        const countEl = document.getElementById("alertsCount");
        const listEl  = document.getElementById("alertsList");

        if (alerts.length === 0) {
            section.style.display = "none";
            return;
        }

        section.style.display = "block";
        countEl.textContent = alerts.length;
        monitoring.totalAlertCount = alerts.length;
        document.getElementById("sumAlerts").textContent = alerts.length;

        // Rebuild (simple approach — last 20)
        listEl.innerHTML = "";
        alerts.slice(-20).reverse().forEach(a => {
            const item = document.createElement("div");
            item.className = "alert-item";
            const time = new Date(a.timestamp).toLocaleTimeString("pl-PL");
            item.innerHTML = `
                <span class="alert-type">${a.type.replace("_", " ")}</span>
                <span class="alert-msg">${a.message}</span>
                <span class="alert-time">${time}</span>
            `;
            listEl.appendChild(item);
        });
    } catch (error) {
        console.error("Error updating alerts:", error);
    }
}

function startAlertsUpdate() {
    updateAlerts();
    monitoring.alertsUpdateInterval = setInterval(updateAlerts, 5000);
}

// ── F15: Summary panel ───────────────────────────────────────
function updateSummary() {
    const events = monitoring.allEventRows;
    const dns   = events.filter(e => e.event_type === "dns").length;
    document.getElementById("sumDns").textContent  = dns;
    document.getElementById("sumTotal").textContent = events.length;
}

// ── UI Helpers ───────────────────────────────────────────────
function updateControlsUI() {
    btnStart.disabled   = monitoring.running;
    btnStop.disabled    = !monitoring.running;
    btnRestart.disabled = !monitoring.running;
}

function updateStatusDisplay() {
    if (monitoring.running) {
        statusDot.classList.remove("stopped");
        statusDot.classList.add("running");
        statusText.textContent = "🟢 Monitoring Active";
    } else {
        statusDot.classList.remove("running");
        statusDot.classList.add("stopped");
        statusText.textContent = "🔴 Stopped";
    }
}

// ── Export / Clear ───────────────────────────────────────────
async function exportLogs() {
    try {
        const response = await fetch("/api/export?format=csv");
        if (!response.ok) throw new Error("Export failed");
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `netcheck_${new Date().toISOString().split("T")[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        showToast("CSV exported", "success");
    } catch (error) {
        showToast("Export failed: " + error.message, "error");
    }
}

async function clearLogs() {
    if (!confirm("Clear all logs? This cannot be undone.")) return;
    try {
        const response = await fetch("/api/logs", { method: "DELETE" });
        if (response.ok) {
            monitoring.events = [];
            monitoring.allEventRows = [];
            monitoring.sparklineStates = [];
            eventTable.innerHTML =
                "<div class='empty-state'>Logs cleared. Monitoring continues…</div>";
            renderSparkline();
            showToast("Logs cleared", "info");
            updateSummary();
        }
    } catch (error) {
        showToast("Error clearing logs: " + error.message, "error");
    }
}

// ── Init ─────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", function () {
    startClock();
    initCharts();
    loadConfig();
    updateControlsUI();
    updateStatusDisplay();

    // Check if monitoring was already running
    fetch("/api/status")
        .then(r => r.json())
        .then(data => {
            monitoring.running = data.running;
            updateControlsUI();
            updateStatusDisplay();

            if (monitoring.running) {
                setupEventStream();
                startStatsUpdate();
                startChartUpdate();
                startAlertsUpdate();

                // Load recent history
                return fetch("/api/history?limit=50");
            }
        })
        .then(r => r ? r.json() : null)
        .then(data => {
            if (data && data.events) {
                data.events.forEach(e => {
                    monitoring.allEventRows.push(e);
                    updateLiveState(e);
                    addEventToTable(e, false);  // already stored above, don't double-push
                });
                // Sort allEventRows newest first
                monitoring.allEventRows.reverse();
            }
        })
        .catch(err => console.error("Initialization error:", err));
});
