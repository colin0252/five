# wuxing/skills.py
"""盘叔盲派技能库（离线读取 skills.zip）。

设计目标：
    1. 纯标准库（zipfile + os + re），不增加任何编译依赖；
    2. 完全离线，不联网；
    3. zip 缺失时自动降级，不影响 App 启动。

用法：
    from wuxing.skills import get_library

    lib = get_library()
    lib.load()
    for item in lib.list_skills():
        print(item["id"], item["name"])

    for hit in lib.search("羊刃", limit=10):
        print(hit["path"], hit["line"], hit["snippet"])
"""

import os
import re
import zipfile


class SkillError(Exception):
    """技能库异常。"""


SKILL_FILENAME = "SKILL.md"
ZIP_NAME = "skills.zip"

# 分组顺序与显示名
GROUP_ORDER = [
    "总控",
    "段派主干",
    "段派断事",
    "体用做功",
    "夏仲奇派",
    "金口诀",
    "工具",
    "其他",
]

GROUP_RULES = [
    ("ps-zonglun", "总控"),
    ("ps-minglizhenbao", "段派主干"),
    ("ps-zhenjue-duanju", "段派主干"),
    ("ps-duan-", "段派断事"),
    ("ps-zhenbao", "段派断事"),
    ("ps-tiwei-", "体用做功"),
    ("ps-xiazhongqi-", "夏仲奇派"),
    ("ps-jinkoujue", "金口诀"),
    ("ps-gdc-jinkoujue", "金口诀"),
    ("ps-anli-ku", "工具"),
    ("ps-shensha", "工具"),
]

FRONT_MATTER_RE = re.compile(
    r"^\ufeff?\s*---\s*\n(.*?)\n---\s*(?:\n|$)",
    re.S,
)


def _fix_zip_name(info):
    """修正 zip 内中文文件名（未置 UTF-8 标志时按 cp437 解码）。"""
    name = info.filename
    if getattr(info, "flag_bits", 0) & 0x800:
        return name
    try:
        return name.encode("cp437").decode("utf-8")
    except Exception:
        return name


def _read_text(raw):
    if isinstance(raw, str):
        text = raw
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", "ignore")
    if text.startswith("\ufeff"):
        text = text[1:]
    return text


def _parse_front_matter(text):
    """解析 YAML front matter，返回 (meta, body)。"""
    meta = {}
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return meta, text
    block = match.group(1)
    body = text[match.end():]
    current_key = None
    buffer = []

    def flush():
        if current_key is None:
            return
        value = " ".join(part.strip() for part in buffer if part.strip())
        meta[current_key] = value

    for line in block.splitlines():
        if not line.strip():
            continue
        if line.startswith((" ", "\t")) and current_key is not None:
            buffer.append(line)
            continue
        if ":" in line:
            flush()
            key, _, value = line.partition(":")
            current_key = key.strip()
            buffer = [value]
        else:
            if current_key is not None:
                buffer.append(line)
    flush()

    cleaned = {}
    for key, value in meta.items():
        value = str(value).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        cleaned[key] = value
    return cleaned, body


def _first_heading(body, fallback):
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if title:
                return title
    return fallback


def _skill_id_from_path(path):
    parts = [part for part in path.split("/") if part]
    if "references" in parts:
        index = parts.index("references")
        if index >= 1:
            return parts[index - 1]
    if len(parts) >= 2:
        return parts[-2]
    return os.path.splitext(parts[-1])[0] if parts else "skill"


def _group_of(skill_id):
    for prefix, group in GROUP_RULES:
        if skill_id.startswith(prefix):
            return group
    return "其他"


def _is_skill_file(path):
    return path.rsplit("/", 1)[-1] == SKILL_FILENAME


