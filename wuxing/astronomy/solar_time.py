"""
真太阳时计算模块。

使用 Skyfield 和本地 JPL DE421 星历计算视太阳时。
计算过程不主动联网下载数据。

输入时间必须带有正确的时区信息。
经度：东经为正，西经为负。
纬度：北纬为正，南纬为负。

返回不带时区的 datetime，表示当地真太阳时。
"""

import os
from datetime import datetime, timedelta, timezone


class SolarTimeError(Exception):
    """真太阳时计算错误。"""


def _validate_coordinates(longitude, latitude):
    """检查经纬度是否有效。"""
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

    # 当前文件位于 wuxing/astronomy/solar_time.py。
    # 项目根目录下的星历路径为 ephemeris/de421.bsp。
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
        "请先将 de421.bsp 放入项目的 ephemeris 文件夹，"
        "并在构建 IPA 时确保文件被打包。"
    )


def calc_true_solar_time(
    local_datetime,
    longitude,
    latitude,
    ephemeris_path=None,
):
    """
    根据当地钟表时间和经纬度计算视太阳时。

    参数：
        local_datetime:
            带时区信息的 datetime。
        longitude:
            经度，东经为正，西经为负。
        latitude:
            纬度，北纬为正，南纬为负。
        ephemeris_path:
            可选的本地 de421.bsp 文件路径。

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
            "输入时间必须包含有效时区。"
            "不能默认把所有地区都当作北京时间。"
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
            "请检查 iOS 构建环境是否包含 Skyfield 及其依赖。"
        ) from exc

    try:
        # 先把当地时间转换为 UTC。
        utc_datetime = local_datetime.astimezone(
            timezone.utc
        )

        # 使用 Skyfield 内置时间尺度数据，
        # 避免为了获取时间尺度文件而主动联网下载。
        timescale = load.timescale(
            builtin=True
        )

        t = timescale.from_datetime(
            utc_datetime
        )

        # 读取已经存在于本地的 DE421 星历。
        ephemeris = load_file(path)

        earth = ephemeris["earth"]
        sun = ephemeris["sun"]

        # 建立真实观测地点。
        location = wgs84.latlon(
            latitude_degrees=latitude,
            longitude_degrees=longitude,
        )

        observer = earth + location

        # 从当地观测位置计算太阳视位置。
        apparent_sun = (
            observer.at(t)
            .observe(sun)
            .apparent()
        )

        # 直接使用该观测位置的时角，
        # 避免把不同参考位置的赤经和恒星时混合计算。
        hour_angle, _, _ = apparent_sun.hadec()

        # 太阳时角为 0 小时时，对应当地视太阳时约 12:00。
        solar_hours = (
            hour_angle.hours + 12.0
        ) % 24.0

        solar_seconds = int(
            round(solar_hours * 3600.0)
        ) % 86400

        # 输入当地钟表时间，不改变它原本的日期和时区语义。
        wall_datetime = (
            local_datetime.replace(
                tzinfo=None
            )
        )

        wall_seconds = (
            local_datetime.hour * 3600
            + local_datetime.minute * 60
            + local_datetime.second
        )

        # 计算真太阳时与当地钟表时间的差值。
        # 将差值限制在 -12 至 +12 小时，
        # 正确处理午夜前后跨日的情况。
        delta_seconds = (
            solar_seconds
            - wall_seconds
            + 43200
        ) % 86400 - 43200

        result = wall_datetime + timedelta(
            seconds=delta_seconds
        )

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
    """格式化真太阳时。"""
    if not isinstance(value, datetime):
        raise SolarTimeError(
            "真太阳时结果不是有效的 datetime。"
        )

    return value.strftime(
        "%Y-%m-%d %H:%M:%S"
    )