from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.resources import resource_find
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen

from .paipan import build_chart


# ---------------------------------------------------------
# 中文字体
# ---------------------------------------------------------

FONT_PATH = resource_find("fonts/NotoSansSC-Regular.otf")


def font_args():
    if FONT_PATH:
        return {"font_name": FONT_PATH}
    return {}


# ---------------------------------------------------------
# 通用控件
# ---------------------------------------------------------

def make_label(text="", size=16, bold=False, **kwargs):
    options = font_args()

    label = Label(
        text=text,
        font_size=dp(size),
        bold=bold,
        color=(0.12, 0.12, 0.12, 1),
        **options,
        **kwargs
    )

    return label


def make_button(text, height=48):
    options = font_args()

    button = Button(
        text=text,
        font_size=dp(16),
        size_hint_y=None,
        height=dp(height),
        **options
    )

    return button


# ---------------------------------------------------------
# 排盘文字
# ---------------------------------------------------------

def chart_to_text(chart, title=None):
    ps = [
        chart.year,
        chart.month,
        chart.day,
        chart.hour,
    ]

    lines = []

    if title:
        lines.append(f"【{title}】")
    else:
        lines.append("【五行排盘】")

    lines += [
        f"出生：{chart.birth:%Y-%m-%d %H:%M}",
        f"经度：{chart.longitude:.4f}°",
        f"真太阳时：{chart.true_solar:%Y-%m-%d %H:%M}",
        "",
        f"年柱：{chart.year.ganzhi}  "
        f"十神：{chart.year.ten_god_gan}  "
        f"纳音：{chart.year.na_yin}",

        f"月柱：{chart.month.ganzhi}  "
        f"十神：{chart.month.ten_god_gan}  "
        f"纳音：{chart.month.na_yin}",

        f"日柱：{chart.day.ganzhi}  "
        f"日主：{chart.day.gan}  "
        f"纳音：{chart.day.na_yin}",

        f"时柱：{chart.hour.ganzhi}  "
        f"十神：{chart.hour.ten_god_gan}  "
        f"纳音：{chart.hour.na_yin}",

        "",
        "【藏干】",
    ]

    for p in ps:
        lines.append(
            f"{p.name} {p.ganzhi}："
            f"{'、'.join(p.hidden)}"
        )

    lines += [
        "",
        f"【胎元】{chart.fetal}",
        f"【命宫】{chart.life_palace}（辅助取象）",
        "",
        "【五行计数】",
        "、".join(
            f"{k}{v}"
            for k, v in chart.wuxing.items()
        ),
        "",
        "【大运】",
    ]

    for x in chart.dayun:
        lines.append(
            f"{x['序']}. {x['干支']} "
            f"约{x['起运岁']}岁起（{x['顺逆']}）"
        )

    if chart.warnings:
        lines += [
            "",
            "【复核提示】",
        ]

        for warning in chart.warnings:
            lines.append(f"• {warning}")

    lines += [
        "",
        "注：纳音、胎元、命宫及神煞属于辅助取象；"
        "本工具不以它们独立定富贵。",
        "",
        "本应用用于传统命理文化研究与娱乐参考，"
        "不构成人生决策依据。",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------
# 首页
# ---------------------------------------------------------

class HomeScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.store = JsonStore(
            App.get_running_app().user_data_dir + "/time_charts.json"
        )

        root = FloatLayout()

        # -------------------------
        # 顶部标题
        # -------------------------

        title = make_label(
            "现在的时间局",
            size=24,
            bold=True,
            size_hint=(1, None),
            height=dp(50),
            halign="center",
            valign="middle",
        )

        title.pos_hint = {
            "top": 1,
            "x": 0,
        }

        title.bind(
            size=lambda obj, value:
            setattr(obj, "text_size", value)
        )

        root.add_widget(title)

        # -------------------------
        # 当前时间局
        # -------------------------

        current_scroll = ScrollView(
            size_hint=(1, None),
            height=dp(260),
            pos_hint={
                "top": 0.88,
                "x": 0,
            },
        )

        self.current_output = make_label(
            "",
            size=14,
            halign="left",
            valign="top",
            size_hint_y=None,
            padding=(dp(8), dp(8)),
        )

        self.current_output.bind(
            texture_size=lambda obj, value:
            setattr(
                obj,
                "height",
                max(value[1] + dp(20), dp(200))
            )
        )

        self.current_output.bind(
            size=lambda obj, value:
            setattr(
                obj,
                "text_size",
                (value[0] - dp(16), None)
            )
        )

        current_scroll.add_widget(self.current_output)
        root.add_widget(current_scroll)

        # -------------------------
        # 分隔标题
        # -------------------------

        list_title = make_label(
            "我的时间局",
            size=19,
            bold=True,
            size_hint=(1, None),
            height=dp(42),
            halign="left",
            valign="middle",
        )

        list_title.pos_hint = {
            "top": 0.57,
            "x": 0,
        }

        list_title.bind(
            size=lambda obj, value:
            setattr(obj, "text_size", value)
        )

        root.add_widget(list_title)

        # -------------------------
        # 保存列表
        # -------------------------

        self.list_scroll = ScrollView(
            size_hint=(1, None),
            height=dp(250),
            pos_hint={
                "top": 0.51,
                "x": 0,
            },
        )

        self.list_box = GridLayout(
            cols=1,
            spacing=dp(8),
            padding=dp(4),
            size_hint_y=None,
        )

        self.list_box.bind(
            minimum_height=self.list_box.setter("height")
        )

        self.list_scroll.add_widget(self.list_box)
        root.add_widget(self.list_scroll)

        # -------------------------
        # 右下角 +
        # -------------------------

        add_button = make_button(
            "+",
            height=60,
        )

        add_button.font_size = dp(32)

        add_button.size_hint = (
            None,
            None,
        )

        add_button.size = (
            dp(60),
            dp(60),
        )

        add_button.pos_hint = {
            "right": 0.96,
            "y": 0.03,
        }

        add_button.bind(
            on_release=self.open_add
        )

        root.add_widget(add_button)

        self.add_widget(root)

        # 每分钟刷新一次“现在的时间局”
        Clock.schedule_once(
            self.refresh_current,
            0
        )

        Clock.schedule_interval(
            self.refresh_current,
            60
        )

    # -----------------------------------------------------
    # 当前时间局
    # -----------------------------------------------------

    def refresh_current(self, *_):

        now = datetime.now()

        try:
            chart = build_chart(
                now,
                -77.49,
                "男",
            )

            self.current_output.text = chart_to_text(
                chart,
                "现在的时间局",
            )

        except Exception as e:
            self.current_output.text = (
                "当前时间局生成失败：\n"
                + str(e)
            )

    # -----------------------------------------------------
    # 刷新保存列表
    # -----------------------------------------------------

    def on_pre_enter(self, *args):
        self.refresh_list()
        self.refresh_current()

    def refresh_list(self):

        self.list_box.clear_widgets()

        keys = list(self.store.keys())

        if not keys:
            empty = make_label(
                "暂无保存的时间局",
                size=15,
                color=(0.45, 0.45, 0.45, 1),
                size_hint_y=None,
                height=dp(50),
                halign="center",
                valign="middle",
            )

            empty.bind(
                size=lambda obj, value:
                setattr(obj, "text_size", value)
            )

            self.list_box.add_widget(empty)
            return

        # 最新保存的放前面
        keys.reverse()

        for key in keys:

            data = self.store.get(key)

            name = data.get(
                "name",
                "未命名时间局"
            )

            dt_text = data.get(
                "time",
                ""
            )

            button = make_button(
                f"{name}\n{dt_text}",
                height=62,
            )

            button.bind(
                on_release=lambda btn, k=key:
                self.open_detail(k)
            )

            self.list_box.add_widget(button)

    # -----------------------------------------------------
    # 新增
    # -----------------------------------------------------

    def open_add(self, *_):
        self.manager.current = "add"


    # -----------------------------------------------------
    # 查看详情
    # -----------------------------------------------------

    def open_detail(self, key):

        detail = self.manager.get_screen(
            "detail"
        )

        detail.show_chart(key)

        self.manager.current = "detail"


# ---------------------------------------------------------
# 添加时间局
# ---------------------------------------------------------

class AddScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(12),
        )

        # 顶部
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(50),
            spacing=dp(8),
        )

        back = make_button(
            "‹ 返回",
            height=46,
        )

        back.size_hint_x = None
        back.width = dp(90)

        back.bind(
            on_release=self.go_home
        )

        header.add_widget(back)

        title = make_label(
            "添加时间局",
            size=21,
            bold=True,
            halign="center",
            valign="middle",
        )

        title.bind(
            size=lambda obj, value:
            setattr(obj, "text_size", value)
        )

        header.add_widget(title)

        root.add_widget(header)

        # 表单
        form = GridLayout(
            cols=1,
            spacing=dp(8),
            size_hint_y=None,
        )

        form.bind(
            minimum_height=form.setter("height")
        )

        name_title = make_label(
            "名字",
            size=16,
            size_hint_y=None,
            height=dp(32),
            halign="left",
            valign="middle",
        )

        name_title.bind(
            size=lambda obj, value:
            setattr(obj, "text_size", value)
        )

        form.add_widget(name_title)

        self.name_input = TextInput(
            text="",
            hint_text="例如：我的命盘",
            multiline=False,
            size_hint_y=None,
            height=dp(48),
            **font_args()
        )

        form.add_widget(self.name_input)

        time_title = make_label(
            "时间",
            size=16,
            size_hint_y=None,
            height=dp(32),
            halign="left",
            valign="middle",
        )

        time_title.bind(
            size=lambda obj, value:
            setattr(obj, "text_size", value)
        )

        form.add_widget(time_title)

        self.time_input = TextInput(
            text=datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            ),
            hint_text="YYYY-MM-DD HH:MM",
            multiline=False,
            size_hint_y=None,
            height=dp(48),
            **font_args()
        )

        form.add_widget(self.time_input)

        tip = make_label(
            "时间格式：2026-10-05 12:30",
            size=13,
            color=(0.45, 0.45, 0.45, 1),
            size_hint_y=None,
            height=dp(32),
            halign="left",
            valign="middle",
        )

        tip.bind(
            size=lambda obj, value:
            setattr(obj, "text_size", value)
        )

        form.add_widget(tip)

        root.add_widget(form)

        # 错误提示
        self.error = make_label(
            "",
            size=14,
            color=(0.75, 0.15, 0.15, 1),
            size_hint_y=None,
            height=dp(60),
            halign="left",
            valign="top",
        )

        self.error.bind(
            size=lambda obj, value:
            setattr(obj, "text_size", value)
        )

        root.add_widget(self.error)

        # 保存
        save = make_button(
            "保存时间局",
            height=52,
        )

        save.bind(
            on_release=self.save_chart
        )

        root.add_widget(save)

        # 底部空白
        root.add_widget(
            WidgetSpacer()
        )

        self.add_widget(root)

    def go_home(self, *_):
        self.manager.current = "home"

    def save_chart(self, *_):

        name = self.name_input.text.strip()
        time_text = self.time_input.text.strip()

        if not name:
            self.error.text = "请输入时间局名字。"
            return

        try:
            dt = datetime.strptime(
                time_text,
                "%Y-%m-%d %H:%M"
            )
        except ValueError:
            self.error.text = (
                "时间格式不正确。\n"
                "请输入：YYYY-MM-DD HH:MM"
            )
            return

        try:
            # 先验证确实能够排盘
            build_chart(
                dt,
                -77.49,
                "男",
            )
        except Exception as e:
            self.error.text = (
                "这个时间无法生成排盘：\n"
                + str(e)
            )
            return

        app = App.get_running_app()

        store = JsonStore(
            app.user_data_dir
            + "/time_charts.json"
        )

        key = (
            datetime.now().strftime(
                "%Y%m%d%H%M%S%f"
            )
        )

        store.put(
            key,
            name=name,
            time=dt.strftime(
                "%Y-%m-%d %H:%M"
            ),
            longitude=-77.49,
            sex="男",
        )

        # 清空表单
        self.name_input.text = ""
        self.time_input.text = datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        )
        self.error.text = ""

        self.manager.current = "home"


