# wuxing/astronomy/solar_time.py
"""使用 Skyfield 和 DE421 星历计算真太阳时。"""
import os
from datetime import datetime, timedelta, timezone
class SolarTimeError(Exception):
    """真太阳时计算异常。"""
def _validate_coordinates(latitude, longitude):
    """检查经纬度范围。"""
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError) as exc:
        raise SolarTimeError(
            "纬度和经度必须是有效数字。"
        ) from exc
    if not -90.0 <= latitude <= 90.0:
        raise SolarTimeError("纬度必须在 -90 至 90 度之间。")
    if not -180.0 <= longitude <= 180.0:
        raise SolarTimeError("经度必须在 -180 至 180 度之间。")
    return latitude, longitude
def _get_ephemeris_path(ephemeris_path=None):
    """查找本地 DE421 星历文件。"""
    candidates = []
    if ephemeris_path:
        candidates.append(os.fspath(ephemeris_path))
    env_path = os.environ.get("WUXING_DE421_PATH")
    if env_path:
        candidates.append(env_path)
    project_root = os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )
    candidates.append(
        os.path.join(project_root, "ephemeris", "de421.bsp")
    )
    for path in candidates:
        if os.path.isfile(path):
            return os.path.abspath(path)
    raise SolarTimeError(
        "找不到 DE421 星历文件。"
        "请确认 ephemeris/de421.bsp 已包含在应用中，"
        "或设置 WUXING_DE421_PATH。"
    )
def calc_true_solar_time(
    local_datetime,
    longitude,
    latitude,
    ephemeris_path=None,
):
    """
    计算出生地的真太阳时。
    参数：
        local_datetime:
            出生地当地时间，必须是带有效时区的 datetime。
        longitude:
            出生地经度，东经为正，西经为负。
        latitude:
            出生地纬度，北纬为正，南纬为负。
        ephemeris_path:
            可选的 DE421 星历文件路径。
    返回：
        不带时区的 datetime，表示真太阳钟表时间。
    说明：
        该函数以当地民用时间为输入，结合出生地时区、
        经纬度和太阳视位置计算真太阳时。
        计算失败时抛出 SolarTimeError，不静默返回近似结果。
    """
    if not isinstance(local_datetime, datetime):
        raise SolarTimeError(
            "local_datetime 必须是 datetime 对象。"
        )
    if (
        local_datetime.tzinfo is None
        or local_datetime.utcoffset() is None
    ):
        raise SolarTimeError(
            "出生时间必须包含出生地时区信息。"
        )
    latitude, longitude = _validate_coordinates(
        latitude,
        longitude,
    )
    try:
        from skyfield.api import load, load_file, wgs84
    except ImportError as exc:
        raise SolarTimeError(
            "未安装 Skyfield，无法计算真太阳时。"
        ) from exc
    path = _get_ephemeris_path(ephemeris_path)
    try:
        # 不联网下载星历，使用应用内已存在的 DE421 文件。
        ts = load.timescale(builtin=True)
        eph = load_file(path)
        earth = eph["earth"]
        sun = eph["sun"]
        # 转换为绝对时刻，再计算天文位置。
        utc_datetime = local_datetime.astimezone(timezone.utc)
        t = ts.from_datetime(utc_datetime)
        observer = (
            earth
            + wgs84.latlon(
                latitude_degrees=latitude,
                longitude_degrees=longitude,
            )
        )
        apparent = observer.at(t).observe(sun).apparent()
        ra, dec, distance = apparent.radec(epoch="date")
        # 格林尼治视恒星时与当地经度共同给出当地恒星时。
        gast_hours = t.gast
        local_sidereal_hours = (
            gast_hours + longitude / 15.0
        ) % 24.0
        # 太阳赤经转为小时角。
        ra_hours = ra.hours
        hour_angle_hours = (
            local_sidereal_hours - ra_hours + 12.0
        ) % 24.0 - 12.0
        # 将太阳小时角转成真太阳钟表时间。
        solar_hours = (ra_hours + hour_angle_hours) % 24.0
        # 太阳赤经与小时角相加会受角度环绕影响；
        # 这里用当地钟表时间加校正量，保持日期连续。
        wall_time = local_datetime.replace(tzinfo=None)
        # 民用时间对应的 UTC 偏移。
        offset = local_datetime.utcoffset()
        if offset is None:
            raise SolarTimeError(
                "无法确定出生地的 UTC 时差。"
            )
        timezone_hours = offset.total_seconds() / 3600.0
        # 以当地视太阳时与当地民用时间的差值为基础。
        # 恒星时计算给出太阳时角，需换算成太阳时分钟。
        hour_angle_minutes = hour_angle_hours * 60.0
        # 太阳时角的近似当地真太阳时：
        # 12:00 + 太阳时角。与民用时间相减后归一到 ±12 小时。
        apparent_solar_minutes = (
            12.0 * 60.0 + hour_angle_minutes
        )
        wall_minutes = (
            wall_time.hour * 60.0
            + wall_time.minute
            + wall_time.second / 60.0
            + wall_time.microsecond / 60000000.0
        )
        correction = (
            apparent_solar_minutes - wall_minutes
        )
        # 选取最接近 0 的等价日内校正值。
        while correction > 720.0:
            correction -= 1440.0
        while correction < -720.0:
            correction += 1440.0
        # 地方时区与经度之间的差异已由观测者的当地恒星时体现。
        # 输出当地钟表时间格式，不附带时区。
        result = wall_time + timedelta(minutes=correction)
        return result.replace(microsecond=0)
    except SolarTimeError:
        raise
    except Exception as exc:
        raise SolarTimeError(
            f"Skyfield 真太阳时计算失败："
            f"{type(exc).__name__}: {exc}"
        ) from exc
def format_true_solar_time(value):
    """格式化真太阳时。"""
    if not isinstance(value, datetime):
        raise TypeError("value 必须是 datetime 对象。")
    return value.strftime("%Y-%m-%d %H:%M:%S")