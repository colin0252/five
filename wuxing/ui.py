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


# ============================================================
# 首页
# ============================================================
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

        root = BoxLayout(
            orientation="vertical",
            padding=[dp(14), dp(8), dp(14), dp(8)],
            spacing=dp(8),
        )

        # ---------------- 顶部标题 ----------------
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(46),
            spacing=dp(8),
        )
        title_box = BoxLayout(
            orientation="vertical",
            spacing=dp(0),
        )
        title_box.add_widget(
            make_label(
                "五行排盘",
                font_size=dp(26),
                bold=True,
                color=GREEN,
                height=dp(32),
            )
        )
        title_box.add_widget(
            make_label(
                "时间与命理",
                font_size=dp(10),
                color=MUTED,
                height=dp(14),
            )
        )
        header.add_widget(title_box)
        settings_button = make_button(
            "设置",
            size_hint=(None, None),
            size=(dp(58), dp(30)),
            font_size=dp(12),
            background_color=GREEN_LIGHT,
            color=GREEN,
        )
        settings_button.bind(on_release=self.open_settings)
        header.add_widget(settings_button)
        root.add_widget(header)

        # ---------------- 即时局主卡片 ----------------
        main_card = Card(
            orientation="horizontal",
            padding=dp(10),
            spacing=dp(8),
            size_hint_y=None,
            height=dp(318),
            card_color=CARD,
        )
        side_card = Card(
            orientation="vertical",
            size_hint=(None, 1),
            width=dp(38),
            padding=[dp(2), dp(12), dp(2), dp(12)],
            spacing=dp(2),
            card_color=(0.940, 0.925, 0.895, 1),
            radius=10,
        )
        for char in ("即", "时", "局"):
            side_card.add_widget(
                make_label(
                    char,
                    font_size=dp(20),
                    bold=True,
                    color=GOLD,
                    halign="center",
                    height=dp(34),
                )
            )
        side_card.add_widget(Widget())
        main_card.add_widget(side_card)

        content = BoxLayout(
            orientation="vertical",
            spacing=dp(5),
        )
        now_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(24),
        )
        now_row.add_widget(
            make_label(
                "即时局",
                font_size=dp(14),
                bold=True,
                color=GREEN,
                height=dp(24),
            )
        )
        self.now_label = make_label(
            "当地时间 --:--:--",
            font_size=dp(11),
            color=MUTED,
            halign="right",
            height=dp(24),
        )
        now_row.add_widget(self.now_label)
        content.add_widget(now_row)

        self.pillars_grid = GridLayout(
            cols=4,
            spacing=dp(6),
            size_hint_y=None,
            height=dp(160),
        )
        self.pillar_cells = []
        for name in ("年", "月", "日", "时"):
            cell = Card(
                orientation="vertical",
                padding=[dp(2), dp(4), dp(2), dp(4)],
                spacing=dp(0),
                card_color=CARD_SOFT,
                radius=10,
            )
            cell.add_widget(
                make_label(
                    name,
                    font_size=dp(11),
                    color=MUTED,
                    halign="center",
                    height=dp(20),
                )
            )
            gan_label = make_label(
                "—",
                font_size=dp(31),
                bold=True,
                halign="center",
                height=dp(44),
            )
            zhi_label = make_label(
                "—",
                font_size=dp(31),
                bold=True,
                halign="center",
                height=dp(44),
            )
            na_label = make_label(
                "",
                font_size=dp(9),
                color=MUTED,
                halign="center",
                height=dp(16),
            )
            cell.add_widget(gan_label)
            cell.add_widget(zhi_label)
            cell.add_widget(na_label)
            self.pillars_grid.add_widget(cell)
            self.pillar_cells.append(
                (gan_label, zhi_label, na_label)
            )
        content.add_widget(self.pillars_grid)

        info_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(22),
            spacing=dp(8),
        )
        self.birth_label = make_label(
            "排盘 --",
            font_size=dp(10.5),
            color=MUTED,
            height=dp(22),
        )
        self.solar_label = make_label(
            "真太阳时 等待计算",
            font_size=dp(10.5),
            color=MUTED,
            height=dp(22),
        )
        info_row.add_widget(self.birth_label)
        info_row.add_widget(self.solar_label)
        content.add_widget(info_row)

        self.location_hint = make_label(
            "",
            font_size=dp(10),
            color=ORANGE,
            height=dp(16),
        )
        content.add_widget(self.location_hint)

        buttons = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(8),
        )
        self.gender_button = make_button(
            "即时排盘：男",
            height=dp(40),
            font_size=dp(13),
            background_color=GOLD,
        )
        self.gender_button.bind(
            on_release=self.toggle_current_gender
        )
        location_button = make_button(
            "位置设置",
            height=dp(40),
            font_size=dp(13),
            background_color=(0.36, 0.44, 0.38, 1),
        )
        location_button.bind(on_release=self.open_settings)
        buttons.add_widget(self.gender_button)
        buttons.add_widget(location_button)
        content.add_widget(buttons)

        main_card.add_widget(content)
        root.add_widget(main_card)

        # ---------------- 功能占位 ----------------
        feature_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(60),
            spacing=dp(8),
        )

        def make_feature(icon, title, subtitle, color):
            card = Card(
                orientation="horizontal",
                padding=[dp(12), dp(8), dp(12), dp(8)],
                spacing=dp(10),
                card_color=GREEN_LIGHT,
                radius=12,
            )
            card.add_widget(
                make_label(
                    icon,
                    font_size=dp(22),
                    color=color,
                    halign="center",
                    size_hint=(None, 1),
                    width=dp(30),
                )
            )
            text_box = BoxLayout(
                orientation="vertical",
                spacing=dp(0),
            )
            text_box.add_widget(
                make_label(
                    title,
                    font_size=dp(13),
                    bold=True,
                    color=GREEN,
                    height=dp(22),
                )
            )
            text_box.add_widget(
                make_label(
                    subtitle,
                    font_size=dp(9),
                    color=MUTED,
                    height=dp(16),
                )
            )
            card.add_widget(text_box)
            return card

        feature_row.add_widget(
            make_feature("☯", "奇门遁甲", "预留", GREEN)
        )
        feature_row.add_widget(
            make_feature("◉", "罗盘", "预留", GOLD)
        )
        root.add_widget(feature_row)

        # ---------------- 我的时间局 ----------------
        list_header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(30),
        )
        list_header.add_widget(
            make_label(
                "我的时间局",
                font_size=dp(18),
                bold=True,
                color=GREEN,
                height=dp(30),
            )
        )
        self.count_label = make_label(
            "",
            font_size=dp(11),
            color=MUTED,
            halign="right",
            height=dp(30),
        )
        list_header.add_widget(self.count_label)
        root.add_widget(list_header)

        self.list_layout = GridLayout(
            cols=1,
            spacing=dp(8),
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
            height=dp(50),
        )
        bottom.add_widget(Widget())
        add_button = make_button(
            "+",
            size_hint=(None, None),
            size=(dp(50), dp(50)),
            font_size=dp(30),
        )
        add_button.bind(on_release=self.open_add)
        bottom.add_widget(add_button)
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
        if now is None:
            self.now_label.text = "当地时间 --:--:--"
            return
        self.now_label.text = (
            "当地时间 " + now.strftime("%H:%M:%S")
        )

    def toggle_current_gender(self, *_):
        self.current_gender = (
            "女" if self.current_gender == "男" else "男"
        )
        self.gender_button.text = (
            f"即时排盘：{self.current_gender}"
        )
        self._last_minute_key = None
        self.refresh_current(force=True)

    def refresh_current(self, *_args, force=False):
        if (
            self.current_latitude is None
            or self.current_longitude is None
        ):
            self.birth_label.text = "排盘 请先设置位置"
            self.solar_label.text = "真太阳时 --:--"
            return
        zone = safe_zone(self.timezone_name)
        if zone is None:
            self.birth_label.text = "排盘 等待时区"
            self.solar_label.text = "真太阳时 --:--"
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
        self.birth_label.text = (
            "排盘 " + now.strftime("%m-%d %H:%M")
        )
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
            gan_label, zhi_label, na_label = self.pillar_cells[index]
            gan_label.text = pillar.gan
            zhi_label.text = pillar.zhi
            na_label.text = pillar.na_yin
            gan_label.color = elem_color(pillar.gan)
            zhi_label.color = elem_color(pillar.zhi)
        self.birth_label.text = f"排盘 {birth}"
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

    def refresh_list(self):
        self.list_layout.clear_widgets()
        self.count_label.text = (
            f"共 {len(self.saved_charts)} 局"
            if self.saved_charts
            else ""
        )
        if not self.saved_charts:
            self.list_layout.add_widget(
                make_label(
                    "还没有保存的时间局",
                    font_size=dp(12),
                    color=MUTED,
                    halign="center",
                    height=dp(52),
                )
            )
            return
        for key, item in reversed(
            list(self.saved_charts.items())
        ):
            name = item.get("name", "未命名时间局")
            time_text = item.get("time", "")
            card = Card(
                orientation="horizontal",
                padding=[dp(12), dp(6), dp(8), dp(6)],
                spacing=dp(8),
                size_hint_y=None,
                height=dp(64),
                card_color=CARD,
                radius=12,
            )
            info = BoxLayout(
                orientation="vertical",
                spacing=dp(0),
            )
            info.add_widget(
                make_label(
                    name,
                    font_size=dp(15),
                    bold=True,
                    color=GREEN,
                    height=dp(30),
                )
            )
            info.add_widget(
                make_label(
                    time_text,
                    font_size=dp(11),
                    color=MUTED,
                    height=dp(20),
                )
            )
            card.add_widget(info)
            open_button = make_button(
                "查看 ›",
                size_hint=(None, None),
                size=(dp(70), dp(36)),
                font_size=dp(12),
                background_color=GREEN_LIGHT,
                color=GREEN,
            )
            open_button.bind(
                on_release=lambda _btn, chart_key=key: (
                    self.open_detail(chart_key)
                )
            )
            card.add_widget(open_button)
            self.list_layout.add_widget(card)

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
        }
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
            spacing=dp(3),
            size_hint_y=None,
            height=dp(104),
            card_color=CARD,
        )
        solar_card.add_widget(
            make_label(
                "当前口径：平太阳时（仅按经度校正）",
                font_size=dp(13),
                bold=True,
                color=TEXT,
                height=dp(26),
            )
        )
        solar_card.add_widget(
            make_label(
                "与主流排盘软件一致；天文真太阳时（含均时差）将在后续版本提供切换。",
                font_size=dp(10.5),
                color=MUTED,
                height=dp(40),
            )
        )
        content.add_widget(solar_card)

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
        manager.add_widget(AddScreen(name="add"))
        manager.add_widget(DetailScreen(name="detail"))
        return manager
