import os
import json
from datetime import datetime
from threading import Thread
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from .paipan import build_chart
# ============================================================
# 中文字体
# 字体文件必须放在仓库的 fonts/NotoSansSC-Regular.ttf
# ============================================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_PATH = os.path.join(
    PROJECT_ROOT,
    "fonts",
    "NotoSansSC-Regular.ttf",
)
def font_args():
    """字体文件存在时使用中文字体，否则使用 Kivy 默认字体。"""
    if os.path.isfile(FONT_PATH):
        return {"font_name": FONT_PATH}
    return {}
def make_label(text="", **kwargs):
    kwargs.setdefault("color", (0.12, 0.12, 0.12, 1))
    kwargs.setdefault("font_size", dp(16))
    kwargs.setdefault("halign", "left")
    kwargs.setdefault("valign", "middle")
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", dp(36))
    kwargs.update(font_args())
    label = Label(text=str(text), **kwargs)
    label.bind(
        size=lambda instance, size: setattr(
            instance, "text_size", (size[0], None)
        )
    )
    return label
def make_button(text, **kwargs):
    kwargs.setdefault("font_size", dp(16))
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", dp(46))
    kwargs.setdefault("background_normal", "")
    kwargs.setdefault("background_color", (0.20, 0.43, 0.34, 1))
    kwargs.setdefault("color", (1, 1, 1, 1))
    kwargs.update(font_args())
    return Button(text=text, **kwargs)
def make_input(**kwargs):
    kwargs.setdefault("font_size", dp(16))
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", dp(46))
    kwargs.setdefault("multiline", False)
    kwargs.setdefault("padding", [dp(10), dp(10), dp(10), dp(10)])
    kwargs.update(font_args())
    return TextInput(**kwargs)
