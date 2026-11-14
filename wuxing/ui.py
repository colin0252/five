# wuxing/ui.py
import os
import json
import re
from datetime import datetime
from threading import Thread
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner

from .paipan import build_chart
from .location import get_location, resolve_location, get_timezone
from .rules import ELEMENT

try:
    from .lunar import solar_to_lunar
except Exception:
    solar_to_lunar = None

try:
    from .skills import get_library
except Exception:
    def get_library(*_args, **_kwargs):
        raise RuntimeError("技能库模块不可用")

try:
    from . import ai as ai_module
except Exception:
    ai_module = None

try:
    from .qimen import build_qimen
except Exception:
    build_qimen = None


# ============================================================
# 颜色与字体
# ============================================================
BG = (0.960, 0.950, 0.928, 1)
CARD = (1.000, 0.995, 0.980, 1)
CARD_SOFT = (0.968, 0.958, 0.938, 1)
GREEN = (0.070, 0.290, 0.230, 1)
GREEN_LIGHT = (0.895, 0.930, 0.890, 1)
GOLD = (0.620, 0.440, 0.120, 1)
TEXT = (0.170, 0.190, 0.180, 1)
MUTED = (0.440, 0.470, 0.455, 1)
LINE = (0.880, 0.850, 0.790, 1)
ORANGE = (0.760, 0.400, 0.120, 1)
RED = (0.780, 0.200, 0.160, 1)

# AI 中转服务的默认地址与模型（口令由用户自己填写）
AI_DEFAULT_ENDPOINT = "https://wuxing-ai.zkn12306.workers.dev"
AI_DEFAULT_MODEL = "deepseek-chat"

# 五行配色：木绿、火红、土棕、金赭、水蓝
ELEMENT_COLORS = {
    "木": (0.090, 0.420, 0.260, 1),
    "火": (0.780, 0.200, 0.160, 1),
    "土": (0.545, 0.355, 0.115, 1),
    "金": (0.720, 0.520, 0.100, 1),
    "水": (0.100, 0.320, 0.580, 1),
}

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
FONT_PATH = os.path.join(
    PROJECT_ROOT,
    "fonts",
    "NotoSansSC-Regular.ttf",
)
FONT_ARGS = (
    {"font_name": FONT_PATH}
    if os.path.isfile(FONT_PATH)
    else {}
)


def font_args():
    return FONT_ARGS.copy()


def elem_color(char):
    """按干支对应的五行返回颜色。"""
    element = ELEMENT.get(str(char), "")
    return ELEMENT_COLORS.get(element, TEXT)


def make_label(text="", **kwargs):
    kwargs.setdefault("color", TEXT)
    kwargs.setdefault("font_size", dp(14))
    kwargs.setdefault("halign", "left")
    kwargs.setdefault("valign", "middle")
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", dp(32))
    kwargs.update(font_args())
    label = Label(text=str(text), **kwargs)

    def update_text_size(instance, *_):
        instance.text_size = (instance.width, None)

    label.bind(size=update_text_size)
    return label


def make_button(text, **kwargs):
    kwargs.setdefault("font_size", dp(14))
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", dp(44))
    kwargs.setdefault("background_normal", "")
    kwargs.setdefault("background_down", "")
    kwargs.setdefault("background_color", GREEN)
    kwargs.setdefault("color", (1, 1, 1, 1))
    kwargs.update(font_args())
    return Button(text=text, **kwargs)


def section_title(text):
    return make_label(
        text,
        font_size=dp(13),
        bold=True,
        color=GREEN,
        height=dp(26),
    )


def make_circle_button(text, diameter=40, bg=None, fg=None, on_release=None):
    """圆形小按钮（用 Card 绘制圆角实现）。"""
    if bg is None:
        bg = CARD_SOFT
    if fg is None:
        fg = GREEN
    card = Card(
        orientation="vertical",
        size_hint=(None, None),
        size=(dp(diameter), dp(diameter)),
        padding=[dp(1), dp(2), dp(1), dp(2)],
        card_color=bg,
        radius=diameter / 2.0,
    )
    card.add_widget(
        make_label(
            text,
            font_size=dp(diameter * 0.38),
            bold=True,
            color=fg,
            halign="center",
            height=dp(diameter - 6),
        )
    )
    if on_release is not None:
        def _on_touch(widget, touch):
            if widget.collide_point(*touch.pos):
                on_release()
                return True
            return False
        card.bind(on_touch_down=_on_touch)
    return card


def format_birth_date(time_text):
    """把保存的时间格式化成 1988年06月25日。"""
    try:
        value = datetime.strptime(
            str(time_text).strip(),
            "%Y-%m-%d %H:%M",
        )
        return f"{value.year}年{value.month:02d}月{value.day:02d}日"
    except Exception:
        return str(time_text)


def make_input(**kwargs):
    kwargs.setdefault("font_size", dp(16))
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", dp(46))
    kwargs.setdefault("multiline", False)
    kwargs.setdefault("background_normal", "")
    kwargs.setdefault("background_active", "")
    kwargs.setdefault("background_color", CARD_SOFT)
    kwargs.setdefault("foreground_color", TEXT)
    kwargs.setdefault("cursor_color", GREEN)
    kwargs.setdefault(
        "padding", [dp(12), dp(12), dp(12), dp(12)]
    )
    kwargs.update(font_args())
    return TextInput(**kwargs)


class Card(BoxLayout):
    def __init__(self, card_color=CARD, radius=14, **kwargs):
        super().__init__(**kwargs)
        self.radius = dp(radius)
        with self.canvas.before:
            self.bg_color_instruction = Color(*card_color)
            self.bg_rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[self.radius],
            )
        self.bind(pos=self.update_bg, size=self.update_bg)

    def update_bg(self, *_):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size


class Divider(Widget):
    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(1))
        super().__init__(**kwargs)
        with self.canvas.before:
            self.line_color = Color(*LINE)
            self.line_rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(0.5)],
            )
        self.bind(pos=self.update_line, size=self.update_line)

    def update_line(self, *_):
        self.line_rect.pos = self.pos
        self.line_rect.size = self.size


def safe_top():
    """iPhone 刘海/状态栏需要预留的顶部高度。"""
    try:
        from kivy.utils import platform
        if platform == "ios":
            return dp(50)
    except Exception:
        pass
    return 0


def safe_bottom():
    """底部 Home 指示条预留高度。"""
    try:
        from kivy.utils import platform
        if platform == "ios":
            return dp(18)
    except Exception:
        pass
    return 0


def safe_zone(timezone_name):
    """将时区名称转换为 ZoneInfo；不可用时返回 None。"""
    if not timezone_name or not isinstance(timezone_name, str):
        return None
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


def valid_coordinates(latitude, longitude):
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return False
    return (
        -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


# ============================================================
# 时间选择 / 地点选择
# ============================================================
CITY_LIST = [
    ("北京市", 39.9042, 116.4074, "Asia/Shanghai"),
    ("天津市", 39.0842, 117.2009, "Asia/Shanghai"),
    ("上海市", 31.2304, 121.4737, "Asia/Shanghai"),
    ("重庆市", 29.5630, 106.5516, "Asia/Shanghai"),
    ("广州市", 23.1291, 113.2644, "Asia/Shanghai"),
    ("深圳市", 22.5431, 114.0579, "Asia/Shanghai"),
    ("成都市", 30.5728, 104.0668, "Asia/Shanghai"),
    ("杭州市", 30.2741, 120.1551, "Asia/Shanghai"),
    ("南京市", 32.0603, 118.7969, "Asia/Shanghai"),
    ("武汉市", 30.5928, 114.3055, "Asia/Shanghai"),
    ("西安市", 34.3416, 108.9398, "Asia/Shanghai"),
    ("苏州市", 31.2989, 120.5853, "Asia/Shanghai"),
    ("沈阳市", 41.8057, 123.4315, "Asia/Shanghai"),
    ("哈尔滨市", 45.8038, 126.5350, "Asia/Shanghai"),
    ("长沙市", 28.2282, 112.9388, "Asia/Shanghai"),
    ("郑州市", 34.7466, 113.6254, "Asia/Shanghai"),
    ("福州市", 26.0745, 119.2965, "Asia/Shanghai"),
    ("昆明市", 25.0389, 102.7183, "Asia/Shanghai"),
    ("乌鲁木齐市", 43.8256, 87.6168, "Asia/Shanghai"),
    ("拉萨市", 29.6520, 91.1721, "Asia/Shanghai"),
]


def _month_days(year, month):
    if month == 2:
        if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0:
            return 29
        return 28
    if month in (4, 6, 9, 11):
        return 30
    return 31


class TimePickerPopup(Popup):
    """年月日时分选择弹窗（仿 iOS 时间输入）。"""

    def __init__(self, initial_text="", on_done=None, mode="datetime", **kwargs):
        moment = self._parse(initial_text)
        kwargs.setdefault("title", "时间输入")
        kwargs.setdefault("size_hint", (0.96, 0.66))
        kwargs.setdefault("auto_dismiss", False)
        kwargs.setdefault("separator_color", (0, 0, 0, 0))
        if FONT_ARGS:
            kwargs.setdefault("title_font", FONT_ARGS["font_name"])
        super().__init__(**kwargs)
        self._on_done = on_done
        self._mode = mode

        content = BoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(8),
        )
        columns = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(160),
            spacing=dp(3),
        )
        fields = [
            ("year", "年", [str(y) for y in range(1930, 2036)], moment.year),
            ("month", "月", [str(m) for m in range(1, 13)], moment.month),
            ("day", "日", [str(d) for d in range(1, 32)], moment.day),
        ]
        if mode == "datetime":
            fields.append(
                ("hour", "时", ["%02d" % h for h in range(24)], moment.hour)
            )
            fields.append(
                ("minute", "分", ["%02d" % m for m in range(60)], moment.minute)
            )

        self._spinners = {}
        for key, label, values, current in fields:
            column = BoxLayout(orientation="vertical", spacing=dp(0))
            column.add_widget(
                make_label(
                    label,
                    font_size=dp(11),
                    color=MUTED,
                    halign="center",
                    height=dp(20),
                )
            )
            spinner = Spinner(
                text=str(current),
                values=values,
                size_hint_y=None,
                height=dp(46),
                background_normal="",
                background_down="",
                background_color=CARD_SOFT,
                color=TEXT,
                font_size=dp(14),
                **font_args()
            )
            spinner.bind(
                text=lambda inst, value, k=key: self._on_change(k, value)
            )
            column.add_widget(spinner)
            columns.add_widget(column)
            self._spinners[key] = spinner
        content.add_widget(columns)

        buttons = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(44),
            spacing=dp(8),
        )
        cancel = make_button(
            "取消",
            height=dp(44),
            font_size=dp(14),
            background_color=(0.60, 0.60, 0.58, 1),
        )
        done = make_button("完成", height=dp(44), font_size=dp(14))
        buttons.add_widget(cancel)
        buttons.add_widget(done)
        content.add_widget(buttons)
        self.content = content
        cancel.bind(on_release=lambda *_: self.dismiss())
        done.bind(on_release=self._finish)

    @staticmethod
    def _parse(text):
        if isinstance(text, datetime):
            return text
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(str(text).strip(), fmt)
            except Exception:
                continue
        return datetime.now()

    def _on_change(self, key, value):
        if key not in ("year", "month"):
            return
        try:
            year = int(self._spinners["year"].text)
            month = int(self._spinners["month"].text)
        except Exception:
            return
        day_spinner = self._spinners.get("day")
        if day_spinner is None:
            return
        days = _month_days(year, month)
        day_spinner.values = [str(d) for d in range(1, days + 1)]
        try:
            if int(day_spinner.text) > days:
                day_spinner.text = str(days)
        except Exception:
            day_spinner.text = str(days)

    def _finish(self, *_):
        try:
            year = int(self._spinners["year"].text)
            month = int(self._spinners["month"].text)
            day = int(self._spinners["day"].text)
        except Exception:
            self.dismiss()
            return
        if self._mode == "date":
            text = "%04d-%02d-%02d" % (year, month, day)
        else:
            try:
                hour = int(self._spinners["hour"].text)
                minute = int(self._spinners["minute"].text)
            except Exception:
                hour, minute = 0, 0
            text = "%04d-%02d-%02d %02d:%02d" % (
                year,
                month,
                day,
                hour,
                minute,
            )
        if self._on_done is not None:
            self._on_done(text)
        self.dismiss()


class CityPickerPopup(Popup):
    """内置城市列表选择弹窗。"""

    def __init__(self, on_pick=None, **kwargs):
        kwargs.setdefault("title", "地点")
        kwargs.setdefault("size_hint", (0.9, 0.7))
        kwargs.setdefault("auto_dismiss", False)
        if FONT_ARGS:
            kwargs.setdefault("title_font", FONT_ARGS["font_name"])
        super().__init__(**kwargs)
        self._on_pick = on_pick
        self._selected = 0
        self._buttons = []

        content = BoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(6),
        )
        grid = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for index, item in enumerate(CITY_LIST):
            name, lat, lon, tz = item
            button = make_button(
                name + "    " + ("%.2f, %.2f" % (lat, lon)),
                height=dp(42),
                font_size=dp(12),
                background_color=GREEN if index == 0 else CARD_SOFT,
                color=(1, 1, 1, 1) if index == 0 else TEXT,
            )
            button.bind(
                on_release=lambda _btn, i=index: self._select(i)
            )
            grid.add_widget(button)
            self._buttons.append(button)
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(2))
        scroll.add_widget(grid)
        content.add_widget(scroll)

        bottom = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(44),
            spacing=dp(8),
        )
        cancel = make_button(
            "取消",
            height=dp(44),
            font_size=dp(13),
            background_color=(0.60, 0.60, 0.58, 1),
        )
        cancel.bind(on_release=lambda *_: self.dismiss())
        bottom.add_widget(cancel)
        confirm = make_button("确定", height=dp(44), font_size=dp(13))
        confirm.bind(on_release=self._confirm)
        bottom.add_widget(confirm)
        content.add_widget(bottom)
        self.content = content

    def _select(self, index):
        self._selected = index
        for i, button in enumerate(self._buttons):
            active = i == index
            button.background_color = GREEN if active else CARD_SOFT
            button.color = (1, 1, 1, 1) if active else TEXT

    def _confirm(self, *_):
        name, lat, lon, tz = CITY_LIST[self._selected]
        if self._on_pick is not None:
            self._on_pick(name, lat, lon, tz)
        self.dismiss()


