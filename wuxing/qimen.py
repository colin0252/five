# wuxing/qimen.py
"""时家奇门（转盘）排盘。

只做"排盘"，不做断语。输入是一个 paipan.Chart（含四柱和出生时刻），
输出：阴阳遁、局数、三元、地盘三奇六仪、天盘九星/天盘干、八门、八神。

排法要点（转盘奇门通行规则）：
    1. 定局：按节气 + 三元（上/中/下元，每元 5 天）查表得局数；
       冬至到芒种用阳遁，夏至到大雪用阴遁。
    2. 地盘：阳遁顺布、阴遁逆布，从局数宫起"戊己庚辛壬癸丁丙乙"。
    3. 值符/值使：时柱所在旬的旬首（甲子戊、甲戌己、甲申庚、
       甲午辛、甲辰壬、甲寅癸）在地盘的宫位，该宫的九星为值符、
       八门为值使。
    4. 天盘：值符星随时干落宫（时干在地盘的宫位），其余九星按
       "蓬任冲辅英芮柱心"顺序顺时针跟着转；天盘干随九星一起转。
    5. 八门：值使门从旬首宫起，按阳遁顺、阴遁逆，数到当前时辰
       （旬内第几个时辰），即为值使落宫；其余七门顺时针排。
    6. 八神：从值符星落宫起，阳遁顺时针、阴遁逆时针排
       "值符、腾蛇、太阴、六合、白虎、玄武、九地、九天"。

注意：奇门流派很多（转盘/飞盘、置闰/拆补、时家/日家），本模块
采用最常见的"时家转盘 + 拆补三元"做法，排出来与主流转盘奇门
软件应当一致；若与某个特定软件有差异，多半是定局口径不同。
"""

from datetime import datetime, timezone

from .calendar import find_longitude_time, solar_longitude
from .rules import pair_index

# ------------------------------------------------------------
# 基础数据
# ------------------------------------------------------------
GONG_NAMES = {
    1: "坎",
    2: "坤",
    3: "震",
    4: "巽",
    5: "中",
    6: "乾",
    7: "兑",
    8: "艮",
    9: "离",
}

# 洛书九宫按顺时针排列（不含中宫）
RING = [1, 8, 3, 4, 9, 2, 7, 6]

# 地盘九星固定位置
STAR_FIXED = {
    1: "天蓬",
    2: "天芮",
    3: "天冲",
    4: "天辅",
    5: "天禽",
    6: "天心",
    7: "天柱",
    8: "天任",
    9: "天英",
}

# 顺时针的八星（天禽寄坤二宫，随天芮）
RING_STARS = ["天蓬", "天任", "天冲", "天辅", "天英", "天芮", "天柱", "天心"]

# 地盘八门固定位置
DOOR_FIXED = {
    1: "休门",
    8: "生门",
    3: "伤门",
    4: "杜门",
    9: "景门",
    2: "死门",
    7: "惊门",
    6: "开门",
}

# 顺时针的八门
RING_DOORS = ["休门", "生门", "伤门", "杜门", "景门", "死门", "惊门", "开门"]

# 八神顺序
GODS = ["值符", "腾蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天"]

# 六仪（三奇六仪的布法顺序）
LIUYI = "戊己庚辛壬癸丁丙乙"

# 旬首：60 甲子按每 10 个一组
XUN_SHOU = ["甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅"]
XUN_YI = ["戊", "己", "庚", "辛", "壬", "癸"]
XUN_KONG = [
    "戌亥",
    "申酉",
    "午未",
    "辰巳",
    "寅卯",
    "子丑",
]

# 二十四节气黄经（度）
JIEQI = [
    ("春分", 0),
    ("清明", 15),
    ("谷雨", 30),
    ("立夏", 45),
    ("小满", 60),
    ("芒种", 75),
    ("夏至", 90),
    ("小暑", 105),
    ("大暑", 120),
    ("立秋", 135),
    ("处暑", 150),
    ("白露", 165),
    ("秋分", 180),
    ("寒露", 195),
    ("霜降", 210),
    ("立冬", 225),
    ("小雪", 240),
    ("大雪", 255),
    ("冬至", 270),
    ("小寒", 285),
    ("大寒", 300),
    ("立春", 315),
    ("雨水", 330),
    ("惊蛰", 345),
]

