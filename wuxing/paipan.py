
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import Counter

from .calendar import (
    day_ganzhi,
    year_ganzhi_and_start,
    month_info,
    true_solar_time,
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
    return Pillar(
        name=name,
        ganzhi=gz,
        gan=gz[0],
        zhi=gz[1],
        hidden=HIDDEN[gz[1]],
        ten_god_gan=ten_god(day_gan, gz[0]),
        na_yin=na_yin(gz),
    )


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

    birth:
        当地出生时间。可以是没有时区信息的 datetime，
        也可以是带时区信息的 datetime。

    longitude:
        经度，东经为正，西经为负。

    sex:
        "男" 或 "女"。

    latitude:
        纬度，北纬为正，南纬为负。

    timezone_info:
        出生地对应的时区对象。
        新算法需要正确的时区信息。

    ephemeris_path:
        可选的 DE421 星历文件路径。

    兼容说明：
        旧调用 build_chart(birth, longitude, sex)
        暂时保留旧算法，避免尚未更新的界面立即报错。
        新版界面应传入 latitude 和 timezone_info。
    """
    if not isinstance(birth, datetime):
        raise TypeError("birth 必须是 datetime 对象。")

    warnings = []

    # 保留传入时间对应的时区，再将本地钟表时间
    # 转成无时区 datetime，供现有历法函数使用。
    if birth.tzinfo is not None:
        if timezone_info is None:
            timezone_info = birth.tzinfo

        local_birth = birth.replace(tzinfo=None)
    else:
        local_birth = birth

    try:
        longitude = float(longitude)
    except (TypeError, ValueError) as exc:
        raise ValueError("经度必须是有效数字。") from exc

    if not -180.0 <= longitude <= 180.0:
        raise ValueError("经度必须在 -180 至 180 度之间。")

    if sex not in ("男", "女"):
        raise ValueError('性别必须填写“男”或“女”。')

    # 年柱、月柱和日柱继续使用现有历法函数。
    y_gz, li_chun = year_ganzhi_and_start(local_birth)

    if li_chun and abs(
        (local_birth - li_chun).total_seconds()
    ) < 3600:
        warnings.append(
            "出生时间接近立春交界，请复核节气时刻。"
        )

    m_gan, m_zhi, _solar_lon = month_info(
        local_birth,
        y_gz[0],
    )

    d_gz = day_ganzhi(local_birth)

    # 真太阳时：优先使用新的天文计算模块。
    if latitude is not None and timezone_info is not None:
        try:
            latitude = float(latitude)

            if not -90.0 <= latitude <= 90.0:
                raise ValueError(
                    "纬度必须在 -90 至 90 度之间。"
                )

            aware_birth = local_birth.replace(
                tzinfo=timezone_info
            )

            tst = calc_true_solar_time(
                local_datetime=aware_birth,
                longitude=longitude,
                latitude=latitude,
                ephemeris_path=ephemeris_path,
            )

        except (SolarTimeError, ValueError, TypeError):
            # 新算法失败时不悄悄退回旧算法，
            # 避免把不准确的结果当成真实太阳时。
            raise

    else:
        # 兼容尚未更新的旧版 UI。
        # 这只是过渡方案，不代表精确真太阳时。
        tst = true_solar_time(
            local_birth,
            longitude,
        )

        warnings.append(
            "尚未提供纬度和时区，当前使用旧版简化真太阳时。"
            "请更新界面以启用新的天文计算。"
        )

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
            "出生时刻靠近子丑交界，"
            "建议复核真太阳时与换日口径。"
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

    wx = Counter()

    for p in (year, month, day, hour):
        wx[ELEMENT[p.gan]] += 1
        wx[ELEMENT[p.zhi]] += 1

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
        wuxing=dict(wx),
        warnings=warnings,
    )


def fetal_origin(month_gz):
    # 胎元：月干顺一位，月支顺三位。
    g = GAN[
        (GAN.index(month_gz[0]) + 1) % 10
    ]

    z = ZHI[
        (ZHI.index(month_gz[1]) + 3) % 12
    ]

    return g + z


def life_palace(month_branch, hour_branch):
    # 常用命宫推法。
    m = ZHI.index(month_branch)
    h = ZHI.index(hour_branch)

    idx = (14 - m - h) % 12

    return ZHI[idx]


def calc_dayun(
    birth,
    year_gz,
    month_gz,
    sex,
    longitude,
):
    # 阳男阴女顺；阴男阳女逆。
    yang_year = (
        GAN.index(year_gz[0]) % 2 == 0
    )

    male = sex == "男"

    forward = (
        (yang_year and male)
        or ((not yang_year) and (not male))
    )

    # 沿用项目原有的节气搜索逻辑。
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

    for y in (
        birth.year - 1,
        birth.year,
        birth.year + 1,
    ):
        for target_degree in targets:
            base = (
                datetime(y, 1, 1)
                + timedelta(
                    days=30 * targets.index(target_degree)
                )
            )

            event = find_longitude_time(
                base,
                target_degree,
            )

            if event:
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
    ) / 86400

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
