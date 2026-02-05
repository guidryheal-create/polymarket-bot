"""
Core pipelines module - Pure CAMEL only.
"""
from __future__ import annotations

from .daily_process import DailyProcess
try:
    from .hourly_process import HourlyProcess  # type: ignore
except Exception:  # pragma: no cover
    HourlyProcess = None  # type: ignore
try:
    from .minute_process import MinuteProcess  # type: ignore
except Exception:  # pragma: no cover
    MinuteProcess = None  # type: ignore

__all__ = ["DailyProcess", "HourlyProcess", "MinuteProcess"]