# 节气三元局数：(上元, 中元, 下元)
JU_TABLE = {
    # ---- 阳遁 ----
    "冬至": (1, 7, 4),
    "小寒": (2, 8, 5),
    "大寒": (3, 9, 6),
    "立春": (8, 5, 3),
    "雨水": (9, 6, 4),
    "惊蛰": (1, 7, 4),
    "春分": (3, 9, 6),
    "清明": (4, 1, 7),
    "谷雨": (5, 2, 8),
    "立夏": (4, 1, 7),
    "小满": (5, 2, 8),
    "芒种": (6, 3, 9),
    # ---- 阴遁 ----
    "夏至": (9, 3, 6),
    "小暑": (8, 2, 5),
    "大暑": (7, 1, 4),
    "立秋": (2, 5, 8),
    "处暑": (1, 4, 7),
    "白露": (9, 3, 6),
    "秋分": (7, 1, 4),
    "寒露": (6, 9, 3),
    "霜降": (5, 8, 2),
    "立冬": (6, 9, 3),
    "小雪": (5, 8, 2),
    "大雪": (4, 7, 1),
}

YANG_JIEQI = {
    "冬至",
    "小寒",
    "大寒",
    "立春",
    "雨水",
    "惊蛰",
    "春分",
    "清明",
    "谷雨",
    "立夏",
    "小满",
    "芒种",
}


class QimenError(Exception):
    """奇门排盘异常。"""


# ------------------------------------------------------------
# 工具
# ------------------------------------------------------------
def _ring_index(gong):
    """宫位在顺时针环上的序号（0~7）。中宫寄坤二宫。"""
    if gong == 5:
        gong = 2
    return RING.index(gong)


def _solar_longitude_at(moment):
    return solar_longitude(moment.astimezone(timezone.utc)) % 360.0


