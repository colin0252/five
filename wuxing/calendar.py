
# wuxing/calendar.py
"""历法基础计算：儒略日、太阳黄经、节气、干支及真太阳时。"""

import math
from datetime import datetime, timedelta, timezone

from .rules import GAN, ZHI, ganzhi

UTC = timezone.utc


# --------------------------------------------------
# 时间处理
# --------------------------------------------------

def _as_utc(dt):
    """
    转换为带时区的 UTC datetime。

    带时区时间转换为 UTC；
    不带时区时间按 UTC 解释。
    """
    if not isinstance(dt, datetime):
        raise TypeError("时间必须是 datetime 对象。")

    if dt.tzinfo is None or dt.utcoffset() is None:
        return dt.replace(tzinfo=UTC)

    return dt.astimezone(UTC)


def _wall_time(dt):
    """提取当前显示的当地钟表时间，不转换时区。"""
    if not isinstance(dt, datetime):
        raise TypeError("时间必须是 datetime 对象。")

    return dt.replace(tzinfo=None)


def _as_utc_naive(dt):
    """转换为不带时区的 UTC datetime，兼容旧接口。"""
    return _as_utc(dt).replace(tzinfo=None)


def _resolve_timezone(timezone_info):
    """解析 IANA 时区名称或时区对象。"""
    if isinstance(timezone_info, str):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        name = timezone_info.strip()
        if not name:
            raise ValueError("时区名称不能为空。")

        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
            raise ValueError(f"无法识别时区：{name}") from exc

    if timezone_info is None:
        raise ValueError("缺少时区信息。")

    if not hasattr(timezone_info, "utcoffset"):
        raise TypeError("timezone_info 必须是时区名称或时区对象。")

    return timezone_info


# --------------------------------------------------
# 儒略日
# --------------------------------------------------

def julian_day(dt):
    """计算 UTC 时刻对应的儒略日。"""
    dt = _as_utc(dt)

    year = dt.year
    month = dt.month

    day = (
        dt.day
        + dt.hour / 24
        + dt.minute / 1440
        + dt.second / 86400
        + dt.microsecond / 86400000000
    )

    if month <= 2:
        year -= 1
        month += 12

    a = year // 100
    b = 2 - a + a // 4

    return (
        int(365.25 * (year + 4716))
        + int(30.6001 * (month + 1))
        + day
        + b
        - 1524.5
    )


# --------------------------------------------------
# 太阳黄经
# --------------------------------------------------

def solar_longitude(dt):
    """
    近似计算太阳地心视黄经，单位为度。

    带时区输入转换为 UTC；
    不带时区输入按 UTC 解释。
    """
    jd = julian_day(dt)
    t = (jd - 2451545.0) / 36525.0

    mean_longitude = (
        280.46646
        + 36000.76983 * t
        + 0.0003032 * t * t
    ) % 360.0

    mean_anomaly = math.radians(
        (
            357.52911
            + 35999.05029 * t
            - 0.0001537 * t * t
        ) % 360.0
    )

    equation_center = (
        (1.914602 - 0.004817 * t - 0.000014 * t * t)
        * math.sin(mean_anomaly)
        + (0.019993 - 0.000101 * t)
        * math.sin(2 * mean_anomaly)
        + 0.000289 * math.sin(3 * mean_anomaly)
    )

    return (mean_longitude + equation_center) % 360.0


def _angle_difference(angle, target):
    """返回角度与目标角度之间的有符号最短差值。"""
    return (angle - target + 180.0) % 360.0 - 180.0


# --------------------------------------------------
# 搜索太阳黄经交点
# --------------------------------------------------