# ---------------------------------------------------------
# 时间局详情
# ---------------------------------------------------------

class DetailScreen(Screen):

    current_key = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(8),
        )

        # 顶部
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(50),
            spacing=dp(8),
        )

        back = make_button(
            "‹ 返回",
            height=46,
        )

        back.size_hint_x = None
        back.width = dp(90)

        back.bind(
            on_release=self.go_home
        )

        header.add_widget(back)

        self.title = make_label(
            "时间局",
            size=21,
            bold=True,
            halign="center",
            valign="middle",
        )

        self.title.bind(
            size=lambda obj, value:
            setattr(obj, "text_size", value)
        )

        header.add_widget(self.title)

        root.add_widget(header)

        # 内容
        scroll = ScrollView()

        self.output = make_label(
            "",
            size=14,
            halign="left",
            valign="top",
            size_hint_y=None,
            padding=(dp(8), dp(8)),
        )

        self.output.bind(
            texture_size=lambda obj, value:
            setattr(
                obj,
                "height",
                value[1] + dp(30)
            )
        )

        self.output.bind(
            size=lambda obj, value:
            setattr(
                obj,
                "text_size",
                (value[0] - dp(16), None)
            )
        )

        scroll.add_widget(self.output)

        root.add_widget(scroll)

        self.add_widget(root)

    def go_home(self, *_):
        self.manager.current = "home"

    def show_chart(self, key):

        self.current_key = key

        app = App.get_running_app()

        store = JsonStore(
            app.user_data_dir
            + "/time_charts.json"
        )

        if not store.exists(key):
            self.title.text = "找不到时间局"
            self.output.text = "这个时间局已经不存在。"
            return

        data = store.get(key)

        name = data.get(
            "name",
            "未命名时间局"
        )

        time_text = data.get(
            "time",
            ""
        )

        longitude = float(
            data.get(
                "longitude",
                -77.49
            )
        )

        sex = data.get(
            "sex",
            "男"
        )

        try:
            dt = datetime.strptime(
                time_text,
                "%Y-%m-%d %H:%M"
            )

            chart = build_chart(
                dt,
                longitude,
                sex,
            )

            self.title.text = name

            self.output.text = chart_to_text(
                chart,
                name,
            )

        except Exception as e:
            self.title.text = name
            self.output.text = (
                "时间局生成失败：\n"
                + str(e)
            )


# ---------------------------------------------------------
# 空白占位
# ---------------------------------------------------------

class WidgetSpacer(BoxLayout):
    pass


# ---------------------------------------------------------
# App
# ---------------------------------------------------------

class WuxingApp(App):

    title = "五行排盘"

    def build(self):

        Window.softinput_mode = "below_target"

        manager = ScreenManager()

        manager.add_widget(
            HomeScreen(
                name="home"
            )
        )

        manager.add_widget(
            AddScreen(
                name="add"
            )
        )

        manager.add_widget(
            DetailScreen(
                name="detail"
            )
        )

        return manager

    def on_start(self):
        self.root.current = "home"