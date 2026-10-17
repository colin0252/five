
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

from .paipan import build_chart


# ============================================================
# 颜色与字体
# ============================================================

BG = (0.96, 0.95, 0.91, 1)
CARD = (1.00, 0.99, 0.96, 1)
GREEN = (0.15, 0.30, 0.24, 1)
GREEN_LIGHT = (0.88, 0.92, 0.86, 1)
GOLD = (0.72, 0.53, 0.25, 1)
TEXT = (0.16, 0.19, 0.16, 1)
MUTED = (0.48, 0.49, 0.44, 1)
RED = (0.70, 0.20, 0.16, 1)

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

FONT_PATH = os.path.join(
    PROJECT_ROOT, "fonts", "NotoSansSC-Regular.ttf"
)


def font_args():
    if os.path.isfile(FONT_PATH):
        return {"font_name": FONT_PATH}
    return {}


def make_label(text="", **kwargs):
    kwargs.setdefault("color", TEXT)
    kwargs.setdefault("font_size", dp(15))
    kwargs.setdefault("halign", "left")
    kwargs.setdefault("valign", "middle")
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", dp(34))
    kwargs.update(font_args())

    label = Label(text=str(text), **kwargs)
    label.bind(
        size=lambda obj, size: setattr(
            obj, "text_size", (size[0], None)
        )
    )
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
        "padding", [dp(12), dp(12), dp(12), dp(12)]
    )
    kwargs.update(font_args())
    return TextInput(**kwargs)


class Card(BoxLayout):
    """带圆角底色的卡片。"""

    def __init__(self, card_color=CARD, radius=16, **kwargs):
        super().__init__(**kwargs)
        self.card_color = card_color
        self.radius = dp(radius)

        with self.canvas.before:
            self.bg_color = Color(*self.card_color)
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
    """将 Chart 对象整理为中文文本，避免显示 Chart(...)。"""

    if isinstance(chart, str):
        return chart

    if isinstance(chart, dict):
        return json.dumps(
            chart, ensure_ascii=False, indent=2, default=str
        )

    try:
        pillars = [
            chart.year,
            chart.month,
            chart.day,
            chart.hour,
        ]

        lines = [
            title,
            "",
            f"出生时间：{chart.birth:%Y-%m-%d %H:%M}",
            f"真太阳时：{chart.true_solar:%Y-%m-%d %H:%M}",
            f"经度：{chart.longitude}",
            f"性别：{chart.sex}",
            "",
            "四柱",
            "----------------",
        ]

        for p in pillars:
            lines.append(f"{p.name}：{p.ganzhi}")
            lines.append(f"天干：{p.gan}")
            lines.append(f"地支：{p.zhi}")
            lines.append(f"天干十神：{p.ten_god_gan}")
            lines.append(f"纳音：{p.na_yin}")
            lines.append(f"藏干：{'、'.join(p.hidden)}")
            lines.append("")

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
                f"{item.get('干支', '')}　"
                f"{item.get('起运岁', '')}岁起运　"
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


def chart_pillars_text(chart):
    """生成首页四柱卡片的简要内容。"""
    try:
        return [
            ("年柱", chart.year.ganzhi),
            ("月柱", chart.month.ganzhi),
            ("日柱", chart.day.ganzhi),
            ("时柱", chart.hour.ganzhi),
        ]
    except Exception:
        return []


# ============================================================
# 首页
# ============================================================

class HomeScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        app = App.get_running_app()
        self.store_path = os.path.join(
            app.user_data_dir, "time_charts.json"
        )
        self.saved_charts = self.load_saved_charts()

        root = BoxLayout(
            orientation="vertical",
            padding=[dp(18), dp(12), dp(18), dp(12)],
            spacing=dp(12),
        )

        # 顶部标题
        header = BoxLayout(
            size_hint_y=None,
            height=dp(48),
            spacing=dp(8),
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

        # 当前时间局卡片
        # 左边竖排“即时局”，右边显示原有排盘内容
        current_card = Card(
            orientation="horizontal",
            padding=dp(12),
            spacing=dp(10),
            size_hint_y=None,
            height=dp(300),
        )

        current_side_title = make_label(
            "即\n时\n局",
            font_size=dp(19),
            bold=True,
            color=GOLD,
            halign="center",
            valign="middle",
            size_hint=(None, 1),
            width=dp(28),
        )
        current_card.add_widget(current_side_title)

        # 当前时间局右侧内容
        current_content = BoxLayout(
            orientation="vertical",
            spacing=dp(6),
        )

        current_content.add_widget(
            make_label(
                "现在的时间局",
                font_size=dp(20),
                bold=True,
                color=GREEN,
                height=dp(34),
            )
        )

        self.current_time_label = make_label(
            datetime.now().strftime("%Y年%m月%d日  %H:%M"),
            color=MUTED,
            font_size=dp(13),
            height=dp(26),
        )
        current_content.add_widget(self.current_time_label)

        self.pillars_grid = GridLayout(
            cols=4,
            spacing=dp(6),
            size_hint_y=None,
            height=dp(84),
        )
        current_content.add_widget(self.pillars_grid)

        self.current_result = make_label(
            "正在计算当前时间局……",
            font_size=dp(13),
            color=TEXT,
            valign="top",
            size_hint_y=None,
            height=dp(95),
        )

        current_scroll = ScrollView(
            do_scroll_x=False,
            size_hint=(1, 1),
        )
        current_scroll.add_widget(self.current_result)
        current_content.add_widget(current_scroll)

        current_card.add_widget(current_content)
        root.add_widget(current_card)

        # 功能预留区：只显示名称，不实现功能
        feature_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(76),
            spacing=dp(10),
        )

        qimen_card = Card(
            orientation="vertical",
            padding=dp(10),
            card_color=GREEN_LIGHT,
        )
        qimen_card.add_widget(
            make_label(
                "奇门遁甲",
                font_size=dp(17),
                bold=True,
                color=GREEN,
                halign="center",
            )
        )

        compass_card = Card(
            orientation="vertical",
            padding=dp(10),
            card_color=CARD,
        )
        compass_card.add_widget(
            make_label(
                "罗盘",
                font_size=dp(17),
                bold=True,
                color=GREEN,
                halign="center",
            )
        )

        feature_row.add_widget(qimen_card)
        feature_row.add_widget(compass_card)
        root.add_widget(feature_row)

        # 我的时间局
        root.add_widget(
            make_label(
                "我的时间局",
                font_size=dp(20),
                bold=True,
                color=GREEN,
                height=dp(36),
            )
        )

        self.list_layout = GridLayout(
            cols=1,
            spacing=dp(10),
            size_hint_y=None,
        )
        self.list_layout.bind(
            minimum_height=self.list_layout.setter("height")
        )

        list_scroll = ScrollView(do_scroll_x=False)
        list_scroll.add_widget(self.list_layout)
        root.add_widget(list_scroll)

        # 右下角添加按钮
        bottom = BoxLayout(
            size_hint_y=None,
            height=dp(64),
        )
        bottom.add_widget(Widget())

        add_button = make_button(
            "+",
            size_hint=(None, None),
            size=(dp(58), dp(58)),
            font_size=dp(34),
            background_color=GREEN,
        )
        add_button.bind(on_release=self.open_add)
        bottom.add_widget(add_button)

        root.add_widget(bottom)
        self.add_widget(root)

        self.refresh_list()
        Clock.schedule_once(self.refresh_current, 0)
        Clock.schedule_interval(self.refresh_current, 60)

    def load_saved_charts(self):
        if not os.path.isfile(self.store_path):
            return {}

        try:
            with open(self.store_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_saved_charts(self):
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        temp_path = self.store_path + ".tmp"

        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(
                self.saved_charts,
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(temp_path, self.store_path)

    def refresh_current(self, *_):
        now = datetime.now()
        self.current_time_label.text = now.strftime(
            "%Y年%m月%d日  %H:%M"
        )

        def work():
            try:
                chart = build_chart(now, -77.49, "男")
                result = format_chart(chart, "现在的时间局")
                pillars = chart_pillars_text(chart)
                error = None
            except Exception as exc:
                result = ""
                pillars = []
                error = f"{type(exc).__name__}: {exc}"

            Clock.schedule_once(
                lambda dt: self.set_current_result(
                    result, pillars, error
                ),
                0,
            )

        Thread(target=work, daemon=True).start()

    def set_current_result(self, result, pillars, error):
        self.pillars_grid.clear_widgets()

        if error:
            self.current_result.text = (
                f"当前时间局计算失败：{error}"
            )
            return

        for label_text, gz in pillars:
            cell = BoxLayout(
                orientation="vertical",
                padding=dp(4),
                spacing=dp(2),
            )

            with cell.canvas.before:
                cell.bg_color = Color(*GREEN_LIGHT)
                cell.bg_rect = RoundedRectangle(
                    pos=cell.pos,
                    size=cell.size,
                    radius=[dp(10)],
                )

            def update_cell_bg(instance, *_):
                instance.bg_rect.pos = instance.pos
                instance.bg_rect.size = instance.size

            cell.bind(pos=update_cell_bg, size=update_cell_bg)

            cell.add_widget(
                make_label(
                    label_text,
                    font_size=dp(12),
                    color=MUTED,
                    halign="center",
                    height=dp(24),
                )
            )

            cell.add_widget(
                make_label(
                    gz,
                    font_size=dp(23),
                    bold=True,
                    color=GREEN,
                    halign="center",
                    height=dp(42),
                )
            )

            self.pillars_grid.add_widget(cell)

        if "五行统计" in result:
            self.current_result.text = result.split("五行统计")[0]
        else:
            self.current_result.text = result

        self.current_result.texture_update()
        self.current_result.height = max(
            dp(95),
            self.current_result.texture_size[1] + dp(12),
        )

    def refresh_list(self):
        self.list_layout.clear_widgets()

        # 没有保存项目时，列表区域保持空白
        for key, item in reversed(list(self.saved_charts.items())):
            name = item.get("name", "未命名时间局")
            time_text = item.get("time", "")

            card = Card(
                orientation="horizontal",
                padding=[dp(12), dp(8), dp(12), dp(8)],
                spacing=dp(8),
                size_hint_y=None,
                height=dp(72),
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
                    height=dp(30),
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
                "格式示例：2026-10-05 12:30",
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

        self.title_label.text = name
        self.time_label.text = time_text
        self.detail_text.text = "正在计算排盘结果……"
        self.detail_text.height = dp(400)

        def work():
            try:
                birth_time = datetime.strptime(
                    time_text, "%Y-%m-%d %H:%M"
                )
                chart = build_chart(
                    birth_time,
                    -77.49,
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
