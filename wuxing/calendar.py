# wuxing/calendar.py
"""历法基础计算：儒略日、太阳黄经、节气、干支及真太阳时。"""
from datetime import datetime, timedelta, timezone
import math
from .rules import GAN, ZHI, ganzhi
UTC = timezone.utc
# --------------------------------------------------
# 时间处理
# --------------------------------------------------
def _as_utc(dt):
    """
    转换为带时区的 UTC datetime。
    约定：
    - 带时区 datetime：转换为 UTC。
    - 不带时区 datetime：视为 UTC 时间。
    
    注意：当地出生时间必须先结合出生地时区，
    再传给需要绝对时刻的天文计算函数。
    """
    if not isinstance(dt, datetime):
        raise TypeError("时间必须是 datetime 对象。")
    if dt.tzinfo is None or dt.utcoffset() is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
def _wall_time(dt):
    """提取 datetime 当前显示的钟表时间，不转换时区。"""
    if not isinstance(dt, datetime):
        raise TypeError("时间必须是 datetime 对象。")
    return dt.replace(tzinfo=None)
def _as_utc_naive(dt):
    """将时间转换为不带时区的 UTC datetime，供旧接口兼容。"""
    return _as_utc(dt).replace(tzinfo=None)
# --------------------------------------------------
# 儒略日
# --------------------------------------------------
def julian_day(dt):
    """计算 UTC 时刻对应的儒略日。"""
    dt = _as_utc(dt)
    y = dt.year
    m = dt.month
    d = (
        dt.day
        + dt.hour / 24
        + dt.minute / 1440
        + dt.second / 86400
        + dt.microsecond / 86400000000
    )
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return (
        int(365.25 * (y + 4716))
        + int(30.6001 * (m + 1))
        + d
        + b
        - 1524.5
    )
# --------------------------------------------------
# 太阳黄经
# --------------------------------------------------
def solar_longitude(dt):
    """
    近似计算太阳地心视黄经，单位为度。
    输入可以是带时区或不带时区的 datetime。
    带时区时间会先转换为 UTC。
    不带时区时间按 UTC 解释。
    """
    jd = julian_day(dt)
    t = (jd - 2451545.0) / 36525.0
    l0 = (
        280.46646
        + 36000.76983 * t
        + 0.0003032 * t * t
    ) % 360
    m = math.radians(
        (
            357.52911
            + 35999.05029 * t
            - 0.0001537 * t * t
        ) % 360
    )
    c = (
        (1.914602 - 0.004817 * t - 0.000014 * t * t)
        * math.sin(m)
        + (0.019993 - 0.000101 * t)
        * math.sin(2 * m)
        + 0.000289 * math.sin(3 * m)
    )
    return (l0 + c) % 360
def _angle_difference(angle, target):
    """返回角度与目标角度之间的有符号最短差值。"""
    return (angle - target + 180) % 360 - 180
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
    参数：
        local_dt:
            搜索起点。建议传入带时区 datetime；
            不带时区的输入按 UTC 解释。
        target:
            目标太阳黄经，单位为度。
        direction:
            1 向未来搜索，-1 向过去搜索。
        max_days:
            最大搜索天数。
    返回：
        找到时返回 datetime，未找到时返回 None。
    返回时间使用 UTC 时区。
    """
    if not isinstance(local_dt, datetime):
        raise TypeError("local_dt 必须是 datetime 对象。")
    try:
        target = float(target) % 360
    except (TypeError, ValueError) as exc:
        raise ValueError("target 必须是有效角度。") from exc
    if direction not in (-1, 1):
        raise ValueError("direction 必须为 1 或 -1。")
    if max_days <= 0:
        raise ValueError("max_days 必须大于 0。")
    start = _as_utc(local_dt)
    step = timedelta(hours=6)
    max_steps = int(max_days * 4) + 1
    t = start
    previous = _angle_difference(
        solar_longitude(t),
        target,
    )
    for _ in range(max_steps):
        next_t = t + direction * step
        current = _angle_difference(
            solar_longitude(next_t),
            target,
        )
        crossed = (
            previous == 0
            or current == 0
            or (
                previous * current < 0
                and abs(current - previous) < 5
            )
        )
        if crossed:
            lo = min(t, next_t)
            hi = max(t, next_t)
            left_value = _angle_difference(
                solar_longitude(lo),
                target,
            )
            for _ in range(48):
                mid = lo + (hi - lo) / 2
                mid_value = _angle_difference(
                    solar_longitude(mid),
                    target,
                )
                if left_value == 0:
                    hi = lo
                    break
                if left_value * mid_value <= 0:
                    hi = mid
                else:
                    lo = mid
                    left_value = mid_value
            return lo + (hi - lo) / 2
        t = next_t
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
    这里返回的是 UTC 绝对时刻，不是出生地当地钟表时间。
    """
    start = datetime(year, 1, 1, tzinfo=UTC)
    end = datetime(year + 1, 1, 1, tzinfo=UTC)
    out = []
    for k in range(24):
        target = (k * 15) % 360
        event = find_longitude_time(
            start,
            target,
            direction=1,
            max_days=370,
        )
        if event is not None and start <= event < end:
            out.append((target, event))
    out.sort(key=lambda item: item[1])
    return out
