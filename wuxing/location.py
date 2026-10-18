
# wuxing/location.py
"""iOS 原生定位与城市/地址地理编码。"""

import json
import re
import threading
import urllib.parse
import urllib.request

from kivy.clock import Clock
from kivy.utils import platform


DEFAULT_LATITUDE = None
DEFAULT_LONGITUDE = None

_LOCATION_STATE = {
    "manager": None,
    "delegate": None,
    "finished": False,
    "timeout": None,
}


def _valid_coordinates(lat, lon):
    """验证并返回有效的纬度、经度。"""
    lat = float(lat)
    lon = float(lon)

    if not (-90 <= lat <= 90):
        raise ValueError("纬度必须在 -90 至 90 之间")

    if not (-180 <= lon <= 180):
        raise ValueError("经度必须在 -180 至 180 之间")

    if lat == 0 and lon == 0:
        raise ValueError("定位返回了无效的坐标")

    return lat, lon


def _extract_coordinates(location):
    """
    从 iOS CLLocation 对象提取坐标。

    优先读取 coordinate 的常规属性；
    如果 Pyobjus 将结构体转换成 UnknownType，
    再尝试读取结构体成员；
    最后尝试从 CLLocation 的描述字符串提取坐标。
    """
    errors = []

    # 方法一：尝试直接读取 latitude / longitude。
    try:
        coordinate = location.coordinate
        lat = coordinate.latitude
        lon = coordinate.longitude
        return _valid_coordinates(lat, lon)
    except Exception as exc:
        errors.append(f"直接读取坐标失败：{exc}")

    # 方法二：Pyobjus 可能把结构体成员命名为 a、b 等。
    try:
        coordinate = location.coordinate
        fields = coordinate.getMembers(only_fields=True)

        if fields and len(fields) >= 2:
            lat = getattr(coordinate, fields[0])
            lon = getattr(coordinate, fields[1])
            return _valid_coordinates(lat, lon)
    except Exception as exc:
        errors.append(f"读取结构体成员失败：{exc}")

    # 方法三：从 CLLocation 描述中的 <纬度,经度> 提取。
    try:
        description = str(location.description)

        match = re.search(
            r"<\s*([+-]?\d+(?:\.\d+)?)\s*,\s*"
            r"([+-]?\d+(?:\.\d+)?)\s*>",
            description,
        )

        if match:
            return _valid_coordinates(
                match.group(1),
                match.group(2),
            )

        errors.append(
            f"定位描述中未找到坐标：{description}"
        )
    except Exception as exc:
        errors.append(f"读取定位描述失败：{exc}")

    raise ValueError("；".join(errors))


def get_location(callback, timeout=25):
    """
    获取 iPhone 当前定位。

    callback(lat, lon, source, error)

    成功：
        callback(纬度, 经度, "gps", None)

    失败：
        callback(None, None, "error", 错误信息)

    不会自动回退到北京或其他默认位置。
    """
    if platform != "ios":
        callback(
            None,
            None,
            "error",
            "当前定位功能需要在 iOS 设备上运行。",
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
                try:
                    event.cancel()
                except Exception:
                    pass
                state["timeout"] = None

            manager_obj = state.get("manager")
            if manager_obj is not None:
                try:
                    manager_obj.stopUpdatingLocation()
                except Exception:
                    pass

            Clock.schedule_once(
                lambda _dt: callback(
                    lat, lon, source, error
                ),
                0,
            )

        class LocationDelegate:
            @protocol("CLLocationManagerDelegate")
            def locationManager_didUpdateLocations_(
                self, manager, locations
            ):
                if state["finished"]:
                    return

                try:
                    count = int(locations.count())

                    if count < 1:
                        return

                    location = locations.objectAtIndex_(count - 1)
                    lat, lon = _extract_coordinates(location)

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
                try:
                    status = int(status)
                except Exception:
                    return

                # kCLAuthorizationStatusRestricted = 1
                # kCLAuthorizationStatusDenied = 2
                if status == 2:
                    finish(
                        error=(
                            "定位权限已拒绝。请在 iPhone 设置中"
                            "允许五行排盘使用定位。"
                        )
                    )
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
                error=(
                    "定位超时。请检查 iPhone 的定位服务、"
                    "App 定位权限和网络环境后重试。"
                )
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
    将城市名、地址或纬度/经度解析成坐标。

    callback(lat, lon, display_name, error)

    示例：
        Los Angeles
        New York, NY, USA
        Taipei
        34.0522, -118.2437
    """
    query = str(query or "").strip()

    if not query:
        callback(
            None,
            None,
            "",
            "请填写城市、地址或纬度,经度。",
        )
        return

    # 支持直接输入纬度,经度，不需要网络查询。
    if "," in query:
        parts = [part.strip() for part in query.split(",")]

        if len(parts) == 2:
            try:
                lat, lon = _valid_coordinates(
                    parts[0], parts[1]
                )
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
                    "User-Agent": "WuxingPaipan/1.0",
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
                    "没有找到该城市或地址。请补充州名、国家名，"
                    "或直接输入纬度,经度。"
                )

            item = data[0]

            lat, lon = _valid_coordinates(
                item["lat"],
                item["lon"],
            )

            name = item.get("display_name", query)

            Clock.schedule_once(
                lambda _dt: callback(
                    lat, lon, name, None
                ),
                0,
            )

        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"

            Clock.schedule_once(
                lambda _dt: callback(
                    None, None, "", message
                ),
                0,
            )

    threading.Thread(
        target=worker,
        daemon=True,
    ).start()
