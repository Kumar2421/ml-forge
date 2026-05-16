"""system/metrics.py — Live system metrics sampler.

- CPU/RAM via psutil
- GPU/VRAM via NVIDIA NVML (pynvml) when available

Designed to be safe on machines without NVIDIA drivers.
"""

from __future__ import annotations

import time
import psutil # type: ignore
from typing import Optional
import cpuinfo # type: ignore
from observability.logger import get_logger

log = get_logger("system_metrics")

_pynvml = None
try:
    import pynvml # type: ignore
    _pynvml = pynvml
except ImportError:
    log.debug("pynvml_not_found")
except Exception as exc:
    log.debug("pynvml_import_error", error=str(exc))
_nvml_ready = False

# Cache CPU info
_cpu_model: Optional[str] = None

def _get_cpu_model() -> str:
    global _cpu_model
    if _cpu_model is None:
        try:
            # get_cpu_info() is expensive, so we cache it
            info = cpuinfo.get_cpu_info()
            _cpu_model = info.get("brand_raw", "Unknown CPU")
        except Exception:
            _cpu_model = "Unknown CPU"
    return _cpu_model

# Track I/O for rate calculations
_last_io = {
    "ts": time.time(),
    "disk": {},
    "net": {}
}

def _get_io_rates():
    global _last_io
    now = time.time()
    dt = now - _last_io["ts"]
    if dt <= 0:
        return [], []

    # Disk
    disk_rates = []
    try:
        disk_io = psutil.disk_io_counters(perdisk=True)
        for name, counters in disk_io.items():
            last = _last_io["disk"].get(name)
            if last:
                read_rate = (counters.read_bytes - last.read_bytes) / dt
                write_rate = (counters.write_bytes - last.write_bytes) / dt
                disk_rates.append({
                    "device": name,
                    "read_bytes_sec": read_rate,
                    "write_bytes_sec": write_rate
                })
            _last_io["disk"][name] = counters
    except:
        pass

    # Network
    net_rates = []
    try:
        net_io = psutil.net_io_counters(pernic=True)
        for name, counters in net_io.items():
            last = _last_io["net"].get(name)
            if last:
                sent_rate = (counters.bytes_sent - last.bytes_sent) / dt
                recv_rate = (counters.bytes_recv - last.bytes_recv) / dt
                if sent_rate > 0 or recv_rate > 0: # Only active interfaces
                    net_rates.append({
                        "interface": name,
                        "bytes_sent_sec": sent_rate,
                        "bytes_recv_sec": recv_rate
                    })
            _last_io["net"][name] = counters
    except:
        pass

    _last_io["ts"] = now
    return disk_rates, net_rates

def _ensure_nvml() -> bool:
    global _nvml_ready
    if _pynvml is None:
        return False
    if _nvml_ready:
        return True
    try:
        _pynvml.nvmlInit()
        _nvml_ready = True
        return True
    except Exception as exc:
        log.debug("nvml_init_failed", error=str(exc))
        return False


def _gb(n_bytes: int | float | None) -> float:
    if n_bytes is None: return 0.0
    return float(n_bytes) / (1024**3)

def _mb(n_bytes: int | float | None) -> float | None:
    if n_bytes is None:
        return None
    return float(n_bytes) / (1024 * 1024)


def sample_metrics(gpu_index: int = 0):
    """Return a dict matching models.system.SystemMetrics."""
    ts = time.time()

    # Use psutil directly since it's imported at top level
    cpu_pct = float(psutil.cpu_percent(interval=None))
    cpu_model = _get_cpu_model()
    try:
        cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else 0.0
    except:
        cpu_freq = 0.0
        
    cpu_count = psutil.cpu_count()
    vm = psutil.virtual_memory()
    ram_used_mb = _mb(vm.used) or 0.0
    ram_total_mb = _mb(vm.total) or 0.0
    
    # Disk usage
    disks = []
    disk_rates, net_rates = _get_io_rates()
    try:
        for part in psutil.disk_partitions(all=False):
            if 'cdrom' in part.opts or part.fstype == '': continue
            usage = psutil.disk_usage(part.mountpoint)
            rate = next((r for r in disk_rates if part.device.endswith(r["device"])), None)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "total_gb": _gb(usage.total),
                "used_gb": _gb(usage.used),
                "percent": usage.percent,
                "read_bytes_sec": rate["read_bytes_sec"] if rate else 0.0,
                "write_bytes_sec": rate["write_bytes_sec"] if rate else 0.0,
            })
    except: pass
    
    network = net_rates

    gpu: Optional[dict] = None
    if _ensure_nvml():
        try:
            handle = _pynvml.nvmlDeviceGetHandleByIndex(int(gpu_index))
            name = _pynvml.nvmlDeviceGetName(handle)
            util = _pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = _pynvml.nvmlDeviceGetMemoryInfo(handle)
            temp = _pynvml.nvmlDeviceGetTemperature(handle, 0) # 0 = NVML_TEMPERATURE_GPU
            power = _pynvml.nvmlDeviceGetPowerUsage(handle) # mW
            power_limit = _pynvml.nvmlDeviceGetEnforcedPowerLimit(handle) # mW
            clock = _pynvml.nvmlDeviceGetClockInfo(handle, 0) # 0 = NVML_CLOCK_GRAPHICS

            gpu = {
                "index": int(gpu_index),
                "name": name.decode("utf-8", errors="ignore") if isinstance(name, (bytes, bytearray)) else str(name),
                "utilization_pct": float(getattr(util, "gpu", 0.0)),
                "mem_used_mb": _mb(getattr(mem, "used", None)),
                "mem_total_mb": _mb(getattr(mem, "total", None)),
                "temperature_c": float(temp),
                "power_usage_w": float(power) / 1000.0,
                "power_limit_w": float(power_limit) / 1000.0,
                "clock_graphics_mhz": float(clock),
            }
        except Exception as exc:
            log.debug("nvml_sample_failed", error=str(exc))
            gpu = None

    return {
        "ts": ts,
        "cpu_pct": cpu_pct,
        "cpu_model": cpu_model,
        "cpu_freq_mhz": cpu_freq,
        "cpu_count": cpu_count,
        "ram_used_mb": ram_used_mb,
        "ram_total_mb": ram_total_mb,
        "gpu": gpu,
        "disks": disks,
        "network": network,
    }
