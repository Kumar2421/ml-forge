"""models/system.py — Pydantic models for real-time system metrics."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class GpuMetrics(BaseModel):
    index: int
    name: str | None = None
    utilization_pct: float | None = None
    mem_used_mb: float | None = None
    mem_total_mb: float | None = None
    temperature_c: float | None = None
    power_usage_w: float | None = None
    power_limit_w: float | None = None
    clock_graphics_mhz: float | None = None

class DiskMetrics(BaseModel):
    device: str
    mountpoint: str
    total_gb: float
    used_gb: float
    percent: float
    read_bytes_sec: float
    write_bytes_sec: float

class NetworkMetrics(BaseModel):
    interface: str
    bytes_sent_sec: float
    bytes_recv_sec: float

class SystemMetrics(BaseModel):
    ts: float

    cpu_pct: float
    cpu_model: str | None = None
    cpu_freq_mhz: float | None = None
    cpu_count: int | None = None
    ram_used_mb: float
    ram_total_mb: float

    gpu: Optional[GpuMetrics] = None
    disks: list[DiskMetrics] = []
    network: list[NetworkMetrics] = []
