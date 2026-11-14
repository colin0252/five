# wuxing/ai.py
"""AI 解读：四柱 + 技能库条文 → 提示词 → 中转服务 → 大模型解读。

设计约束：
    1. 只用标准库 urllib.request（不引入 requests，避免多编译 recipe）；
    2. 大模型 API Key 不放在 App 里，由中转服务（Cloudflare Worker /
       腾讯云 SCF）保管；
    3. 技能库条文按问题做本地路由，只把相关条文送进提示词，
       控制 token 消耗。

中转服务约定（下一轮的 Worker 按此实现）：
    请求  POST <endpoint>
          Header: Content-Type: application/json
                  Authorization: Bearer <token>
          Body:   {
                    "model": "deepseek-v4-flash",
                    "messages": [{"role": "system", "content": "..."},
                                 {"role": "user", "content": "..."}],
                    "temperature": 0.7
                  }
    响应  200 {"text": "解读内容"}
          或 OpenAI 风格 {"choices": [{"message": {"content": "..."}}]}
    错误  非 200，body 里带 {"error": "..."}
"""

import json
import os
import ssl
import urllib.error
import urllib.request
from datetime import datetime


class AIError(Exception):
    """AI 解读异常。"""


DEFAULT_MODEL = "deepseek-v4-flash"
# 送进提示词的技能条文上限（字符数），避免超长
MAX_SKILL_CHARS = 12000
# 单次解读超时（秒）
DEFAULT_TIMEOUT = 90

CONFIG_NAME = "ai_config.json"


# ============================================================
# 配置
# ============================================================
def default_config():
    return {
        "endpoint": "",
        "token": "",
        "model": DEFAULT_MODEL,
    }


def load_config(data_dir):
    """读取本地 ai_config.json；不存在时返回默认配置。"""
    path = os.path.join(data_dir, CONFIG_NAME)
    config = default_config()
    if not os.path.isfile(path):
        return config
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, dict):
            for key in config:
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    config[key] = value.strip()
    except Exception:
        pass
    return config


def save_config(data_dir, config):
    """保存配置到本地。"""
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, CONFIG_NAME)
    temp_path = path + ".tmp"
    payload = default_config()
    for key in payload:
        value = (config or {}).get(key)
        if isinstance(value, str):
            payload[key] = value.strip()
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def is_configured(config):
    return bool(
        (config or {}).get("endpoint", "").strip()
        and (config or {}).get("token", "").strip()
    )


# ============================================================
# SSL
# ============================================================
def _ssl_context():
    """优先用 certifi 证书；没有就用系统默认。"""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


# ============================================================
# 命盘信息
# ============================================================
def chart_summary(chart, gender="男"):
    """把 Chart 对象转成简洁的文字摘要（给提示词用）。"""
    parts = []
    parts.append(f"性别：{gender}")
    parts.append(
        "四柱："
        f"{chart.year.ganzhi} "
        f"{chart.month.ganzhi} "
        f"{chart.day.ganzhi} "
        f"{chart.hour.ganzhi}"
    )
    parts.append(f"日主：{chart.day.gan}")
    parts.append(
        f"排盘时间：{chart.birth:%Y-%m-%d %H:%M}"
    )
    parts.append(
        f"真太阳时：{chart.true_solar:%Y-%m-%d %H:%M}"
    )
    pillars = (
        ("年柱", chart.year),
        ("月柱", chart.month),
        ("日柱", chart.day),
        ("时柱", chart.hour),
    )
    lines = []
    for name, pillar in pillars:
        hidden = "、".join(pillar.hidden)
        lines.append(
            f"{name}{pillar.ganzhi}"
            f"（天干十神：{pillar.ten_god_gan}，"
            f"藏干：{hidden}，纳音：{pillar.na_yin}）"
        )
    parts.append("四柱明细：" + "；".join(lines))
    wuxing = "、".join(
        f"{element}{chart.wuxing.get(element, 0)}"
        for element in ("木", "火", "土", "金", "水")
    )
    parts.append("五行统计：" + wuxing)
    parts.append(f"胎元：{chart.fetal}")
    parts.append(f"命宫：{chart.life_palace}")
    if chart.dayun:
        dayun_text = "；".join(
            f"{item.get('序', '')}.{item.get('干支', '')}"
            f"（{item.get('起运岁', '')}岁，{item.get('顺逆', '')}）"
            for item in chart.dayun[:8]
        )
        parts.append("大运：" + dayun_text)
    if chart.warnings:
        parts.append("提示：" + "；".join(chart.warnings))
    return "\n".join(parts)


def feature_keywords(chart, gender="男"):
    """根据命盘特征生成技能路由关键词。"""
    keywords = ["八字", "断命"]
    keywords.append("男命" if gender == "男" else "女命")
    keywords.append(chart.day.gan + "日主")
    # 五行偏旺的取象
    if chart.wuxing:
        try:
            strongest = max(
                ("木", "火", "土", "金", "水"),
                key=lambda element: chart.wuxing.get(element, 0),
            )
            keywords.append(strongest + "旺")
        except Exception:
            pass
    return keywords


# ============================================================
# 提示词
# ============================================================
SYSTEM_PROMPT = """你是「五行排盘」App 内置的盲派命理解读助手，服务于段建业—郝金阳体系的学习者。

工作要求：
1. 只依据用户提供的四柱信息和下方给出的技能库条文推理，不得自行编造流派规则。
2. 先给结论，再给推理依据；推理要落在具体的干支作用（刑冲合穿墓、宾主、体用、做功）上。
3. 如果条文中没有对应依据，明确说「技能库中暂无对应条文」，不要硬套。
4. 涉及健康、生死、官司等重大事项时，只作传统文化角度的提示，不作医学或法律建议。
5. 结尾统一附一句：仅供传统文化研究参考，不构成人生决断依据。

输出格式：
【结论】一两句话点明层次或趋势。
【依据】分条列出，每条对应干支关系或引用条文要点。
【补充】需要核实的信息（如出生时辰是否准确）。
"""


