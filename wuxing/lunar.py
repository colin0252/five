# wuxing/lunar.py
"""农历换算（1900-2100）。

纯标准库实现，不依赖网络，可离线运行。

用法：
    from wuxing.lunar import solar_to_lunar

    text = solar_to_lunar(datetime(2026, 11, 14, 14, 58))
    # -> "二零二六年十月初六未时"

数据说明：
    LUNAR_INFO 每个 16 进制数编码一年：
      低 4 位  ：闰月月份（0 表示无闰月）
      0x10000  ：闰月大小（1 = 30 天，0 = 29 天）
      0x8000-0x10：正月至十二月大小（1 = 30 天，0 = 29 天）
    基准日：1900-01-31 = 农历 1900 年正月初一。
"""

from datetime import datetime, date, timedelta

# 1900-2100 年农历数据（共 201 项）
LUNAR_INFO = [
    0x04BD8, 0x04AE0, 0x0A570, 0x054D5, 0x0D260, 0x0D950, 0x16554,
    0x056A0, 0x09AD0, 0x055D2, 0x04AE0, 0x0A5B6, 0x0A4D0, 0x0D250,
    0x1D255, 0x0B540, 0x0D6A0, 0x0ADA2, 0x095B0, 0x14977, 0x04970,
    0x0A4B0, 0x0B4B5, 0x06A50, 0x06D40, 0x1AB54, 0x02B60, 0x09570,
    0x052F2, 0x04970, 0x06566, 0x0D4A0, 0x0EA50, 0x06E95, 0x05AD0,
    0x02B60, 0x186E3, 0x092E0, 0x1C8D7, 0x0C950, 0x0D4A0, 0x1D8A6,
    0x0B550, 0x056A0, 0x1A5B4, 0x025D0, 0x092D0, 0x0D2B2, 0x0A950,
    0x0B557, 0x06CA0, 0x0B550, 0x15355, 0x04DA0, 0x0A5B0, 0x14573,
    0x052B0, 0x0A9A8, 0x0E950, 0x06AA0, 0x0AEA6, 0x0AB50, 0x04B60,
    0x0AAE4, 0x0A570, 0x05260, 0x0F263, 0x0D950, 0x05B57, 0x056A0,
    0x096D0, 0x04DD5, 0x04AD0, 0x0A4D0, 0x0D4D4, 0x0D250, 0x0D558,
    0x0B540, 0x0B6A0, 0x195A6, 0x095B0, 0x049B0, 0x0A974, 0x0A4B0,
    0x0B27A, 0x06A50, 0x06D40, 0x0AF46, 0x0AB60, 0x09570, 0x04AF5,
    0x04970, 0x064B0, 0x074A3, 0x0EA50, 0x06B58, 0x05AC0, 0x0AB60,
    0x096D5, 0x092E0, 0x0C960, 0x0D954, 0x0D4A0, 0x0DA50, 0x07552,
    0x056A0, 0x0ABB7, 0x025D0, 0x092D0, 0x0CAB5, 0x0A950, 0x0B4A0,
    0x0BAA4, 0x0AD50, 0x055D9, 0x04BA0, 0x0A5B0, 0x15176, 0x052B0,
    0x0A930, 0x07954, 0x06AA0, 0x0AD50, 0x05B52, 0x04B60, 0x0A6E6,
    0x0A4E0, 0x0D260, 0x0EA65, 0x0D530, 0x05AA0, 0x076A3, 0x096D0,
    0x04AFB, 0x04AD0, 0x0A4D0, 0x1D0B6, 0x0D250, 0x0D520, 0x0DD45,
    0x0B5A0, 0x056D0, 0x055B2, 0x049B0, 0x0A577, 0x0A4B0, 0x0AA50,
    0x1B255, 0x06D20, 0x0ADA0, 0x14B63, 0x09370, 0x049F8, 0x04970,
    0x064B0, 0x168A6, 0x0EA50, 0x06B20, 0x1A6C4, 0x0AAE0, 0x0A2E0,
    0x0D2E3, 0x0C960, 0x0D557, 0x0D4A0, 0x0DA50, 0x05D55, 0x056A0,
    0x0A6D0, 0x055D4, 0x052D0, 0x0A9B8, 0x0A950, 0x0B4A0, 0x0B6A6,
    0x0AD50, 0x055A0, 0x0ABA4, 0x0A5B0, 0x052B0, 0x0B273, 0x06930,
    0x07337, 0x06AA0, 0x0AD50, 0x14B55, 0x04B60, 0x0A570, 0x054E4,
    0x0D160, 0x0E968, 0x0D520, 0x0DAA0, 0x16AA6, 0x056D0, 0x04AE0,
    0x0A9D4, 0x0A2D0, 0x0D150, 0x0F252, 0x0D520,
]

BASE_YEAR = 1900
LAST_YEAR = 2100

# 1900-01-31 是农历 1900 年正月初一
BASE_DATE = date(1900, 1, 31)

# 农历月份名称
MONTH_NAMES = [
    "正月", "二月", "三月", "四月", "五月", "六月",
    "七月", "八月", "九月", "十月", "冬月", "腊月",
]

