from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class PingResult(BaseModel):
    host: str
    latency_ms: Optional[float]
    timestamp: datetime
    success: bool


class SpeedTestResult(BaseModel):
    download_mbps: Optional[float]
    upload_mbps: Optional[float]
    timestamp: datetime
    success: bool


class DNSResult(BaseModel):
    hostname: str
    resolved_ip: Optional[str]
    latency_ms: Optional[float]
    timestamp: datetime
    success: bool


class WiFiSignal(BaseModel):
    signal_strength_db: Optional[float]
    connection_status: str  # "connected", "disconnected", "N/A"
    timestamp: datetime


class MonitoringEvent(BaseModel):
    event_type: (
        str  # "ping", "speedtest", "dns", "wifi", "packet_loss", "connection_change"
    )
    success: bool
    details: dict
    timestamp: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class MonitoringStatus(BaseModel):
    running: bool
    uptime_sec: int
    events_count: int
    last_check: Optional[datetime] = None


class AggregatedStats(BaseModel):
    uptime_percent: float
    total_disconnects: int
    avg_latency_ms: Optional[float]
    total_events: int
    monitoring_duration_sec: int
