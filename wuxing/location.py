
# wuxing/location.py
"""跨平台定位封装，适用于 Kivy / Plyer。"""

from kivy.utils import platform
from kivy.clock import Clock

# 定位失败时使用的兜底坐标：北京
DEFAULT_LATITUDE = 39.90
DEFAULT_LONGITUDE = 116.40


def get_location(callback, timeout=20):
    """
    异步获取位置。

    callback(lat, lon, source, error)
    source 为 gps 或 default。
    """
    if platform not in ("ios", "android"):
        callback(
            DEFAULT_LATITUDE,
            DEFAULT_LONGITUDE,
            "default",
            "当前不是 iOS 或 Android，使用默认经度",
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
            f"无法导入 Plyer GPS：{exc}",
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

            if not (-90 <= lat <= 90):
                raise ValueError("纬度超出范围")

            if not (-180 <= lon <= 180):
                raise ValueError("经度超出范围")

            finish(lat, lon, "gps", None)

        except Exception as exc:
            finish(
                DEFAULT_LATITUDE,
                DEFAULT_LONGITUDE,
                "default",
                f"定位数据无效：{exc}",
            )

    def on_status(status_type, status):
        # Plyer 的状态回调可能报告定位服务状态。
        # 不把状态通知误当成定位成功。
        print(f"GPS status: {status_type}: {status}")

    def on_timeout(_dt):
        finish(
            DEFAULT_LATITUDE,
            DEFAULT_LONGITUDE,
            "default",
            "等待定位超时。请检查系统定位服务和 App 定位权限。",
        )

    try:
        # Plyer GPS 支持 on_location 和 on_status；
        # 不传入不受支持的 on_error 参数。
        gps.configure(
            on_location=on_location,
            on_status=on_status,
        )

        # 启动系统定位服务
        gps.start(minTime=1000, minDistance=1)

        state["timeout_event"] = Clock.schedule_once(
            on_timeout,
            timeout,
        )

    except Exception as exc:
        finish(
            DEFAULT_LATITUDE,
            DEFAULT_LONGITUDE,
            "default",
            f"启动定位失败：{type(exc).__name__}: {exc}",
        )