def find_longitude_time(
    local_dt,
    target,
    direction=1,
    max_days=370,
):
    """
    搜索太阳黄经经过指定角度的时刻。

    direction=1：向未来搜索。
    direction=-1：向过去搜索。

    返回 UTC datetime；未找到时返回 None。
    不带时区的输入按 UTC 解释。
    """
    if not isinstance(local_dt, datetime):
        raise TypeError("local_dt 必须是 datetime 对象。")

    try:
        target = float(target)
    except (TypeError, ValueError) as exc:
        raise ValueError("target 必须是有效角度。") from exc

    if not math.isfinite(target):
        raise ValueError("target 必须是有限角度。")

    target %= 360.0

    if direction not in (-1, 1):
        raise ValueError("direction 必须为 1 或 -1。")

    try:
        max_days = float(max_days)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_days 必须是正数。") from exc

    if not math.isfinite(max_days) or max_days <= 0:
        raise ValueError("max_days 必须是有限正数。")

    start = _as_utc(local_dt)
    step = timedelta(hours=6)
    max_steps = math.ceil(max_days * 4)

    current_time = start
    previous = _angle_difference(
        solar_longitude(current_time),
        target,
    )

    # 起点恰好位于目标角度时，直接返回起点。
    if abs(previous) < 1e-10:
        return current_time

    for _ in range(max_steps):
        next_time = current_time + direction * step

        current = _angle_difference(
            solar_longitude(next_time),
            target,
        )

        crossed = (
            abs(current) < 1e-10
            or (
                previous * current < 0
                and abs(current - previous) < 5.0
            )
        )

        if crossed:
            lo = min(current_time, next_time)
            hi = max(current_time, next_time)

            left_value = _angle_difference(
                solar_longitude(lo),
                target,
            )

            right_value = _angle_difference(
                solar_longitude(hi),
                target,
            )

            if abs(left_value) < 1e-10:
                return lo

            if abs(right_value) < 1e-10:
                return hi

            # 二分法细化交点。
            for _ in range(50):
                mid = lo + (hi - lo) / 2

                mid_value = _angle_difference(
                    solar_longitude(mid),
                    target,
                )

                if abs(mid_value) < 1e-10:
                    return mid

                if left_value * mid_value <= 0:
                    hi = mid
                    right_value = mid_value
                else:
                    lo = mid
                    left_value = mid_value

            return lo + (hi - lo) / 2

        current_time = next_time
        previous = current

    return None


# --------------------------------------------------
# 二十四节气
# --------------------------------------------------

def term_events(year):
    """
    获取指定 UTC 公历年份内的二十四节气黄经交点。

    返回：
        [(太阳黄经角度, UTC datetime), ...]
    """
    if not isinstance(year, int) or isinstance(year, bool):
        raise TypeError("year 必须是整数年份。")

    if not 1 <= year < 9999:
        raise ValueError("year 超出支持范围。")

    start = datetime(year, 1, 1, tzinfo=UTC)
    end = datetime(year + 1, 1, 1, tzinfo=UTC)

    events = []

    for k in range(24):
        target = (k * 15) % 360

        event = find_longitude_time(
            start,
            target,
            direction=1,
            max_days=370,
        )

        if event is not None and start <= event < end:
            events.append((target, event))

    events.sort(key=lambda item: item[1])
    return events


def recent_terms(dt, count=12):
    """返回 dt 之前最近的 count 个节气事件。"""
    if not isinstance(count, int) or isinstance(count, bool):
        raise TypeError("count 必须是整数。")

    if count <= 0:
        return []

    target_time = _as_utc(dt)
    events = []

    for year in (
        target_time.year - 1,
        target_time.year,
        target_time.year + 1,
    ):
        if 1 <= year < 9999:
            events.extend(term_events(year))

    events.sort(key=lambda item: item[1])

    previous = [
        item for item in events
        if item[1] <= target_time
    ]

    return previous[-count:]


# --------------------------------------------------
# 日柱与时支
# --------------------------------------------------

def adjusted_date_for_day_pillar(dt):
    """按子初换日口径处理日柱日期。"""
    wall = _wall_time(dt)

    if wall.hour >= 23:
        return wall.date() + timedelta(days=1)

    return wall.date()


def day_ganzhi(dt):
    """
    计算日干支。

    以 2000-01-07 为甲子日基准。
    使用传入时间显示的当地日期，不先转换为 UTC 日期。
    """
    adjusted_date = adjusted_date_for_day_pillar(dt)
    base_date = datetime(2000, 1, 7).date()
    delta = (adjusted_date - base_date).days

    return ganzhi(delta % 60)


def branch_for_hour(hour, minute=0):
    """根据时、分计算时支。"""
    hour = int(hour)
    minute = int(minute)

    if not 0 <= hour <= 23:
        raise ValueError("小时必须在 0 至 23 之间。")

    if not 0 <= minute <= 59:
        raise ValueError("分钟必须在 0 至 59 之间。")

    total = hour * 60 + minute

    if total >= 23 * 60 or total < 60:
        return "子"

    index = ((total - 60) // 120) + 1
    return ZHI[index % 12]


# --------------------------------------------------
# 均时差与真太阳时备用算法
# --------------------------------------------------

def equation_of_time_minutes(dt):
    """使用常见近似公式计算均时差，单位为分钟。"""
    dt = _as_utc(dt)

    day_of_year = dt.timetuple().tm_yday
    year_length = 366 if _is_leap_year(dt.year) else 365

    hour = (
        dt.hour
        + dt.minute / 60
        + dt.second / 3600
    )

    gamma = (
        2 * math.pi / year_length
        * (day_of_year - 1 + (hour - 12) / 24)
    )

    return 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )


def _is_leap_year(year):
    """判断公历闰年。"""
    return year % 4 == 0 and (
        year % 100 != 0 or year % 400 == 0
    )


def true_solar_time(local_dt, longitude, timezone_info=None):
    """
    备用真太阳时近似计算。

    经度东正西负。
    正式排盘优先使用 astronomy.solar_time 中的星历算法。
    """
    if not isinstance(local_dt, datetime):
        raise TypeError("local_dt 必须是 datetime 对象。")

    try:
        longitude = float(longitude)
    except (TypeError, ValueError) as exc:
        raise ValueError("经度必须是有效数字。") from exc

    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("经度必须是 -180 至 180 度之间的有效数字。")

    if local_dt.tzinfo is None or local_dt.utcoffset() is None:
        if timezone_info is None:
            raise ValueError(
                "计算真太阳时需要出生地时区，不能使用设备时区代替。"
            )

        timezone_obj = _resolve_timezone(timezone_info)
        aware_dt = local_dt.replace(tzinfo=timezone_obj)
    else:
        aware_dt = local_dt

    offset = aware_dt.utcoffset()

    if offset is None:
        raise ValueError("无法确定当地时间的 UTC 偏移。")

    timezone_hours = offset.total_seconds() / 3600.0

    correction_minutes = (
        equation_of_time_minutes(aware_dt)
        + 4 * longitude
        - 60 * timezone_hours
    )

    wall_time = aware_dt.replace(tzinfo=None)

    return wall_time + timedelta(minutes=correction_minutes)


# --------------------------------------------------
# 年柱与月柱
# --------------------------------------------------

def year_ganzhi_and_start(dt, timezone_info=None):
    """
    以立春（太阳黄经 315 度）作为干支年分界。

    关键约定：
    - 出生地当地年份用于确定要搜索哪一年的立春；
    - UTC 绝对时刻用于比较出生时刻和立春时刻；
    - 返回的立春时刻为 UTC datetime。

    返回：
        (年干支, 该当地年份的立春时刻)
    """
    if not isinstance(dt, datetime):
        raise TypeError("dt 必须是 datetime 对象。")

    if dt.tzinfo is None or dt.utcoffset() is None:
        if timezone_info is not None:
            timezone_obj = _resolve_timezone(timezone_info)
            aware_dt = dt.replace(tzinfo=timezone_obj)
        else:
            # 兼容旧接口：无时区且未指定时区时按 UTC 解释。
            aware_dt = dt.replace(tzinfo=UTC)
    else:
        aware_dt = dt

    # 不能用 UTC 年份替代当地出生年份。
    # 例如当地时间与 UTC 跨年时，仍需查当地年份的立春。
    local_year = aware_dt.year
    instant = _as_utc(aware_dt)

    year_start = datetime(
        local_year,
        1,
        1,
        tzinfo=UTC,
    )

    li_chun = find_longitude_time(
        year_start,
        315.0,
        direction=1,
        max_days=370,
    )

    if li_chun is None:
        raise ValueError(
            f"无法计算 {local_year} 年的立春时刻。"
        )

    ganzhi_year = (
        local_year - 1
        if instant < li_chun
        else local_year
    )

    return ganzhi((ganzhi_year - 4) % 60), li_chun


def month_info(dt, year_gan, timezone_info=None):
    """
    根据太阳黄经计算节气月支与月干。

    315° 为寅月起点，此后每 30° 切换一月。

    返回：
        (月干, 月支, 太阳黄经)
    """
    if not isinstance(dt, datetime):
        raise TypeError("dt 必须是 datetime 对象。")

    if year_gan not in GAN:
        raise ValueError(f"无效的年干：{year_gan!r}")

    if dt.tzinfo is None or dt.utcoffset() is None:
        if timezone_info is not None:
            timezone_obj = _resolve_timezone(timezone_info)
            calculation_time = dt.replace(tzinfo=timezone_obj)
        else:
            # 兼容旧接口：未指定时区时按 UTC 解释。
            calculation_time = dt.replace(tzinfo=UTC)
    else:
        calculation_time = dt

    longitude = solar_longitude(calculation_time)

    adjusted_longitude = longitude

    if adjusted_longitude < 315.0:
        adjusted_longitude += 360.0

    index = int(
        math.floor((adjusted_longitude - 315.0) / 30.0)
    ) % 12

    branch = ZHI[(2 + index) % 12]

    from .rules import month_gan

    return (
        month_gan(year_gan, branch),
        branch,
        longitude,
    )