# ============================================================
# 排盘结果格式化（详情页使用）
# ============================================================
def get_pillars(chart):
    return [
        ("年", chart.year),
        ("月", chart.month),
        ("日", chart.day),
        ("时", chart.hour),
    ]


def format_chart(chart, title="时间局"):
    if isinstance(chart, str):
        return chart
    if isinstance(chart, dict):
        return json.dumps(
            chart,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    try:
        lines = [
            title,
            "",
            f"出生时间：{chart.birth:%Y-%m-%d %H:%M}",
            f"真太阳时：{chart.true_solar:%Y-%m-%d %H:%M}",
            f"经度：{chart.longitude:.4f}°",
            "",
            "四柱",
            "----------------",
        ]
        for name, pillar in (
            ("年柱", chart.year),
            ("月柱", chart.month),
            ("日柱", chart.day),
            ("时柱", chart.hour),
        ):
            lines.extend([
                f"{name}：{pillar.ganzhi}",
                f"天干：{pillar.gan}",
                f"地支：{pillar.zhi}",
                f"天干十神：{pillar.ten_god_gan}",
                f"纳音：{pillar.na_yin}",
                f"藏干：{'、'.join(pillar.hidden)}",
                "",
            ])
        lines.extend([
            f"胎元：{chart.fetal}",
            f"命宫地支：{chart.life_palace}",
            "",
            "五行统计",
            "----------------",
        ])
        for element in ("木", "火", "土", "金", "水"):
            lines.append(
                f"{element}：{chart.wuxing.get(element, 0)}"
            )
        lines.extend(["", "大运", "----------------"])
        for item in chart.dayun:
            lines.append(
                f"第{item.get('序', '')}步："
                f"{item.get('干支', '')} "
                f"{item.get('起运岁', '')}岁起运 "
                f"{item.get('顺逆', '')}行"
            )
        if chart.warnings:
            lines.extend(["", "注意事项", "----------------"])
            for warning in chart.warnings:
                lines.append(f"• {warning}")
        lines.extend([
            "",
            "说明：排盘结果仅供参考。"
            "节气交界、真太阳时和换日口径可能影响结果。",
        ])
        return "\n".join(lines)
    except Exception as exc:
        return (
            "排盘结果格式化失败\n"
            f"{type(exc).__name__}: {exc}"
        )


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        app = App.get_running_app()
        self.data_dir = app.user_data_dir
        self.store_path = os.path.join(
            self.data_dir,
            "time_charts.json",
        )
        self.location_path = os.path.join(
            self.data_dir,
            "location.json",
        )
        self.settings_path = os.path.join(
            self.data_dir,
            "settings.json",
        )
        self.solar_mode = "mean"
        self.saved_charts = self.load_saved_charts()
        self.current_latitude = None
        self.current_longitude = None
        self.current_gender = "男"
        self.location_name = "尚未设置位置"
        self.location_source = "none"
        self.timezone_name = None
        self.location_error = None
        self._location_requesting = False
        self._timezone_requesting = False
        self._chart_request_id = 0
        self._last_minute_key = None
        self._clock_event = None
        self._minute_event = None
        self.load_location()
        self.load_settings()

        root = BoxLayout(
            orientation="vertical",
            padding=[dp(14), dp(8), dp(14), dp(8)],
            spacing=dp(8),
        )

        # ---------------- 顶部栏 ----------------
        top_bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(8),
        )
        top_bar.add_widget(
            make_circle_button(
                "我",
                diameter=38,
                bg=(0.900, 0.880, 0.820, 1),
                on_release=self.open_settings,
            )
        )
        self.search_input = make_input(
            hint_text="搜索名字、标签",
            height=dp(36),
            font_size=dp(12.5),
            padding=[dp(10), dp(10), dp(10), dp(10)],
        )
        self.search_input.bind(text=self.on_search_text)
        top_bar.add_widget(self.search_input)
        root.add_widget(top_bar)

        # ---------------- 即时局 ----------------
        main_card = Card(
            orientation="vertical",
            padding=[dp(12), dp(8), dp(12), dp(8)],
            spacing=dp(2),
            size_hint_y=None,
            height=dp(264),
            card_color=CARD,
        )
        title_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(26),
        )
        title_row.add_widget(
            make_label(
                "即时局",
                font_size=dp(14),
                bold=True,
                color=GREEN,
                height=dp(26),
            )
        )
        title_row.add_widget(Widget())
        main_card.add_widget(title_row)

        self.pillars_grid = GridLayout(
            cols=4,
            spacing=dp(4),
            size_hint_y=None,
            height=dp(92),
        )
        self.pillar_cells = []
        for name in ("年", "月", "日", "时"):
            cell = BoxLayout(
                orientation="vertical",
                spacing=dp(0),
            )
            cell.add_widget(
                make_label(
                    name,
                    font_size=dp(10),
                    color=MUTED,
                    halign="center",
                    height=dp(16),
                )
            )
            gz_label = make_label(
                "—",
                font_size=dp(28),
                bold=True,
                halign="center",
                height=dp(72),
            )
            cell.add_widget(gz_label)
            self.pillars_grid.add_widget(cell)
            self.pillar_cells.append(gz_label)
        main_card.add_widget(self.pillars_grid)

        self.date_label = make_label(
            "农历 --　公历 --",
            font_size=dp(10.5),
            color=MUTED,
            height=dp(30),
        )
        main_card.add_widget(self.date_label)
        self.solar_label = make_label(
            "真太阳时 --",
            font_size=dp(10),
            color=MUTED,
            height=dp(18),
        )
        main_card.add_widget(self.solar_label)
        self.location_hint = make_label(
            "",
            font_size=dp(9.5),
            color=ORANGE,
            height=dp(16),
        )
        main_card.add_widget(self.location_hint)

        icon_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(52),
            spacing=dp(4),
        )
        icon_items = (
            ("奇", "奇门遁甲", GREEN, "qimen"),
            ("罗", "罗盘", RED, "compass"),
            ("日", "日记", (0.20, 0.38, 0.62, 1), "diary"),
            ("更", "更多", GOLD, "more"),
        )
        for icon_char, icon_title, icon_color, icon_action in icon_items:
            item = BoxLayout(
                orientation="vertical",
                spacing=dp(1),
            )
            holder = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(30),
            )
            holder.add_widget(Widget())
            holder.add_widget(
                make_circle_button(
                    icon_char,
                    diameter=28,
                    bg=(0.940, 0.930, 0.900, 1),
                    fg=icon_color,
                    on_release=lambda title=icon_title, action=icon_action: (
                        self.on_icon_action(title, action)
                    ),
                )
            )
            holder.add_widget(Widget())
            item.add_widget(holder)
            item.add_widget(
                make_label(
                    icon_title,
                    font_size=dp(9),
                    color=MUTED,
                    halign="center",
                    height=dp(16),
                )
            )
            icon_row.add_widget(item)
        main_card.add_widget(icon_row)
        root.add_widget(main_card)

        # ---------------- 我的时间局 ----------------
        list_header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(28),
        )
        list_header.add_widget(
            make_label(
                "我的时间局",
                font_size=dp(16),
                bold=True,
                color=GREEN,
                height=dp(28),
            )
        )
        self.count_label = make_label(
            "",
            font_size=dp(10.5),
            color=MUTED,
            halign="right",
            height=dp(28),
        )
        list_header.add_widget(self.count_label)
        root.add_widget(list_header)

        self.list_layout = GridLayout(
            cols=1,
            spacing=dp(6),
            size_hint_y=None,
        )
        self.list_layout.bind(
            minimum_height=self.list_layout.setter("height")
        )
        list_scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(2),
        )
        list_scroll.add_widget(self.list_layout)
        root.add_widget(list_scroll)

        bottom = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(54),
        )
        add_button = make_button(
            "+",
            size_hint=(None, None),
            size=(dp(52), dp(52)),
            font_size=dp(30),
            background_color=(0.955, 0.760, 0.735, 1),
            color=(0.720, 0.220, 0.200, 1),
        )
        add_button.bind(on_release=self.open_add)
        bottom.add_widget(add_button)
        bottom.add_widget(Widget())
        root.add_widget(bottom)

        self.add_widget(root)
        self.refresh_list()
        self.update_location_hint()

    # --------------------------------------------------------
    # 位置与时区
    # --------------------------------------------------------
    def load_location(self):
        if not os.path.isfile(self.location_path):
            return
        try:
            with open(
                self.location_path,
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)
            lat = data.get("latitude")
            lon = data.get("longitude")
            if lat is not None and lon is not None:
                lat = float(lat)
                lon = float(lon)
                if valid_coordinates(lat, lon):
                    self.current_latitude = lat
                    self.current_longitude = lon
                    self.location_name = data.get(
                        "name",
                        "已保存的位置",
                    )
                    self.location_source = data.get(
                        "source",
                        "manual",
                    )
                    self.timezone_name = data.get("timezone")
        except Exception as exc:
            print(f"[Location] 读取位置失败：{exc}")

    def load_settings(self):
        if not os.path.isfile(self.settings_path):
            return
        try:
            with open(
                self.settings_path,
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)
            mode = data.get("solar_mode")
            if mode in ("mean", "apparent"):
                self.solar_mode = mode
        except Exception as exc:
            print(f"[Settings] 读取失败：{exc}")

    def save_settings(self):
        os.makedirs(self.data_dir, exist_ok=True)
        data = {"solar_mode": self.solar_mode}
        temp_path = self.settings_path + ".tmp"
        with open(
            temp_path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(temp_path, self.settings_path)

    def set_solar_mode(self, mode):
        if mode not in ("mean", "apparent"):
            return
        self.solar_mode = mode
        try:
            self.save_settings()
        except Exception as exc:
            print(f"[Settings] 保存失败：{exc}")
        self._last_minute_key = None
        self.refresh_current(force=True)

    def save_location(self):
        os.makedirs(self.data_dir, exist_ok=True)
        data = {
            "latitude": self.current_latitude,
            "longitude": self.current_longitude,
            "name": self.location_name,
            "source": self.location_source,
            "timezone": self.timezone_name,
        }
        temp_path = self.location_path + ".tmp"
        with open(
            temp_path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )
        os.replace(temp_path, self.location_path)

    def get_settings_screen(self):
        try:
            if self.manager and self.manager.has_screen("settings"):
                return self.manager.get_screen("settings")
        except Exception:
            pass
        return None

    def update_location_hint(self):
        if (
            self.current_latitude is None
            or self.current_longitude is None
        ):
            self.location_hint.text = "请先在「设置」中获取定位或设置城市"
        else:
            self.location_hint.text = ""
        screen = self.get_settings_screen()
        if screen is not None and hasattr(
            screen,
            "refresh_location",
        ):
            screen.refresh_location()

    # 兼容旧调用名
    def update_location_label(self):
        self.update_location_hint()

    def request_timezone(self, lat, lon):
        """异步获取坐标对应的 IANA 时区。"""
        if not valid_coordinates(lat, lon):
            self.location_error = "无法获取时区：坐标无效。"
            self.update_location_hint()
            return
        self._timezone_requesting = True
        self.location_error = None
        self.update_location_hint()

        def callback(tz_value, error):
            def apply_result(_dt):
                self._timezone_requesting = False
                if error or not tz_value:
                    self.location_error = (
                        "获取时区失败："
                        + str(error or "服务没有返回时区")
                    )
                    self.update_location_hint()
                    return
                tz_text = str(tz_value).strip()
                if safe_zone(tz_text) is None:
                    self.location_error = (
                        "已收到时区名称，"
                        "但本机时区数据库不可用："
                        + tz_text
                    )
                    self.update_location_hint()
                    return
                # 如果定位在请求期间已改变，不应用旧请求的时区。
                if (
                    self.current_latitude is None
                    or self.current_longitude is None
                    or abs(
                        float(self.current_latitude) - float(lat)
                    ) > 0.0001
                    or abs(
                        float(self.current_longitude) - float(lon)
                    ) > 0.0001
                ):
                    return
                self.timezone_name = tz_text
                try:
                    self.save_location()
                except Exception as exc:
                    print(f"[Location] 保存时区失败：{exc}")
                self._last_minute_key = None
                self.update_location_hint()
                self.refresh_current(force=True)

            Clock.schedule_once(apply_result, 0)

        try:
            get_timezone(lat, lon, callback, timeout=12)
        except Exception as exc:
            self._timezone_requesting = False
            self.location_error = (
                f"请求时区失败：{type(exc).__name__}: {exc}"
            )
            self.update_location_hint()

    # --------------------------------------------------------
    # 设备定位
    # --------------------------------------------------------
    def request_location(self, *_):
        if self._location_requesting:
            return
        self._location_requesting = True
        self.location_error = None
        self.update_location_hint()

        def callback(lat, lon, source, error):
            Clock.schedule_once(
                lambda _dt: self.on_location_result(
                    lat,
                    lon,
                    source,
                    error,
                ),
                0,
            )

        try:
            get_location(callback, timeout=25)
        except Exception as exc:
            self.on_location_result(
                None,
                None,
                "error",
                f"{type(exc).__name__}: {exc}",
            )

    def on_location_result(self, lat, lon, source, error):
        self._location_requesting = False
        if error or lat is None or lon is None:
            self.location_error = (
                error or "没有取得有效定位坐标。"
            )
            self.update_location_hint()
            print(f"[Location] {self.location_error}")
            return
        try:
            lat = float(lat)
            lon = float(lon)
            if not valid_coordinates(lat, lon):
                raise ValueError("坐标超出范围")
        except (TypeError, ValueError) as exc:
            self.location_error = f"定位坐标无效：{exc}"
            self.update_location_hint()
            return
        self.current_latitude = lat
        self.current_longitude = lon
        self.location_source = source or "device"
        self.location_name = "iPhone 设备定位"
        self.timezone_name = None
        self.location_error = None
        self._last_minute_key = None
        try:
            self.save_location()
        except Exception as exc:
            print(f"[Location] 保存位置失败：{exc}")
        self.update_location_hint()
        self.request_timezone(lat, lon)

    # --------------------------------------------------------
    # 手动设置城市、地址或坐标
    # --------------------------------------------------------
    def open_location_popup(self, *_):
        content = BoxLayout(
            orientation="vertical",
            padding=dp(14),
            spacing=dp(8),
        )
        content.add_widget(
            make_label(
                "输入城市、完整地址，或输入纬度,经度",
                font_size=dp(12),
                color=MUTED,
                height=dp(32),
            )
        )
        query_input = make_input(
            hint_text="例如 杭州 或 30.27,120.15",
        )
        content.add_widget(query_input)
        message = make_label(
            "城市/地址解析需要网络连接。",
            font_size=dp(11),
            color=MUTED,
            height=dp(40),
        )
        content.add_widget(message)
        popup = Popup(
            title="设置位置",
            content=content,
            size_hint=(0.92, 0.52),
            auto_dismiss=True,
        )

        def do_resolve(*_):
            query = query_input.text.strip()
            if not query:
                message.text = "请先输入城市、地址或坐标。"
                return
            message.text = "正在解析位置……"
            resolve_button.disabled = True
            coord_match = re.fullmatch(
                r"\s*(-?\d+(?:\.\d+)?)\s*[,，]\s*"
                r"(-?\d+(?:\.\d+)?)\s*",
                query,
            )
            if coord_match:
                lat_value = float(coord_match.group(1))
                lon_value = float(coord_match.group(2))
                if not valid_coordinates(lat_value, lon_value):
                    resolve_button.disabled = False
                    message.text = "坐标无效，请检查纬度和经度。"
                    return
                self.apply_manual_location(
                    lat_value,
                    lon_value,
                    query,
                )
                popup.dismiss()
                return

            def callback(lat, lon, name, error):
                def apply_result(_dt):
                    resolve_button.disabled = False
                    if error or lat is None or lon is None:
                        message.text = (
                            "解析失败："
                            + str(error or "没有返回坐标")
                        )
                        return
                    try:
                        lat_value = float(lat)
                        lon_value = float(lon)
                        if not valid_coordinates(
                            lat_value,
                            lon_value,
                        ):
                            raise ValueError("坐标超出范围")
                    except (TypeError, ValueError) as exc:
                        message.text = f"坐标无效：{exc}"
                        return
                    self.apply_manual_location(
                        lat_value,
                        lon_value,
                        name or query,
                    )
                    popup.dismiss()

                Clock.schedule_once(apply_result, 0)

            try:
                resolve_location(query, callback)
            except Exception as exc:
                resolve_button.disabled = False
                message.text = (
                    f"解析出错：{type(exc).__name__}: {exc}"
                )

        resolve_button = make_button(
            "解析并保存位置",
            height=dp(44),
        )
        resolve_button.bind(on_release=do_resolve)
        content.add_widget(resolve_button)
        content.add_widget(
            make_label(
                "坐标格式：纬度,经度，例如 30.2741,120.1551",
                font_size=dp(10),
                color=MUTED,
                height=dp(28),
            )
        )
        popup.open()

    def apply_manual_location(self, lat, lon, name):
        self.current_latitude = float(lat)
        self.current_longitude = float(lon)
        self.location_name = str(name or "手动设置位置")
        self.location_source = "manual"
        self.timezone_name = None
        self.location_error = None
        self._last_minute_key = None
        try:
            self.save_location()
        except Exception as exc:
            print(f"[Location] 保存位置失败：{exc}")
        self.update_location_hint()
        self.request_timezone(lat, lon)

    # --------------------------------------------------------
    # 当前时间和排盘刷新
    # --------------------------------------------------------
    def on_pre_enter(self, *_):
        if self._clock_event is None:
            self._clock_event = Clock.schedule_interval(
                self.update_current_time,
                1,
            )
        if self._minute_event is None:
            self._minute_event = Clock.schedule_interval(
                self.refresh_current,
                60,
            )
        self.update_current_time(0)
        self.refresh_current(force=True)
        self.update_location_hint()
        if (
            self.current_latitude is not None
            and self.current_longitude is not None
            and not self.timezone_name
            and not self._timezone_requesting
        ):
            Clock.schedule_once(
                lambda _dt: self.request_timezone(
                    self.current_latitude,
                    self.current_longitude,
                ),
                0.3,
            )
    def on_leave(self, *_):
        if self._clock_event is not None:
            self._clock_event.cancel()
            self._clock_event = None
        if self._minute_event is not None:
            self._minute_event.cancel()
            self._minute_event = None

    def get_location_now(self):
        """返回地点当地时间；未取得时区时不伪造当地时间。"""
        zone = safe_zone(self.timezone_name)
        if zone is None:
            return None
        return datetime.now(zone)

    def update_current_time(self, _dt):
        now = self.get_location_now()
        lunar_text = "--"
        if now is not None and solar_to_lunar is not None:
            try:
                lunar_text = solar_to_lunar(now)
            except Exception:
                lunar_text = "--"
        if now is None:
            self.date_label.text = "农历 " + lunar_text + "　公历 --"
            return
        self.date_label.text = (
            "农历:" + lunar_text
            + "　公历:" + now.strftime("%Y-%m-%d %H:%M")
        )

    def refresh_current(self, *_args, force=False):
        if (
            self.current_latitude is None
            or self.current_longitude is None
        ):
            self.solar_label.text = "真太阳时 -- 请先设置位置"
            return
        zone = safe_zone(self.timezone_name)
        if zone is None:
            self.solar_label.text = "真太阳时 -- 等待时区"
            return
        now = datetime.now(zone)
        minute_key = (
            f"{self.timezone_name}:"
            + now.strftime("%Y%m%d%H%M")
        )
        if not force and minute_key == self._last_minute_key:
            return
        self._last_minute_key = minute_key
        try:
            latitude = float(self.current_latitude)
            longitude = float(self.current_longitude)
            if not valid_coordinates(latitude, longitude):
                raise ValueError("位置坐标超出范围")
        except (TypeError, ValueError) as exc:
            self.solar_label.text = f"位置无效：{exc}"
            return
        self._chart_request_id += 1
        request_id = self._chart_request_id
        self.solar_label.text = "真太阳时 计算中…"
        timezone_name = self.timezone_name
        gender = self.current_gender

        def work():
            try:
                chart = build_chart(
                    now,
                    longitude,
                    gender,
                    latitude=latitude,
                    timezone_info=timezone_name,
                    solar_mode=self.solar_mode,
                )
                pillars = get_pillars(chart)
                birth = chart.birth.strftime("%m-%d %H:%M")
                solar = chart.true_solar.strftime("%H:%M")
                error = None
            except Exception as exc:
                pillars = []
                birth = ""
                solar = ""
                error = f"{type(exc).__name__}: {exc}"
            Clock.schedule_once(
                lambda _dt: self.set_current_result(
                    request_id,
                    pillars,
                    birth,
                    solar,
                    error,
                ),
                0,
            )

        Thread(target=work, daemon=True).start()

    def set_current_result(
        self,
        request_id,
        pillars,
        birth,
        solar,
        error,
    ):
        if request_id != self._chart_request_id:
            return
        if error:
            self.solar_label.text = f"排盘失败：{error}"
            return
        if not pillars:
            return
        for index, (_, pillar) in enumerate(pillars):
            gz_label = self.pillar_cells[index]
            gz_label.text = pillar.gan + "\n" + pillar.zhi
            gz_label.color = ELEMENT_COLORS.get(
                ELEMENT.get(pillar.gan, ""),
                TEXT,
            )
        self.solar_label.text = f"真太阳时 {solar}"

    # --------------------------------------------------------
    # 已保存时间局
    # --------------------------------------------------------
    def load_saved_charts(self):
        if not os.path.isfile(self.store_path):
            return {}
        try:
            with open(
                self.store_path,
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            print(f"[Storage] 读取失败：{exc}")
            return {}

    def save_saved_charts(self):
        os.makedirs(self.data_dir, exist_ok=True)
        temp_path = self.store_path + ".tmp"
        with open(
            temp_path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                self.saved_charts,
                file,
                ensure_ascii=False,
                indent=2,
            )
        os.replace(temp_path, self.store_path)

    def on_search_text(self, _instance, _value):
        self.refresh_list()

    def filtered_items(self):
        keyword = ""
        try:
            keyword = self.search_input.text.strip().lower()
        except Exception:
            keyword = ""
        items = list(reversed(list(self.saved_charts.items())))
        if keyword:
            matched = []
            for key, item in items:
                name = str(item.get("name", "")).lower()
                tags = " ".join(item.get("tags", []) or []).lower()
                if keyword in name or keyword in tags:
                    matched.append((key, item))
            items = matched
        starred = [pair for pair in items if pair[1].get("starred")]
        normal = [pair for pair in items if not pair[1].get("starred")]
        return starred + normal

    def refresh_list(self):
        self.list_layout.clear_widgets()
        items = self.filtered_items()
        self.count_label.text = (
            f"共 {len(items)} 局" if items else ""
        )
        if not items:
            searching = False
            try:
                searching = bool(self.search_input.text.strip())
            except Exception:
                searching = False
            self.list_layout.add_widget(
                make_label(
                    "没有匹配的时间局"
                    if searching
                    else "还没有保存的时间局",
                    font_size=dp(12),
                    color=MUTED,
                    halign="center",
                    height=dp(60),
                )
            )
            return
        for key, item in items:
            name = str(item.get("name", "未命名时间局"))
            time_text = str(item.get("time", ""))
            row = Card(
                orientation="horizontal",
                padding=[dp(8), dp(4), dp(6), dp(4)],
                spacing=dp(8),
                size_hint_y=None,
                height=dp(66),
                card_color=CARD,
                radius=12,
            )
            avatar = Card(
                orientation="vertical",
                size_hint=(None, None),
                size=(dp(38), dp(38)),
                padding=[dp(1), dp(2), dp(1), dp(2)],
                card_color=(0.890, 0.925, 0.890, 1),
                radius=19,
            )
            avatar.add_widget(
                make_label(
                    name[:1] if name else "?",
                    font_size=dp(15),
                    bold=True,
                    color=GREEN,
                    halign="center",
                    height=dp(30),
                )
            )
            row.add_widget(avatar)
            info = BoxLayout(
                orientation="vertical",
                spacing=dp(0),
            )
            info.add_widget(
                make_label(
                    name,
                    font_size=dp(14.5),
                    bold=True,
                    color=TEXT,
                    height=dp(28),
                )
            )
            tags = item.get("tags", []) or []
            tag_text = " · ".join(
                [format_birth_date(time_text)] + [str(tag) for tag in tags[:3]]
            )
            info.add_widget(
                make_label(
                    tag_text,
                    font_size=dp(10.5),
                    color=MUTED,
                    height=dp(18),
                )
            )
            row.add_widget(info)
            tag_button = make_button(
                "#",
                size_hint=(None, None),
                size=(dp(24), dp(30)),
                font_size=dp(15),
                background_color=(0, 0, 0, 0),
                color=(GOLD if tags else (0.760, 0.760, 0.740, 1)),
            )
            tag_button.bind(
                on_release=lambda _btn, chart_key=key: (
                    self.edit_tags(chart_key)
                )
            )
            row.add_widget(tag_button)
            star_button = make_button(
                "★" if item.get("starred") else "☆",
                size_hint=(None, None),
                size=(dp(30), dp(30)),
                font_size=dp(16),
                background_color=(0, 0, 0, 0),
                color=(
                    GOLD
                    if item.get("starred")
                    else (0.720, 0.720, 0.700, 1)
                ),
            )
            star_button.bind(
                on_release=lambda _btn, chart_key=key: (
                    self.toggle_star(chart_key)
                )
            )
            row.add_widget(star_button)
            open_button = make_button(
                "›",
                size_hint=(None, None),
                size=(dp(26), dp(30)),
                font_size=dp(20),
                background_color=(0, 0, 0, 0),
                color=MUTED,
            )
            open_button.bind(
                on_release=lambda _btn, chart_key=key: (
                    self.open_detail(chart_key)
                )
            )
            row.add_widget(open_button)
            self.list_layout.add_widget(row)

    def edit_tags(self, key):
        item = self.saved_charts.get(key)
        if not item:
            return
        content = BoxLayout(
            orientation="vertical",
            padding=dp(14),
            spacing=dp(8),
        )
        content.add_widget(
            make_label(
                "给「" + str(item.get("name", "未命名时间局")) + "」添加标签",
                font_size=dp(12.5),
                color=TEXT,
                height=dp(28),
            )
        )
        tag_input = make_input(
            hint_text="多个标签用空格分隔，例如：朋友 客户",
            height=dp(40),
            font_size=dp(12),
        )
        tag_input.text = " ".join(item.get("tags", []) or [])
        content.add_widget(tag_input)
        message = make_label(
            "",
            font_size=dp(10.5),
            color=MUTED,
            height=dp(24),
        )
        content.add_widget(message)
        popup = Popup(
            title="标签",
            content=content,
            size_hint=(0.9, 0.5),
            auto_dismiss=True,
        )

        def do_save(*_):
            raw = tag_input.text.strip()
            tags = []
            for part in raw.split():
                part = part.strip().lstrip("#")
                if part and part not in tags:
                    tags.append(part)
            item["tags"] = tags
            try:
                self.save_saved_charts()
            except Exception as exc:
                message.text = "保存失败：" + str(exc)
                return
            self.refresh_list()
            popup.dismiss()

        save_button = make_button(
            "保存标签",
            height=dp(42),
            on_release=do_save,
        )
        content.add_widget(save_button)
        popup.open()

    def toggle_star(self, key):
        item = self.saved_charts.get(key)
        if not item:
            return
        item["starred"] = not bool(item.get("starred"))
        try:
            self.save_saved_charts()
        except Exception as exc:
            print(f"[Storage] 保存星标失败：{exc}")
        self.refresh_list()

    def on_icon_action(self, title, action, *_args):
        if not isinstance(action, str):
            return
        if action == "diary":
            self.manager.current = "diary"
            return
        if action == "tags":
            self.manager.current = "tags"
            return
        if action == "qimen":
            self.manager.current = "qimen"
            return
        if action == "more":
            self.manager.current = "more"
            return
        self.show_placeholder(title)

    def show_placeholder(self, title):
        content = BoxLayout(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(8),
        )
        content.add_widget(
            make_label(
                "「" + str(title) + "」功能开发中",
                font_size=dp(14),
                color=TEXT,
                halign="center",
                height=dp(40),
            )
        )
        content.add_widget(
            make_label(
                "后续版本会开放，敬请期待。",
                font_size=dp(11),
                color=MUTED,
                halign="center",
                height=dp(28),
            )
        )
        close_button = make_button("知道了", height=dp(42))
        content.add_widget(close_button)
        popup = Popup(
            title=str(title),
            content=content,
            size_hint=(0.86, 0.38),
            auto_dismiss=True,
        )
        close_button.bind(on_release=lambda *_: popup.dismiss())
        popup.open()


    def open_add(self, *_):
        self.manager.get_screen("add").reset_form()
        self.manager.current = "add"

    def open_detail(self, key):
        detail = self.manager.get_screen("detail")
        detail.show_chart(key)
        self.manager.current = "detail"

    def open_settings(self, *_):
        self.manager.current = "settings"

    def add_chart(
        self,
        name,
        time_text,
        gender="男",
        latitude=None,
        longitude=None,
        location_name=None,
        timezone=None,
    ):
        key = datetime.now().strftime("%Y%m%d%H%M%S%f")
        item = {
            "name": name.strip() or "未命名时间局",
            "time": time_text.strip(),
            "gender": gender if gender in ("男", "女") else "男",
            "longitude": (
                self.current_longitude if longitude is None else longitude
            ),
            "latitude": (
                self.current_latitude if latitude is None else latitude
            ),
            "location_name": (
                self.location_name
                if location_name is None
                else location_name
            ),
            "timezone": (
                self.timezone_name if timezone is None else timezone
            ),
            "starred": False,
            "tags": list(getattr(self, "pending_tags", []) or []),
        }
        self.pending_tags = []
        self.saved_charts[key] = item
        self.save_saved_charts()
        self.refresh_list()


# ============================================================
# 设置
# ============================================================
class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.home = None
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(8), dp(16), dp(8)],
            spacing=dp(8),
        )

        top = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(44),
            spacing=dp(10),
        )
        back_button = make_button(
            "‹ 返回",
            size_hint=(None, None),
            size=(dp(74), dp(34)),
            font_size=dp(12),
            background_color=(0.420, 0.450, 0.410, 1),
        )
        back_button.bind(on_release=self.go_back)
        top.add_widget(back_button)
        top.add_widget(
            make_label(
                "设置",
                font_size=dp(22),
                bold=True,
                color=GREEN,
                height=dp(40),
            )
        )
        root.add_widget(top)

        scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(2),
        )
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            size_hint_y=None,
        )
        content.bind(
            minimum_height=content.setter("height")
        )

        content.add_widget(
            make_label(
                "位置信息",
                font_size=dp(13),
                bold=True,
                color=GREEN,
                height=dp(26),
            )
        )
        location_card = Card(
            orientation="vertical",
            padding=dp(14),
            spacing=dp(4),
            size_hint_y=None,
            height=dp(180),
            card_color=CARD,
        )
        self.loc_name_label = make_label(
            "尚未设置位置",
            font_size=dp(16),
            bold=True,
            color=TEXT,
            height=dp(32),
        )
        self.loc_coord_label = make_label(
            "纬度 --    经度 --",
            font_size=dp(12),
            color=MUTED,
            height=dp(24),
        )
        self.loc_tz_label = make_label(
            "时区：未获取",
            font_size=dp(12),
            color=MUTED,
            height=dp(24),
        )
        self.loc_status_label = make_label(
            "",
            font_size=dp(10.5),
            color=ORANGE,
            height=dp(56),
        )
        location_card.add_widget(self.loc_name_label)
        location_card.add_widget(self.loc_coord_label)
        location_card.add_widget(self.loc_tz_label)
        location_card.add_widget(self.loc_status_label)
        content.add_widget(location_card)

        location_buttons = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(44),
            spacing=dp(8),
        )
        self.get_loc_button = make_button(
            "获取定位",
            height=dp(44),
            font_size=dp(13),
        )
        self.get_loc_button.bind(
            on_release=lambda *_: (
                self.home.request_location()
                if self.home is not None
                else None
            )
        )
        manual_button = make_button(
            "设置城市 / 地址",
            height=dp(44),
            font_size=dp(13),
            background_color=(0.360, 0.440, 0.380, 1),
        )
        manual_button.bind(
            on_release=lambda *_: (
                self.home.open_location_popup()
                if self.home is not None
                else None
            )
        )
        location_buttons.add_widget(self.get_loc_button)
        location_buttons.add_widget(manual_button)
        content.add_widget(location_buttons)

        content.add_widget(
            make_label(
                "真太阳时",
                font_size=dp(13),
                bold=True,
                color=GREEN,
                height=dp(26),
            )
        )
        solar_card = Card(
            orientation="vertical",
            padding=dp(14),
            spacing=dp(6),
            size_hint_y=None,
            height=dp(150),
            card_color=CARD,
        )
        self.solar_mode_label = make_label(
            "当前口径：平太阳时（仅按经度校正）",
            font_size=dp(12.5),
            bold=True,
            color=TEXT,
            height=dp(26),
        )
        solar_card.add_widget(self.solar_mode_label)
        self.solar_mode_hint = make_label(
            "与主流排盘软件一致。切换后首页和详情页会重新计算。",
            font_size=dp(9.5),
            color=MUTED,
            height=dp(30),
        )
        solar_card.add_widget(self.solar_mode_hint)
        solar_buttons = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(38),
            spacing=dp(8),
        )
        self.solar_mean_button = make_button(
            "平太阳时",
            height=dp(38),
            font_size=dp(12),
            on_release=lambda *_: self.choose_solar_mode("mean"),
        )
        self.solar_apparent_button = make_button(
            "天文真太阳时",
            height=dp(38),
            font_size=dp(12),
            on_release=lambda *_: self.choose_solar_mode("apparent"),
        )
        solar_buttons.add_widget(self.solar_mean_button)
        solar_buttons.add_widget(self.solar_apparent_button)
        solar_card.add_widget(solar_buttons)
        content.add_widget(solar_card)

        content.add_widget(
            make_label(
                "AI 解读",
                font_size=dp(13),
                bold=True,
                color=GREEN,
                height=dp(26),
            )
        )
        ai_card = Card(
            orientation="vertical",
            padding=dp(14),
            spacing=dp(4),
            size_hint_y=None,
            height=dp(232),
            card_color=CARD,
        )
        self.ai_status_label = make_label(
            "检查中……",
            font_size=dp(10.5),
            color=MUTED,
            height=dp(20),
        )
        ai_card.add_widget(self.ai_status_label)
        ai_card.add_widget(
            make_label(
                "中转地址",
                font_size=dp(10.5),
                color=MUTED,
                height=dp(16),
            )
        )
        self.ai_endpoint_input = make_input(
            hint_text="https://wuxing-ai.xxx.workers.dev",
            height=dp(38),
            font_size=dp(11),
            padding=[dp(8), dp(8), dp(8), dp(8)],
        )
        ai_card.add_widget(self.ai_endpoint_input)
        ai_card.add_widget(
            make_label(
                "访问口令",
                font_size=dp(10.5),
                color=MUTED,
                height=dp(16),
            )
        )
        self.ai_token_input = make_input(
            hint_text="APP_TOKEN",
            height=dp(38),
            font_size=dp(11),
            password=True,
            padding=[dp(8), dp(8), dp(8), dp(8)],
        )
        ai_card.add_widget(self.ai_token_input)
        ai_card.add_widget(
            make_label(
                "模型名",
                font_size=dp(10.5),
                color=MUTED,
                height=dp(16),
            )
        )
        self.ai_model_input = make_input(
            hint_text="deepseek-chat",
            height=dp(38),
            font_size=dp(11),
            padding=[dp(8), dp(8), dp(8), dp(8)],
        )
        ai_card.add_widget(self.ai_model_input)
        content.add_widget(ai_card)

        ai_buttons = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(42),
            spacing=dp(8),
        )
        save_ai_button = make_button(
            "保存配置",
            height=dp(42),
            font_size=dp(12.5),
            on_release=self.save_ai_config,
        )
        ai_buttons.add_widget(save_ai_button)
        content.add_widget(ai_buttons)

        content.add_widget(
            make_label(
                "技能库",
                font_size=dp(13),
                bold=True,
                color=GREEN,
                height=dp(26),
            )
        )
        skills_card = Card(
            orientation="vertical",
            padding=dp(14),
            spacing=dp(3),
            size_hint_y=None,
            height=dp(96),
            card_color=CARD,
        )
        self.skills_title = make_label(
            "盘叔盲派断法库",
            font_size=dp(13),
            bold=True,
            color=TEXT,
            height=dp(26),
        )
        self.skills_status = make_label(
            "正在检查技能库……",
            font_size=dp(10.5),
            color=MUTED,
            height=dp(34),
        )
        skills_card.add_widget(self.skills_title)
        skills_card.add_widget(self.skills_status)
        content.add_widget(skills_card)

        open_skills_button = make_button(
            "打开技能库",
            height=dp(44),
            font_size=dp(13),
            background_color=(0.360, 0.440, 0.380, 1),
            on_release=self.open_skills,
        )
        content.add_widget(open_skills_button)

        content.add_widget(
            make_label(
                "关于",
                font_size=dp(13),
                bold=True,
                color=GREEN,
                height=dp(26),
            )
        )
        about_card = Card(
            orientation="vertical",
            padding=dp(14),
            spacing=dp(2),
            size_hint_y=None,
            height=dp(92),
            card_color=CARD,
        )
        about_card.add_widget(
            make_label(
                "五行排盘 · 本地离线计算",
                font_size=dp(12.5),
                color=TEXT,
                height=dp(24),
            )
        )
        about_card.add_widget(
            make_label(
                "四柱 / 节气 / 真太阳时 / 大运 / 胎元 / 命宫",
                font_size=dp(10),
                color=MUTED,
                height=dp(34),
            )
        )
        content.add_widget(about_card)
        content.add_widget(Widget(size_hint_y=None, height=dp(12)))

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_pre_enter(self, *_):
        self.home = self.manager.get_screen("home")
        self.refresh_location()
        self.refresh_solar_mode()
        self.refresh_skills_status()
        self.refresh_ai_config()

    def refresh_ai_config(self):
        if ai_module is None:
            self.ai_status_label.text = "AI 模块不可用"
            return
        config = ai_module.load_config(self.home.data_dir)
        self.ai_endpoint_input.text = (
            config.get("endpoint", "") or AI_DEFAULT_ENDPOINT
        )
        self.ai_token_input.text = config.get("token", "")
        self.ai_model_input.text = (
            config.get("model", "") or AI_DEFAULT_MODEL
        )
        effective = dict(config)
        if not effective.get("endpoint"):
            effective["endpoint"] = AI_DEFAULT_ENDPOINT
        if not effective.get("model"):
            effective["model"] = AI_DEFAULT_MODEL
        if ai_module.is_configured(effective):
            self.ai_status_label.text = (
                "已配置 · " + ai_module.describe_config(effective)
            )
        else:
            self.ai_status_label.text = (
                "未配置：请填写访问口令后点「保存配置」"
            )

    def save_ai_config(self, *_):
        if ai_module is None:
            self.ai_status_label.text = "AI 模块不可用"
            return
        config = {
            "endpoint": (
                self.ai_endpoint_input.text.strip()
                or AI_DEFAULT_ENDPOINT
            ),
            "token": self.ai_token_input.text.strip(),
            "model": (
                self.ai_model_input.text.strip()
                or AI_DEFAULT_MODEL
            ),
        }
        try:
            ai_module.save_config(self.home.data_dir, config)
        except Exception as exc:
            self.ai_status_label.text = f"保存失败：{exc}"
            return
        self.ai_status_label.text = (
            "已保存 · " + ai_module.describe_config(config)
        )

    def open_skills(self, *_):
        self.manager.current = "skills"

    def refresh_skills_status(self):
        try:
            library = get_library()
        except Exception as exc:
            self.skills_status.text = (
                "技能库不可用：" + str(exc)
            )
            return
        try:
            library.load()
            info = library.stats()
        except Exception as exc:
            self.skills_status.text = (
                "读取技能库失败：" + str(exc)
            )
            return
        if not info.get("loaded"):
            self.skills_status.text = (
                "未找到 skills.zip（请上传到仓库根目录）"
            )
            return
        self.skills_status.text = (
            f"已加载 {info['skills']} 个技能"
            f" · {info['references']} 篇参考"
            f" · 约 {info['chars'] // 1000} 千字"
        )

    def choose_solar_mode(self, mode):
        if self.home is None:
            return
        self.home.set_solar_mode(mode)
        self.refresh_solar_mode()

    def refresh_solar_mode(self):
        if self.home is None:
            return
        mode = self.home.solar_mode
        if mode == "apparent":
            self.solar_mode_label.text = "当前口径：天文真太阳时（含均时差）"
            self.solar_mode_hint.text = (
                "按 Skyfield 星历计算，比平太阳时多一项均时差（最多约 ±16 分钟）。"
            )
        else:
            self.solar_mode_label.text = "当前口径：平太阳时（仅按经度校正）"
            self.solar_mode_hint.text = (
                "与主流排盘软件一致。切换后首页和详情页会重新计算。"
            )
        active = GREEN
        inactive = GREEN_LIGHT
        self.solar_mean_button.background_color = (
            active if mode == "mean" else inactive
        )
        self.solar_mean_button.color = (
            (1, 1, 1, 1) if mode == "mean" else GREEN
        )
        self.solar_apparent_button.background_color = (
            active if mode == "apparent" else inactive
        )
        self.solar_apparent_button.color = (
            (1, 1, 1, 1) if mode == "apparent" else GREEN
        )

    def refresh_location(self):
        if self.home is None:
            return
        home = self.home
        self.loc_name_label.text = home.location_name
        if home.current_latitude is None:
            self.loc_coord_label.text = "纬度 --    经度 --"
        else:
            self.loc_coord_label.text = (
                f"纬度 {home.current_latitude:.4f}°    "
                f"经度 {home.current_longitude:.4f}°"
            )
        self.loc_tz_label.text = (
            "时区：" + (home.timezone_name or "未获取")
        )
        status_lines = []
        if home._location_requesting:
            status_lines.append("正在获取 iPhone 定位……")
        if home._timezone_requesting:
            status_lines.append("正在获取时区……")
        if home.location_error:
            status_lines.append("提示：" + home.location_error)
        self.loc_status_label.text = "\n".join(status_lines)
        self.get_loc_button.disabled = home._location_requesting
        self.get_loc_button.text = (
            "正在定位……"
            if home._location_requesting
            else "获取定位"
        )

    def go_back(self, *_):
        self.manager.current = "home"


