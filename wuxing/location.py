
# wuxing/location.py
"""iOS 原生定位、城市/地址解析和时区查询。"""

import json
import re
import threading
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from kivy.clock import Clock
from kivy.utils import platform


DEFAULT_LATITUDE = None
DEFAULT_LONGITUDE = None

# 同一时间只保留一个定位请求，防止重复请求互相覆盖。
_LOCATION_LOCK = threading.RLock()
_LOCATION_REQUEST = {"state": None}
MAX_LOCATION_AGE_SECONDS = 120
MAX_HORIZONTAL_ACCURACY_METERS = 10000


def _valid_coordinates(lat, lon):
    """验证并返回有效的纬度、经度。"""
    lat = float(lat)
    lon = float(lon)

    if not (-90 <= lat <= 90):
        raise ValueError("纬度必须在 -90 至 90 之间")

    if not (-180 <= lon <= 180):
        raise ValueError("经度必须在 -180 至 180 之间")

    if lat == 0 and lon == 0:
        raise ValueError("定位返回了无效坐标")

    return lat, lon


def _schedule_callback(callback, *args):
    """将回调安排在 Kivy 主线程执行。"""
    Clock.schedule_once(
        lambda _dt: callback(*args),
        0,
    )


def _extract_coordinates(location):
    """从 iOS CLLocation 对象读取经纬度。"""
    errors = []

    try:
        coordinate = location.coordinate
        return _valid_coordinates(
            coordinate.latitude,
            coordinate.longitude,
        )
    except Exception as exc:
        errors.append(f"直接读取坐标失败：{exc}")

    try:
        coordinate = location.coordinate
        fields = coordinate.getMembers(only_fields=True)

        if fields and len(fields) >= 2:
            return _valid_coordinates(
                getattr(coordinate, fields[0]),
                getattr(coordinate, fields[1]),
            )
    except Exception as exc:
        errors.append(f"读取坐标结构失败：{exc}")

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

        errors.append("定位描述中未找到坐标")
    except Exception as exc:
        errors.append(f"读取定位描述失败：{exc}")

    raise ValueError("；".join(errors))


def _location_timestamp(location):
    """读取 CLLocation 时间戳，返回 Unix 时间秒数。"""
    try:
        timestamp = location.timestamp
        return float(timestamp.timeIntervalSince1970())
    except Exception:
        return None


def _location_accuracy(location):
    """读取 CLLocation 水平精度，单位为米。"""
    try:
        return float(location.horizontalAccuracy)
    except Exception:
        return None


def get_location(callback, timeout=25):
    """
    获取 iPhone 当前定位。

    成功：
        callback(lat, lon, "gps", None)

    失败：
        callback(None, None, "error", 错误信息)

    注意：
        需要 iOS 原生定位支持和用户授权。
        不会自动使用固定坐标代替实际定位。
    """
    if not callable(callback):
        raise TypeError("callback 必须是可调用对象")

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

        # 如果前一个定位仍在进行，先终止它。
        with _LOCATION_LOCK:
            previous = _LOCATION_REQUEST.get("state")

            if previous is not None:
                previous["finished"] = True

                old_event = previous.get("timeout")
                if old_event is not None:
                    try:
                        old_event.cancel()
                    except Exception:
                        pass

                old_manager = previous.get("manager")
                if old_manager is not None:
                    try:
                        old_manager.stopUpdatingLocation()
                    except Exception:
                        pass

            state = {
                "finished": False,
                "manager": None,
                "delegate": None,
                "timeout": None,
                "callback": callback,
                "lock": threading.RLock(),
            }

            _LOCATION_REQUEST["state"] = state

        def finish(lat=None, lon=None, source="error", error=None):
            """结束当前定位请求，并且只回调一次。"""
            with state["lock"]:
                if state["finished"]:
                    return
                state["finished"] = True

            event = state.get("timeout")
            if event is not None:
                try:
                    event.cancel()
                except Exception:
                    pass

            manager_obj = state.get("manager")
            if manager_obj is not None:
                try:
                    manager_obj.stopUpdatingLocation()
                except Exception:
                    pass

            with _LOCATION_LOCK:
                if _LOCATION_REQUEST.get("state") is state:
                    _LOCATION_REQUEST["state"] = None

            _schedule_callback(
                callback,
                lat,
                lon,
                source,
                error,
            )

        class LocationDelegate:
            @protocol("CLLocationManagerDelegate")
            def locationManager_didUpdateLocations_(
                self,
                manager,
                locations,
            ):
                if state["finished"]:
                    return

                try:
                    count = int(locations.count())

                    if count < 1:
                        return

                    # 只检查本次收到的最新位置。
                    location = locations.objectAtIndex_(count - 1)

                    timestamp = _location_timestamp(location)

                    if timestamp is None:
                        finish(
                            error="无法读取定位时间，已拒绝使用该位置。"
                        )
                        return

                    age = (
                        datetime.now(timezone.utc).timestamp()
                        - timestamp
                    )

                    if age < -30:
                        finish(
                            error="定位时间异常，已拒绝使用该位置。"
                        )
                        return

                    if age > MAX_LOCATION_AGE_SECONDS:
                        # 旧位置不直接使用，继续等待新位置。
                        return

                    accuracy = _location_accuracy(location)

                    if accuracy is not None and accuracy < 0:
                        finish(
                            error="iOS 返回的定位精度无效。"
                        )
                        return

                    if (
                        accuracy is not None
                        and accuracy > MAX_HORIZONTAL_ACCURACY_METERS
                    ):
                        # 精度太差时继续等待更好的位置。
                        return

                    lat, lon = _extract_coordinates(location)

                    finish(
                        lat,
                        lon,
                        "gps",
                        None,
                    )

                except Exception as exc:
                    finish(
                        error=(
                            "读取定位失败："
                            f"{type(exc).__name__}: {exc}"
                        )
                    )

            @protocol("CLLocationManagerDelegate")
            def locationManager_didFailWithError_(
                self,
                manager,
                error,
            ):
                try:
                    message = str(error)
                except Exception:
                    message = "iOS 未能取得设备位置"

                finish(error=f"iOS 定位失败：{message}")

            # 兼容旧版 iOS 的授权状态回调。
            @protocol("CLLocationManagerDelegate")
            def locationManager_didChangeAuthorizationStatus_(
                self,
                manager,
                status,
            ):
                try:
                    status = int(status)
                except Exception:
                    return

                # 0：未决定；1：受限制；2：拒绝；
                # 3：仅使用期间允许；4：始终允许。
                if status == 1:
                    finish(error="系统限制了定位权限。")

                elif status == 2:
                    finish(
                        error=(
                            "定位权限已拒绝。请前往 iPhone 设置，"
                            "允许五行排盘使用定位。"
                        )
                    )

                elif status in (3, 4):
                    try:
                        manager.startUpdatingLocation()
                    except Exception as exc:
                        finish(
                            error=(
                                "启动定位失败："
                                f"{type(exc).__name__}: {exc}"
                            )
                        )

        delegate = LocationDelegate()
        manager = CLLocationManager.alloc().init()

        state["delegate"] = delegate
        state["manager"] = manager

        # 必须先设置 delegate，再请求权限或启动服务。
        manager.setDelegate_(delegate)

        try:
            manager.setDesiredAccuracy_(-1.0)
        except Exception:
            pass

        try:
            manager.setDistanceFilter_(-1.0)
        except Exception:
            pass

        state["timeout"] = Clock.schedule_once(
            lambda _dt: finish(
                error=(
                    "定位超时。请检查 iPhone 定位服务、"
                    "应用定位权限及设备环境后重试。"
                )
            ),
            max(1, float(timeout)),
        )

        try:
            status = int(
                CLLocationManager.authorizationStatus()
            )
        except Exception:
            status = 0

        if status == 1:
            finish(error="系统限制了定位权限。")
            return

        if status == 2:
            finish(
                error=(
                    "定位权限已拒绝。请前往 iPhone 设置，"
                    "允许五行排盘使用定位。"
                )
            )
            return

        if status in (3, 4):
            manager.startUpdatingLocation()
        else:
            # 0：尚未决定。等待授权状态回调后再启动。
            manager.requestWhenInUseAuthorization()

    except Exception as exc:
        with _LOCATION_LOCK:
            state = _LOCATION_REQUEST.get("state")
            if state is not None:
                state["finished"] = True
                _LOCATION_REQUEST["state"] = None

        callback(
            None,
            None,
            "error",
            "启动 iOS 原生定位失败："
            f"{type(exc).__name__}: {exc}",
        )