class SkillLibrary:
    """技能库：加载、列举、检索。"""

    def __init__(self, archive_path=None, skills_dir=None):
        self.archive_path = archive_path
        self.skills_dir = skills_dir
        self.root_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        self.skills = []
        self.references = []
        self.loaded = False
        self.load_error = None
        self.source = ""

    # --------------------------------------------------------
    # 路径
    # --------------------------------------------------------
    def candidate_archives(self):
        candidates = []
        if self.archive_path:
            candidates.append(self.archive_path)
        env_path = os.environ.get("WUXING_SKILLS_ZIP")
        if env_path:
            candidates.append(env_path)
        candidates.append(os.path.join(self.root_dir, ZIP_NAME))
        candidates.append(
            os.path.join(self.root_dir, "panshu-mangpai-skillpack.zip")
        )
        candidates.append(
            os.path.join(self.root_dir, "盘叔盲派-skillpack.zip")
        )
        result = []
        seen = set()
        for path in candidates:
            if not path:
                continue
            absolute = os.path.abspath(path)
            if absolute in seen:
                continue
            seen.add(absolute)
            if os.path.isfile(absolute):
                result.append(absolute)
        return result

    def candidate_dirs(self):
        candidates = []
        if self.skills_dir:
            candidates.append(self.skills_dir)
        env_dir = os.environ.get("WUXING_SKILLS_DIR")
        if env_dir:
            candidates.append(env_dir)
        candidates.append(os.path.join(self.root_dir, "盘叔盲派"))
        candidates.append(os.path.join(self.root_dir, "skills"))
        result = []
        for path in candidates:
            if path and os.path.isdir(path):
                result.append(os.path.abspath(path))
        return result

    # --------------------------------------------------------
    # 加载
    # --------------------------------------------------------
    def load(self, force=False):
        if self.loaded and not force:
            return True
        self.skills = []
        self.references = []
        self.load_error = None
        archives = self.candidate_archives()
        if archives:
            try:
                self._load_archive(archives[0])
                self.loaded = True
                return True
            except Exception as exc:
                self.load_error = (
                    f"读取 {os.path.basename(archives[0])} 失败："
                    f"{type(exc).__name__}: {exc}"
                )
        dirs = self.candidate_dirs()
        if dirs:
            try:
                self._load_directory(dirs[0])
                self.loaded = True
                return True
            except Exception as exc:
                self.load_error = (
                    f"读取目录 {dirs[0]} 失败："
                    f"{type(exc).__name__}: {exc}"
                )
        if self.load_error is None:
            self.load_error = (
                f"未找到 {ZIP_NAME}，请把它上传到仓库根目录。"
            )
        return False

    def _load_archive(self, path):
        self.source = os.path.basename(path)
        with zipfile.ZipFile(path) as archive:
            entries = []
            for info in archive.infolist():
                if info.is_dir():
                    continue
                name = _fix_zip_name(info)
                entries.append((name, info))
            skill_entries = [
                item for item in entries if _is_skill_file(item[0])
            ]
            reference_entries = [
                item
                for item in entries
                if item[0].lower().endswith(".md")
                and not _is_skill_file(item[0])
            ]
            for name, info in skill_entries:
                try:
                    text = _read_text(archive.read(info))
                except Exception:
                    continue
                self.skills.append(
                    self._build_skill(name, text)
                )
            for name, info in reference_entries:
                if "references/" not in name and "/references" not in name:
                    continue
                try:
                    text = _read_text(archive.read(info))
                except Exception:
                    continue
                self.references.append(
                    {
                        "path": name,
                        "skill_id": _skill_id_from_path(name),
                        "text": text,
                    }
                )
        self._sort_skills()

    def _load_directory(self, path):
        self.source = os.path.basename(path)
        for current, _dirs, files in os.walk(path):
            for filename in files:
                if not filename.lower().endswith(".md"):
                    continue
                full = os.path.join(current, filename)
                relative = os.path.relpath(full, self.root_dir)
                relative = relative.replace(os.sep, "/")
                try:
                    with open(full, "r", encoding="utf-8") as file:
                        text = file.read()
                except Exception:
                    continue
                if filename == SKILL_FILENAME:
                    self.skills.append(
                        self._build_skill(relative, text)
                    )
                elif "/references/" in relative:
                    self.references.append(
                        {
                            "path": relative,
                            "skill_id": _skill_id_from_path(relative),
                            "text": text,
                        }
                    )
        self._sort_skills()

    def _build_skill(self, path, text):
        meta, body = _parse_front_matter(text)
        skill_id = _skill_id_from_path(path)
        name = meta.get("name") or skill_id
        description = meta.get("description", "")
        return {
            "id": skill_id,
            "name": name,
            "title": _first_heading(body, name),
            "description": description,
            "group": _group_of(skill_id),
            "path": path,
            "text": text,
            "body": body,
            "length": len(text),
        }

    def _sort_skills(self):
        def key(item):
            try:
                group_index = GROUP_ORDER.index(item["group"])
            except ValueError:
                group_index = len(GROUP_ORDER)
            return (group_index, item["id"])

        self.skills.sort(key=key)

    # --------------------------------------------------------
    # 查询
    # --------------------------------------------------------
    def list_skills(self):
        """返回技能列表（不含正文，避免界面卡顿）。"""
        result = []
        for item in self.skills:
            result.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "title": item["title"],
                    "description": item["description"],
                    "group": item["group"],
                    "path": item["path"],
                    "length": item["length"],
                }
            )
        return result

    def groups(self):
        """返回 {分组: [技能...]}。"""
        data = {}
        for item in self.list_skills():
            data.setdefault(item["group"], []).append(item)
        return data

    def get_skill(self, skill_id):
        for item in self.skills:
            if item["id"] == skill_id:
                return item
        return None

    def stats(self):
        return {
            "skills": len(self.skills),
            "references": len(self.references),
            "chars": sum(item["length"] for item in self.skills)
            + sum(len(item["text"]) for item in self.references),
            "source": self.source,
            "loaded": self.loaded,
            "error": self.load_error,
        }

    # --------------------------------------------------------
    # 检索
    # --------------------------------------------------------
    @staticmethod
    def _keywords(query):
        if not query:
            return []
        parts = re.split(r"[\s,，、;；]+", str(query).strip())
        return [part for part in parts if part]

    def search(self, query, limit=30):
        """全文检索技能正文与 references。

        多个关键词用空格分隔，要求全部命中（AND）。
        返回：路径、行号、片段、所属技能。
        """
        keywords = self._keywords(query)
        if not keywords:
            return []
        lowered = [keyword.lower() for keyword in keywords]
        results = []
        documents = [
            (item["path"], item["id"], item["text"])
            for item in self.skills
        ] + [
            (item["path"], item["skill_id"], item["text"])
            for item in self.references
        ]
        for path, skill_id, text in documents:
            lines = text.splitlines()
            for index, line in enumerate(lines):
                lower_line = line.lower()
                if all(keyword in lower_line for keyword in lowered):
                    results.append(
                        {
                            "path": path,
                            "skill_id": skill_id,
                            "line": index + 1,
                            "snippet": line.strip()[:160],
                        }
                    )
                    if len(results) >= limit:
                        return results
        return results

    def match_skills(self, query, limit=8):
        """按名称与描述做路由匹配，返回带分数的技能。"""
        keywords = self._keywords(query)
        if not keywords:
            return []
        lowered = [keyword.lower() for keyword in keywords]
        scored = []
        for item in self.skills:
            haystack = (
                item["id"]
                + " "
                + item["name"]
                + " "
                + item["description"]
            ).lower()
            score = 0
            for keyword in lowered:
                if keyword in item["id"].lower():
                    score += 5
                if keyword in item["name"].lower():
                    score += 3
                if keyword in item["description"].lower():
                    score += 1
            if score > 0:
                scored.append(
                    (score, item)
                )
        scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
        return [
            {
                "id": item["id"],
                "name": item["name"],
                "description": item["description"],
                "group": item["group"],
                "score": score,
            }
            for score, item in scored[:limit]
        ]

    def get_reference(self, skill_id):
        """返回某技能下的全部 references 文本。"""
        return [
            item
            for item in self.references
            if item["skill_id"] == skill_id
        ]


_LIBRARY = None


def get_library(force_reload=False):
    """返回全局技能库单例。"""
    global _LIBRARY
    if _LIBRARY is None:
        _LIBRARY = SkillLibrary()
    if force_reload:
        _LIBRARY.load(force=True)
    return _LIBRARY