# ============================================================
# 技能库
# ============================================================
class SkillsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.library = None
        self.filtered = []
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(8), dp(16), dp(8)],
            spacing=dp(8),
        )

        top = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(10),
        )
        back_button = make_button(
            "‹ 设置",
            size_hint=(None, None),
            size=(dp(72), dp(34)),
            font_size=dp(12),
            background_color=(0.420, 0.450, 0.410, 1),
            on_release=self.go_back,
        )
        top.add_widget(back_button)
        top.add_widget(
            make_label(
                "技能库",
                font_size=dp(22),
                bold=True,
                color=GREEN,
                height=dp(36),
            )
        )
        self.count_label = make_label(
            "",
            font_size=dp(10.5),
            color=MUTED,
            halign="right",
            height=dp(36),
        )
        top.add_widget(self.count_label)
        root.add_widget(top)

        self.search_input = make_input(
            hint_text="搜索技能或规则条文，例如：羊刃、婚姻、反局",
            height=dp(40),
            font_size=dp(12.5),
        )
        self.search_input.bind(text=self.on_search)
        root.add_widget(self.search_input)

        self.status_label = make_label(
            "",
            font_size=dp(10.5),
            color=MUTED,
            height=dp(22),
        )
        root.add_widget(self.status_label)

        self.list_layout = GridLayout(
            cols=1,
            spacing=dp(6),
            size_hint_y=None,
        )
        self.list_layout.bind(
            minimum_height=self.list_layout.setter("height")
        )
        scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(2),
        )
        scroll.add_widget(self.list_layout)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_pre_enter(self, *_):
        # 技能库文件多，放后台线程加载，避免卡死主线程被系统杀掉
        self.status_label.text = "正在加载技能库……"
        self.list_layout.clear_widgets()
        Thread(target=self._load_work, daemon=True).start()

    def _load_work(self):
        try:
            library = get_library()
            library.load()
            info = library.stats()
            error = None
        except Exception as exc:
            library = None
            info = None
            error = f"{type(exc).__name__}: {exc}"
        Clock.schedule_once(
            lambda _dt: self._load_done(library, info, error),
            0,
        )

    def _load_done(self, library, info, error):
        if error:
            self.library = None
            self.status_label.text = "技能库不可用：" + error
            return
        self.library = library
        if not info.get("loaded"):
            self.status_label.text = (
                "未找到 skills.zip，请检查构建日志"
            )
        else:
            self.status_label.text = (
                f"来源 {info.get('source', '')}"
                f" · {info['skills']} 个技能"
            )
        try:
            self.render()
        except Exception as exc:
            self.status_label.text = "显示失败：" + str(exc)

    def on_search(self, _instance, _value):
        try:
            self.render()
        except Exception as exc:
            self.status_label.text = "搜索失败：" + str(exc)

    def go_back(self, *_):
        self.manager.current = "more"

    def render(self):
        self.list_layout.clear_widgets()
        if self.library is None:
            return
        keyword = ""
        try:
            keyword = self.search_input.text.strip()
        except Exception:
            keyword = ""

        if keyword:
            hits = self.library.search(keyword, limit=60)
            self.count_label.text = f"{len(hits)} 条"
            if not hits:
                self.list_layout.add_widget(
                    make_label(
                        "没有找到相关条文",
                        font_size=dp(12),
                        color=MUTED,
                        halign="center",
                        height=dp(80),
                    )
                )
                return
            for hit in hits:
                card = Card(
                    orientation="vertical",
                    padding=dp(10),
                    spacing=dp(1),
                    size_hint_y=None,
                    height=dp(76),
                    card_color=CARD,
                    radius=10,
                )
                card.add_widget(
                    make_label(
                        hit["snippet"],
                        font_size=dp(11),
                        color=TEXT,
                        height=dp(44),
                    )
                )
                card.add_widget(
                    make_label(
                        hit["path"].rsplit("/", 1)[-1]
                        + " · 第 "
                        + str(hit["line"])
                        + " 行 · "
                        + hit["skill_id"],
                        font_size=dp(9),
                        color=MUTED,
                        height=dp(18),
                    )
                )
                self.list_layout.add_widget(card)
            return

        groups = self.library.groups()
        total = 0
        for group_name in (
            "总控",
            "段派主干",
            "段派断事",
            "体用做功",
            "夏仲奇派",
            "金口诀",
            "工具",
            "其他",
        ):
            items = groups.get(group_name)
            if not items:
                continue
            self.list_layout.add_widget(
                make_label(
                    group_name + f"（{len(items)}）",
                    font_size=dp(12.5),
                    bold=True,
                    color=GREEN,
                    height=dp(28),
                )
            )
            for item in items:
                total += 1
                card = Card(
                    orientation="horizontal",
                    padding=[dp(10), dp(4), dp(8), dp(4)],
                    spacing=dp(6),
                    size_hint_y=None,
                    height=dp(62),
                    card_color=CARD,
                    radius=10,
                )
                info_box = BoxLayout(
                    orientation="vertical",
                    spacing=dp(0),
                )
                info_box.add_widget(
                    make_label(
                        item["id"],
                        font_size=dp(13),
                        bold=True,
                        color=TEXT,
                        height=dp(24),
                    )
                )
                info_box.add_widget(
                    make_label(
                        (item.get("description") or "")[:46]
                        or item.get("title", ""),
                        font_size=dp(9),
                        color=MUTED,
                        height=dp(28),
                    )
                )
                card.add_widget(info_box)
                open_button = make_button(
                    "›",
                    size_hint=(None, None),
                    size=(dp(28), dp(34)),
                    font_size=dp(20),
                    background_color=(0, 0, 0, 0),
                    color=MUTED,
                )
                open_button.bind(
                    on_release=lambda _btn, sid=item["id"]: (
                        self.open_skill(sid)
                    )
                )
                card.add_widget(open_button)
                self.list_layout.add_widget(card)
        self.count_label.text = f"{total} 个技能"

    def open_skill(self, skill_id):
        detail = self.manager.get_screen("skill_detail")
        detail.show_skill(skill_id)
        self.manager.current = "skill_detail"


class SkillDetailScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(8), dp(16), dp(8)],
            spacing=dp(8),
        )
        root.add_widget(
            make_button(
                "‹ 技能库",
                size_hint=(None, None),
                size=(dp(84), dp(34)),
                font_size=dp(12),
                background_color=(0.420, 0.450, 0.410, 1),
                on_release=self.go_back,
            )
        )
        self.title_label = make_label(
            "技能",
            font_size=dp(20),
            bold=True,
            color=GREEN,
            height=dp(38),
        )
        root.add_widget(self.title_label)
        self.meta_label = make_label(
            "",
            font_size=dp(9.5),
            color=MUTED,
            height=dp(22),
        )
        root.add_widget(self.meta_label)
        card = Card(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(2),
        )
        self.body_text = make_label(
            "",
            valign="top",
            font_size=dp(11),
            size_hint_y=None,
            height=dp(600),
        )
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.body_text)
        card.add_widget(scroll)
        root.add_widget(card)
        self.add_widget(root)
        self._current_id = None

    def show_skill(self, skill_id):
        self._current_id = skill_id
        try:
            library = get_library()
            library.load()
            item = library.get_skill(skill_id)
        except Exception as exc:
            self.title_label.text = "读取失败"
            self.meta_label.text = str(exc)
            self.body_text.text = ""
            return
        if item is None:
            self.title_label.text = "未找到技能"
            self.meta_label.text = skill_id
            self.body_text.text = ""
            return
        self.title_label.text = item["id"]
        self.meta_label.text = (
            item["group"]
            + " · "
            + str(item["length"])
            + " 字"
        )
        try:
            body = item.get("body") or item.get("text") or ""
            total = len(item.get("text") or body)
            limit = 6000
            if len(body) > limit:
                body = (
                    body[:limit]
                    + "\n\n……（全文 " + str(total) + " 字，仅显示前 "
                    + str(limit) + " 字）"
                )
            self.body_text.text = body
            self.body_text.texture_update()
            self.body_text.height = max(
                dp(600),
                self.body_text.texture_size[1] + dp(30),
            )
        except Exception as exc:
            self.body_text.text = "显示失败：" + str(exc)

    def go_back(self, *_):
        self.manager.current = "skills"


