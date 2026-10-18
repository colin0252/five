# wuxing/paipan.py
"""五行排盘核心：四柱、真太阳时、胎元、命宫、大运与五行统计。"""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .calendar import (
    day_ganzhi,
    year_ganzhi_and_start,
    month_info,
    branch_for_hour,
    find_longitude_time,
)
from .astronomy.solar_time import (
    calc_true_solar_time,
    SolarTimeError,
)
from .rules import (
    GAN,
    ZHI,
    ELEMENT,
    HIDDEN,
    ten_god,
    hour_gan,
    na_yin,
    ganzhi,
    pair_index,
)
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
    """生成单柱信息。"""
    return Pillar(
        name=name,
        ganzhi=gz,
        gan=gz[0],
        zhi=gz[1],
        hidden=HIDDEN[gz[1]],
        ten_god_gan=ten_god(day_gan, gz[0]),
        na_yin=na_yin(gz),
    )
def _resolve_timezone(timezone_info):
    """
    解析出生地时区。
    接受：
    - ZoneInfo 时区对象
    - 其他有效的 datetime.tzinfo 对象
    - IANA 时区名称字符串，例如 America/Los_Angeles
    """
    if timezone_info is None:
        raise ValueError(
            "缺少出生地时区，不能计算真太阳时。"
        )
    if isinstance(timezone_info, str):
        name = timezone_info.strip()
        if not name:
            raise ValueError("出生地时区名称不能为空。")
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(
                f"无法识别出生地时区：{name}。"
                "请检查时区名称及应用中的时区数据。"
            ) from exc
    if not hasattr(timezone_info, "utcoffset"):
        raise TypeError(
            "timezone_info 必须是时区对象或 IANA 时区名称。"
        )
    return timezone_info
def _make_aware_local_datetime(local_birth, timezone_info):
    """
    将当地钟表时间与出生地时区结合。
    对于夏令时跳时造成的不存在时间，拒绝继续计算。
    对于重复出现的当地时间，默认采用 fold=0；
    如需区分重复时刻，应由界面提供额外选择。
    """
    aware_birth = local_birth.replace(
        tzinfo=timezone_info,
        fold=0,
    )
    try:
        round_trip = aware_birth.astimezone(
            __import__("datetime").timezone.utc
        ).astimezone(timezone_info)
    except Exception as exc:
        raise ValueError(
            f"无法解析出生地当地时间：{exc}"
        ) from exc
    if round_trip.replace(tzinfo=None) != local_birth:
        raise ValueError(
            "该出生时间在此地点的时区规则下不存在，"
            "可能是夏令时切换导致。请核对出生时间。"
        )
    return aware_birth