# 农历日名称
DAY_NAMES = [
    "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八",
    "初九", "初十", "十一", "十二", "十三", "十四", "十五", "十六",
    "十七", "十八", "十九", "二十", "廿一", "廿二", "廿三", "廿四",
    "廿五", "廿六", "廿七", "廿八", "廿九", "三十",
]

# 十二时辰（子时从 23 点开始）
HOUR_BRANCHES = [
    "子", "丑", "寅", "卯", "辰", "巳",
    "午", "未", "申", "酉", "戌", "亥",
]

CHINESE_DIGITS = "零一二三四五六七八九"


class LunarError(Exception):
    """农历换算异常。"""


def _info(year):
    if not BASE_YEAR <= year <= LAST_YEAR:
        raise LunarError(
            f"农历数据只支持 {BASE_YEAR}-{LAST_YEAR} 年。"
        )
    return LUNAR_INFO[year - BASE_YEAR]


def leap_month(year):
    """返回闰月月份；无闰月返回 0。"""
    return _info(year) & 0xF


def leap_days(year):
    """返回闰月天数；无闰月返回 0。"""
    if leap_month(year) == 0:
        return 0
    return 30 if (_info(year) & 0x10000) else 29


def month_days(year, month):
    """返回某农历月的天数（29 或 30）。"""
    return 30 if (_info(year) & (0x10000 >> month)) else 29


def year_days(year):
    """返回某农历年的总天数。"""
    total = 348
    info = _info(year)
    bit = 0x8000
    while bit > 0x8:
        if info & bit:
            total += 1
        bit >>= 1
    return total + leap_days(year)


def solar_to_lunar_dict(target):
    """公历日期转农历，返回字典。

    参数：
        target: datetime.date 或 datetime.datetime

    返回：
        {
            "year": 2026, "month": 10, "day": 6,
            "leap": False, "year_ganzhi": "丙午",
        }
    """
    if isinstance(target, datetime):
        target_date = target.date()
    elif isinstance(target, date):
        target_date = target
    else:
        raise LunarError("target 必须是 date 或 datetime。")
    if target_date < BASE_DATE:
        raise LunarError(
            f"日期早于 {BASE_DATE}，超出农历数据范围。"
        )
    offset = (target_date - BASE_DATE).days
    year = BASE_YEAR
    while year <= LAST_YEAR:
        days = year_days(year)
        if offset < days:
            break
        offset -= days
        year += 1
    if year > LAST_YEAR:
        raise LunarError(
            f"日期超出 {LAST_YEAR} 年农历数据范围。"
        )
    leap = leap_month(year)
    is_leap = False
    month = 1
    while month <= 12:
        if leap > 0 and month == leap + 1 and not is_leap:
            days = leap_days(year)
            is_leap = True
        else:
            days = month_days(year, month)
            if is_leap:
                is_leap = False
        if offset < days:
            break
        offset -= days
        month += 1
    return {
        "year": year,
        "month": month,
        "day": offset + 1,
        "leap": leap > 0 and month == leap + 1 and is_leap,
        "year_ganzhi": year_ganzhi(year),
    }


def year_ganzhi(year):
    """农历年干支（以农历年为准）。"""
    gan = "甲乙丙丁戊己庚辛壬癸"
    zhi = "子丑寅卯辰巳午未申酉戌亥"
    index = (year - 4) % 60
    return gan[index % 10] + zhi[index % 12]


def hour_branch(target):
    """按时辰返回地支（子时 23:00-00:59）。"""
    hour = target.hour if isinstance(target, datetime) else 0
    return HOUR_BRANCHES[((hour + 1) // 2) % 12]


def _chinese_year(year):
    """年份逐位读，例如 2026 -> 二零二六。"""
    return "".join(CHINESE_DIGITS[int(ch)] for ch in str(year))


def format_lunar(info, target=None, with_hour=True):
    """把农历字典格式化为「二零二六年十月初六未时」。"""
    text = _chinese_year(info["year"]) + "年"
    text += ("闰" if info.get("leap") else "")
    text += MONTH_NAMES[info["month"] - 1]
    text += DAY_NAMES[info["day"] - 1]
    if with_hour and isinstance(target, datetime):
        text += hour_branch(target) + "时"
    return text


def solar_to_lunar(target, with_hour=True):
    """公历转农历字符串，例如「二零二六年十月初六未时」。

    参数：
        target: datetime 或 date
        with_hour: datetime 时是否追加时辰

    返回：
        字符串；超出 1900-2100 范围时抛出 LunarError。
    """
    info = solar_to_lunar_dict(target)
    return format_lunar(info, target, with_hour=with_hour)


def lunar_to_solar(year, month, day, leap=False):
    """农历转公历，返回 datetime.date。"""
    _info(year)
    offset = 0
    for y in range(BASE_YEAR, year):
        offset += year_days(y)
    leap_month_value = leap_month(year)
    for m in range(1, month):
        offset += month_days(year, m)
        if leap_month_value == m:
            offset += leap_days(year)
    if leap:
        if leap_month_value != month:
            raise LunarError(
                f"{year} 年 {month} 月不是闰月。"
            )
        offset += month_days(year, month)
    offset += day - 1
    return BASE_DATE + timedelta(days=offset)
