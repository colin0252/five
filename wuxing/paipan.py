from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import Counter
from .calendar import day_ganzhi, year_ganzhi_and_start, month_info, true_solar_time, branch_for_hour, solar_longitude, find_longitude_time
from .rules import GAN, ZHI, ELEMENT, HIDDEN, ten_god, hour_gan, na_yin, ganzhi, pair_index

@dataclass
class Pillar:
    name: str
    ganzhi: str
    gan: str
    zhi: str
    hidden: list
    ten_god_gan: str
    na_yin: str

@dataclass
class Chart:
    birth: datetime
    longitude: float
    sex: str
    true_solar: datetime
    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar
    fetal: str
    life_palace: str
    dayun: list
    wuxing: dict
    warnings: list

def pillar(name, gz, day_gan):
    return Pillar(
        name=name,
        ganzhi=gz,
        gan=gz[0],
        zhi=gz[1],
        hidden=HIDDEN[gz[1]],
        ten_god_gan=ten_god(day_gan, gz[0]),
        na_yin=na_yin(gz)
    )

def build_chart(birth, longitude, sex):
    warnings = []
    y_gz, li_chun = year_ganzhi_and_start(birth)
    if li_chun and abs((birth-li_chun).total_seconds()) < 3600:
        warnings.append("åºçæ¶é´æ¥è¿ç«æ¥äº¤çï¼è¯·å¤æ ¸èæ°æ¶å»ã")

    m_gan, m_zhi, lon = month_info(birth, y_gz[0])
    d_gz = day_ganzhi(birth)

    tst = true_solar_time(birth, longitude)
    h_zhi = branch_for_hour(tst.hour, tst.minute)
    h_gan = hour_gan(d_gz[0], h_zhi)
    h_gz = h_gan + h_zhi

    if birth.hour in (0,1,2,23) or tst.hour in (0,1,2,23):
        warnings.append("åºçæ¶å»é è¿å­ä¸äº¤çï¼å»ºè®®å¤æ ¸çå¤ªé³æ¶ä¸æ¢æ¥å£å¾ã")

    year = pillar("å¹´æ±", y_gz, d_gz[0])
    month = pillar("ææ±", m_gan+m_zhi, d_gz[0])
    day = pillar("æ¥æ±", d_gz, d_gz[0])
    hour = pillar("æ¶æ±", h_gz, d_gz[0])

    fetal = fetal_origin(m_gan+m_zhi)
    life = life_palace(m_zhi, h_zhi)
    dayun = calc_dayun(birth, y_gz, m_gan+m_zhi, sex, longitude)
    wx = Counter()
    for p in (year, month, day, hour):
        wx[ELEMENT[p.gan]] += 1
        wx[ELEMENT[p.zhi]] += 1

    return Chart(birth, longitude, sex, tst, year, month, day, hour, fetal, life, dayun, dict(wx), warnings)

def fetal_origin(month_gz):
    # èåï¼æå¹²é¡ºä¸ä½ï¼ææ¯é¡ºä¸ä½
    g = GAN[(GAN.index(month_gz[0]) + 1) % 10]
    z = ZHI[(ZHI.index(month_gz[1]) + 3) % 12]
    return g + z

def life_palace(month_branch, hour_branch):
    # å¸¸ç¨å½å®«æ¨æ³ï¼å¯æä¸ºèµ·ç¹ï¼é¡ºæ°çæãéæ°çæ¶ï¼å­ä¸ºåäºå®«å®ä½ã
    # è¿éä½ä¸ºè¾å©ç»æï¼ä¸åä¸æ ¼å±ç¬ç«å¤æ­ã
    m = ZHI.index(month_branch)
    h = ZHI.index(hour_branch)
    idx = (14 - m - h) % 12
    return ZHI[idx]  # å½å®«æ¯ï¼å¹²æäºèééæåºå¯ç»§ç»­æ©å±

def calc_dayun(birth, year_gz, month_gz, sex, longitude):
    # é³ç·é´å¥³é¡ºï¼é´ç·é³å¥³éã
    yang_year = GAN.index(year_gz[0]) % 2 == 0
    male = sex == "ç·"
    forward = (yang_year and male) or ((not yang_year) and (not male))

    # é¡ºè¡ååºçåä¸ä¸ä¸ªèæ°ï¼éè¡ååºçåä¸ä¸ªèæ°ã
    targets = [315,345,15,45,75,105,135,165,195,225,255,285]
    terms = []
    for y in (birth.year-1, birth.year, birth.year+1):
        for target in targets:
            base = datetime(y,1,1) + timedelta(days=30*targets.index(target))
            ev = find_longitude_time(base, target)
            if ev:
                terms.append(ev)
    terms = sorted(set(terms))
    before = [x for x in terms if x < birth]
    after = [x for x in terms if x >= birth]
    if forward:
        target = after[0] if after else birth + timedelta(days=30)
    else:
        target = before[-1] if before else birth - timedelta(days=30)
    days = abs((target-birth).total_seconds()) / 86400
    start_age = days / 3.0

    mi = pair_index(month_gz)
    result = []
    for n in range(8):
        step = n + 1 if forward else -(n + 1)
        gz = ganzhi(mi + step)
        result.append({
            "åº": n + 1,
            "å¹²æ¯": gz,
            "èµ·è¿å²": round(start_age + n*10, 2),
            "é¡ºé": "é¡º" if forward else "é",
            "å¤§è¿éæ¯": gz[1]
        })
    return result