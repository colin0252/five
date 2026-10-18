
"""天文计算模块。"""

from .solar_time import (
    SolarTimeError,
    calc_true_solar_time,
    format_true_solar_time,
)

__all__ = [
    "SolarTimeError",
    "calc_true_solar_time",
    "format_true_solar_time",
]
