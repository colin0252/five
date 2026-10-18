
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
        raise SolarTimeError(
            "纬度必须在 -90 至 90 度之间。"
        )

    if not -180.0 <= longitude <= 180.0:
        raise SolarTimeError(
            "经度必须在 -180 至 180 度之间。"
        )

    return latitude, longitude


def _get_ephemeris_path(ephemeris_path=None):
    """查找本地 DE421 星历文件，不联网下载。"""
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
        os.path.join(
            project_root,
            "ephemeris",
            "de421.bsp",
        )
    )

    checked = set()

    for path in candidates:
        path = os.path.abspath(path)

        if path in checked:
            continue

        checked.add(path)

        if os.path.isfile(path):
            return path

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
    根据出生地当地时间、经纬度和 Skyfield 太阳位置计算真太阳时。

    参数：
        local_datetime:
            出生地当地钟表时间，必须包含有效时区。
        longitude:
            经度，东经为正，西经为负。
        latitude:
            纬度，北纬为正，南纬为负。
        ephemeris_path:
            可选的 DE421 星历文件路径。

    返回：
        不带时区的 datetime，表示真太阳钟表时间。

    注意：
        此函数不会在星历缺失时静默切换为其他算法。
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
        # 使用本地星历文件，不联网下载。
        timescale = load.timescale(builtin=True)
        ephemeris = load_file(path)

        earth = ephemeris["earth"]
        sun = ephemeris["sun"]

        # Skyfield 使用绝对时刻，因此先转换为 UTC。
        utc_datetime = local_datetime.astimezone(timezone.utc)
        sky_time = timescale.from_datetime(utc_datetime)

        # 建立出生地点的观测位置。
        observer = earth + wgs84.latlon(
            latitude_degrees=latitude,
            longitude_degrees=longitude,
        )

        # 计算观测地点看到的太阳视位置。
        apparent_sun = (
            observer
            .at(sky_time)
            .observe(sun)
            .apparent()
        )

        # 获取太阳相对当地子午线的时角。
        # Skyfield 返回的时角范围为 -12 至 +12 小时。
        hour_angle, _, _ = apparent_sun.hadec()

        # 太阳过当地子午线时，真太阳时约为 12:00。
        # 此值允许落在午夜前后，不提前强制取模。
        apparent_solar_minutes = (
            12.0 * 60.0
            + hour_angle.hours * 60.0
        )

        # 当地钟表时间，不含时区信息。
        wall_time = local_datetime.replace(tzinfo=None)

        wall_minutes = (
            wall_time.hour * 60.0
            + wall_time.minute
            + wall_time.second / 60.0
            + wall_time.microsecond / 60000000.0
        )

        # 计算真太阳时相对钟表时间的原始校正量。
        correction_minutes = (
            apparent_solar_minutes - wall_minutes
        )

        # 估算合理的校正范围：
        # 经度每度约对应 4 分钟；
        # 当地时区偏移需要从经度对应的太阳时中扣除。
        utc_offset = local_datetime.utcoffset()

        if utc_offset is None:
            raise SolarTimeError(
                "无法获取出生时间的 UTC 时区偏移。"
            )

        utc_offset_minutes = (
            utc_offset.total_seconds() / 60.0
        )

        expected_correction = (
            longitude * 4.0 - utc_offset_minutes
        )

        # 太阳时角以 24 小时为周期。
        # 选择最接近合理经度/时区校正量的等价结果，
        # 而不是一律把校正值限制在正负 12 小时内。
        correction_minutes += 1440.0 * round(
            (
                expected_correction
                - correction_minutes
            ) / 1440.0
        )

        # 应用校正量，允许真太阳时跨日。
        result = wall_time + timedelta(
            minutes=correction_minutes
        )

        # 保留到秒。
        return result.replace(microsecond=0)

    except SolarTimeError:
        raise

    except Exception as exc:
        raise SolarTimeError(
            "Skyfield 真太阳时计算失败："
            f"{type(exc).__name__}: {exc}"
        ) from exc


def format_true_solar_time(value):
    """格式化真太阳时。"""
    if not isinstance(value, datetime):
        raise TypeError(
            "value 必须是 datetime 对象。"
        )

    return value.strftime("%Y-%m-%d %H:%M:%S")
