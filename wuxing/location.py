# wuxing/location.py
"""
跨平台定位封装。
iOS/Android 用 plyer.gps；桌面用默认值。
"""
from kivy.utils import platform
from kivy.clock import Clock

# 兜底经度：北京
DEFAULT_LATITUDE = 39.90
DEFAULT_LONGITUDE = 116.40


def get_location(callback, timeout=10):
    """
    异步获取经纬度。
    callback(lat, lon, source, error)
      source: "gps" | "default"
      error: None 或 错误字符串
    """
    if platform in ("ios", "android"):
        _get_mobile(callback, timeout)
    else:
        callback(DEFAULT_LATITUDE, DEFAULT_LONGITUDE, "default", "桌面环境，使用默认经度")


def _get_mobile(callback, timeout):
    try:
        from plyer import gps
    except Exception as e:
        callback(DEFAULT_LATITUDE, DEFAULT_LONGITUDE, "default", f"plyer 不可用: {e}")
        return

    state = {"done": False}

    def finish(lat, lon, source, error):
        if state["done"]:
            return
        state["done"] = True
        callback(lat, lon, source, error)
        try:
            gps.stop()
        except Exception:
            pass

    def on_loc(**kwargs):
        lat = kwargs.get("lat")
        lon = kwargs.get("lon")
        if lat is None or lon is None:
            finish(DEFAULT_LATITUDE, DEFAULT_LONGITUDE, "default", "定位返回空值")
        else:
            finish(lat, lon, "gps", None)

    def on_err(*args):
        finish(DEFAULT_LATITUDE, DEFAULT_LONGITUDE, "default", f"定位失败: {args}")

    def on_timeout(*_):
        finish(DEFAULT_LATITUDE, DEFAULT_LONGITUDE, "default", "定位超时")

    try:
        gps.configure(on_location=on_loc, on_error=on_err)
        gps.start(minTime=1000, minDistance=1)
        Clock.schedule_once(on_timeout, timeout)
    except Exception as e:
        finish(DEFAULT_LATITUDE, DEFAULT_LONGITUDE, "default", f"启动定位失败: {e}")