def recent_terms(dt, count=12):
    """
    返回 dt 之前最近的 count 个节气事件。
    dt 可以带时区或不带时区。
    比较前统一转换成 UTC。
    """
    if count <= 0:
        return []
    target_time = _as_utc(dt)
    events = []
    for year in (
        target_time.year - 1,
        target_time.year,
        target_time.year + 1,
    ):
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
    计算日干支，采用 2000-01-07 为甲子日的基准。
    日柱以出生地当地钟表日期为依据，
    因此传入带时区时间时，不先转换成 UTC 日期。
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
    """
    使用常见近似公式计算均时差，单位为分钟。
    这是备用近似算法，不替代 Skyfield 星历算法。
    """
    dt = _as_utc(dt)
    day_of_year = dt.timetuple().tm_yday
    year_length = (
        366 if _is_leap_year(dt.year) else 365
    )
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
    local_dt:
        出生地当地钟表时间。
    timezone_info:
        出生地时区对象或时区名称。
        如果 local_dt 已带时区，则优先使用它自身的时区。
    正式排盘应使用 astronomy.solar_time 中的
    Skyfield + DE421 算法。
    """
    try:
        longitude = float(longitude)
    except (TypeError, ValueError) as exc:
        raise ValueError("经度必须是有效数字。") from exc
    if not -180 <= longitude <= 180:
        raise ValueError("经度必须在 -180 至 180 度之间。")
    if not isinstance(local_dt, datetime):
        raise TypeError("local_dt 必须是 datetime 对象。")
    if (
        local_dt.tzinfo is None
        or local_dt.utcoffset() is None
    ):
        if timezone_info is None:
            raise ValueError(
                "计算真太阳时需要出生地时区，不能使用设备时区代替。"
            )
        if isinstance(timezone_info, str):
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
            try:
                timezone_info = ZoneInfo(timezone_info)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError(
                    f"无法识别出生地时区：{timezone_info}"
                ) from exc
        aware_dt = local_dt.replace(tzinfo=timezone_info)
    else:
        aware_dt = local_dt
    offset = aware_dt.utcoffset()
    if offset is None:
        raise ValueError("无法确定当地时间的 UTC 偏移。")
    timezone_hours = offset.total_seconds() / 3600
    correction_minutes = (
        equation_of_time_minutes(aware_dt)
        + 4 * longitude
        - 60 * timezone_hours
    )
    wall_time = aware_dt.replace(tzinfo=None)
    return wall_time + timedelta(
        minutes=correction_minutes
    )
# --------------------------------------------------
# 年柱与月柱
# --------------------------------------------------
def year_ganzhi_and_start(dt, timezone_info=None):
    """
    以立春（太阳黄经 315 度）作为干支年分界。
    带时区 datetime：
        直接与 UTC 立春时刻比较。
    不带时区 datetime：
        如果提供 timezone_info，则按该时区解释；
        否则为兼容旧接口，按 UTC 解释。
    返回：
        (年干支, 立春时刻)
    立春时刻返回 UTC datetime。
    """
    if not isinstance(dt, datetime):
        raise TypeError("dt 必须是 datetime 对象。")
    if (
        dt.tzinfo is None
        or dt.utcoffset() is None
    ) and timezone_info is not None:
        if isinstance(timezone_info, str):
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
            try:
                timezone_info = ZoneInfo(timezone_info)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError(
                    f"无法识别出生地时区：{timezone_info}"
                ) from exc
        aware_dt = dt.replace(tzinfo=timezone_info)
    else:
        aware_dt = dt
    instant = _as_utc(aware_dt)
    start = datetime(
        instant.year,
        1,
        1,
        tzinfo=UTC,
    )
    li_chun = find_longitude_time(
        start,
        315,
        direction=1,
        max_days=370,
    )
    if li_chun is not None and instant < li_chun:
        year = instant.year - 1
    else:
        year = instant.year
    return ganzhi((year - 4) % 60), li_chun
def month_info(dt, year_gan, timezone_info=None):
    """
    根据太阳黄经估算节气月支与月干。
    315° 为寅月起点，此后每 30° 切换一月。
    带时区 datetime 会根据其绝对时刻计算太阳黄经。
    对不带时区的当地时间，可传入 timezone_info。
    返回：
        (月干, 月支, 太阳黄经)
    """
    if not isinstance(dt, datetime):
        raise TypeError("dt 必须是 datetime 对象。")
    if (
        dt.tzinfo is None
        or dt.utcoffset() is None
    ) and timezone_info is not None:
        if isinstance(timezone_info, str):
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
            try:
                timezone_info = ZoneInfo(timezone_info)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError(
                    f"无法识别出生地时区：{timezone_info}"
                ) from exc
        calculation_time = dt.replace(tzinfo=timezone_info)
    else:
        calculation_time = dt
    longitude = solar_longitude(calculation_time)
    x = longitude
    if x < 315:
        x += 360
    index = int(
        math.floor((x - 315) / 30)
    ) % 12
    branch = ZHI[(2 + index) % 12]
    from .rules import month_gan
    return (
        month_gan(year_gan, branch),
        branch,
        longitude,
    )