# ============================================================
# 日记
# ============================================================
class DiaryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.path = None
        self.entries = {}
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(8), dp(16), dp(8)],
            spacing=dp(8),
        )

        top = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(10),
        )
        top.add_widget(
            make_button(
                "‹ 首页",
                size_hint=(None, None),
                size=(dp(72), dp(34)),
                font_size=dp(12),
                background_color=(0.420, 0.450, 0.410, 1),
                on_release=self.go_back,
            )
        )
        top.add_widget(
            make_label(
                "日记",
                font_size=dp(22),
                bold=True,
                color=GREEN,
                height=dp(36),
            )
        )
        self.count_label = make_label(
            "",
            font_size=dp(10.5),
            color=MUTED,
            halign="right",
            height=dp(36),
        )
        top.add_widget(self.count_label)
        root.add_widget(top)

        self.list_layout = GridLayout(
            cols=1,
            spacing=dp(6),
            size_hint_y=None,
        )
        self.list_layout.bind(
            minimum_height=self.list_layout.setter("height")
        )
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(2))
        scroll.add_widget(self.list_layout)
        root.add_widget(scroll)

        bottom = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(50),
        )
        add_button = make_button(
            "+ 写日记",
            size_hint=(None, None),
            size=(dp(120), dp(46)),
            font_size=dp(14),
            on_release=lambda *_: self.open_editor(None),
        )
        bottom.add_widget(add_button)
        bottom.add_widget(Widget())
        root.add_widget(bottom)
        self.add_widget(root)

    # --------------------------------------------------------
    def get_data_dir(self):
        home = self.manager.get_screen("home")
        return home.data_dir

    def get_path(self):
        return os.path.join(self.get_data_dir(), "diary.json")

    def load_entries(self):
        path = self.get_path()
        self.entries = {}
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                self.entries = data
        except Exception as exc:
            print(f"[Diary] 读取失败：{exc}")

    def save_entries(self):
        path = self.get_path()
        temp_path = path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(self.entries, file, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)

    @staticmethod
    def day_ganzhi_text(date_text):
        try:
            from .calendar import day_ganzhi
            value = datetime.strptime(date_text, "%Y-%m-%d")
            return day_ganzhi(value) + "日"
        except Exception:
            return ""

    def on_pre_enter(self, *_):
        self.load_entries()
        self.refresh_list()

    def refresh_list(self):
        self.list_layout.clear_widgets()
        keys = sorted(self.entries.keys(), reverse=True)
        self.count_label.text = f"{len(keys)} 篇" if keys else ""
        if not keys:
            self.list_layout.add_widget(
                make_label(
                    "还没有日记，点下方「+ 写日记」记录今天。",
                    font_size=dp(12),
                    color=MUTED,
                    halign="center",
                    height=dp(70),
                )
            )
            return
        for key in keys:
            entry = self.entries.get(key) or {}
            date_text = entry.get("date", key)
            text = str(entry.get("text", "")).strip()
            preview = text.replace("\n", " ")[:46]
            if len(text.replace("\n", " ")) > 46:
                preview += "…"
            row = Card(
                orientation="vertical",
                padding=[dp(12), dp(6), dp(10), dp(6)],
                spacing=dp(1),
                size_hint_y=None,
                height=dp(90),
                card_color=CARD,
                radius=12,
            )
            head = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(24),
            )
            head.add_widget(
                make_label(
                    date_text,
                    font_size=dp(13),
                    bold=True,
                    color=TEXT,
                    height=dp(24),
                )
            )
            head.add_widget(
                make_label(
                    self.day_ganzhi_text(date_text),
                    font_size=dp(9.5),
                    color=MUTED,
                    halign="right",
                    height=dp(24),
                )
            )
            row.add_widget(head)
            row.add_widget(
                make_label(
                    preview or "（空）",
                    font_size=dp(10.5),
                    color=MUTED if preview else ORANGE,
                    height=dp(20),
                )
            )
            row.add_widget(
                make_button(
                    "编辑 ›",
                    size_hint=(None, None),
                    size=(dp(62), dp(24)),
                    font_size=dp(10),
                    background_color=GREEN_LIGHT,
                    color=GREEN,
                    on_release=lambda _btn, k=key: self.open_editor(k),
                )
            )
            self.list_layout.add_widget(row)

    # --------------------------------------------------------
    def open_editor(self, key):
        today = datetime.now().strftime("%Y-%m-%d")
        entry = self.entries.get(key, {}) if key else {}
        content = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(6),
        )
        content.add_widget(
            make_label(
                "日期",
                font_size=dp(10.5),
                color=MUTED,
                height=dp(18),
            )
        )
        date_state = {
            "text": entry.get("date", today),
        }
        date_button = make_button(
            date_state["text"],
            height=dp(40),
            font_size=dp(12.5),
            background_color=CARD_SOFT,
            color=TEXT,
        )

        def pick_date(*_):
            def apply(text):
                date_state["text"] = text
                date_button.text = text

            TimePickerPopup(
                initial_text=date_state["text"],
                mode="date",
                on_done=apply,
            ).open()

        date_button.bind(on_release=pick_date)
        content.add_widget(date_button)
        content.add_widget(
            make_label(
                "今天发生了什么",
                font_size=dp(10.5),
                color=MUTED,
                height=dp(18),
            )
        )
        text_input = TextInput(
            text=entry.get("text", ""),
            multiline=True,
            font_size=dp(12.5),
            background_normal="",
            background_active="",
            background_color=CARD_SOFT,
            foreground_color=TEXT,
            cursor_color=GREEN,
            padding=[dp(10), dp(10), dp(10), dp(10)],
            **font_args()
        )
        content.add_widget(text_input)
        message = make_label(
            "",
            font_size=dp(10),
            color=RED,
            height=dp(22),
        )
        content.add_widget(message)
        popup = Popup(
            title="写日记",
            content=content,
            size_hint=(0.94, 0.78),
            auto_dismiss=False,
        )

        def do_save(*_):
            date_text = date_state["text"].strip()
            try:
                datetime.strptime(date_text, "%Y-%m-%d")
            except ValueError:
                message.text = "日期格式不对，应为 YYYY-MM-DD"
                return
            body = text_input.text.strip()
            if not body:
                message.text = "日记内容不能为空"
                return
            self.entries[date_text] = {
                "date": date_text,
                "text": body,
                "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            try:
                self.save_entries()
            except Exception as exc:
                message.text = f"保存失败：{exc}"
                return
            self.refresh_list()
            popup.dismiss()

        def do_delete(*_):
            if not key:
                popup.dismiss()
                return
            self.entries.pop(key, None)
            try:
                self.save_entries()
            except Exception as exc:
                message.text = f"删除失败：{exc}"
                return
            self.refresh_list()
            popup.dismiss()

        buttons = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(42),
            spacing=dp(8),
        )
        buttons.add_widget(
            make_button(
                "取消",
                height=dp(42),
                font_size=dp(12.5),
                background_color=(0.520, 0.540, 0.520, 1),
                on_release=lambda *_: popup.dismiss(),
            )
        )
        if key:
            buttons.add_widget(
                make_button(
                    "删除",
                    height=dp(42),
                    font_size=dp(12.5),
                    background_color=(0.780, 0.320, 0.280, 1),
                    on_release=do_delete,
                )
            )
        buttons.add_widget(
            make_button(
                "保存",
                height=dp(42),
                font_size=dp(12.5),
                on_release=do_save,
            )
        )
        content.add_widget(buttons)
        popup.open()

    def go_back(self, *_):
        self.manager.current = "home"


