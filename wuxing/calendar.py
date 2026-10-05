from datetime import datetime, timedelta, timezone
import math
from .rules import GAN, ZHI, ganzhi

# 以 UTC 时间近似计算太阳黄经。精度足够用于普通排盘的节气边界显示，
# 临界分钟仍建议用户复核专业万年历。

def julian_day(dt):
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    y, m = dt.year, dt.month
    d = dt.day + (dt.hour + dt.minute/60 + dt.second/3600) / 24
    if m <= 2:
        y -= 1
        m += 12
    A = y // 100
    B = 2 - A + A // 4
    return int(365.25*(y+4716)) + int(30.6001*(m+1)) + d + B - 1524.5

def solar_longitude(dt):
    jd = julian_day(dt)
    T = (jd - 2451545.0) / 36525.0
    L0 = (280.46646 + 36000.76983*T + 0.0003032*T*T) % 360
    M = math.radians((357.52911 + 35999.05029*T - 0.0001537*T*T) % 360)
    C = ((1.914602 - 0.004817*T - 0.000014*T*T)*math.sin(M)
         + (0.019993 - 0.000101*T)*math.sin(2*M)
         + 0.000289*math.sin(3*M))
    return (L0 + C) % 360

def find_longitude_time(local_dt, target, direction=-1):
    # 搜索 local_dt 前后约 370 天，定位最近一次太阳黄经 target。
    # 用二分逼近穿越点。
    step = timedelta(hours=6)
    t = local_dt
    prev = solar_longitude(t)
    best = None
    for _ in range(160):
        nt = t + step
        cur = solar_longitude(nt)
        a = (prev - target + 180) % 360 - 180
        b = (cur - target + 180) % 360 - 180
        if a == 0 or a*b <= 0:
            lo, hi = t, nt
            for _ in range(30):
                mid = lo + (hi-lo)/2
                mv = (solar_longitude(mid)-target+180)%360-180
                lv = (solar_longitude(lo)-target+180)%360-180
                if lv*mv <= 0:
                    hi = mid
                else:
                    lo = mid
            cand = lo + (hi-lo)/2
            if best is None or abs((cand-local_dt).total_seconds()) < abs((best-local_dt).total_seconds()):
                best = cand
        t, prev = nt, cur
    return best

def term_events(year):
    # 24 节气太阳黄经：0,15,...345。返回该年附近的事件。
    start = datetime(year-1, 12, 1)
    out = []
    for k in range(25):
        target = (k * 15) % 360
        # 从上一个结果附近继续搜索
        if k == 0:
            base = start
        else:
            base = out[-1][1] + timedelta(days=12)
        ev = find_longitude_time(base, target)
        if ev:
            out.append((target, ev))
    return out

def recent_terms(dt, count=12):
    events = []
    for y in (dt.year-1, dt.year, dt.year+1):
        events.extend(term_events(y))
    events.sort(key=lambda x: x[1])
    return [x for x in events if x[1] <= dt + timedelta(days=400)][-count:]

def adjusted_date_for_day_pillar(dt):
    # 子初（23:00）换日
    if dt.hour >= 23:
        return dt.date() + timedelta(days=1)
    return dt.date()

def day_ganzhi(dt):
    d = adjusted_date_for_day_pillar(dt)
    base = datetime(2000, 1, 7)
    delta = (d - base.date()).days
    return ganzhi(delta % 60)

def branch_for_hour(hour, minute=0):
    total = hour * 60 + minute
    if total >= 23*60 or total < 60:
        return "子"
    idx = ((total - 60) // 120) + 1
    return ZHI[idx % 12]

def true_solar_time(local_dt, longitude):
    # 标准经线按时区中心估算；美国常见时区会由用户自行输入 UTC 偏移。
    # longitude: 东经为正，西经为负。
    # 这里仅做经度修正，界面会明确这是简化真太阳时。
    return local_dt + timedelta(minutes=longitude * 4)

def year_ganzhi_and_start(dt):
    # 315°（立春）为子平年界。
    li_chun = find_longitude_time(datetime(dt.year, 1, 1), 315)
    if li_chun and dt < li_chun:
        y = dt.year - 1
    else:
        y = dt.year
    return ganzhi((y - 4) % 60), li_chun

def month_info(dt, year_gan):
    # 以太阳黄经确定月支：315寅、345卯、15辰...
    lon = solar_longitude(dt)
    # 归一化到 [315,675)，对应寅到丑
    x = lon
    if x < 315:
        x += 360
    idx = int(math.floor((x - 315) / 30)) % 12
    branch = ZHI[(2 + idx) % 12]
    from .rules import month_gan
    return month_gan(year_gan, branch), branch, lon
