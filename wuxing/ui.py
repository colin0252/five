
# wuxing/ui.py
import os
import json
from datetime import datetime
from threading import Thread

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
from .location import get_location, resolve_location


# ============================================================
# 颜色与字体
# ============================================================

BG = (0.97, 0.96, 0.93, 1)
CARD = (1.00, 0.99, 0.96, 1)
GREEN = (0.08, 0.31, 0.25, 1)
GREEN_LIGHT = (0.89, 0.93, 0.87, 1)
GOLD = (0.58, 0.39, 0.10, 1)
TEXT = (0.20, 0.24, 0.23, 1)
MUTED = (0.43, 0.47, 0.48, 1)
RED = (0.82, 0.18, 0.18, 1)
BLUE = (0.10, 0.48, 0.85, 1)
BROWN = (0.52, 0.34, 0.13, 1)
ORANGE = (0.92, 0.39, 0.03, 1)

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

FONT_PATH = os.path.join(
    PROJECT_ROOT, "fonts", "NotoSansSC-Regular.ttf"
)

FONT_ARGS = (
    {"font_name": FONT_PATH}
    if os.path.isfile(FONT_PATH)
    else {}
)


def font_args():
    return FONT_ARGS.copy()


def make_label(text="", **kwargs):
    kwargs.setdefault("color", TEXT)
    kwargs.setdefault("font_size", dp(15))
    kwargs.setdefault("halign", "left")
    kwargs.setdefault("valign", "middle")
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", dp(34))
    kwargs.update(font_args())

    label = Label(text=str(text), **kwargs)

    def update_text_size(instance, *_):
        instance.text_size = (instance.width, None)

    label.bind(size=update_text_size)
    return label


def make_button(text, **kwargs):
    kwargs.setdefault("font_size", dp(15))
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", dp(44))
    kwargs.setdefault("background_normal", "")
    kwargs.setdefault("background_down", "")
    kwargs.setdefault("background_color", GREEN)
    kwargs.setdefault("color", (1, 1, 1, 1))
    kwargs.update(font_args())
    return Button(text=text, **kwargs)


def make_input(**kwargs):
    kwargs.setdefault("font_size", dp(16))
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", dp(48))
    kwargs.setdefault("multiline", False)
    kwargs.setdefault("background_normal", "")
    kwargs.setdefault("background_active", "")
    kwargs.setdefault("background_color", CARD)
    kwargs.setdefault("foreground_color", TEXT)
    kwargs.setdefault("cursor_color", GREEN)
    kwargs.setdefault(
        "padding", [dp(12), dp(12), dp(12), dp(12)]
    )
    kwargs.update(font_args())
    return TextInput(**kwargs)


class Card(BoxLayout):
    def __init__(self, card_color=CARD, radius=15, **kwargs):
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