def _truncate_skills(items, limit=MAX_SKILL_CHARS):
    """把技能条文拼成一段文本，超长时截断。"""
    blocks = []
    used = 0
    for item in items:
        title = item.get("id") or item.get("name") or "技能"
        text = str(item.get("body") or item.get("text") or "").strip()
        if not text:
            continue
        block = f"《{title}》\n{text}"
        if used + len(block) > limit:
            remain = limit - used
            if remain > 400:
                blocks.append(block[:remain] + "\n……（条文过长已截断）")
            break
        blocks.append(block)
        used += len(block)
    return "\n\n".join(blocks)


def build_messages(
    chart,
    gender="男",
    question="",
    skill_items=None,
    extra_keywords=None,
):
    """组装发给大模型的 messages。"""
    question_text = (question or "").strip() or "整体看命：层次、事业财运、婚姻、健康。"
    summary = chart_summary(chart, gender)
    skills_text = _truncate_skills(skill_items or [])
    user_parts = [
        "【命盘信息】",
        summary,
        "",
        "【求测问题】",
        question_text,
    ]
    if extra_keywords:
        user_parts.extend(
            ["", "【命盘特征关键词】", "、".join(extra_keywords)]
        )
    if skills_text:
        user_parts.extend(
            ["", "【可用技能库条文】", skills_text]
        )
    else:
        user_parts.extend(
            ["", "【可用技能库条文】", "（技能库未加载，请只做基础排盘说明，不给断语。）"]
        )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


# ============================================================
# 网络请求
# ============================================================
def _post_json(url, payload, headers, timeout):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(
        request,
        timeout=timeout,
        context=_ssl_context(),
    ) as response:
        raw = response.read()
    text = raw.decode("utf-8", "ignore")
    try:
        return json.loads(text)
    except Exception as exc:
        raise AIError(
            "中转服务返回的不是 JSON：" + text[:200]
        ) from exc


def _extract_text(data):
    """从响应中取出文本，兼容多种格式。"""
    if isinstance(data, str):
        return data
    if not isinstance(data, dict):
        raise AIError("中转服务返回格式无法识别。")
    for key in ("text", "content", "answer", "reply"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
            text = first.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    error = data.get("error")
    if error:
        raise AIError(str(error))
    raise AIError("中转服务没有返回解读内容。")


def call_relay(config, messages, timeout=DEFAULT_TIMEOUT):
    """调用中转服务，返回解读文本。"""
    endpoint = (config or {}).get("endpoint", "").strip()
    token = (config or {}).get("token", "").strip()
    model = (config or {}).get("model", "").strip() or DEFAULT_MODEL
    if not endpoint:
        raise AIError("尚未填写中转服务地址。")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        # Cloudflare 会拦截 Python 默认的 User-Agent（Error 1010），
        # 伪装成 iPhone Safari 的 UA，避免请求在边缘节点被挡掉。
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        data = _post_json(endpoint, payload, headers, timeout)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "ignore")[:300]
        except Exception:
            detail = ""
        if exc.code == 401:
            raise AIError(
                "中转服务鉴权失败（401），请检查 Token。"
            ) from exc
        if exc.code == 429:
            raise AIError(
                "请求过于频繁或额度不足（429）。"
            ) from exc
        if exc.code == 403 and "1010" in detail:
            raise AIError(
                "中转服务被 Cloudflare 拦截（Error 1010）。"
                "请确认用的是最新版 App（新版已伪装浏览器标识）。"
            ) from exc
        raise AIError(
            f"中转服务返回 HTTP {exc.code}。{detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise AIError(
            "网络连接失败：" + str(getattr(exc, "reason", exc))
        ) from exc
    except TimeoutError as exc:
        raise AIError("请求超时，请检查网络后重试。") from exc
    return _extract_text(data)


def interpret(
    chart,
    gender,
    question,
    config,
    library=None,
    skill_limit=3,
):
    """一次性完成：路由技能 → 组装提示词 → 调用 → 返回文本。"""
    keywords = feature_keywords(chart, gender)
    query = " ".join(
        [question or "", " ".join(keywords)]
    ).strip()
    skill_items = []
    if library is not None:
        try:
            library.load()
            matched = library.match_skills(query, limit=skill_limit)
            for item in matched:
                full = library.get_skill(item["id"])
                if full:
                    skill_items.append(full)
            # 总控路由表始终带上（若有）
            zonglun = library.get_skill("ps-zonglun")
            if zonglun and zonglun not in skill_items:
                skill_items.insert(0, zonglun)
        except Exception:
            skill_items = []
    messages = build_messages(
        chart,
        gender,
        question,
        skill_items,
        extra_keywords=keywords,
    )
    return call_relay(config, messages)


def describe_config(config):
    """给界面显示用的配置状态文字。"""
    config = config or {}
    endpoint = config.get("endpoint", "").strip()
    model = config.get("model", "").strip() or DEFAULT_MODEL
    if not endpoint:
        return "未配置（需要中转服务地址）"
    host = endpoint
    try:
        host = endpoint.split("://", 1)[-1].split("/", 1)[0]
    except Exception:
        pass
    return f"{host} · {model}"
