# wuxing/calendar.py
"""历法基础计算：儒略日、太阳黄经、节气、干支及真太阳时。"""
from datetime import datetime, timedelta, timezone
import math
from .rules import GAN, ZHI, ganzhi
# --------------------------------------------------
# 儒略日
# --------------------------------------------------
def julian_day(dt):
    """计算日期对应的儒略日。带时区的时间先转换为 UTC。"""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    y, m = dt.year, dt.month
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
    结果范围为 0 至 360 度。
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
    搜索太阳黄经经过指定角度的时间。
    参数：
        local_dt: 搜索起点，建议使用不带时区的当地钟表时间。
        target: 目标太阳黄经，单位为度。
        direction: 1 向未来搜索，-1 向过去搜索。
        max_days: 最大搜索天数。
    返回：
        找到时返回 datetime；没有找到时返回 None。
    """
    if not isinstance(local_dt, datetime):
        raise TypeError("local_dt 必须是 datetime 对象。")
    target = float(target) % 360
    if direction not in (-1, 1):
        raise ValueError("direction 必须为 1 或 -1。")
    if max_days <= 0:
        raise ValueError("max_days 必须大于 0。")
    # 节气搜索使用六小时步长，再通过二分法细化。
    step = timedelta(hours=6)
    max_steps = int(max_days * 4) + 1
    t = local_dt
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
        # 排除太阳黄经经过 180 度附近时的角度折返。
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
            # 交点附近的太阳黄经变化连续，二分逼近交点。
            for _ in range(40):
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
    获取指定公历年份内的二十四节气黄经交点。
    返回列表：
        [(太阳黄经角度, datetime), ...]
    时间采用不带时区的 datetime，表示计算用的统一时间坐标。
    """
    start = datetime(year, 1, 1)
    end = datetime(year + 1, 1, 1)
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
    不把尚未发生的节气当成已经发生的节气。
    """
    if count <= 0:
        return []
    events = []
    for year in (dt.year - 1, dt.year, dt.year + 1):
        events.extend(term_events(year))
    events.sort(key=lambda item: item[1])
    previous = [
        item for item in events
        if item[1] <= dt
    ]
    return previous[-count:]
# --------------------------------------------------
# 日柱与时支
# --------------------------------------------------
def adjusted_date_for_day_pillar(dt):
    """按子初换日口径处理日柱日期。"""
    if dt.hour >= 23:
        return dt.date() + timedelta(days=1)
    return dt.date()
def day_ganzhi(dt):
    """计算日干支，采用 2000-01-07 为甲子日的基准。"""
    adjusted_date = adjusted_date_for_day_pillar(dt)
    base_date = datetime(2000, 1, 7).date()
    delta = (adjusted_date - base_date).days
    return ganzhi(delta % 60)
def branch_for_hour(hour, minute=0):
    """根据钟表时间计算时支。"""
    total = int(hour) * 60 + int(minute)
    if not 0 <= int(hour) <= 23:
        raise ValueError("小时必须在 0 至 23 之间。")
    if not 0 <= int(minute) <= 59:
        raise ValueError("分钟必须在 0 至 59 之间。")
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
    这是备用近似算法，不替代项目中的 Skyfield 星历算法。
    """
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
    有效时区信息优先取 local_dt 自身的时区；
    如果 local_dt 不带时区，则尝试使用 timezone_info。
    若仍没有时区，则只能采用设备当前时区作近似。
    正式排盘优先使用 paipan.py 中的
    astronomy.solar_time.calc_true_solar_time。
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
        if timezone_info is not None:
            aware_dt = local_dt.replace(tzinfo=timezone_info)
        else:
            # 仅作兼容旧调用：使用运行设备的当地时区。
            aware_dt = local_dt.astimezone()
    else:
        aware_dt = local_dt
    offset = aware_dt.utcoffset()
    if offset is None:
        raise ValueError("无法确定当地时间的 UTC 偏移。")
    timezone_hours = offset.total_seconds() / 3600
    # 视太阳时 = 当地钟表时间
    # + 均时差 + 4*经度 - 60*时区偏移。
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
def year_ganzhi_and_start(dt):
    """
    以立春（太阳黄经 315 度）作为干支年分界。
    """
    start = datetime(dt.year, 1, 1)
    li_chun = find_longitude_time(
        start,
        315,
        direction=1,
        max_days=370,
    )
    if li_chun is not None and dt < li_chun:
        year = dt.year - 1
    else:
        year = dt.year
    return ganzhi((year - 4) % 60), li_chun
def month_info(dt, year_gan):
    """
    根据太阳黄经估算节气月支与月干。
    315° 为寅月起点，此后每 30° 切换一月。
    """
    longitude = solar_longitude(dt)
    x = longitude
    if x < 315:
        x += 360
    index = int(math.floor((x - 315) / 30)) % 12
    branch = ZHI[(2 + index) % 12]
    from .rules import month_gan
    return month_gan(year_gan, branch), branch, longitude