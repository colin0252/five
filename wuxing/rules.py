
# wuxing/rules.py
"""五行排盘基础规则：干支、五行、藏干、十神、纳音。"""

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

ELEMENT = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
    "子": "水", "丑": "土",
    "寅": "木", "卯": "木",
    "辰": "土", "巳": "火",
    "午": "火", "未": "土",
    "申": "金", "酉": "金",
    "戌": "土", "亥": "水",
}

YIN_YANG = {
    char: ("阳" if index % 2 == 0 else "阴")
    for index, char in enumerate(GAN)
}

YIN_YANG.update({
    char: ("阳" if index % 2 == 0 else "阴")
    for index, char in enumerate(ZHI)
})

# 地支藏干
HIDDEN = {
    "子": ["癸"],
    "丑": ["己", "癸", "辛"],
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "戊", "庚"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"],
}

# 六十甲子纳音，按甲子至癸亥排列
NA_YIN = [
    "海中金", "炉中火", "大林木", "路旁土", "剑锋金",
    "山头火", "涧下水", "城头土", "白蜡金", "杨柳木",
    "泉中水", "屋上土", "霹雳火", "松柏木", "长流水",
    "砂中金", "山下火", "平地木", "壁上土", "金箔金",
    "覆灯火", "天河水", "大驿土", "钗钏金", "桑柘木",
    "大溪水", "沙中土", "天上火", "石榴木", "大海水",
    "海中金", "炉中火", "大林木", "路旁土", "剑锋金",
    "山头火", "涧下水", "城头土", "白蜡金", "杨柳木",
    "泉中水", "屋上土", "霹雳火", "松柏木", "长流水",
    "砂中金", "山下火", "平地木", "壁上土", "金箔金",
    "覆灯火", "天河水", "大驿土", "钗钏金", "桑柘木",
    "大溪水", "沙中土", "天上火", "石榴木", "大海水",
]

# 五行相生、相克
GEN = {
    "木": "火",
    "火": "土",
    "土": "金",
    "金": "水",
    "水": "木",
}

CTRL = {
    "木": "土",
    "土": "水",
    "水": "火",
    "火": "金",
    "金": "木",
}


def ten_god(day_gan, other_gan):
    """根据日主与另一天干的五行生克、阴阳关系确定十神。"""
    if day_gan not in GAN or other_gan not in GAN:
        raise ValueError("十神计算必须传入有效的天干。")

    day_element = ELEMENT[day_gan]
    other_element = ELEMENT[other_gan]

    same_polarity = (
        YIN_YANG[day_gan] == YIN_YANG[other_gan]
    )

    if day_element == other_element:
        return "比肩" if same_polarity else "劫财"

    # 日主生另一干：食神、伤官
    if GEN[day_element] == other_element:
        return "食神" if same_polarity else "伤官"

    # 另一干生日主：偏印、正印
    if GEN[other_element] == day_element:
        return "偏印" if same_polarity else "正印"

    # 日主克另一干：偏财、正财
    if CTRL[day_element] == other_element:
        return "偏财" if same_polarity else "正财"

    # 另一干克日主：七杀、正官
    if CTRL[other_element] == day_element:
        return "七杀" if same_polarity else "正官"

    return "未知"


def pair_index(pair):
    """返回六十甲子干支对的序号，甲子为 0，癸亥为 59。"""
    if not isinstance(pair, str) or len(pair) != 2:
        raise ValueError(
            "干支必须是两个字符，例如甲子。"
        )

    gan, zhi = pair

    if gan not in GAN or zhi not in ZHI:
        raise ValueError(f"无效的干支：{pair}")

    gan_index = GAN.index(gan)
    zhi_index = ZHI.index(zhi)

    for index in range(60):
        if index % 10 == gan_index and index % 12 == zhi_index:
            return index

    raise ValueError(
        f"{pair} 不是有效的六十甲子组合。"
    )


def ganzhi_index(pair):
    """返回干支对在六十甲子中的序号。"""
    return pair_index(pair)


def ganzhi(index):
    """根据序号返回六十甲子干支，支持正负序号循环。"""
    index = int(index) % 60
    return GAN[index % 10] + ZHI[index % 12]


def hidden_stems(zhi):
    """返回地支藏干。"""
    if zhi not in HIDDEN:
        raise ValueError(f"无效的地支：{zhi}")

    return list(HIDDEN[zhi])


def na_yin(pair):
    """根据六十甲子干支返回纳音。"""
    return NA_YIN[pair_index(pair)]


# 年干决定寅月月干：
# 甲己丙、乙庚戊、丙辛庚、丁壬壬、戊癸甲
FIRST_YUE_GAN = {
    "甲": "丙",
    "己": "丙",
    "乙": "戊",
    "庚": "戊",
    "丙": "庚",
    "辛": "庚",
    "丁": "壬",
    "壬": "壬",
    "戊": "甲",
    "癸": "甲",
}


def month_gan(year_gan, month_branch):
    """根据年干与月支计算月干。"""
    if year_gan not in FIRST_YUE_GAN:
        raise ValueError(f"无效的年干：{year_gan}")

    if month_branch not in ZHI:
        raise ValueError(f"无效的月支：{month_branch}")

    start = GAN.index(FIRST_YUE_GAN[year_gan])
    offset = ZHI.index(month_branch) - ZHI.index("寅")

    return GAN[(start + offset) % 10]


def hour_gan(day_gan, branch):
    """根据日干与时支计算时干。"""
    if day_gan not in GAN:
        raise ValueError(f"无效的日干：{day_gan}")

    if branch not in ZHI:
        raise ValueError(f"无效的时支：{branch}")

    # 甲己日起甲子；乙庚丙子；
    # 丙辛戊子；丁壬庚子；戊癸壬子。
    first = {
        "甲": "甲",
        "己": "甲",
        "乙": "丙",
        "庚": "丙",
        "丙": "戊",
        "辛": "戊",
        "丁": "庚",
        "壬": "庚",
        "戊": "壬",
        "癸": "壬",
    }[day_gan]

    return GAN[
        (GAN.index(first) + ZHI.index(branch)) % 10
    ]
