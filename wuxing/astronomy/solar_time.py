
# wuxing/astronomy/solar_time.py
"""
使用 Skyfield 与 JPL DE421 星历计算真太阳时。

输入：
    aware_datetime: 带时区信息的当地日期时间
    longitude: 经度，东经为正，西经为负
    latitude: 纬度，北纬为正，南纬为负
    ephemeris_path: 本地 de421.bsp 文件路径

输出：
    naive datetime，表示当地真太阳时的钟面日期与时间。

重要：
    1. 输入时间必须包含正确的时区信息。
    2. 星历必须作为本地文件提供，不在排盘时自动下载。
    3. 该模块只负责计算真太阳时，不负责八字时辰换算。
"""

import os
from datetime import datetime, timedelta, timezone


class SolarTimeError(Exception):
    """真太阳时计算错误。"""


def _validate_coordinates(longitude, latitude):
    try:
        longitude = float(longitude)
        latitude = float(latitude)
    except (TypeError, ValueError) as exc:
        raise SolarTimeError("经纬度必须是有效数字。") from exc

    if not -180.0 <= longitude <= 180.0:
        raise SolarTimeError("经度必须在 -180 至 180 之间。")

    if not -90.0 <= latitude <= 90.0:
        raise SolarTimeError("纬度必须在 -90 至 90 之间。")

    if longitude == 0.0 and latitude == 0.0:
        raise SolarTimeError("坐标为 0,0，不能作为有效定位。")

    return longitude, latitude


def _get_ephemeris_path(ephemeris_path=None):
    """定位随应用打包的 DE421 星历文件。"""
    candidates = []

    if ephemeris_path:
        candidates.append(os.path.abspath(ephemeris_path))

    # 项目目录：five/ephemeris/de421.bsp
    project_root = os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )
    candidates.append(
        os.path.join(project_root, "ephemeris", "de421.bsp")
    )

    # 允许通过环境变量指定星历路径。
    env_path = os.environ.get("WUXING_DE421_PATH")
    if env_path:
        candidates.append(os.path.abspath(env_path))

    for path in candidates:
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            return path

    raise SolarTimeError(
        "未找到 DE421 星历文件。"
        "请将 de421.bsp 放入项目的 ephemeris 文件夹，"
        "并确保构建 IPA 时将该文件打包进去。"
    )


def calc_true_solar_time(
    local_datetime,
    longitude,
    latitude,
    ephemeris_path=None,
):
    """
    计算视太阳时。

    local_datetime 必须是带时区信息的 datetime，例如：

        from datetime import datetime
        from zoneinfo import ZoneInfo

        dt = datetime(
            2026, 10, 18, 11, 2, 39,
            tzinfo=ZoneInfo("Asia/Shanghai")
        )

    返回的 datetime 是不带时区的真太阳时钟面时间。
    """
    if not isinstance(local_datetime, datetime):
        raise SolarTimeError("输入时间必须是 datetime 对象。")

    if local_datetime.tzinfo is None:
        raise SolarTimeError(
            "输入时间没有时区信息。"
            "请先确定出生地或手机所在地区的真实时区，"
            "不要默认按北京时间处理。"
        )

    longitude, latitude = _validate_coordinates(
        longitude,
        latitude,
    )

    path = _get_ephemeris_path(ephemeris_path)

    try:
        from skyfield.api import load, wgs84
    except Exception as exc:
        raise SolarTimeError(
            "无法导入 Skyfield。"
            "当前 iOS 构建环境可能尚未包含所需依赖。"
        ) from exc

    try:
        # 将当地时间转换为 UTC，避免重复计算时区偏移。
        utc_datetime = local_datetime.astimezone(timezone.utc)

        ts = load.timescale()
        t = ts.from_datetime(utc_datetime)

        # 只读取本地星历文件，不联网下载。
        eph = load_file(path)

        earth = eph["earth"]
        sun = eph["sun"]

        observer_location = wgs84.latlon(
            latitude_degrees=latitude,
            longitude_degrees=longitude,
        )
        observer = earth + observer_location

        # 太阳视赤经包含 Skyfield 计算的视位置修正。
        apparent_sun = (
            observer.at(t)
            .observe(sun)
            .apparent()
        )
        ra, dec, distance = apparent_sun.radec()

        # 格林尼治视恒星时，单位为小时。
        gast_hours = t.gast

        # 当地视太阳时角，换算成 0 至 24 小时。
        solar_hours = (
            gast_hours
            + longitude / 15.0
            - ra.hours
            + 12.0
        ) % 24.0

        # 转换成当天的时、分、秒。
        total_seconds = int(round(solar_hours * 3600.0))

        # 四舍五入可能得到恰好 86400 秒，需要归一化。
        day_shift, seconds_in_day = divmod(
            total_seconds,
            86400,
        )

        hours, remainder = divmod(seconds_in_day, 3600)
        minutes, seconds = divmod(remainder, 60)

        # 用输入当地日期作为参考，处理真太阳时跨日。
        local_date = local_datetime.date()
        result_date = local_date + timedelta(days=day_shift)

        # 如果太阳时与当地钟表时间跨越午夜，修正日期归属。
        wall_seconds = (
            local_datetime.hour * 3600
            + local_datetime.minute * 60
            + local_datetime.second
        )
        solar_seconds = seconds_in_day

        if wall_seconds - solar_seconds > 12 * 3600:
            result_date = local_date - timedelta(days=1)
        elif solar_seconds - wall_seconds > 12 * 3600:
            result_date = local_date + timedelta(days=1)

        return datetime(
            result_date.year,
            result_date.month,
            result_date.day,
            hours,
            minutes,
            seconds,
        )

    except SolarTimeError:
        raise
    except Exception as exc:
        raise SolarTimeError(
            f"Skyfield 计算真太阳时失败："
            f"{type(exc).__name__}: {exc}"
        ) from exc


def load_file(path):
    """读取本地星历，禁止在计算时自动下载。"""
    from skyfield.api import load_file as skyfield_load_file

    return skyfield_load_file(path)


def format_true_solar_time(value):
    """格式化真太阳时，供界面或日志使用。"""
    if not isinstance(value, datetime):
        raise SolarTimeError("真太阳时结果不是有效的 datetime。")

    return value.strftime("%Y-%m-%d %H:%M:%S")