def resolve_location(query, callback, timeout=12):
    """
    将城市名、地址或纬度,经度解析成坐标。

    callback(lat, lon, display_name, error)
    """
    if not callable(callback):
        raise TypeError("callback 必须是可调用对象")

    query = str(query or "").strip()

    if not query:
        _schedule_callback(
            callback,
            None,
            None,
            "",
            "请填写城市、地址或纬度,经度。",
        )
        return

    # 支持直接输入经纬度，无需网络。
    if "," in query:
        parts = [part.strip() for part in query.split(",")]

        if len(parts) == 2:
            try:
                lat, lon = _valid_coordinates(
                    parts[0],
                    parts[1],
                )

                _schedule_callback(
                    callback,
                    lat,
                    lon,
                    query,
                    None,
                )
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
                timeout=max(1, float(timeout)),
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

            _schedule_callback(
                callback,
                lat,
                lon,
                name,
                None,
            )

        except Exception as exc:
            _schedule_callback(
                callback,
                None,
                None,
                "",
                f"{type(exc).__name__}: {exc}",
            )

    threading.Thread(
        target=worker,
        daemon=True,
    ).start()


def get_timezone(lat, lon, callback, timeout=12):
    """
    根据经纬度查询地点的 IANA 时区名称。

    成功：
        callback("America/Los_Angeles", None)

    失败：
        callback(None, "时区查询失败：...")
    """
    if not callable(callback):
        raise TypeError("callback 必须是可调用对象")

    try:
        lat, lon = _valid_coordinates(lat, lon)

    except (TypeError, ValueError) as exc:
        _schedule_callback(
            callback,
            None,
            f"无效坐标，无法查询时区：{exc}",
        )
        return

    def worker():
        try:
            params = urllib.parse.urlencode({
                "latitude": f"{lat:.7f}",
                "longitude": f"{lon:.7f}",
                "timezone": "auto",
                "forecast_days": 1,
            })

            url = (
                "https://api.open-meteo.com/v1/forecast?"
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
                timeout=max(1, float(timeout)),
            ) as response:
                data = json.loads(
                    response.read().decode("utf-8")
                )

            timezone_name = data.get("timezone")

            if (
                not isinstance(timezone_name, str)
                or "/" not in timezone_name
            ):
                raise ValueError(
                    "服务没有返回有效的 IANA 时区名称。"
                )

            _schedule_callback(
                callback,
                timezone_name,
                None,
            )

        except Exception as exc:
            _schedule_callback(
                callback,
                None,
                (
                    "时区查询失败："
                    f"{type(exc).__name__}: {exc}"
                ),
            )

    threading.Thread(
        target=worker,
        daemon=True,
    ).start()