# ============================================================
# 标签管理
# ============================================================
class TagsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(8), dp(16), dp(8)],
            spacing=dp(8),
        )
        top = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(10),
        )
        top.add_widget(
            make_button(
                "‹ 首页",
                size_hint=(None, None),
                size=(dp(72), dp(34)),
                font_size=dp(12),
                background_color=(0.420, 0.450, 0.410, 1),
                on_release=self.go_back,
            )
        )
        top.add_widget(
            make_label(
                "标签管理",
                font_size=dp(22),
                bold=True,
                color=GREEN,
                height=dp(36),
            )
        )
        self.count_label = make_label(
            "",
            font_size=dp(10.5),
            color=MUTED,
            halign="right",
            height=dp(36),
        )
        top.add_widget(self.count_label)
        root.add_widget(top)

        self.list_layout = GridLayout(
            cols=1,
            spacing=dp(6),
            size_hint_y=None,
        )
        self.list_layout.bind(
            minimum_height=self.list_layout.setter("height")
        )
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(2))
        scroll.add_widget(self.list_layout)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_pre_enter(self, *_):
        self.refresh_list()

    def refresh_list(self):
        self.list_layout.clear_widgets()
        home = self.manager.get_screen("home")
        counter = {}
        for item in home.saved_charts.values():
            for tag in item.get("tags", []) or []:
                counter[tag] = counter.get(tag, 0) + 1
        self.count_label.text = (
            f"{len(counter)} 个标签" if counter else ""
        )
        if not counter:
            self.list_layout.add_widget(
                make_label(
                    "还没有标签。在时间局列表点 # 给某人加标签。",
                    font_size=dp(12),
                    color=MUTED,
                    halign="center",
                    height=dp(70),
                )
            )
            return
        for tag in sorted(counter.keys(), key=lambda x: (-counter[x], x)):
            row = Card(
                orientation="horizontal",
                padding=[dp(12), dp(6), dp(10), dp(6)],
                spacing=dp(8),
                size_hint_y=None,
                height=dp(52),
                card_color=CARD,
                radius=12,
            )
            row.add_widget(
                make_label(
                    "# " + str(tag),
                    font_size=dp(14),
                    bold=True,
                    color=GOLD,
                    height=dp(40),
                )
            )
            row.add_widget(
                make_label(
                    f"{counter[tag]} 人",
                    font_size=dp(10.5),
                    color=MUTED,
                    halign="right",
                    height=dp(40),
                )
            )
            self.list_layout.add_widget(row)

    def go_back(self, *_):
        self.manager.current = "home"


# ============================================================
# 添加时间局
# ============================================================
class AddScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gender_value = "男"
        self.time_text = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.city_name = ""
        self.city_lat = None
        self.city_lon = None
        self.city_tz = ""
        self.tab_value = "公历"
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(14), dp(6), dp(14), dp(8)],
            spacing=dp(6),
        )

        top = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(6),
        )
        top.add_widget(
            make_button(
                "‹",
                size_hint=(None, None),
                size=(dp(38), dp(32)),
                font_size=dp(16),
                background_color=(0.420, 0.450, 0.410, 1),
                on_release=self.go_back,
            )
        )
        top.add_widget(
            make_label(
                "新增用户",
                font_size=dp(20),
                bold=True,
                color=GREEN,
                height=dp(36),
            )
        )
        top.add_widget(Widget())
        import_button = make_button(
            "导入",
            size_hint=(None, None),
            size=(dp(52), dp(30)),
            font_size=dp(12),
            background_color=(0, 0, 0, 0),
            color=GREEN,
        )
        import_button.bind(on_release=self.show_import)
        top.add_widget(import_button)
        root.add_widget(top)

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(2))
        form = BoxLayout(
            orientation="vertical",
            spacing=dp(4),
            size_hint_y=None,
        )
        form.bind(minimum_height=form.setter("height"))

        form.add_widget(self._field_title("名", "姓名"))
        self.name_input = make_input(hint_text="请输入姓名", height=dp(40))
        form.add_widget(self.name_input)

        form.add_widget(self._field_title("性", "性别"))
        gender_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(38),
            spacing=dp(8),
        )
        self.male_button = make_button("男", height=dp(38), font_size=dp(13))
        self.female_button = make_button(
            "女",
            height=dp(38),
            font_size=dp(13),
            background_color=CARD_SOFT,
            color=TEXT,
        )
        self.male_button.bind(on_release=lambda *_: self.set_gender("男"))
        self.female_button.bind(on_release=lambda *_: self.set_gender("女"))
        gender_row.add_widget(self.male_button)
        gender_row.add_widget(self.female_button)
        form.add_widget(gender_row)

        form.add_widget(self._field_title("地", "出生城市（选填）"))
        self.city_button = make_button(
            "未设置，默认用首页位置  ›",
            height=dp(40),
            font_size=dp(12),
            background_color=CARD_SOFT,
            color=MUTED,
        )
        self.city_button.bind(on_release=self.pick_city)
        form.add_widget(self.city_button)

        form.add_widget(self._field_title("时", "出生时间"))
        tab_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(34),
            spacing=dp(4),
        )
        self.tab_buttons = {}
        for name in ("公历", "农历", "四柱"):
            button = make_button(name, height=dp(34), font_size=dp(11.5))
            button.bind(on_release=lambda _btn, n=name: self.choose_tab(n))
            tab_row.add_widget(button)
            self.tab_buttons[name] = button
        form.add_widget(tab_row)
        self.time_button = make_button(
            self.time_text,
            height=dp(42),
            font_size=dp(13),
            background_color=CARD_SOFT,
            color=TEXT,
        )
        self.time_button.bind(on_release=self.pick_time)
        form.add_widget(self.time_button)

        form.add_widget(self._field_title("签", "默认标签"))
        self.tag_input = make_input(
            hint_text="例如：家人、客户",
            height=dp(38),
        )
        form.add_widget(self.tag_input)

        form.add_widget(
            make_label(
                "真太阳时校准",
                font_size=dp(10.5),
                color=ORANGE,
                height=dp(22),
            )
        )
        form.add_widget(Widget(size_hint_y=None, height=dp(8)))
        scroll.add_widget(form)
        root.add_widget(scroll)

        self.message = make_label(
            "",
            color=RED,
            font_size=dp(11),
            height=dp(22),
        )
        root.add_widget(self.message)
        root.add_widget(
            make_button(
                "时间局",
                height=dp(48),
                font_size=dp(15),
                background_color=(0.62, 0.62, 0.60, 1),
                on_release=self.save_chart,
            )
        )
        self.add_widget(root)
        self.refresh_tabs()

    def _field_title(self, char, text):
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(24),
            spacing=dp(4),
        )
        row.add_widget(
            make_label(
                char,
                font_size=dp(10),
                color=GREEN,
                halign="center",
                size_hint_x=None,
                width=dp(18),
                height=dp(24),
            )
        )
        row.add_widget(
            make_label(text, font_size=dp(11.5), color=GREEN, height=dp(24))
        )
        return row

    def set_gender(self, value):
        self.gender_value = value
        self.male_button.background_color = GREEN if value == "男" else CARD_SOFT
        self.male_button.color = (1, 1, 1, 1) if value == "男" else TEXT
        self.female_button.background_color = GREEN if value == "女" else CARD_SOFT
        self.female_button.color = (1, 1, 1, 1) if value == "女" else TEXT

    def choose_tab(self, name):
        self.tab_value = name
        if name != "公历":
            self.message.text = "目前仅支持公历输入，农历/四柱稍后开放"
        else:
            self.message.text = ""
        self.refresh_tabs()

    def refresh_tabs(self):
        for name, button in self.tab_buttons.items():
            active = name == self.tab_value
            button.background_color = GREEN if active else CARD_SOFT
            button.color = (1, 1, 1, 1) if active else TEXT

    def pick_time(self, *_):
        TimePickerPopup(
            initial_text=self.time_text,
            on_done=self._set_time,
        ).open()

    def _set_time(self, text):
        self.time_text = text
        self.time_button.text = text

    def pick_city(self, *_):
        CityPickerPopup(on_pick=self._set_city).open()

    def _set_city(self, name, lat, lon, tz):
        self.city_name = name
        self.city_lat = lat
        self.city_lon = lon
        self.city_tz = tz
        self.city_button.text = name + "  ›"
        self.city_button.color = TEXT

    def show_import(self, *_):
        self.message.text = "导入功能稍后开放"

    def reset_form(self):
        home = self.manager.get_screen("home")
        local_now = home.get_location_now()
        if local_now is None:
            local_now = datetime.now()
        self.name_input.text = ""
        self.time_text = local_now.strftime("%Y-%m-%d %H:%M")
        self.time_button.text = self.time_text
        self.tag_input.text = ""
        self.city_name = ""
        self.city_lat = None
        self.city_lon = None
        self.city_tz = ""
        self.city_button.text = "未设置，默认用首页位置  ›"
        self.city_button.color = MUTED
        self.tab_value = "公历"
        self.refresh_tabs()
        self.set_gender("男")
        self.message.text = ""

    def go_back(self, *_):
        self.manager.current = "home"

    def save_chart(self, *_):
        name = self.name_input.text.strip()
        time_text = self.time_text.strip()
        try:
            datetime.strptime(time_text, "%Y-%m-%d %H:%M")
        except ValueError:
            self.message.text = "时间格式不正确"
            return
        home = self.manager.get_screen("home")
        if self.city_tz:
            latitude = self.city_lat
            longitude = self.city_lon
            location_name = self.city_name
            tz_name = self.city_tz
        else:
            latitude = home.current_latitude
            longitude = home.current_longitude
            location_name = home.location_name
            tz_name = home.timezone_name
        if not tz_name:
            self.message.text = "请选择出生城市，或先回首页设置位置"
            return
        tag = self.tag_input.text.strip()
        home.pending_tags = [tag] if tag else []
        home.add_chart(
            name,
            time_text,
            self.gender_value,
            latitude=latitude,
            longitude=longitude,
            location_name=location_name,
            timezone=tz_name,
        )
        self.manager.current = "home"


