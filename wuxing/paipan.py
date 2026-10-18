
# wuxing/paipan.py
"""五行排盘核心：四柱、真太阳时、胎元、命宫、大运与五行统计。"""

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .calendar import (
    day_ganzhi,
    year_ganzhi_and_start,
    month_info,
    branch_for_hour,
    find_longitude_time,
    solar_longitude,
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
    """解析出生地时区。"""
    if timezone_info is None:
        raise ValueError(
            "缺少出生地时区，不能准确计算排盘。"
        )

    if isinstance(timezone_info, str):
        name = timezone_info.strip()

        if not name:
            raise ValueError("出生地时区名称不能为空。")

        try:
            return ZoneInfo(name)
        except (
            ZoneInfoNotFoundError,
            ValueError,
            OSError,
        ) as exc:
            raise ValueError(
                f"无法识别出生地时区：{name}。"
                "请检查应用中的时区数据。"
            ) from exc

    if not hasattr(timezone_info, "utcoffset"):
        raise TypeError(
            "timezone_info 必须是时区对象或 IANA 时区名称。"
        )

    return timezone_info


def _make_aware_local_datetime(local_birth, timezone_obj):
    """
    将当地钟表时间转换为带时区的 datetime。

    不存在的夏令时本地时间会被拒绝。
    夏令时回拨产生的重复时间暂时采用 fold=0。
    """
    aware_birth = local_birth.replace(
        tzinfo=timezone_obj,
        fold=0,
    )

    try:
        round_trip = (
            aware_birth
            .astimezone(timezone.utc)
            .astimezone(timezone_obj)
        )
    except Exception as exc:
        raise ValueError(
            f"无法解析出生地当地时间：{exc}"
        ) from exc

    if round_trip.replace(tzinfo=None) != local_birth:
        raise ValueError(
            "该时间在此地点的时区规则下不存在，"
            "可能是夏令时切换造成的。请核对出生时间。"
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
    """生成四柱排盘。"""

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

    # 输入是出生地当地钟表时间。
    local_birth = birth.replace(tzinfo=None)

    aware_birth = _make_aware_local_datetime(
        local_birth,
        timezone_obj,
    )

    birth_utc = aware_birth.astimezone(timezone.utc)
    warnings = []

    # 年柱：以立春为分界。
    y_gz, li_chun = year_ganzhi_and_start(aware_birth)

    if li_chun is not None:
        li_chun_utc = li_chun.astimezone(timezone.utc)

        if abs(
            (birth_utc - li_chun_utc).total_seconds()
        ) < 3600:
            warnings.append(
                "出生时间接近立春交界，"
                "请复核节气时刻及当地时区。"
            )

    # 月柱：使用出生时刻对应的太阳黄经。
    m_gan, m_zhi, _solar_lon = month_info(
        aware_birth,
        y_gz[0],
    )

    # 日柱按当地钟表日期和项目换日规则计算。
    d_gz = day_ganzhi(local_birth)

    # 真太阳时：需要星历、经纬度和出生地时区。
    tst = calc_true_solar_time(
        local_datetime=aware_birth,
        longitude=longitude,
        latitude=latitude,
        ephemeris_path=ephemeris_path,
    )

    # 时柱采用真太阳时。
    h_zhi = branch_for_hour(
        tst.hour,
        tst.minute,
    )

    h_gan = hour_gan(d_gz[0], h_zhi)
    h_gz = h_gan + h_zhi

    if (
        local_birth.hour in (0, 1, 2, 23)
        or tst.hour in (0, 1, 2, 23)
    ):
        warnings.append(
            "出生时刻接近子丑交界，"
            "请复核真太阳时与换日口径。"
        )

    year = pillar("年柱", y_gz, d_gz[0])
    month = pillar("月柱", m_gan + m_zhi, d_gz[0])
    day = pillar("日柱", d_gz, d_gz[0])
    hour = pillar("时柱", h_gz, d_gz[0])

    fetal = fetal_origin(m_gan + m_zhi)
    life = life_palace(m_zhi, h_zhi)

    dayun = calc_dayun(
        aware_birth,
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


def _nearest_solar_term(birth_utc, direction):
    """
    搜索出生时刻之前或之后最近的节气交点。

    二十四节气的太阳黄经间隔为 15 度。
    返回 UTC datetime；搜索失败时返回 None。
    """
    if direction not in (-1, 1):
        raise ValueError("direction 必须为 1 或 -1。")

    longitude = solar_longitude(birth_utc)

    if direction == 1:
        # 向未来：选择严格大于当前黄经的下一个 15 度交点。
        target = (
            (math.floor(longitude / 15.0) + 1) * 15
        ) % 360
    else:
        # 向过去：选择严格小于当前黄经的上一个 15 度交点。
        target = (
            (math.ceil(longitude / 15.0) - 1) * 15
        ) % 360

    return find_longitude_time(
        birth_utc,
        target,
        direction=direction,
        max_days=20,
    )


def calc_dayun(
    birth,
    year_gz,
    month_gz,
    sex,
    longitude,
):
    """
    根据年干阴阳与性别判断大运顺逆。

    birth 必须是带出生地时区的 datetime。
    起运方向按常见规则：
      阳年男、阴年女顺行；
      阴年男、阳年女逆行。

    起运时间以出生时刻到相邻节气的时间差估算，
    按传统常用换算：三天折一年。
    """
    if not isinstance(birth, datetime):
        raise TypeError("birth 必须是 datetime 对象。")

    if birth.tzinfo is None or birth.utcoffset() is None:
        raise ValueError(
            "计算大运时需要带出生地时区的出生时间。"
        )

    if sex not in ("男", "女"):
        raise ValueError('性别必须填写“男”或“女”。')

    birth_utc = birth.astimezone(timezone.utc)

    yang_year = GAN.index(year_gz[0]) % 2 == 0
    male = sex == "男"

    forward = (
        (yang_year and male)
        or ((not yang_year) and (not male))
    )

    direction = 1 if forward else -1

    # 顺行取出生后最近节气，逆行取出生前最近节气。
    term = _nearest_solar_term(
        birth_utc,
        direction,
    )

    if term is None:
        raise ValueError(
            "无法找到相邻节气，暂时不能计算起运时间。"
        )

    days_to_term = abs(
        (term - birth_utc).total_seconds()
    ) / 86400.0

    # 常见传统换算：三天折一年。
    start_age = days_to_term / 3.0

    month_index = pair_index(month_gz)
    result = []

    for n in range(8):
        step = (
            n + 1
            if forward
            else -(n + 1)
        )

        gz = ganzhi(month_index + step)

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