def _jieqi_and_yuan(moment):
    """返回 (节气名, 元序 0/1/2, 节气起始时刻)。"""
    if moment.tzinfo is None:
        raise QimenError("计算奇门定局需要带时区的时刻。")
    current = _solar_longitude_at(moment)

    # 找当前所处节气：黄经区间 [起始, 起始+15)
    active_name = None
    active_degree = None
    for name, degree in JIEQI:
        if current >= degree:
            if active_degree is None or degree > active_degree:
                active_degree = degree
                active_name = name
    if active_name is None:
        # 黄经小于 0 度的情况（不会发生，保险）
        active_name, active_degree = JIEQI[0]

    start = find_longitude_time(
        moment.astimezone(timezone.utc),
        float(active_degree),
        direction=-1,
        max_days=40,
    )
    if start is None:
        raise QimenError("找不到当前节气的起始时刻。")

    days = (moment.astimezone(timezone.utc) - start).total_seconds() / 86400.0
    if days < 0:
        days = 0.0
    yuan = int(days // 5)
    if yuan > 2:
        yuan = 2
    return active_name, yuan, start


def _build_di_pan(ju, yang):
    """地盘三奇六仪：阳遁顺布、阴遁逆布。"""
    result = {}
    for index, gan in enumerate(LIUYI):
        if yang:
            gong = ((ju - 1 + index) % 9) + 1
        else:
            gong = ((ju - 1 - index) % 9) + 1
        result[gong] = gan
    return result


# ------------------------------------------------------------
# 主函数
# ------------------------------------------------------------
def build_qimen(chart, moment=None):
    """根据 paipan.Chart 排一张时家奇门盘。

    chart.birth 是不带时区的当地钟表时间，所以定局必须另外传入
    带时区的时刻 moment；不传时退回 chart.birth（可能报错）。
    """
    if chart is None or not getattr(chart, "hour", None):
        raise QimenError("缺少四柱信息，无法排奇门盘。")

    if moment is None:
        moment = getattr(chart, "birth", None)
    if moment is None:
        raise QimenError("缺少排盘时刻。")
    if moment.tzinfo is None:
        raise QimenError("排盘时刻必须带时区。")

    jieqi, yuan, jieqi_start = _jieqi_and_yuan(moment)
    yang = jieqi in YANG_JIEQI
    ju = JU_TABLE[jieqi][yuan]
    yuan_name = ("上元", "中元", "下元")[yuan]

    di_pan = _build_di_pan(ju, yang)

    hour_gz = chart.hour.ganzhi
    if not isinstance(hour_gz, str) or len(hour_gz) != 2:
        raise QimenError("时柱格式不正确：" + str(hour_gz))
    hour_index = pair_index(hour_gz)
    if hour_index is None:
        raise QimenError("无法解析时柱：" + hour_gz)

    xun_index = hour_index // 10
    xun_name = XUN_SHOU[xun_index]
    xun_yi = XUN_YI[xun_index]
    xun_kong = XUN_KONG[xun_index]
    step_in_xun = hour_index % 10

    # 旬首在地盘的宫位
    p0 = None
    for gong, gan in di_pan.items():
        if gan == xun_yi:
            p0 = gong
            break
    if p0 is None:
        raise QimenError("地盘里找不到旬首六仪：" + xun_yi)

    p0_ring = _ring_index(p0)
    zhi_fu_star = STAR_FIXED[5] if p0 == 5 else STAR_FIXED[p0]
    zhi_shi_door = DOOR_FIXED[2] if p0 == 5 else DOOR_FIXED[p0]

    # 时干在地盘的宫位
    hour_gan = hour_gz[0]
    if hour_gan == "甲":
        p1 = p0
    else:
        p1 = None
        for gong, gan in di_pan.items():
            if gan == hour_gan:
                p1 = gong
                break
        if p1 is None:
            raise QimenError("地盘里找不到时干：" + hour_gan)
    p1_ring = _ring_index(p1)

    # 天盘九星与天盘干：整体顺时针旋转
    offset = (p1_ring - p0_ring) % 8
    tian_stars = {}
    tian_gans = {}
    for position, gong in enumerate(RING):
        source = RING[(position - offset) % 8]
        tian_stars[gong] = RING_STARS[(position - offset) % 8]
        tian_gans[gong] = di_pan.get(source, "")

    # 值使门落宫
    direction = 1 if yang else -1
    door_ring = (p0_ring + step_in_xun * direction) % 8
    door_base = RING_DOORS.index(zhi_shi_door) if zhi_shi_door in RING_DOORS else 0
    doors = {}
    for position, gong in enumerate(RING):
        doors[gong] = RING_DOORS[(door_base + (position - door_ring)) % 8]

    # 八神
    gods = {}
    for index, god in enumerate(GODS):
        position = (p1_ring + index * direction) % 8
        gods[RING[position]] = god

    # 逐宫整理
    palaces = []
    for gong in (1, 2, 3, 4, 5, 6, 7, 8, 9):
        if gong == 5:
            palaces.append(
                {
                    "gong": 5,
                    "name": GONG_NAMES[5],
                    "di_gan": di_pan.get(5, ""),
                    "tian_gan": "",
                    "star": "天禽",
                    "door": "",
                    "god": "",
                }
            )
            continue
        star = tian_stars.get(gong, "")
        if star == "天芮":
            star = "天芮/天禽"
        palaces.append(
            {
                "gong": gong,
                "name": GONG_NAMES[gong],
                "di_gan": di_pan.get(gong, ""),
                "tian_gan": tian_gans.get(gong, ""),
                "star": star,
                "door": doors.get(gong, ""),
                "god": gods.get(gong, ""),
            }
        )

    return {
        "moment": moment,
        "hour_gz": hour_gz,
        "jieqi": jieqi,
        "jieqi_start": jieqi_start,
        "yuan": yuan,
        "yuan_name": yuan_name,
        "dun": "阳遁" if yang else "阴遁",
        "ju": ju,
        "ju_text": ("阳遁" if yang else "阴遁") + _number_cn(ju) + "局",
        "xun": xun_name,
        "xun_yi": xun_yi,
        "xun_kong": xun_kong,
        "zhi_fu": zhi_fu_star,
        "zhi_shi": zhi_shi_door,
        "palaces": palaces,
    }


def _number_cn(number):
    names = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
    if 0 <= number <= 9:
        return names[number]
    return str(number)


def build_from_values(
    moment, latitude, longitude, timezone_name, solar_mode="mean", sex="男"
):
    """给界面用的便捷入口：自己传时刻和经纬度，直接排奇门盘。"""
    from .paipan import build_chart

    if moment.tzinfo is None:
        raise QimenError("排盘时刻必须带时区。")
    chart = build_chart(
        moment,
        float(longitude),
        sex,
        latitude=float(latitude),
        timezone_info=timezone_name,
        solar_mode=solar_mode,
    )
    return build_qimen(chart, moment=moment)


def summary(result):
    """把排盘结果整理成多行文字（给界面用）。"""
    if not result:
        return ""
    lines = [
        f"时辰：{result['hour_gz']}",
        f"节气：{result['jieqi']} · {result['yuan_name']}",
        f"局数：{result['ju_text']}",
        f"旬首：{result['xun']}（{result['xun_yi']}）  旬空：{result['xun_kong']}",
        f"值符：{result['zhi_fu']}    值使：{result['zhi_shi']}",
    ]
    return "\n".join(lines)


def grid_rows(result):
    """按洛书九宫排出 3x3 的宫位序号，方便界面画表格。"""
    return [
        [4, 9, 2],
        [3, 5, 7],
        [8, 1, 6],
    ]


def palace_of(result, gong):
    for item in result.get("palaces", []):
        if item["gong"] == gong:
            return item
    return None
