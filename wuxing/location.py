# wuxing/location.py
"""iOS 原生定位与城市/地址地理编码。"""

import json
import threading
import urllib.parse
import urllib.request

from kivy.clock import Clock
from kivy.utils import platform

DEFAULT_LATITUDE = None
DEFAULT_LONGITUDE = None

# 保留原生定位对象，避免被 Python 垃圾回收。
_LOCATION_STATE = {
    "manager": None,
    "delegate": None,
    "finished": False,
    "timeout": None,
}


def _valid_coordinates(lat, lon):
    lat = float(lat)
    lon = float(lon)

    if not -90 <= lat <= 90:
        raise ValueError("纬度必须在 -90 至 90 之间")
    if not -180 <= lon <= 180:
        raise ValueError("经度必须在 -180 至 180 之间")

    return lat, lon


def get_location(callback, timeout=25):
    """
    callback(lat, lon, source, error)

    source 为 gps 或 error。
    定位失败时不再自动回退到北京。
    """
    if platform != "ios":
        callback(
            None, None, "error",
            "当前定位实现使用 iOS 原生 Core Location；"
            "当前平台不是 iOS。",
        )
        return

    try:
        from pyobjus import autoclass, protocol

        CLLocationManager = autoclass("CLLocationManager")

        state = _LOCATION_STATE
        state["finished"] = False

        def finish(lat=None, lon=None, source="error", error=None):
            if state["finished"]:
                return

            state["finished"] = True

            event = state.get("timeout")
            if event is not None:
                event.cancel()
                state["timeout"] = None

            try:
                manager = state.get("manager")
                if manager is not None:
                    manager.stopUpdatingLocation()
            except Exception:
                pass

            Clock.schedule_once(
                lambda _dt: callback(lat, lon, source, error),
                0,
            )

        class LocationDelegate:
            @protocol("CLLocationManagerDelegate")
            def locationManager_didUpdateLocations_(
                self, manager, locations
            ):
                try:
                    count = int(locations.count())
                    if count < 1:
                        return

                    location = locations.objectAtIndex_(count - 1)
                    coordinate = location.coordinate

                    lat, lon = _valid_coordinates(
                        coordinate.latitude,
                        coordinate.longitude,
                    )
                    finish(lat, lon, "gps", None)

                except Exception as exc:
                    finish(
                        error=(
                            "读取定位坐标失败："
                            f"{type(exc).__name__}: {exc}"
                        )
                    )

            @protocol("CLLocationManagerDelegate")
            def locationManager_didFailWithError_(
                self, manager, error
            ):
                try:
                    message = str(error)
                except Exception:
                    message = "iOS 未能取得设备位置"

                finish(error=f"iOS 定位失败：{message}")

            @protocol("CLLocationManagerDelegate")
            def locationManager_didChangeAuthorizationStatus_(
                self, manager, status
            ):
                # iOS 状态：
                # 0 未决定，1 受限，2 拒绝，3/4 已授权
                try:
                    status = int(status)
                except Exception:
                    return

                if status == 2:
                    finish(error="定位权限已拒绝，请到 iPhone 设置中允许定位。")
                elif status == 1:
                    finish(error="系统限制了定位权限。")

        delegate = LocationDelegate()
        manager = CLLocationManager.alloc().init()

        state["delegate"] = delegate
        state["manager"] = manager

        manager.setDelegate_(delegate)
        manager.setDesiredAccuracy_(-1.0)

        state["timeout"] = Clock.schedule_once(
            lambda _dt: finish(
                error="定位超时。请检查系统定位服务和本 App 的定位权限。"
            ),
            max(1, timeout),
        )

        manager.requestWhenInUseAuthorization()
        manager.startUpdatingLocation()

    except Exception as exc:
        callback(
            None,
            None,
            "error",
            "启动 iOS 原生定位失败："
            f"{type(exc).__name__}: {exc}",
        )


def resolve_location(query, callback, timeout=12):
    """
    将城市名或地址解析为坐标。

    callback(lat, lon, display_name, error)

    示例输入：
        Los Angeles
        New York, NY, USA
        Taipei
        34.0522, -118.2437

    城市/地址解析使用 OpenStreetMap Nominatim。
    """
    query = str(query or "").strip()

    if not query:
        callback(None, None, "", "请填写城市、地址或纬度,经度。")
        return

    # 允许直接输入“纬度,经度”，无需联网。
    if "," in query:
        parts = [part.strip() for part in query.split(",")]

        if len(parts) == 2:
            try:
                lat, lon = _valid_coordinates(parts[0], parts[1])
                callback(lat, lon, query, None)
                return
            except (TypeError, ValueError):
                pass

    def worker():
        try:
            params = urllib.parse.urlencode({
                "q": query,
                "format": "jsonv2",
                "limit": 1,
            })

            url = (
                "https://nominatim.openstreetmap.org/search?"
                + params
            )

            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "WuxingPaipan/1.0 "
                                  "(location lookup)",
                    "Accept": "application/json",
                },
            )

            with urllib.request.urlopen(
                request,
                timeout=timeout,
            ) as response:
                data = json.loads(
                    response.read().decode("utf-8")
                )

            if not data:
                raise ValueError(
                    "没有找到这个城市或地址，请补充州名、国家名，"
                    "或直接输入纬度,经度。"
                )

            item = data[0]
            lat, lon = _valid_coordinates(
                item["lat"],
                item["lon"],
            )
            name = item.get("display_name", query)

            Clock.schedule_once(
                lambda _dt: callback(lat, lon, name, None),
                0,
            )

        except Exception as exc:
            message = (
                f"{type(exc).__name__}: {exc}"
            )
            Clock.schedule_once(
                lambda _dt: callback(None, None, "", message),
                0,
            )

    threading.Thread(target=worker, daemon=True).start()