# ============================================================
# 排盘结果格式化
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
            chart, ensure_ascii=False, indent=2, default=str
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
            self.data_dir, "time_charts.json"
        )
        self.location_path = os.path.join(
            self.data_dir, "location.json"
        )

        self.saved_charts = self.load_saved_charts()

        # 没有取得定位时不假装用户在北京。
        self.current_latitude = None
        self.current_longitude = None
        self.location_name = "尚未设置位置"
        self.location_source = "none"
        self.location_error = None

        self._location_requesting = False
        self._chart_request_id = 0
        self._last_minute_key = None
        self._clock_event = None
        self._minute_event = None

        self.load_location()

        root = BoxLayout(
            orientation="vertical",
            padding=[dp(12), dp(6), dp(12), dp(6)],
            spacing=dp(7),
        )

        # 顶部标题
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(42),
            spacing=dp(6),
        )

        header.add_widget(
            make_label(
                "五行排盘",
                font_size=dp(24),
                bold=True,
                color=GREEN,
            )
        )
        header.add_widget(
            make_label(
                "时间与命理",
                font_size=dp(12),
                color=MUTED,
                halign="right",
            )
        )
        root.add_widget(header)

        # 即时局主卡片
        main_card = Card(
            orientation="horizontal",
            padding=dp(8),
            spacing=dp(8),
            size_hint_y=None,
            height=dp(350),
            card_color=CARD,
        )

        side_card = Card(
            orientation="vertical",
            size_hint=(None, 1),
            width=dp(42),
            padding=[dp(2), dp(10), dp(2), dp(10)],
            spacing=dp(4),
            card_color=(0.93, 0.91, 0.84, 1),
        )

        for char in ("即", "时", "局"):
            side_card.add_widget(
                make_label(
                    char,
                    font_size=dp(24),
                    bold=True,
                    color=GOLD,
                    halign="center",
                    height=dp(42),
                )
            )

        side_card.add_widget(Widget())
        main_card.add_widget(side_card)

        content = BoxLayout(
            orientation="vertical",
            spacing=dp(6),
        )

        # 当前系统时间独立刷新，不依赖排盘是否完成
        self.now_label = make_label(
            "当前时间：正在读取……",
            font_size=dp(13),
            color=GREEN,
            height=dp(26),
        )
        content.add_widget(self.now_label)

        self.pillars_grid = GridLayout(
            cols=4,
            spacing=dp(4),
            size_hint_y=None,
            height=dp(150),
        )

        self.pillar_cells = []

        for name in ("年", "月", "日", "时"):
            cell = Card(
                orientation="vertical",
                padding=[dp(1), dp(3), dp(1), dp(3)],
                spacing=dp(1),
                card_color=GREEN_LIGHT,
                radius=9,
            )

            cell.add_widget(
                make_label(
                    name,
                    font_size=dp(13),
                    bold=True,
                    halign="center",
                    height=dp(28),
                )
            )

            gan_label = make_label(
                "—",
                font_size=dp(25),
                bold=True,
                halign="center",
                height=dp(45),
            )
            zhi_label = make_label(
                "—",
                font_size=dp(25),
                bold=True,
                halign="center",
                height=dp(45),
            )

            cell.add_widget(gan_label)
            cell.add_widget(zhi_label)
            self.pillars_grid.add_widget(cell)
            self.pillar_cells.append((gan_label, zhi_label))

        content.add_widget(self.pillars_grid)

        # 时间、真太阳时、位置
        self.birth_label = make_label(
            "排盘时间：等待计算",
            font_size=dp(11),
            color=GREEN,
            height=dp(24),
        )
        self.solar_label = make_label(
            "真太阳时：等待计算",
            font_size=dp(11),
            color=GREEN,
            height=dp(24),
        )
        self.location_label = make_label(
            "",
            font_size=dp(11),
            color=GREEN,
            height=dp(40),
        )

        content.add_widget(self.birth_label)
        content.add_widget(self.solar_label)
        content.add_widget(self.location_label)

        buttons = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(36),
            spacing=dp(6),
        )

        self.location_button = make_button(
            "获取定位",
            height=dp(36),
            font_size=dp(12),
        )
        self.location_button.bind(
            on_release=self.request_location
        )

        manual_button = make_button(
            "设置城市/地址",
            height=dp(36),
            font_size=dp(12),
            background_color=(0.32, 0.42, 0.34, 1),
        )
        manual_button.bind(
            on_release=self.open_location_popup
        )

        buttons.add_widget(self.location_button)
        buttons.add_widget(manual_button)
        content.add_widget(buttons)

        main_card.add_widget(content)
        root.add_widget(main_card)

        # 功能占位区
        feature_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(68),
            spacing=dp(8),
        )

        qimen_card = Card(
            orientation="vertical",
            padding=dp(4),
            card_color=GREEN_LIGHT,
        )
        qimen_card.add_widget(
            make_label(
                "☯",
                font_size=dp(23),
                color=GREEN,
                halign="center",
                height=dp(30),
            )
        )
        qimen_card.add_widget(
            make_label(
                "奇门遁甲（预留）",
                font_size=dp(13),
                bold=True,
                color=GREEN,
                halign="center",
                height=dp(24),
            )
        )

        compass_card = Card(
            orientation="vertical",
            padding=dp(4),
            card_color=CARD,
        )
        compass_card.add_widget(
            make_label(
                "◉",
                font_size=dp(23),
                color=GOLD,
                halign="center",
                height=dp(30),
            )
        )
        compass_card.add_widget(
            make_label(
                "罗盘（预留）",
                font_size=dp(13),
                bold=True,
                color=GREEN,
                halign="center",
                height=dp(24),
            )
        )

        feature_row.add_widget(qimen_card)
        feature_row.add_widget(compass_card)
        root.add_widget(feature_row)

        root.add_widget(
            make_label(
                "我的时间局",
                font_size=dp(20),
                bold=True,
                color=GREEN,
                height=dp(34),
            )
        )

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
            height=dp(52),
        )
        bottom.add_widget(Widget())

        add_button = make_button(
            "+",
            size_hint=(None, None),
            size=(dp(52), dp(52)),
            font_size=dp(32),
        )
        add_button.bind(on_release=self.open_add)
        bottom.add_widget(add_button)
        root.add_widget(bottom)

        self.add_widget(root)

        self.refresh_list()
        self.update_location_label()

    # --------------------------------------------------------
    # 本地位置设置保存
    # --------------------------------------------------------

    def load_location(self):
        if not os.path.isfile(self.location_path):
            return

        try:
            with open(
                self.location_path, "r", encoding="utf-8"
            ) as file:
                data = json.load(file)

            lat = data.get("latitude")
            lon = data.get("longitude")

            if lat is not None and lon is not None:
                lat = float(lat)
                lon = float(lon)

                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    self.current_latitude = lat
                    self.current_longitude = lon
                    self.location_name = data.get(
                        "name", "已保存的位置"
                    )
                    self.location_source = data.get(
                        "source", "manual"
                    )
        except Exception as exc:
            print(f"[Location] 读取位置失败：{exc}")

    def save_location(self):
        os.makedirs(self.data_dir, exist_ok=True)

        data = {
            "latitude": self.current_latitude,
            "longitude": self.current_longitude,
            "name": self.location_name,
            "source": self.location_source,
        }

        temp_path = self.location_path + ".tmp"

        with open(
            temp_path, "w", encoding="utf-8"
        ) as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

        os.replace(temp_path, self.location_path)

    def update_location_label(self):
        if (
            self.current_latitude is None
            or self.current_longitude is None
        ):
            text = (
                f"位置：{self.location_name}\n"
                "请获取定位，或手动设置城市/地址"
            )
        else:
            text = (
                f"位置：{self.location_name}\n"
                f"纬度 {self.current_latitude:.4f}°  "
                f"经度 {self.current_longitude:.4f}°"
            )

        if self.location_error:
            text += f"\n提示：{self.location_error}"

        self.location_label.text = text

    # --------------------------------------------------------
    # 设备定位
    # --------------------------------------------------------

    def request_location(self, *_):
        if self._location_requesting:
            return

        self._location_requesting = True
        self.location_button.disabled = True
        self.location_button.text = "正在定位……"
        self.location_error = None

        self.location_label.text = (
            "正在请求 iPhone 定位……\n"
            "请允许本 App 使用定位服务"
        )

        def callback(lat, lon, source, error):
            Clock.schedule_once(
                lambda _dt: self.on_location_result(
                    lat, lon, source, error
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
        self.location_button.disabled = False
        self.location_button.text = "获取定位"

        if error or lat is None or lon is None:
            self.location_error = error or "没有取得有效定位坐标。"
            self.update_location_label()
            print(f"[Location] {self.location_error}")
            return

        try:
            lat = float(lat)
            lon = float(lon)

            if not -90 <= lat <= 90:
                raise ValueError("纬度超出范围")
            if not -180 <= lon <= 180:
                raise ValueError("经度超出范围")
        except (TypeError, ValueError) as exc:
            self.location_error = f"定位坐标无效：{exc}"
            self.update_location_label()
            return

        self.current_latitude = lat
        self.current_longitude = lon
        self.location_source = source or "gps"
        self.location_name = "iPhone 设备定位"
        self.location_error = None

        try:
            self.save_location()
        except Exception as exc:
            print(f"[Location] 保存位置失败：{exc}")

        self.update_location_label()
        self.refresh_current(force=True)

    # --------------------------------------------------------
    # 手动设置城市、地址或坐标
    # --------------------------------------------------------

    def open_location_popup(self, *_):
        content = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(8),
        )

        content.add_widget(
            make_label(
                "输入城市、完整地址，或直接输入纬度,经度",
                font_size=dp(13),
                color=MUTED,
                height=dp(34),
            )
        )

        current_text = ""
        if (
            self.current_latitude is not None
            and self.current_longitude is not None
        ):
            current_text = (
                f"{self.current_latitude:.6f}, "
                f"{self.current_longitude:.6f}"
            )

        query_input = make_input(
            text="",
            hint_text="例如 Los Angeles, CA, USA",
        )
        content.add_widget(query_input)

        if current_text:
            content.add_widget(
                make_label(
                    f"当前坐标：{current_text}",
                    font_size=dp(11),
                    color=MUTED,
                    height=dp(24),
                )
            )

        message = make_label(
            "城市/地址解析需要网络连接。",
            font_size=dp(12),
            color=MUTED,
            height=dp(40),
        )
        content.add_widget(message)

        popup = Popup(
            title="设置位置",
            content=content,
            size_hint=(0.92, 0.55),
            auto_dismiss=True,
        )

        def do_resolve(*_):
            query = query_input.text.strip()

            if not query:
                message.text = "请先输入城市、地址或坐标。"
                return

            message.text = "正在解析位置……"
            resolve_button.disabled = True

            def callback(lat, lon, name, error):
                def apply_result(_dt):
                    resolve_button.disabled = False

                    if error or lat is None or lon is None:
                        message.text = (
                            "解析失败："
                            + (error or "没有返回坐标")
                        )
                        return

                    try:
                        lat_value = float(lat)
                        lon_value = float(lon)

                        if not -90 <= lat_value <= 90:
                            raise ValueError("纬度超出范围")
                        if not -180 <= lon_value <= 180:
                            raise ValueError("经度超出范围")
                    except (TypeError, ValueError) as exc:
                        message.text = f"坐标无效：{exc}"
                        return

                    self.current_latitude = lat_value
                    self.current_longitude = lon_value
                    self.location_name = name or query
                    self.location_source = "manual"
                    self.location_error = None

                    try:
                        self.save_location()
                    except Exception as exc:
                        print(f"[Location] 保存失败：{exc}")

                    self.update_location_label()
                    self.refresh_current(force=True)
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
                "提示：坐标格式为 纬度,经度，例如 34.0522,-118.2437",
                font_size=dp(11),
                color=MUTED,
                height=dp(32),
            )
        )

        popup.open()

    # --------------------------------------------------------
    # 当前时间和排盘刷新
    # --------------------------------------------------------

    def on_pre_enter(self, *_):
        if self._clock_event is None:
            self._clock_event = Clock.schedule_interval(
                self.update_current_time, 1
            )

        if self._minute_event is None:
            self._minute_event = Clock.schedule_interval(
                self.refresh_current, 60
            )

        self.update_current_time(0)
        self.refresh_current(force=True)

        # 只在没有已保存位置时，自动尝试定位。
        if (
            self.current_latitude is None
            or self.current_longitude is None
        ):
            Clock.schedule_once(
                lambda _dt: self.request_location(),
                0.5,
            )

    def on_leave(self, *_):
        if self._clock_event is not None:
            self._clock_event.cancel()
            self._clock_event = None

        if self._minute_event is not None:
            self._minute_event.cancel()
            self._minute_event = None

    def update_current_time(self, _dt):
        now = datetime.now()
        self.now_label.text = (
            "当前时间："
            + now.strftime("%Y-%m-%d %H:%M:%S")
        )

    def refresh_current(self, *_args, force=False):
        now = datetime.now()
        minute_key = now.strftime("%Y%m%d%H%M")

        if not force and minute_key == self._last_minute_key:
            return

        self._last_minute_key = minute_key

        # 没有位置时，不将北京或其他默认坐标冒充为用户位置。
        if self.current_longitude is None:
            self.birth_label.text = (
                "排盘时间：" + now.strftime("%Y-%m-%d %H:%M")
            )
            self.solar_label.text = (
                "真太阳时：请先设置有效位置"
            )
            return

        longitude = float(self.current_longitude)

        # 每次启动一个新的排盘任务，旧任务完成后不能覆盖新结果。
        self._chart_request_id += 1
        request_id = self._chart_request_id

        self.birth_label.text = (
            "排盘时间：" + now.strftime("%Y-%m-%d %H:%M")
        )
        self.solar_label.text = "真太阳时：正在计算……"

        def work():
            try:
                chart = build_chart(now, longitude, "男")
                pillars = get_pillars(chart)
                birth = chart.birth.strftime("%Y-%m-%d %H:%M")
                solar = chart.true_solar.strftime("%Y-%m-%d %H:%M")
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
        self, request_id, pillars, birth, solar, error
    ):
        # 忽略旧任务的结果，防止慢任务覆盖最新时间。
        if request_id != self._chart_request_id:
            return

        if error:
            self.solar_label.text = f"排盘计算失败：{error}"
            return

        if not pillars:
            return

        gan_colors = [RED, BROWN, GREEN, ORANGE]
        zhi_colors = [RED, BROWN, BLUE, ORANGE]

        for index, (_, pillar) in enumerate(pillars):
            gan_label, zhi_label = self.pillar_cells[index]
            ganzhi = str(pillar.ganzhi)

            gan_label.text = ganzhi[0] if len(ganzhi) > 0 else ""
            zhi_label.text = ganzhi[1] if len(ganzhi) > 1 else ""

            gan_label.color = gan_colors[index]
            zhi_label.color = zhi_colors[index]

        self.birth_label.text = f"排盘时间：{birth}"
        self.solar_label.text = f"真太阳时：{solar}"

    # --------------------------------------------------------
    # 已保存时间局
    # --------------------------------------------------------

    def load_saved_charts(self):
        if not os.path.isfile(self.store_path):
            return {}

        try:
            with open(
                self.store_path, "r", encoding="utf-8"
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
            temp_path, "w", encoding="utf-8"
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

        if not self.saved_charts:
            self.list_layout.add_widget(
                make_label(
                    "还没有保存的时间局",
                    font_size=dp(13),
                    color=MUTED,
                    halign="center",
                    height=dp(48),
                )
            )
            return

        for key, item in reversed(list(self.saved_charts.items())):
            name = item.get("name", "未命名时间局")
            time_text = item.get("time", "")

            card = Card(
                orientation="horizontal",
                padding=[dp(10), dp(6), dp(8), dp(6)],
                spacing=dp(8),
                size_hint_y=None,
                height=dp(68),
                card_color=CARD,
            )

            info = BoxLayout(
                orientation="vertical",
                spacing=dp(1),
            )
            info.add_widget(
                make_label(
                    name,
                    font_size=dp(15),
                    bold=True,
                    color=GREEN,
                    height=dp(28),
                )
            )
            info.add_widget(
                make_label(
                    time_text,
                    font_size=dp(12),
                    color=MUTED,
                    height=dp(23),
                )
            )
            card.add_widget(info)

            open_button = make_button(
                "查看 ›",
                size_hint=(None, None),
                size=(dp(76), dp(40)),
                font_size=dp(12),
            )
            open_button.bind(
                on_release=lambda _btn, chart_key=key:
                self.open_detail(chart_key)
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

    def add_chart(self, name, time_text):
        key = datetime.now().strftime("%Y%m%d%H%M%S%f")

        item = {
            "name": name.strip() or "未命名时间局",
            "time": time_text.strip(),
            "longitude": self.current_longitude,
            "latitude": self.current_latitude,
            "location_name": self.location_name,
        }

        self.saved_charts[key] = item
        self.save_saved_charts()
        self.refresh_list()


# ============================================================
# 添加时间局
# ============================================================

class AddScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(
            orientation="vertical",
            padding=[dp(18), dp(12), dp(18), dp(12)],
            spacing=dp(10),
        )

        root.add_widget(
            make_button(
                "‹ 返回首页",
                background_color=(0.38, 0.40, 0.36, 1),
                on_release=self.go_back,
            )
        )

        root.add_widget(
            make_label(
                "添加时间局",
                font_size=dp(25),
                bold=True,
                color=GREEN,
                height=dp(48),
            )
        )

        form_card = Card(
            orientation="vertical",
            padding=dp(14),
            spacing=dp(7),
            size_hint_y=None,
            height=dp(230),
        )

        form_card.add_widget(
            make_label("名字", bold=True, color=GREEN)
        )
        self.name_input = make_input(
            hint_text="例如：我的命盘"
        )
        form_card.add_widget(self.name_input)

        form_card.add_widget(
            make_label("时间", bold=True, color=GREEN)
        )
        self.time_input = make_input(
            text=datetime.now().strftime("%Y-%m-%d %H:%M"),
            hint_text="YYYY-MM-DD HH:MM",
        )
        form_card.add_widget(self.time_input)

        form_card.add_widget(
            make_label(
                "格式示例：2026-10-17 13:30",
                font_size=dp(12),
                color=MUTED,
                height=dp(24),
            )
        )
        root.add_widget(form_card)

        self.message = make_label("", color=RED, height=dp(40))
        root.add_widget(self.message)

        root.add_widget(
            make_button(
                "保存时间局",
                height=dp(50),
                on_release=self.save_chart,
            )
        )

        root.add_widget(Widget())
        self.add_widget(root)

    def reset_form(self):
        self.name_input.text = ""
        self.time_input.text = datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        )
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
        home.add_chart(name, time_text)
        self.manager.current = "home"


# ============================================================
# 时间局详情
# ============================================================

class DetailScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(
            orientation="vertical",
            padding=[dp(14), dp(10), dp(14), dp(10)],
            spacing=dp(8),
        )

        root.add_widget(
            make_button(
                "‹ 返回列表",
                background_color=(0.38, 0.40, 0.36, 1),
                on_release=self.go_back,
            )
        )

        self.title_label = make_label(
            "时间局详情",
            font_size=dp(23),
            bold=True,
            color=GREEN,
            height=dp(44),
        )
        root.add_widget(self.title_label)

        self.time_label = make_label(
            "",
            font_size=dp(12),
            color=MUTED,
            height=dp(28),
        )
        root.add_widget(self.time_label)

        detail_card = Card(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(5),
        )

        self.detail_text = make_label(
            "",
            valign="top",
            font_size=dp(13),
            size_hint_y=None,
            height=dp(400),
        )

        detail_scroll = ScrollView(do_scroll_x=False)
        detail_scroll.add_widget(self.detail_text)
        detail_card.add_widget(detail_scroll)
        root.add_widget(detail_card)

        self.add_widget(root)

    def show_chart(self, key):
        home = self.manager.get_screen("home")
        item = home.saved_charts.get(key, {})

        name = item.get("name", "未命名时间局")
        time_text = item.get("time", "")

        longitude = item.get("longitude")
        if longitude is None:
            longitude = home.current_longitude

        self.title_label.text = name
        self.time_label.text = time_text
        self.detail_text.text = "正在计算排盘结果……"
        self.detail_text.height = dp(400)

        if longitude is None:
            self.detail_text.text = (
                "尚未设置有效位置。\n"
                "请返回首页，获取定位或手动设置城市/地址。"
            )
            return

        def work():
            try:
                birth_time = datetime.strptime(
                    time_text, "%Y-%m-%d %H:%M"
                )
                chart = build_chart(
                    birth_time, float(longitude), "男"
                )
                result = format_chart(chart, name)
            except Exception as exc:
                result = (
                    "排盘计算失败\n"
                    f"{type(exc).__name__}: {exc}"
                )

            Clock.schedule_once(
                lambda _dt: self.set_detail_text(result),
                0,
            )

        Thread(target=work, daemon=True).start()

    def set_detail_text(self, text):
        self.detail_text.text = text
        self.detail_text.texture_update()
        self.detail_text.height = max(
            dp(400),
            self.detail_text.texture_size[1] + dp(24),
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
        manager.add_widget(AddScreen(name="add"))
        manager.add_widget(DetailScreen(name="detail"))

        return manager
