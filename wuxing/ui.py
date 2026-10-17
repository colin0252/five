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
from .location import (
    get_location,
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
)


# ============================================================
# 颜色
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

_FONT_ARGS = (
    {"font_name": FONT_PATH}
    if os.path.isfile(FONT_PATH)
    else {}
)


def font_args():
    return _FONT_ARGS.copy()


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
    kwargs.setdefault("height", dp(46))
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
        "padding",
        [dp(12), dp(12), dp(12), dp(12)],
    )
    kwargs.update(font_args())

    return TextInput(**kwargs)


class Card(BoxLayout):
    def __init__(self, card_color=CARD, radius=15, **kwargs):
        super().__init__(**kwargs)

        self.card_color = card_color
        self.radius = dp(radius)

        with self.canvas.before:
            self.bg_color_instruction = Color(*self.card_color)
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
            f"经度：{chart.longitude}",
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
            f"错误类型：{type(exc).__name__}\n"
            f"错误详情：{exc}"
        )


def get_pillars(chart):
    return [
        ("年", chart.year),
        ("月", chart.month),
        ("日", chart.day),
        ("时", chart.hour),
    ]


# ============================================================
# 首页
# ============================================================

class HomeScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        app = App.get_running_app()
        self.store_path = os.path.join(
            app.user_data_dir,
            "time_charts.json",
        )
        self.saved_charts = self.load_saved_charts()

        # 定位状态
        self.current_latitude = DEFAULT_LATITUDE
        self.current_longitude = DEFAULT_LONGITUDE
        self.location_source = "default"
        self.location_error = None
        self._location_requesting = False
        self._refresh_event = None

        root = BoxLayout(
            orientation="vertical",
            padding=[dp(14), dp(8), dp(14), dp(8)],
            spacing=dp(9),
        )

        # 顶部标题
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(46),
            spacing=dp(6),
        )

        header.add_widget(
            make_label(
                "五行排盘",
                font_size=dp(25),
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
            padding=dp(9),
            spacing=dp(9),
            size_hint_y=None,
            height=dp(310),
            card_color=CARD,
        )

        # 左侧竖排“即时局”
        side_card = Card(
            orientation="vertical",
            size_hint=(None, 1),
            width=dp(48),
            padding=[dp(3), dp(12), dp(3), dp(12)],
            spacing=dp(8),
            card_color=(0.93, 0.91, 0.84, 1),
        )

        for char in ("即", "时", "局"):
            side_card.add_widget(
                make_label(
                    char,
                    font_size=dp(25),
                    bold=True,
                    color=GOLD,
                    halign="center",
                    height=dp(43),
                )
            )

        side_card.add_widget(Widget())
        main_card.add_widget(side_card)

        # 右侧主内容
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
        )

        # 四柱表格
        self.pillars_grid = GridLayout(
            cols=4,
            spacing=dp(5),
            size_hint_y=None,
            height=dp(158),
        )
        content.add_widget(self.pillars_grid)

        self.pillar_cells = []

        for name in ("年", "月", "日", "时"):
            cell = Card(
                orientation="vertical",
                padding=[dp(2), dp(4), dp(2), dp(4)],
                spacing=dp(1),
                card_color=GREEN_LIGHT,
                radius=10,
            )

            cell.add_widget(
                make_label(
                    name,
                    font_size=dp(14),
                    bold=True,
                    color=TEXT,
                    halign="center",
                    height=dp(30),
                )
            )

            gan_label = make_label(
                "",
                font_size=dp(26),
                bold=True,
                color=TEXT,
                halign="center",
                height=dp(48),
            )

            zhi_label = make_label(
                "",
                font_size=dp(26),
                bold=True,
                color=TEXT,
                halign="center",
                height=dp(48),
            )

            cell.add_widget(gan_label)
            cell.add_widget(zhi_label)

            self.pillars_grid.add_widget(cell)
            self.pillar_cells.append((gan_label, zhi_label))

        # 出生时间信息卡片
        self.birth_info = Card(
            orientation="vertical",
            padding=[dp(8), dp(5), dp(5), dp(5)],
            spacing=dp(1),
            size_hint_y=None,
            height=dp(145),
            card_color=GREEN_LIGHT,
        )

        self.birth_label = make_label(
            "出生时间：计算中……",
            font_size=dp(12),
            color=GREEN,
            height=dp(27),
        )

        self.solar_label = make_label(
            "真太阳时：计算中……",
            font_size=dp(12),
            color=GREEN,
            height=dp(27),
        )

        self.longitude_label = make_label(
            "经度：正在获取位置……",
            font_size=dp(12),
            color=GREEN,
            height=dp(27),
        )

        self.longitude_label.bind(
            on_touch_down=self._on_longitude_click
        )

        self.birth_info.add_widget(self.birth_label)
        self.birth_info.add_widget(self.solar_label)
        self.birth_info.add_widget(self.longitude_label)

        # 手动刷新定位按钮
        self.location_button = make_button(
            "刷新定位",
            height=dp(36),
            font_size=dp(13),
        )
        self.location_button.bind(
            on_release=self._request_location
        )
        self.birth_info.add_widget(self.location_button)

        content.add_widget(self.birth_info)
        main_card.add_widget(content)
        root.add_widget(main_card)

        # 奇门遁甲、罗盘：仅预留入口
        feature_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(76),
            spacing=dp(10),
        )

        qimen_card = Card(
            orientation="vertical",
            padding=dp(6),
            spacing=dp(1),
            card_color=GREEN_LIGHT,
        )

        qimen_card.add_widget(
            make_label(
                "☯",
                font_size=dp(25),
                color=GREEN,
                halign="center",
                height=dp(32),
            )
        )

        qimen_card.add_widget(
            make_label(
                "奇门遁甲",
                font_size=dp(16),
                bold=True,
                color=GREEN,
                halign="center",
                height=dp(28),
            )
        )

        compass_card = Card(
            orientation="vertical",
            padding=dp(6),
            spacing=dp(1),
            card_color=CARD,
        )

        compass_card.add_widget(
            make_label(
                "◷",
                font_size=dp(25),
                color=RED,
                halign="center",
                height=dp(32),
            )
        )

        compass_card.add_widget(
            make_label(
                "罗盘",
                font_size=dp(16),
                bold=True,
                color=GREEN,
                halign="center",
                height=dp(28),
            )
        )

        feature_row.add_widget(qimen_card)
        feature_row.add_widget(compass_card)
        root.add_widget(feature_row)

        # 我的时间局标题
        root.add_widget(
            make_label(
                "我的时间局",
                font_size=dp(21),
                bold=True,
                color=GREEN,
                height=dp(38),
            )
        )

        # 已保存时间局列表
        self.list_layout = GridLayout(
            cols=1,
            spacing=dp(9),
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

        # 右下角加号按钮
        bottom = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(58),
        )
        bottom.add_widget(Widget())

        add_button = make_button(
            "+",
            size_hint=(None, None),
            size=(dp(56), dp(56)),
            font_size=dp(34),
        )
        add_button.bind(on_release=self.open_add)
        bottom.add_widget(add_button)

        root.add_widget(bottom)
        self.add_widget(root)

        self.refresh_list()

        # 启动后请求定位
        Clock.schedule_once(
            lambda dt: self._request_location(),
            0.5,
        )

    # ========================================================
    # 定位
    # ========================================================

    def _request_location(self, *_):
        """点击按钮或启动首页时请求设备定位。"""

        if self._location_requesting:
            return

        self._location_requesting = True
        self.location_button.disabled = True
        self.location_button.text = "正在获取位置……"
        self.longitude_label.text = "经度：正在定位……"

        def callback(lat, lon, source, error):
            Clock.schedule_once(
                lambda dt: self._on_location(
                    lat,
                    lon,
                    source,
                    error,
                ),
                0,
            )

        try:
            get_location(callback, timeout=20)
        except Exception as exc:
            Clock.schedule_once(
                lambda dt: self._on_location(
                    DEFAULT_LATITUDE,
                    DEFAULT_LONGITUDE,
                    "default",
                    f"定位异常：{type(exc).__name__}: {exc}",
                ),
                0,
            )

    def _on_location(self, lat, lon, source, error):
        """接收定位结果并刷新即时局。"""

        self._location_requesting = False
        self.location_button.disabled = False
        self.location_button.text = "刷新定位"

        try:
            lat = float(lat)
            lon = float(lon)

            if not -90 <= lat <= 90:
                raise ValueError("纬度超出范围")

            if not -180 <= lon <= 180:
                raise ValueError("经度超出范围")

        except (TypeError, ValueError):
            lat = DEFAULT_LATITUDE
            lon = DEFAULT_LONGITUDE
            source = "default"
            error = "定位坐标无效，已使用北京默认位置。"

        self.current_latitude = lat
        self.current_longitude = lon
        self.location_source = source
        self.location_error = error

        if source == "gps":
            self.longitude_label.text = (
                f"经度：{lon:.4f}°（设备定位）"
            )
        elif source == "manual":
            self.longitude_label.text = (
                f"经度：{lon:.4f}°（手动设置）"
            )
        else:
            self.longitude_label.text = (
                f"经度：{lon:.2f}°（北京默认，点击可改）"
            )

        if error:
            print(f"[Location] {error}")

        # 定位完成后重新计算即时局
        self.refresh_current()

    def _on_longitude_click(self, instance, touch):
        if not instance.collide_point(*touch.pos):
            return False

        self._show_longitude_input()
        return True

    def _show_longitude_input(self):
        content = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(8),
        )

        content.add_widget(
            make_label(
                "手动输入经度（东经为正，西经为负）",
                font_size=dp(13),
                color=MUTED,
                height=dp(28),
            )
        )

        inp = make_input(
            text=f"{self.current_longitude:.4f}",
            hint_text="例如：116.40",
        )
        content.add_widget(inp)

        popup = Popup(
            title="经度",
            content=content,
            size_hint=(0.85, 0.35),
        )

        def do_save(*_):
            try:
                value = float(inp.text.strip())
                if not -180 <= value <= 180:
                    raise ValueError("经度范围为 -180 至 180")
            except ValueError:
                self.longitude_label.text = (
                    "经度格式不正确，请重新输入"
                )
                return

            self.current_longitude = value
            self.location_source = "manual"
            self.location_error = None

            self.longitude_label.text = (
                f"经度：{value:.4f}°（手动设置）"
            )

            self.refresh_current()
            popup.dismiss()

        content.add_widget(
            make_button("保存", on_release=do_save)
        )

        popup.open()

    # ========================================================
    # 定时刷新
    # ========================================================

    def on_pre_enter(self, *_):
        self.refresh_current()

        if self._refresh_event is None:
            self._refresh_event = Clock.schedule_interval(
                self.refresh_current,
                60,
            )

    def on_leave(self, *_):
        if self._refresh_event is not None:
            self._refresh_event.cancel()
            self._refresh_event = None

    # ========================================================
    # 本地存储
    # ========================================================

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
            print(f"[Storage] 读取保存数据失败：{exc}")
            return {}

    def save_saved_charts(self):
        os.makedirs(
            os.path.dirname(self.store_path),
            exist_ok=True,
        )

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

    # ========================================================
    # 即时局计算
    # ========================================================

    def refresh_current(self, *_):
        now = datetime.now()
        longitude = self.current_longitude

        def work():
            try:
                chart = build_chart(
                    now,
                    longitude,
                    "男",
                )

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
                lambda dt: self.set_current_result(
                    pillars,
                    birth,
                    solar,
                    error,
                ),
                0,
            )

        Thread(target=work, daemon=True).start()

    def set_current_result(self, pillars, birth, solar, error):
        if error:
            self.birth_label.text = "出生时间：计算失败"
            self.solar_label.text = f"计算错误：{error}"
            return

        if not pillars:
            return

        gan_colors = [RED, BROWN, GREEN, ORANGE]
        zhi_colors = [RED, BROWN, BLUE, ORANGE]

        for index, (_, pillar) in enumerate(pillars):
            gan_label, zhi_label = self.pillar_cells[index]

            ganzhi = str(pillar.ganzhi)

            gan_label.text = (
                ganzhi[0] if len(ganzhi) > 0 else ""
            )
            zhi_label.text = (
                ganzhi[1] if len(ganzhi) > 1 else ""
            )

            gan_label.color = gan_colors[index]
            zhi_label.color = zhi_colors[index]

        self.birth_label.text = f"出生时间：{birth}"
        self.solar_label.text = f"真太阳时：{solar}"

    # ========================================================
    # 我的时间局列表
    # ========================================================

    def refresh_list(self):
        self.list_layout.clear_widgets()

        for key, item in reversed(
            list(self.saved_charts.items())
        ):
            name = item.get("name", "未命名时间局")
            time_text = item.get("time", "")

            card = Card(
                orientation="horizontal",
                padding=[dp(12), dp(8), dp(10), dp(8)],
                spacing=dp(8),
                size_hint_y=None,
                height=dp(72),
                card_color=CARD,
            )

            info = BoxLayout(
                orientation="vertical",
                spacing=dp(2),
            )

            info.add_widget(
                make_label(
                    name,
                    font_size=dp(16),
                    bold=True,
                    color=GREEN,
                    height=dp(29),
                )
            )

            info.add_widget(
                make_label(
                    time_text,
                    font_size=dp(12),
                    color=MUTED,
                    height=dp(24),
                )
            )

            card.add_widget(info)

            open_button = make_button(
                "查看  ›",
                size_hint=(None, None),
                size=(dp(88), dp(42)),
                font_size=dp(13),
            )

            open_button.bind(
                on_release=lambda instance, chart_key=key:
                self.open_detail(chart_key)
            )

            card.add_widget(open_button)
            self.list_layout.add_widget(card)

    def open_add(self, *_):
        add_screen = self.manager.get_screen("add")
        add_screen.reset_form()
        self.manager.current = "add"

    def open_detail(self, key):
        detail = self.manager.get_screen("detail")
        detail.show_chart(key)
        self.manager.current = "detail"

    def add_chart(self, name, time_text):
        key = datetime.now().strftime("%Y%m%d%H%M%S%f")

        self.saved_charts[key] = {
            "name": name.strip() or "未命名时间局",
            "time": time_text.strip(),
            "longitude": self.current_longitude,
        }

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
            padding=[dp(20), dp(16), dp(20), dp(16)],
            spacing=dp(12),
        )

        root.add_widget(
            make_button(
                "‹  返回首页",
                background_color=(0.38, 0.40, 0.36, 1),
                on_release=self.go_back,
            )
        )

        root.add_widget(
            make_label(
                "添加时间局",
                font_size=dp(26),
                bold=True,
                color=GREEN,
                height=dp(52),
            )
        )

        root.add_widget(
            make_label(
                "为这份时间局取一个名字",
                font_size=dp(14),
                color=MUTED,
                height=dp(30),
            )
        )

        form_card = Card(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(8),
            size_hint_y=None,
            height=dp(250),
        )

        form_card.add_widget(
            make_label("名字", bold=True, color=GREEN)
        )

        self.name_input = make_input(
            hint_text="例如：我的命盘",
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
                height=dp(26),
            )
        )

        root.add_widget(form_card)

        self.message = make_label(
            "",
            color=RED,
            height=dp(38),
        )
        root.add_widget(self.message)

        root.add_widget(
            make_button(
                "保存时间局",
                height=dp(52),
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

        if not time_text:
            self.message.text = "请填写时间。"
            return

        try:
            datetime.strptime(
                time_text,
                "%Y-%m-%d %H:%M",
            )
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
            padding=[dp(16), dp(12), dp(16), dp(12)],
            spacing=dp(10),
        )

        root.add_widget(
            make_button(
                "‹  返回列表",
                background_color=(0.38, 0.40, 0.36, 1),
                on_release=self.go_back,
            )
        )

        self.title_label = make_label(
            "时间局详情",
            font_size=dp(24),
            bold=True,
            color=GREEN,
            height=dp(48),
        )
        root.add_widget(self.title_label)

        self.time_label = make_label(
            "",
            font_size=dp(13),
            color=MUTED,
            height=dp(30),
        )
        root.add_widget(self.time_label)

        detail_card = Card(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(6),
        )

        self.detail_text = make_label(
            "",
            valign="top",
            font_size=dp(14),
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

        # 使用保存时的经度；旧数据使用当前经度
        longitude = item.get(
            "longitude",
            home.current_longitude,
        )

        self.title_label.text = name
        self.time_label.text = time_text
        self.detail_text.text = "正在计算排盘结果……"
        self.detail_text.height = dp(400)

        def work():
            try:
                birth_time = datetime.strptime(
                    time_text,
                    "%Y-%m-%d %H:%M",
                )

                chart = build_chart(
                    birth_time,
                    longitude,
                    "男",
                )

                result = format_chart(chart, name)

            except Exception as exc:
                result = (
                    "排盘计算失败\n"
                    f"错误类型：{type(exc).__name__}\n"
                    f"错误详情：{exc}"
                )

            Clock.schedule_once(
                lambda dt: self.set_detail_text(result),
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