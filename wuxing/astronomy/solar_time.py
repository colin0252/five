# wuxing/astronomy/solar_time.py
"""
基于 Skyfield + NASA JPL DE421 的视太阳时计算。
要求：
1. 输入必须是带有正确时区信息的当地出生时间。
2. 经度：东经为正，西经为负。
3. 纬度：北纬为正，南纬为负。
4. 使用本地 DE421 文件，不在计算过程中主动联网下载星历。
5. 返回不带时区的 datetime，表示当地视太阳时。
注意：
高精度星历不等于整个程序必然具有小于 1 秒的总误差。
计算结果应通过独立天文算法或可靠历书进行验证。
"""
import os
from datetime import datetime, timedelta, timezone
class SolarTimeError(Exception):
    """真太阳时计算错误。"""
def _validate_coordinates(longitude, latitude):
    """检查经纬度。"""
    try:
        longitude = float(longitude)
        latitude = float(latitude)
    except (TypeError, ValueError) as exc:
        raise SolarTimeError(
            "经度和纬度必须是有效数字。"
        ) from exc
    if not -180.0 <= longitude <= 180.0:
        raise SolarTimeError(
            "经度必须在 -180 至 180 度之间。"
        )
    if not -90.0 <= latitude <= 90.0:
        raise SolarTimeError(
            "纬度必须在 -90 至 90 度之间。"
        )
    return longitude, latitude
def _get_ephemeris_path(ephemeris_path=None):
    """查找本地 DE421 星历文件。"""
    candidates = []
    if ephemeris_path:
        candidates.append(
            os.path.abspath(ephemeris_path)
        )
    # 文件位于 wuxing/astronomy/solar_time.py。
    # 默认星历位置：项目根目录/ephemeris/de421.bsp。
    project_root = os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )
    )
    candidates.append(
        os.path.join(
            project_root,
            "ephemeris",
            "de421.bsp",
        )
    )
    env_path = os.environ.get(
        "WUXING_DE421_PATH"
    )
    if env_path:
        candidates.append(
            os.path.abspath(env_path)
        )
    for path in candidates:
        if (
            os.path.isfile(path)
            and os.path.getsize(path) > 0
        ):
            return path
    raise SolarTimeError(
        "找不到本地 DE421 星历文件。"
        "请确认 de421.bsp 已放入 ephemeris 文件夹，"
        "并且 GitHub Actions 已将其打包进 IPA。"
    )
def calc_true_solar_time(
    local_datetime,
    longitude,
    latitude,
    ephemeris_path=None,
):
    """
    根据出生地位置和当地钟表时间计算视太阳时。
    参数：
        local_datetime:
            带有效时区的 datetime。
            例如使用 ZoneInfo('America/Los_Angeles')
            或 ZoneInfo('Asia/Shanghai') 构造的时间。
        longitude:
            出生地经度，东经为正，西经为负。
        latitude:
            出生地纬度，北纬为正，南纬为负。
        ephemeris_path:
            可选的本地 DE421 文件路径。
    返回：
        不带时区的 datetime，表示当地视太阳时。
    """
    if not isinstance(local_datetime, datetime):
        raise SolarTimeError(
            "输入时间必须是 datetime 对象。"
        )
    if (
        local_datetime.tzinfo is None
        or local_datetime.utcoffset() is None
    ):
        raise SolarTimeError(
            "输入时间必须包含正确的时区信息。"
            "请勿将不同时区的时间一律当作北京时间。"
        )
    longitude, latitude = _validate_coordinates(
        longitude,
        latitude,
    )
    path = _get_ephemeris_path(
        ephemeris_path
    )
    try:
        from skyfield.api import (
            load,
            load_file,
            wgs84,
        )
    except Exception as exc:
        raise SolarTimeError(
            "无法导入 Skyfield。"
            "请检查构建环境是否包含 Skyfield 及其依赖。"
        ) from exc
    try:
        # 1. 转换成 UTC，确保天文计算使用正确的时刻。
        utc_datetime = local_datetime.astimezone(
            timezone.utc
        )
        # 使用内置时间尺度数据，避免主动联网下载时间尺度文件。
        timescale = load.timescale(
            builtin=True
        )
        t = timescale.from_datetime(
            utc_datetime
        )
        # 2. 读取本地 JPL DE421 星历。
        ephemeris = load_file(path)
        earth = ephemeris["earth"]
        sun = ephemeris["sun"]
        # 3. 建立实际观测地点。
        location = wgs84.latlon(
            latitude_degrees=latitude,
            longitude_degrees=longitude,
        )
        observer = earth + location
        # 4. 计算观测者位置看到的太阳视位置。
        apparent_sun = (
            observer.at(t)
            .observe(sun)
            .apparent()
        )
        # 5. 获取日期参考系下的视赤经。
        # t.gast 是格林尼治视恒星时，因此赤经也必须
        # 使用与日期相同的参考系，避免 J2000 与日期坐标混用。
        ra, _dec, _distance = apparent_sun.radec(
            epoch="date"
        )
        # 6. 计算当地视恒星时。
        local_gast_hours = (
            t.gast + longitude / 15.0
        ) % 24.0
        # 7. 太阳时角 = 当地视恒星时 - 太阳视赤经。
        hour_angle_hours = (
            local_gast_hours - ra.hours + 12.0
        ) % 24.0 - 12.0
        # 8. 视太阳时 = 太阳时角 + 12 小时。
        solar_hours = (
            hour_angle_hours + 12.0
        ) % 24.0
        solar_seconds = int(
            round(solar_hours * 3600.0)
        ) % 86400
        # 9. 计算相对于当地钟表时间的修正量。
        wall_datetime = local_datetime.replace(
            tzinfo=None
        )
        wall_seconds = (
            local_datetime.hour * 3600
            + local_datetime.minute * 60
            + local_datetime.second
            + local_datetime.microsecond / 1_000_000
        )
        # 将差值限制在 [-12小时, +12小时)，
        # 正确处理真太阳时跨越午夜的情况。
        delta_seconds = (
            solar_seconds
            - wall_seconds
            + 43200
        ) % 86400 - 43200
        result = wall_datetime + timedelta(
            seconds=delta_seconds
        )
        # 结果保留到秒。
        return result.replace(
            microsecond=0
        )
    except SolarTimeError:
        raise
    except Exception as exc:
        raise SolarTimeError(
            "计算真太阳时失败："
            f"{type(exc).__name__}: {exc}"
        ) from exc
def format_true_solar_time(value):
    """格式化真太阳时为 YYYY-MM-DD HH:MM:SS。"""
    if not isinstance(value, datetime):
        raise SolarTimeError(
            "真太阳时结果不是有效的 datetime。"
        )
    return value.strftime(
        "%Y-%m-%d %H:%M:%S"
    )