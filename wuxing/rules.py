GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

ELEMENT = {
    "甲":"木","乙":"木","丙":"火","丁":"火","戊":"土","己":"土",
    "庚":"金","辛":"金","壬":"水","癸":"水",
    "子":"水","丑":"土","寅":"木","卯":"木","辰":"土","巳":"火",
    "午":"火","未":"土","申":"金","酉":"金","戌":"土","亥":"水"
}

YIN_YANG = {c: ("阳" if i % 2 == 0 else "阴") for i, c in enumerate(GAN)}
YIN_YANG.update({c: ("阳" if i % 2 == 0 else "阴") for i, c in enumerate(ZHI)})

HIDDEN = {
    "子":["癸"], "丑":["己","癸","辛"], "寅":["甲","丙","戊"],
    "卯":["乙"], "辰":["戊","乙","癸"], "巳":["丙","戊","庚"],
    "午":["丁","己"], "未":["己","丁","乙"], "申":["庚","壬","戊"],
    "酉":["辛"], "戌":["戊","辛","丁"], "亥":["壬","甲"]
}

# 纳音六十甲子
NA_YIN = [
"海中金","炉中火","大林木","路旁土","剑锋金","山头火","涧下水","城头土","白蜡金","杨柳木",
"泉中水","屋上土","霹雳火","松柏木","长流水","砂中金","山下火","平地木","壁上土","金箔金",
"覆灯火","天河水","大驿土","钗钏金","桑柘木","大溪水","沙中土","天上火","石榴木","大海水",
"海中金","炉中火","大林木","路旁土","剑锋金","山头火","涧下水","城头土","白蜡金","杨柳木",
"泉中水","屋上土","霹雳火","松柏木","长流水","砂中金","山下火","平地木","壁上土","金箔金",
"覆灯火","天河水","大驿土","钗钏金","桑柘木","大溪水","沙中土","天上火","石榴木","大海水"
]

# 日主到十神：先按五行生克，再按阴阳同异定正偏
GEN = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
CTRL = {"木":"土","土":"水","水":"火","火":"金","金":"木"}

def ten_god(day_gan, other_gan):
    if day_gan == other_gan:
        return "比肩"
    de = ELEMENT[day_gan]
    oe = ELEMENT[other_gan]
    same_polarity = YIN_YANG[day_gan] == YIN_YANG[other_gan]
    if oe == de:
        return "比肩" if same_polarity else "劫财"
    if GEN[de] == oe:
        return "食神" if same_polarity else "伤官"
    if GEN[oe] == de:
        return "偏印" if same_polarity else "正印"
    if CTRL[de] == oe:
        return "偏财" if same_polarity else "正财"
    if CTRL[oe] == de:
        return "七杀" if same_polarity else "正官"
    return "未知"

def ganzhi_index(pair):
    return GAN.index(pair[0]) * 6 + 0  # unused; see pair_index

def pair_index(pair):
    g, z = pair
    for i in range(60):
        if GAN[i % 10] + ZHI[i % 12] == g + z:
            return i
    raise ValueError(pair)

def ganzhi(i):
    i %= 60
    return GAN[i % 10] + ZHI[i % 12]

def hidden_stems(zhi):
    return HIDDEN[zhi]

def na_yin(pair):
    return NA_YIN[pair_index(pair)]

# 年干决定寅月月干：甲己丙、乙庚戊、丙辛庚、丁壬壬、戊癸甲
FIRST_YUE_GAN = {"甲":"丙","己":"丙","乙":"戊","庚":"戊","丙":"庚","辛":"庚","丁":"壬","壬":"壬","戊":"甲","癸":"甲"}

def month_gan(year_gan, month_branch):
    start = GAN.index(FIRST_YUE_GAN[year_gan])
    offset = ZHI.index(month_branch) - ZHI.index("寅")
    return GAN[(start + offset) % 10]

def hour_gan(day_gan, branch):
    # 甲己日起甲子；乙庚丙子；丙辛戊子；丁壬庚子；戊癸壬子
    first = {"甲":"甲","己":"甲","乙":"丙","庚":"丙","丙":"戊","辛":"戊","丁":"庚","壬":"庚","戊":"壬","癸":"壬"}[day_gan]
    return GAN[(GAN.index(first) + ZHI.index(branch)) % 10]