# ============================================================
# 时间局详情
# ============================================================
class DetailScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(8), dp(16), dp(10)],
            spacing=dp(8),
        )
        root.add_widget(
            make_button(
                "‹ 返回列表",
                size_hint=(None, None),
                size=(dp(90), dp(34)),
                font_size=dp(12),
                background_color=(0.420, 0.450, 0.410, 1),
                on_release=self.go_back,
            )
        )
        self.title_label = make_label(
            "时间局详情",
            font_size=dp(22),
            bold=True,
            color=GREEN,
            height=dp(42),
        )
        root.add_widget(self.title_label)
        self.time_label = make_label(
            "",
            font_size=dp(11),
            color=MUTED,
            height=dp(24),
        )
        root.add_widget(self.time_label)
        self.body = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            size_hint_y=None,
        )
        self.body.bind(
            minimum_height=self.body.setter("height")
        )
        detail_scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(2),
        )
        detail_scroll.add_widget(self.body)
        root.add_widget(detail_scroll)
        self.add_widget(root)
        self._detail_request_id = 0
        self._current_key = None
        self._current_chart = None
        self._current_gender = "男"

    def show_chart(self, key):
        home = self.manager.get_screen("home")
        item = home.saved_charts.get(key, {})
        name = item.get("name", "未命名时间局")
        time_text = item.get("time", "")
        gender = item.get("gender", "男")
        if gender not in ("男", "女"):
            gender = "男"
        latitude = item.get("latitude")
        longitude = item.get("longitude")
        timezone_name = item.get("timezone")
        # 兼容旧记录：只有旧记录没有保存时区时才尝试使用首页时区。
        if latitude is None:
            latitude = home.current_latitude
        if longitude is None:
            longitude = home.current_longitude
        if not timezone_name:
            timezone_name = home.timezone_name
        self._current_key = key
        self._current_gender = gender
        self._current_chart = None
        self.title_label.text = name
        self.time_label.text = time_text
        self.show_message("正在计算排盘结果……")
        if latitude is None or longitude is None:
            self.show_message(
                "尚未设置有效位置。\n"
                "请返回首页，获取定位或手动设置城市/地址。"
            )
            return
        zone = safe_zone(timezone_name)
        if zone is None:
            self.show_message(
                "无法确定此时间局的时区。\n"
                "请返回首页，确认已成功获取地点时区后再试。"
            )
            return
        self._detail_request_id += 1
        request_id = self._detail_request_id

        def work():
            try:
                # 用户输入的是该地点的当地墙上时间。
                naive_birth = datetime.strptime(
                    time_text,
                    "%Y-%m-%d %H:%M",
                )
                birth_time = naive_birth.replace(tzinfo=zone)
                latitude_value = float(latitude)
                longitude_value = float(longitude)
                if not valid_coordinates(
                    latitude_value,
                    longitude_value,
                ):
                    raise ValueError("纬度或经度超出范围")
                chart = build_chart(
                    birth_time,
                    longitude_value,
                    gender,
                    latitude=latitude_value,
                    timezone_info=timezone_name,
                    solar_mode=home.solar_mode,
                )
                error = None
            except Exception as exc:
                chart = None
                error = f"{type(exc).__name__}: {exc}"
            Clock.schedule_once(
                lambda _dt: self.set_detail(
                    request_id,
                    chart,
                    error,
                ),
                0,
            )

        Thread(target=work, daemon=True).start()

    def show_message(self, text):
        self.body.clear_widgets()
        self.body.add_widget(
            make_label(
                text,
                font_size=dp(12.5),
                color=MUTED,
                halign="center",
                height=dp(120),
            )
        )

    def set_detail(self, request_id, chart, error):
        if request_id != self._detail_request_id:
            return
        if error or chart is None:
            self.show_message(
                "排盘计算失败\n" + str(error or "未知错误")
            )
            return
        self.render_detail(chart)

    def render_detail(self, chart):
        self.body.clear_widgets()

        # 四柱
        pillars_grid = GridLayout(
            cols=4,
            spacing=dp(6),
            size_hint_y=None,
            height=dp(168),
        )
        for name, pillar in get_pillars(chart):
            cell = Card(
                orientation="vertical",
                padding=[dp(2), dp(4), dp(2), dp(4)],
                spacing=dp(0),
                card_color=CARD_SOFT,
                radius=10,
            )
            cell.add_widget(
                make_label(
                    name + "柱",
                    font_size=dp(10),
                    color=MUTED,
                    halign="center",
                    height=dp(18),
                )
            )
            cell.add_widget(
                make_label(
                    pillar.gan,
                    font_size=dp(27),
                    bold=True,
                    color=elem_color(pillar.gan),
                    halign="center",
                    height=dp(38),
                )
            )
            cell.add_widget(
                make_label(
                    pillar.zhi,
                    font_size=dp(27),
                    bold=True,
                    color=elem_color(pillar.zhi),
                    halign="center",
                    height=dp(38),
                )
            )
            cell.add_widget(
                make_label(
                    "日主" if name == "日" else pillar.ten_god_gan,
                    font_size=dp(9),
                    color=GREEN,
                    halign="center",
                    height=dp(17),
                )
            )
            cell.add_widget(
                make_label(
                    "藏 " + "".join(pillar.hidden),
                    font_size=dp(8),
                    color=MUTED,
                    halign="center",
                    height=dp(15),
                )
            )
            cell.add_widget(
                make_label(
                    pillar.na_yin,
                    font_size=dp(8),
                    color=MUTED,
                    halign="center",
                    height=dp(15),
                )
            )
            pillars_grid.add_widget(cell)
        self.body.add_widget(pillars_grid)

        # 基础信息
        info_card = Card(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(2),
            size_hint_y=None,
            height=dp(102),
            card_color=CARD,
        )
        info_card.add_widget(
            make_label(
                "排盘时间　" + chart.birth.strftime("%Y-%m-%d %H:%M"),
                font_size=dp(11.5),
                color=TEXT,
                height=dp(24),
            )
        )
        info_card.add_widget(
            make_label(
                "真太阳时　" + chart.true_solar.strftime("%Y-%m-%d %H:%M"),
                font_size=dp(11.5),
                color=TEXT,
                height=dp(24),
            )
        )
        info_card.add_widget(
            make_label(
                "胎元 " + chart.fetal + "　　命宫 " + chart.life_palace,
                font_size=dp(11.5),
                color=TEXT,
                height=dp(24),
            )
        )
        self.body.add_widget(info_card)

        # 五行统计
        self.body.add_widget(section_title("五行统计"))
        wuxing_row = GridLayout(
            cols=5,
            spacing=dp(4),
            size_hint_y=None,
            height=dp(52),
        )
        for element in ("木", "火", "土", "金", "水"):
            count = chart.wuxing.get(element, 0)
            cell = Card(
                orientation="vertical",
                padding=[dp(1), dp(2), dp(1), dp(2)],
                spacing=dp(0),
                card_color=CARD_SOFT,
                radius=8,
            )
            cell.add_widget(
                make_label(
                    element,
                    font_size=dp(12),
                    bold=True,
                    color=ELEMENT_COLORS[element],
                    halign="center",
                    height=dp(24),
                )
            )
            cell.add_widget(
                make_label(
                    str(count),
                    font_size=dp(11),
                    color=TEXT,
                    halign="center",
                    height=dp(20),
                )
            )
            wuxing_row.add_widget(cell)
        self.body.add_widget(wuxing_row)

        # 大运
        self.body.add_widget(section_title("大运"))
        for item in chart.dayun:
            gz = str(item.get("干支", ""))
            row = Card(
                orientation="horizontal",
                padding=[dp(10), dp(4), dp(10), dp(4)],
                spacing=dp(4),
                size_hint_y=None,
                height=dp(32),
                card_color=CARD,
                radius=8,
            )
            row.add_widget(
                make_label(
                    f"{item.get('序', '')}",
                    font_size=dp(9.5),
                    color=MUTED,
                    halign="center",
                    size_hint_x=None,
                    width=dp(20),
                    height=dp(24),
                )
            )
            row.add_widget(
                make_label(
                    gz[0] if len(gz) > 0 else "",
                    font_size=dp(13),
                    bold=True,
                    color=elem_color(gz[0]) if gz else TEXT,
                    halign="center",
                    size_hint_x=None,
                    width=dp(22),
                    height=dp(24),
                )
            )
            row.add_widget(
                make_label(
                    gz[1] if len(gz) > 1 else "",
                    font_size=dp(13),
                    bold=True,
                    color=elem_color(gz[1]) if len(gz) > 1 else TEXT,
                    halign="center",
                    size_hint_x=None,
                    width=dp(22),
                    height=dp(24),
                )
            )
            row.add_widget(
                make_label(
                    f"{item.get('起运岁', '')}岁起运 · {item.get('顺逆', '')}行",
                    font_size=dp(9.5),
                    color=MUTED,
                    height=dp(24),
                )
            )
            self.body.add_widget(row)

        # 提示
        if chart.warnings:
            self.body.add_widget(section_title("注意事项"))
            warning_card = Card(
                orientation="vertical",
                padding=dp(12),
                spacing=dp(1),
                size_hint_y=None,
                height=dp(26 + 22 * len(chart.warnings)),
                card_color=CARD,
            )
            for warning in chart.warnings:
                warning_card.add_widget(
                    make_label(
                        "• " + warning,
                        font_size=dp(10.5),
                        color=ORANGE,
                        height=dp(22),
                    )
                )
            self.body.add_widget(warning_card)

        self.body.add_widget(Widget(size_hint_y=None, height=dp(8)))
        self.render_ai_section(chart)

    def render_ai_section(self, chart):
        self._current_chart = chart
        self.body.add_widget(section_title("AI 解读"))
        ai_card = Card(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(6),
            size_hint_y=None,
            height=dp(196),
            card_color=CARD,
        )
        tip = make_label(
            "填写想问的问题，点下方按钮由 AI 结合技能库条文解读。",
            font_size=dp(9.5),
            color=MUTED,
            height=dp(26),
        )
        ai_card.add_widget(tip)
        self.ai_question_input = make_input(
            hint_text="例如：这命婚姻和财运如何？",
            height=dp(40),
            font_size=dp(12),
            padding=[dp(10), dp(10), dp(10), dp(10)],
        )
        ai_card.add_widget(self.ai_question_input)
        self.ai_button = make_button(
            "开始 AI 解读",
            height=dp(42),
            font_size=dp(13),
            on_release=self.start_ai_interpret,
        )
        ai_card.add_widget(self.ai_button)
        self.ai_status = make_label(
            "",
            font_size=dp(9.5),
            color=MUTED,
            height=dp(30),
        )
        ai_card.add_widget(self.ai_status)
        self.body.add_widget(ai_card)

        self.ai_result_label = make_label(
            "",
            font_size=dp(11),
            color=TEXT,
            valign="top",
            halign="left",
            size_hint_y=None,
            height=dp(0),
        )
        self.body.add_widget(self.ai_result_label)

    def start_ai_interpret(self, *_):
        if ai_module is None:
            self.ai_status.text = "AI 模块不可用"
            return
        if self._current_chart is None:
            self.ai_status.text = "请先等待排盘完成"
            return
        home = self.manager.get_screen("home")
        config = ai_module.load_config(home.data_dir)
        if not config.get("endpoint"):
            config["endpoint"] = AI_DEFAULT_ENDPOINT
        if not config.get("model"):
            config["model"] = AI_DEFAULT_MODEL
        if not ai_module.is_configured(config):
            self.ai_status.text = "请先到「设置」填写 AI 中转地址和口令"
            return
        question = ""
        try:
            question = self.ai_question_input.text.strip()
        except Exception:
            question = ""
        self.ai_button.disabled = True
        self.ai_button.text = "解读中……"
        self.ai_status.text = "正在检索技能库并请求大模型，请稍候（约 10-60 秒）"
        self.ai_result_label.text = ""
        self.ai_result_label.height = dp(0)
        chart = self._current_chart
        gender = self._current_gender
        request_id = self._detail_request_id

        def work():
            try:
                library = get_library()
                library.load()
            except Exception:
                library = None
            try:
                text = ai_module.interpret(
                    chart,
                    gender,
                    question,
                    config,
                    library=library,
                )
                error = None
            except Exception as exc:
                text = ""
                error = f"{type(exc).__name__}: {exc}"
            Clock.schedule_once(
                lambda _dt: self.set_ai_result(
                    request_id,
                    text,
                    error,
                ),
                0,
            )

        Thread(target=work, daemon=True).start()

    def set_ai_result(self, request_id, text, error):
        if request_id != self._detail_request_id:
            return
        try:
            self.ai_button.disabled = False
            self.ai_button.text = "重新解读"
        except Exception:
            pass
        if error:
            self.ai_status.text = "解读失败"
            self.ai_result_label.text = "【出错】" + str(error)
        else:
            self.ai_status.text = "解读完成"
            self.ai_result_label.text = text
        self.ai_result_label.texture_update()
        self.ai_result_label.height = max(
            dp(0),
            self.ai_result_label.texture_size[1] + dp(16),
        )

    def go_back(self, *_):
        self.manager.current = "home"


