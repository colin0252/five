
"""iOS / Android 定位封装，失败时回退到北京。"""

from kivy.clock import Clock
from kivy.utils import platform

# 北京兜底坐标
DEFAULT_LATITUDE = 39.90
DEFAULT_LONGITUDE = 116.40


def get_location(callback, timeout=20):
    """
    callback(lat, lon, source, error)

    source:
        gps     成功获取设备位置
        default 定位失败，使用北京坐标
    """
    if platform not in ("ios", "android"):
        callback(
            DEFAULT_LATITUDE,
            DEFAULT_LONGITUDE,
            "default",
            "当前运行平台不支持移动设备定位，已使用北京坐标。",
        )
        return

    _get_mobile(callback, timeout)


def _get_mobile(callback, timeout):
    try:
        from plyer import gps
    except Exception as exc:
        callback(
            DEFAULT_LATITUDE,
            DEFAULT_LONGITUDE,
            "default",
            f"无法加载定位模块：{type(exc).__name__}: {exc}",
        )
        return

    state = {
        "done": False,
        "timeout_event": None,
    }

    def finish(lat, lon, source, error=None):
        if state["done"]:
            return

        state["done"] = True

        event = state["timeout_event"]
        if event is not None:
            event.cancel()

        try:
            gps.stop()
        except Exception:
            pass

        callback(lat, lon, source, error)

    def on_location(**kwargs):
        try:
            lat = float(kwargs["lat"])
            lon = float(kwargs["lon"])

            if not -90 <= lat <= 90:
                raise ValueError("纬度超出有效范围")

            if not -180 <= lon <= 180:
                raise ValueError("经度超出有效范围")

            finish(lat, lon, "gps", None)

        except Exception as exc:
            finish(
                DEFAULT_LATITUDE,
                DEFAULT_LONGITUDE,
                "default",
                f"定位数据无效：{type(exc).__name__}: {exc}",
            )

    def on_status(status_type, status):
        print(f"[Location] {status_type}: {status}")

    def on_timeout(_dt):
        finish(
            DEFAULT_LATITUDE,
            DEFAULT_LONGITUDE,
            "default",
            "等待定位超过限定时间，请检查定位权限和系统定位服务。",
        )

    try:
        gps.configure(
            on_location=on_location,
            on_status=on_status,
        )

        gps.start(minTime=1000, minDistance=1)

        state["timeout_event"] = Clock.schedule_once(
            on_timeout,
            max(1, timeout),
        )

    except Exception as exc:
        finish(
            DEFAULT_LATITUDE,
            DEFAULT_LONGITUDE,
            "default",
            f"启动定位失败：{type(exc).__name__}: {exc}",
        )