def build_chart(
    birth,
    longitude,
    sex,
    latitude=None,
    timezone_info=None,
    ephemeris_path=None,
):
    """
    生成四柱排盘。
    参数：
        birth:
            出生地当地钟表时间，datetime 对象。
            如果自带时区，仍建议显式传入出生地 timezone_info。
        longitude:
            出生地经度，东经为正，西经为负。
        sex:
            "男" 或 "女"。
        latitude:
            出生地纬度，北纬为正，南纬为负。
        timezone_info:
            出生地时区对象或 IANA 时区名称。
            例如 "America/Los_Angeles"。
        ephemeris_path:
            可选的本地 DE421 星历文件路径。
    注意：
        缺少纬度、时区或星历文件时会明确报错，
        不会静默切换到旧版简化真太阳时算法。
    """
    if not isinstance(birth, datetime):
        raise TypeError("birth 必须是 datetime 对象。")
    if sex not in ("男", "女"):
        raise ValueError('性别必须填写“男”或“女”。')
    try:
        longitude = float(longitude)
    except (TypeError, ValueError) as exc:
        raise ValueError("经度必须是有效数字。") from exc
    if not -180.0 <= longitude <= 180.0:
        raise ValueError("经度必须在 -180 至 180 度之间。")
    if latitude is None:
        raise ValueError(
            "缺少出生地纬度，不能计算真太阳时。"
        )
    try:
        latitude = float(latitude)
    except (TypeError, ValueError) as exc:
        raise ValueError("纬度必须是有效数字。") from exc
    if not -90.0 <= latitude <= 90.0:
        raise ValueError("纬度必须在 -90 至 90 度之间。")
    timezone_obj = _resolve_timezone(timezone_info)
    # birth 表示当地钟表时间。
    # 计算时重新按出生地时区解释，不使用手机当前时区。
    local_birth = birth.replace(tzinfo=None)
    aware_birth = _make_aware_local_datetime(
        local_birth,
        timezone_obj,
    )
    warnings = []
    # 使用出生地当地钟表时间计算年柱、月柱、日柱。
    # 节气算法自身仍需在 calendar.py 中继续统一时间基准。
    y_gz, li_chun = year_ganzhi_and_start(
        local_birth
    )
    if li_chun is not None:
        if abs(
            (local_birth - li_chun).total_seconds()
        ) < 3600:
            warnings.append(
                "出生时间接近立春交界，"
                "请复核节气时刻及当地时区。"
            )
    m_gan, m_zhi, _solar_lon = month_info(
        local_birth,
        y_gz[0],
    )
    d_gz = day_ganzhi(local_birth)
    # 使用 Skyfield + 本地 DE421 星历计算真太阳时。
    # 若失败则抛出错误，不使用简化算法冒充正式结果。
    try:
        tst = calc_true_solar_time(
            local_datetime=aware_birth,
            longitude=longitude,
            latitude=latitude,
            ephemeris_path=ephemeris_path,
        )
    except (SolarTimeError, ValueError, TypeError):
        raise
    except Exception as exc:
        raise SolarTimeError(
            f"真太阳时计算出现意外错误：{exc}"
        ) from exc
    # 时柱使用真太阳时。
    h_zhi = branch_for_hour(
        tst.hour,
        tst.minute,
    )
    h_gan = hour_gan(
        d_gz[0],
        h_zhi,
    )
    h_gz = h_gan + h_zhi
    if (
        local_birth.hour in (0, 1, 2, 23)
        or tst.hour in (0, 1, 2, 23)
    ):
        warnings.append(
            "出生时刻接近子丑交界，"
            "请复核真太阳时与换日口径。"
        )
    year = pillar(
        "年柱",
        y_gz,
        d_gz[0],
    )
    month = pillar(
        "月柱",
        m_gan + m_zhi,
        d_gz[0],
    )
    day = pillar(
        "日柱",
        d_gz,
        d_gz[0],
    )
    hour = pillar(
        "时柱",
        h_gz,
        d_gz[0],
    )
    fetal = fetal_origin(
        m_gan + m_zhi
    )
    life = life_palace(
        m_zhi,
        h_zhi,
    )
    dayun = calc_dayun(
        local_birth,
        y_gz,
        m_gan + m_zhi,
        sex,
        longitude,
    )
    wuxing = Counter()
    for item in (year, month, day, hour):
        wuxing[ELEMENT[item.gan]] += 1
        wuxing[ELEMENT[item.zhi]] += 1
    return Chart(
        birth=local_birth,
        longitude=longitude,
        sex=sex,
        true_solar=tst,
        year=year,
        month=month,
        day=day,
        hour=hour,
        fetal=fetal,
        life_palace=life,
        dayun=dayun,
        wuxing=dict(wuxing),
        warnings=warnings,
    )
def fetal_origin(month_gz):
    """根据月柱推算胎元。"""
    gan_index = (
        GAN.index(month_gz[0]) + 1
    ) % 10
    zhi_index = (
        ZHI.index(month_gz[1]) + 3
    ) % 12
    return GAN[gan_index] + ZHI[zhi_index]
def life_palace(month_branch, hour_branch):
    """使用项目现有规则推算命宫。"""
    month_index = ZHI.index(month_branch)
    hour_index = ZHI.index(hour_branch)
    index = (14 - month_index - hour_index) % 12
    return ZHI[index]
def calc_dayun(
    birth,
    year_gz,
    month_gz,
    sex,
    longitude,
):
    """
    根据年干阴阳与性别判断大运顺逆。
    注意：
        这里暂时保留现有节气搜索逻辑。
        节气时间基准与起运算法将在 calendar.py
        完成统一后再进一步核验。
    """
    yang_year = (
        GAN.index(year_gz[0]) % 2 == 0
    )
    male = sex == "男"
    forward = (
        (yang_year and male)
        or ((not yang_year) and (not male))
    )
    targets = [
        315,
        345,
        15,
        45,
        75,
        105,
        135,
        165,
        195,
        225,
        255,
        285,
    ]
    terms = []
    for year in (
        birth.year - 1,
        birth.year,
        birth.year + 1,
    ):
        for index, target_degree in enumerate(targets):
            # 使用约每月一个的搜索起点，之后由黄经交点算法定位。
            base = (
                datetime(year, 1, 1)
                + timedelta(days=30 * index)
            )
            event = find_longitude_time(
                base,
                target_degree,
                direction=1,
                max_days=370,
            )
            if event is not None:
                terms.append(event)
    terms = sorted(set(terms))
    before = [
        event for event in terms
        if event < birth
    ]
    after = [
        event for event in terms
        if event >= birth
    ]
    if forward:
        target = (
            after[0]
            if after
            else birth + timedelta(days=30)
        )
    else:
        target = (
            before[-1]
            if before
            else birth - timedelta(days=30)
        )
    days = abs(
        (target - birth).total_seconds()
    ) / 86400.0
    start_age = days / 3.0
    month_index = pair_index(month_gz)
    result = []
    for n in range(8):
        step = (
            n + 1
            if forward
            else -(n + 1)
        )
        gz = ganzhi(
            month_index + step
        )
        result.append({
            "序": n + 1,
            "干支": gz,
            "起运岁": round(
                start_age + n * 10,
                2,
            ),
            "顺逆": "顺" if forward else "逆",
            "大运重支": gz[1],
        })
    return result