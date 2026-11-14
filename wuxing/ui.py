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
        top_bar.add_widget(
            make_circle_button(
                "信",
                diameter=38,
                bg=GREEN_LIGHT,
                on_release=self.open_messages,
            )
        )
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
        self.gender_button = make_button(
            "男",
            size_hint=(None, None),
            size=(dp(34), dp(22)),
            font_size=dp(11),
            background_color=GREEN_LIGHT,
            color=GREEN,
        )
        self.gender_button.bind(on_release=self.toggle_current_gender)
        title_row.add_widget(self.gender_button)
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
            ("标", "标签管理", GOLD, "tags"),
            ("日", "日记", (0.20, 0.38, 0.62, 1), "diary"),
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

        def callback(timezone_name, error):
            def apply_result(_dt):
                nonlocal timezone_name
                self._timezone_requesting = False
                if error or not timezone_name:
                    self.location_error = (
                        "获取时区失败："
                        + str(error or "服务没有返回时区")
                    )
                    self.update_location_hint()
                    return
                timezone_name = str(timezone_name).strip()
                if safe_zone(timezone_name) is None:
                    self.location_error = (
                        "已收到时区名称，"
                        "但本机时区数据库不可用："
                        + timezone_name
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
                self.timezone_name = timezone_name
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

    def toggle_current_gender(self, *_):
        self.current_gender = (
            "女" if self.current_gender == "男" else "男"
        )
        self.gender_button.text = self.current_gender
        self._last_minute_key = None
        self.refresh_current(force=True)

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

    def on_icon_action(self, title, action):
        if action == "diary":
            self.manager.current = "diary"
            return
        if action == "tags":
            self.manager.current = "tags"
            return
        self.show_placeholder(title)

    def open_messages(self, *_):
        self.show_placeholder("消息")

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

    def add_chart(self, name, time_text, gender="男"):
        key = datetime.now().strftime("%Y%m%d%H%M%S%f")
        item = {
            "name": name.strip() or "未命名时间局",
            "time": time_text.strip(),
            "gender": gender if gender in ("男", "女") else "男",
            "longitude": self.current_longitude,
            "latitude": self.current_latitude,
            "location_name": self.location_name,
            "timezone": self.timezone_name,
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
        self.ai_endpoint_input.text = config.get("endpoint", "")
        self.ai_token_input.text = config.get("token", "")
        self.ai_model_input.text = config.get("model", "")
        if ai_module.is_configured(config):
            self.ai_status_label.text = (
                "已配置 · " + ai_module.describe_config(config)
            )
        else:
            self.ai_status_label.text = "未配置（填写后点保存）"

    def save_ai_config(self, *_):
        if ai_module is None:
            self.ai_status_label.text = "AI 模块不可用"
            return
        config = {
            "endpoint": self.ai_endpoint_input.text.strip(),
            "token": self.ai_token_input.text.strip(),
            "model": self.ai_model_input.text.strip()
            or ai_module.DEFAULT_MODEL,
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
        try:
            self.library = get_library()
            self.library.load()
        except Exception as exc:
            self.library = None
            self.status_label.text = "技能库不可用：" + str(exc)
            return
        info = self.library.stats()
        if not info.get("loaded"):
            self.status_label.text = (
                "未找到 skills.zip，请先上传到仓库根目录。"
            )
        else:
            self.status_label.text = (
                f"来源 {info.get('source', '')}"
                f" · {info['skills']} 个技能"
            )
        self.render()

    def on_search(self, _instance, _value):
        self.render()

    def go_back(self, *_):
        self.manager.current = "settings"

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
                        item["description"][:46] or item["title"],
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
        self.body_text.text = item["body"] or item["text"]
        self.body_text.texture_update()
        self.body_text.height = max(
            dp(600),
            self.body_text.texture_size[1] + dp(30),
        )

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
                "日期（YYYY-MM-DD）",
                font_size=dp(10.5),
                color=MUTED,
                height=dp(18),
            )
        )
        date_input = make_input(
            text=entry.get("date", today),
            height=dp(40),
            font_size=dp(12.5),
        )
        content.add_widget(date_input)
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
            date_text = date_input.text.strip()
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
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(8), dp(16), dp(10)],
            spacing=dp(10),
        )
        root.add_widget(
            make_button(
                "‹ 返回首页",
                size_hint=(None, None),
                size=(dp(90), dp(34)),
                font_size=dp(12),
                background_color=(0.420, 0.450, 0.410, 1),
                on_release=self.go_back,
            )
        )
        root.add_widget(
            make_label(
                "添加时间局",
                font_size=dp(24),
                bold=True,
                color=GREEN,
                height=dp(46),
            )
        )
        form_card = Card(
            orientation="vertical",
            padding=dp(14),
            spacing=dp(6),
            size_hint_y=None,
            height=dp(322),
        )
        form_card.add_widget(
            make_label("名字", font_size=dp(12.5), bold=True, color=GREEN, height=dp(24))
        )
        self.name_input = make_input(
            hint_text="例如：我的命盘"
        )
        form_card.add_widget(self.name_input)
        form_card.add_widget(
            make_label("时间", font_size=dp(12.5), bold=True, color=GREEN, height=dp(24))
        )
        self.time_input = make_input(
            text=datetime.now().strftime("%Y-%m-%d %H:%M"),
            hint_text="YYYY-MM-DD HH:MM",
        )
        form_card.add_widget(self.time_input)
        form_card.add_widget(
            make_label("性别", font_size=dp(12.5), bold=True, color=GREEN, height=dp(24))
        )
        self.gender_value = "男"
        self.gender_button = make_button(
            "男（点击切换为女）",
            height=dp(40),
            font_size=dp(13),
            background_color=GOLD,
        )
        self.gender_button.bind(
            on_release=self.toggle_gender
        )
        form_card.add_widget(self.gender_button)
        form_card.add_widget(
            make_label(
                "格式示例：2026-10-17 13:30",
                font_size=dp(10.5),
                color=MUTED,
                height=dp(22),
            )
        )
        root.add_widget(form_card)
        self.message = make_label(
            "",
            color=RED,
            font_size=dp(12),
            height=dp(36),
        )
        root.add_widget(self.message)
        root.add_widget(
            make_button(
                "保存时间局",
                height=dp(48),
                font_size=dp(15),
                on_release=self.save_chart,
            )
        )
        root.add_widget(Widget())
        self.add_widget(root)

    def toggle_gender(self, *_):
        self.gender_value = (
            "女" if self.gender_value == "男" else "男"
        )
        self.gender_button.text = (
            "男（点击切换为女）"
            if self.gender_value == "男"
            else "女（点击切换为男）"
        )

    def reset_form(self):
        home = self.manager.get_screen("home")
        local_now = home.get_location_now()
        if local_now is None:
            local_now = datetime.now()
        self.name_input.text = ""
        self.time_input.text = local_now.strftime(
            "%Y-%m-%d %H:%M"
        )
        self.gender_value = "男"
        self.gender_button.text = "男（点击切换为女）"
        self.message.text = ""

    def go_back(self, *_):
        self.manager.current = "home"

    def save_chart(self, *_):
        name = self.name_input.text.strip()
        time_text = self.time_input.text.strip()
        try:
            datetime.strptime(time_text, "%Y-%m-%d %H:%M")
        except ValueError:
            self.message.text = (
                "时间格式不正确，请使用 YYYY-MM-DD HH:MM"
            )
            return
        home = self.manager.get_screen("home")
        if not home.timezone_name:
            self.message.text = (
                "尚未取得地点时区，请先返回首页设置位置。"
            )
            return
        home.add_chart(name, time_text, self.gender_value)
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
        return manager