def format_chart(chart, title):
    """将排盘结果转成可显示文本。"""
    if isinstance(chart, str):
        return chart
    if isinstance(chart, dict):
        try:
            return json.dumps(
                chart,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        except Exception:
            return str(chart)
    return str(chart)
# ============================================================
# 首页
# ============================================================
class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store_path = os.path.join(
            App.get_running_app().user_data_dir,
            "time_charts.json",
        )
        self.saved_charts = self.load_saved_charts()
        root = BoxLayout(
            orientation="vertical",
            padding=dp(14),
            spacing=dp(8),
        )
        root.add_widget(
            make_label(
                "五行排盘",
                font_size=dp(24),
                bold=True,
                height=dp(48),
                halign="center",
            )
        )
        root.add_widget(
            make_label(
                "现在的时间局",
                font_size=dp(19),
                bold=True,
                height=dp(40),
            )
        )
        self.current_result = make_label(
            "正在计算当前时间局……",
            size_hint_y=None,
            height=dp(180),
            valign="top",
        )
        current_scroll = ScrollView(
            size_hint=(1, None),
            height=dp(200),
            do_scroll_x=False,
        )
        current_scroll.add_widget(self.current_result)
        root.add_widget(current_scroll)
        root.add_widget(
            make_label(
                "我的时间局",
                font_size=dp(19),
                bold=True,
                height=dp(40),
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
        list_scroll = ScrollView(do_scroll_x=False)
        list_scroll.add_widget(self.list_layout)
        root.add_widget(list_scroll)
        bottom = BoxLayout(
            size_hint_y=None,
            height=dp(62),
            spacing=dp(8),
        )
        bottom.add_widget(Label())
        add_button = make_button(
            "+",
            size_hint=(None, None),
            size=(dp(58), dp(58)),
            font_size=dp(34),
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
        def work():
            try:
                # 沿用项目原本的排盘函数调用方式。
                chart = build_chart(now, -77.49, "男")
                text = format_chart(chart, "现在的时间局")
            except Exception as exc:
                text = f"当前时间局计算失败：{exc}"
            Clock.schedule_once(
                lambda dt: self.set_current_text(text),
                0,
            )
        Thread(target=work, daemon=True).start()
    def set_current_text(self, text):
        self.current_result.text = text
        self.current_result.texture_update()
        self.current_result.height = max(
            dp(180),
            self.current_result.texture_size[1] + dp(20),
        )
    def refresh_list(self):
        self.list_layout.clear_widgets()
        # 没有保存项目时保持空白，不额外显示提示文字。
        for key, item in reversed(list(self.saved_charts.items())):
            name = item.get("name", "未命名时间局")
            time_text = item.get("time", "")
            button = make_button(
                f"{name}\n{time_text}",
                height=dp(64),
                halign="left",
            )
            button.bind(
                on_release=lambda instance, chart_key=key:
                self.open_detail(chart_key)
            )
            self.list_layout.add_widget(button)
    def open_add(self, *_):
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
# 添加时间局页面
# ============================================================
class AddScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(
            orientation="vertical",
            padding=dp(18),
            spacing=dp(12),
        )
        root.add_widget(
            make_button(
                "‹ 返回",
                height=dp(42),
                background_color=(0.35, 0.35, 0.35, 1),
                on_release=self.go_back,
            )
        )
        root.add_widget(
            make_label(
                "添加时间局",
                font_size=dp(23),
                bold=True,
                height=dp(50),
            )
        )
        root.add_widget(make_label("名字", height=dp(32)))
        self.name_input = make_input(
            hint_text="例如：我的命盘",
        )
        root.add_widget(self.name_input)
        root.add_widget(make_label("时间", height=dp(32)))
        self.time_input = make_input(
            text=datetime.now().strftime("%Y-%m-%d %H:%M"),
            hint_text="YYYY-MM-DD HH:MM",
        )
        root.add_widget(self.time_input)
        root.add_widget(
            make_label(
                "时间格式：2026-10-05 12:30",
                color=(0.4, 0.4, 0.4, 1),
                height=dp(30),
            )
        )
        self.message = make_label(
            "",
            color=(0.75, 0.12, 0.12, 1),
            height=dp(42),
        )
        root.add_widget(self.message)
        root.add_widget(
            make_button(
                "保存时间局",
                height=dp(50),
                on_release=self.save_chart,
            )
        )
        root.add_widget(Label())
        self.add_widget(root)
    def go_back(self, *_):
        self.manager.current = "home"
    def save_chart(self, *_):
        name = self.name_input.text.strip()
        time_text = self.time_input.text.strip()
        try:
            datetime.strptime(time_text, "%Y-%m-%d %H:%M")
        except ValueError:
            self.message.text = "时间格式不正确，请使用 YYYY-MM-DD HH:MM"
            return
        home = self.manager.get_screen("home")
        home.add_chart(name, time_text)
        self.name_input.text = ""
        self.time_input.text = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.message.text = ""
        self.manager.current = "home"
# ============================================================
# 时间局详情页面
# ============================================================
class DetailScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_key = None
        root = BoxLayout(
            orientation="vertical",
            padding=dp(14),
            spacing=dp(8),
        )
        root.add_widget(
            make_button(
                "‹ 返回",
                height=dp(42),
                background_color=(0.35, 0.35, 0.35, 1),
                on_release=self.go_back,
            )
        )
        self.title_label = make_label(
            "时间局详情",
            font_size=dp(22),
            bold=True,
            height=dp(48),
        )
        root.add_widget(self.title_label)
        self.detail_text = make_label(
            "",
            valign="top",
            size_hint_y=None,
            height=dp(300),
        )
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.detail_text)
        root.add_widget(scroll)
        self.add_widget(root)
    def show_chart(self, key):
        self.current_key = key
        home = self.manager.get_screen("home")
        item = home.saved_charts.get(key, {})
        name = item.get("name", "未命名时间局")
        time_text = item.get("time", "")
        self.title_label.text = name
        self.detail_text.text = (
            f"名字：{name}\n"
            f"时间：{time_text}\n\n"
            "正在计算排盘结果……"
        )
        self.calculate_detail(name, time_text)
    def calculate_detail(self, name, time_text):
        def work():
            try:
                birth_time = datetime.strptime(
                    time_text,
                    "%Y-%m-%d %H:%M",
                )
                chart = build_chart(birth_time, -77.49, "男")
                result = format_chart(chart, name)
                text = (
                    f"名字：{name}\n"
                    f"时间：{time_text}\n\n"
                    f"{result}"
                )
            except Exception as exc:
                text = (
                    f"名字：{name}\n"
                    f"时间：{time_text}\n\n"
                    f"排盘计算失败：{exc}"
                )
            Clock.schedule_once(
                lambda dt: self.set_detail_text(text),
                0,
            )
        Thread(target=work, daemon=True).start()
    def set_detail_text(self, text):
        self.detail_text.text = text
        self.detail_text.texture_update()
        self.detail_text.height = max(
            dp(300),
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
        Window.clearcolor = (0.96, 0.95, 0.91, 1)
        manager = ScreenManager()
        manager.add_widget(HomeScreen(name="home"))
        manager.add_widget(AddScreen(name="add"))
        manager.add_widget(DetailScreen(name="detail"))
        return manager