# ============================================================
# 奇门遁甲
# ============================================================
QIMEN_ORDER = [4, 9, 2, 3, 5, 7, 8, 1, 6]


QIMEN_GONG_LABEL = {
    1: "坎1",
    2: "坤2",
    3: "震3",
    4: "巽4",
    5: "中5",
    6: "乾6",
    7: "兑7",
    8: "艮8",
    9: "离9",
}


def make_qimen_cell(item):
    """画一个奇门宫位格子。"""
    card = Card(
        orientation="vertical",
        padding=[dp(4), dp(3), dp(4), dp(3)],
        spacing=dp(1),
        size_hint_y=None,
        height=dp(90),
        card_color=CARD,
        radius=10,
    )
    top_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(14),
    )
    top_row.add_widget(
        make_label(
            item.get("palace_label", ""),
            font_size=dp(8),
            color=MUTED,
            halign="left",
            size_hint_x=None,
            width=dp(24),
            height=dp(14),
        )
    )
    top_row.add_widget(
        make_label(
            item.get("god") or "",
            font_size=dp(9),
            color=GOLD,
            halign="center",
            height=dp(14),
        )
    )
    card.add_widget(top_row)

    star = item.get("star") or ""
    door = item.get("door") or ""
    middle = " ".join(part for part in (star, door) if part)
    card.add_widget(
        make_label(
            middle,
            font_size=dp(10),
            bold=True,
            color=GREEN,
            halign="center",
            height=dp(18),
        )
    )
    gan_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(24),
    )
    tian = item.get("tian_gan") or ""
    di = item.get("di_gan") or ""
    if tian:
        gan_row.add_widget(
            make_label(
                tian,
                font_size=dp(13),
                bold=True,
                color=elem_color(tian),
                halign="center",
                height=dp(24),
            )
        )
        gan_row.add_widget(
            make_label(
                "／",
                font_size=dp(9),
                color=MUTED,
                halign="center",
                height=dp(24),
            )
        )
    gan_row.add_widget(
        make_label(
            di,
            font_size=dp(13),
            bold=True,
            color=elem_color(di),
            halign="center",
            height=dp(24),
        )
    )
    card.add_widget(gan_row)
    return card


class QimenScreen(Screen):
    """奇门遁甲：时间、地点可自选，九宫盘面。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._request_id = 0
        self.time_text = ""
        self.city_name = ""
        self.city_lat = None
        self.city_lon = None
        self.city_tz = ""
        self.tab_value = "公历"
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(12), dp(6), dp(12), dp(6)],
            spacing=dp(5),
        )

        top = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(8),
        )
        top.add_widget(
            make_button(
                "‹ 首页",
                size_hint=(None, None),
                size=(dp(68), dp(32)),
                font_size=dp(12),
                background_color=(0.420, 0.450, 0.410, 1),
                on_release=self.go_back,
            )
        )
        top.add_widget(
            make_label(
                "奇门",
                font_size=dp(20),
                bold=True,
                color=GREEN,
                height=dp(36),
            )
        )
        root.add_widget(top)

        tab_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(32),
            spacing=dp(4),
        )
        self.tab_buttons = {}
        for name in ("公历", "农历", "四柱"):
            button = make_button(name, height=dp(32), font_size=dp(11))
            button.bind(on_release=lambda _btn, n=name: self.choose_tab(n))
            tab_row.add_widget(button)
            self.tab_buttons[name] = button
        root.add_widget(tab_row)

        time_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(6),
        )
        time_row.add_widget(
            make_label("时间", font_size=dp(11), color=MUTED, size_hint_x=None, width=dp(34), height=dp(40))
        )
        self.time_button = make_button(
            "",
            height=dp(38),
            font_size=dp(13),
            background_color=CARD_SOFT,
            color=TEXT,
        )
        self.time_button.bind(on_release=self.pick_time)
        time_row.add_widget(self.time_button)
        root.add_widget(time_row)

        addr_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(6),
        )
        addr_row.add_widget(
            make_label("起盘地址", font_size=dp(11), color=MUTED, size_hint_x=None, width=dp(58), height=dp(40))
        )
        self.city_button = make_button(
            "未设置  ›",
            height=dp(38),
            font_size=dp(12),
            background_color=CARD_SOFT,
            color=TEXT,
        )
        self.city_button.bind(on_release=self.pick_city)
        addr_row.add_widget(self.city_button)
        root.add_widget(addr_row)

        calc_button = make_button(
            "计算",
            height=dp(46),
            font_size=dp(15),
            background_color=(0.90, 0.35, 0.20, 1),
            on_release=self.calculate,
        )
        root.add_widget(calc_button)

        self.status_label = make_label(
            "",
            font_size=dp(9.5),
            color=ORANGE,
            height=dp(16),
        )
        root.add_widget(self.status_label)

        content = BoxLayout(
            orientation="vertical",
            spacing=dp(4),
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter("height"))
        content.add_widget(
            make_label(
                "时间局",
                font_size=dp(13),
                bold=True,
                color=GREEN,
                height=dp(22),
            )
        )

        header = GridLayout(cols=4, spacing=dp(2), size_hint_y=None, height=dp(44))
        self.header_values = {}
        for key, label in (
            ("zhi_shi", "值使门"),
            ("xun", "旬首"),
            ("ju", "局数"),
            ("kong", "空亡"),
        ):
            cell = BoxLayout(orientation="vertical", spacing=dp(0))
            cell.add_widget(
                make_label(label, font_size=dp(9), color=RED, halign="center", height=dp(16))
            )
            value = make_label("—", font_size=dp(11), bold=True, color=TEXT, halign="center", height=dp(24))
            cell.add_widget(value)
            self.header_values[key] = value
            header.add_widget(cell)
        content.add_widget(header)

        self.grid = GridLayout(
            cols=3,
            spacing=dp(4),
            size_hint_y=None,
            height=dp(288),
        )
        content.add_widget(self.grid)

        self.detail_label = make_label(
            "",
            font_size=dp(9),
            color=MUTED,
            height=dp(18),
        )
        content.add_widget(self.detail_label)
        content.add_widget(Widget(size_hint_y=None, height=dp(6)))

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(2))
        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)
        self.refresh_tabs()

    def on_pre_enter(self, *_):
        home = self.manager.get_screen("home")
        zone = safe_zone(home.timezone_name) or safe_zone("Asia/Shanghai")
        if not self.time_text:
            self.time_text = datetime.now(zone).strftime("%Y-%m-%d %H:%M")
        self.time_button.text = self.time_text
        if not self.city_name and home.current_latitude is not None:
            name = home.location_name or ""
            if not name or name == "尚未设置位置":
                name = "首页位置"
            self.city_name = name
            self.city_lat = home.current_latitude
            self.city_lon = home.current_longitude
            self.city_tz = home.timezone_name or "Asia/Shanghai"
            self.city_button.text = name + "  ›"
        if not self.city_name:
            self.city_name = "北京市"
            self.city_lat = 39.9042
            self.city_lon = 116.4074
            self.city_tz = "Asia/Shanghai"
            self.city_button.text = "北京市"
        self.calculate()

    def go_back(self, *_):
        self.manager.current = "home"

    def choose_tab(self, name):
        self.tab_value = name
        if name != "公历":
            self.status_label.text = "目前仅支持公历起局"
        else:
            self.status_label.text = ""
        self.refresh_tabs()

    def refresh_tabs(self):
        for name, button in self.tab_buttons.items():
            active = name == self.tab_value
            button.background_color = GREEN if active else CARD_SOFT
            button.color = (1, 1, 1, 1) if active else TEXT

    def pick_time(self, *_):
        TimePickerPopup(
            initial_text=self.time_text or datetime.now().strftime("%Y-%m-%d %H:%M"),
            on_done=self._set_time,
        ).open()

    def _set_time(self, text):
        self.time_text = text
        self.time_button.text = text

    def pick_city(self, *_):
        CityPickerPopup(on_pick=self._set_city).open()

    def _set_city(self, name, lat, lon, tz):
        self.city_name = name
        self.city_lat = lat
        self.city_lon = lon
        self.city_tz = tz
        self.city_button.text = name + "  ›"

    def calculate(self, *_):
        if build_qimen is None:
            self.status_label.text = "奇门模块不可用（qimen.py 未上传）"
            return
        try:
            naive = datetime.strptime(self.time_text, "%Y-%m-%d %H:%M")
        except Exception:
            self.status_label.text = "请选择时间"
            return
        tz_name = self.city_tz or "Asia/Shanghai"
        zone = safe_zone(tz_name) or safe_zone("Asia/Shanghai")
        moment = naive.replace(tzinfo=zone)
        latitude = self.city_lat if self.city_lat is not None else 39.9042
        longitude = self.city_lon if self.city_lon is not None else 116.4074
        home = self.manager.get_screen("home")
        solar_mode = home.solar_mode
        self.status_label.text = "正在起局……"
        self._request_id += 1
        request_id = self._request_id

        def work():
            try:
                chart = build_chart(
                    moment,
                    float(longitude),
                    "男",
                    latitude=float(latitude),
                    timezone_info=tz_name,
                    solar_mode=solar_mode,
                )
                chart.birth = moment
                result = build_qimen(chart, moment=moment)
                error = None
            except Exception as exc:
                result = None
                error = f"{type(exc).__name__}: {exc}"
            Clock.schedule_once(
                lambda _dt: self.show_result(request_id, result, error),
                0,
            )

        Thread(target=work, daemon=True).start()

    def show_result(self, request_id, result, error):
        if request_id != self._request_id:
            return
        self.grid.clear_widgets()
        if error or result is None:
            self.status_label.text = "起局失败：" + str(error)
            return
        self.status_label.text = ""
        self.header_values["zhi_shi"].text = result["zhi_shi"]
        self.header_values["xun"].text = result["xun"]
        self.header_values["ju"].text = result["ju_text"].replace("阳遁", "").replace("阴遁", "")
        self.header_values["kong"].text = result["xun_kong"]
        self.detail_label.text = (
            result["ju_text"] + "　" + result["jieqi"] + "·" + result["yuan_name"]
            + "　值符 " + result["zhi_fu"] + "　时柱 " + result["hour_gz"]
        )
        palaces = {item["gong"]: item for item in result["palaces"]}
        for gong in QIMEN_ORDER:
            item = palaces.get(gong)
            if item is None:
                self.grid.add_widget(Widget())
            else:
                item["palace_label"] = QIMEN_GONG_LABEL.get(gong, "")
                self.grid.add_widget(make_qimen_cell(item))


class MoreScreen(Screen):
    """更多功能入口。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(14), dp(8), dp(14), dp(8)],
            spacing=dp(8),
        )
        top = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(44),
            spacing=dp(10),
        )
        top.add_widget(
            make_button(
                "‹ 首页",
                size_hint=(None, None),
                size=(dp(74), dp(34)),
                font_size=dp(12),
                background_color=(0.420, 0.450, 0.410, 1),
                on_release=self.go_back,
            )
        )
        top.add_widget(
            make_label(
                "更多",
                font_size=dp(22),
                bold=True,
                color=GREEN,
                height=dp(40),
            )
        )
        root.add_widget(top)

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(2))
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(6),
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter("height"))

        items = (
            ("标", "标签管理", GOLD, "tags"),
            ("日", "日记", (0.20, 0.38, 0.62, 1), "diary"),
            ("书", "技能库", GREEN, "skills"),
            ("设", "设置", (0.420, 0.450, 0.410, 1), "settings"),
        )
        for char, title, color, action in items:
            row = Card(
                orientation="horizontal",
                padding=[dp(10), dp(6), dp(10), dp(6)],
                spacing=dp(10),
                size_hint_y=None,
                height=dp(54),
                card_color=CARD,
            )
            row.add_widget(
                make_circle_button(
                    char,
                    diameter=30,
                    bg=(0.940, 0.930, 0.900, 1),
                    fg=color,
                    on_release=lambda a=action: self.open_item(a),
                )
            )
            row.add_widget(
                make_label(
                    title,
                    font_size=dp(14),
                    color=TEXT,
                    height=dp(30),
                )
            )
            arrow = make_button(
                "›",
                size_hint=(None, None),
                size=(dp(30), dp(30)),
                font_size=dp(16),
                background_color=(0.900, 0.890, 0.860, 1),
                color=MUTED,
                on_release=lambda _btn, a=action: self.open_item(a),
            )
            row.add_widget(arrow)
            content.add_widget(row)

        content.add_widget(Widget(size_hint_y=None, height=dp(10)))
        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def go_back(self, *_):
        self.manager.current = "home"

    def open_item(self, action, *_args):
        # 按钮回调可能把按钮实例传进来，这里只接受字符串
        if not isinstance(action, str):
            return
        if action not in ("skills", "tags", "diary", "settings", "more"):
            return
        self.manager.current = action


# ============================================================
# 应用入口
# ============================================================
class WuxingApp(App):
    title = "五行排盘"

    def build(self):
        Window.clearcolor = BG
        manager = ScreenManager()
        manager.add_widget(HomeScreen(name="home"))
        manager.add_widget(SettingsScreen(name="settings"))
        manager.add_widget(SkillsScreen(name="skills"))
        manager.add_widget(DiaryScreen(name="diary"))
        manager.add_widget(TagsScreen(name="tags"))
        manager.add_widget(SkillDetailScreen(name="skill_detail"))
        manager.add_widget(AddScreen(name="add"))
        manager.add_widget(DetailScreen(name="detail"))
        manager.add_widget(QimenScreen(name="qimen"))
        manager.add_widget(MoreScreen(name="more"))
        # iOS 上给刘海和底部指示条留白，避免顶部标题被摄像头挡住
        root = BoxLayout(
            orientation="vertical",
            padding=[0, safe_top(), 0, safe_bottom()],
        )
        root.add_widget(manager)
        return root
