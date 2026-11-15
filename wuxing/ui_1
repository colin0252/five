# wuxing/ui_1.py
"""增量补丁 1：给时间局加「删除」功能。

设计原则：不改 ui.py，只在这里扩展。
main.py 启动时 import 本模块并调用 install()，用 monkey patch 方式：

    1. HomeScreen.refresh_list  → 在原列表渲染完后，给每行加一个红色「删」按钮；
    2. DetailScreen.set_detail  → 在详情页底部加「删除此时间局」按钮。

以后新增补丁可以继续建 ui_2.py、ui_3.py，并在 main.py 的补丁列表里加名字。
"""

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup

from .ui import (
    CARD_SOFT,
    GREEN,
    MUTED,
    RED,
    TEXT,
    Card,
    make_button,
    make_label,
)


def install():
    """把删除功能挂到 HomeScreen / DetailScreen 上。只执行一次。"""
    from .ui import DetailScreen, HomeScreen

    if getattr(HomeScreen, "_delete_patched", False):
        return

    original_refresh = HomeScreen.refresh_list
    original_set_detail = DetailScreen.set_detail

    def refresh_list_with_delete(self):
        original_refresh(self)
        _add_row_delete_buttons(self)

    def set_detail_with_delete(self, request_id, chart, error):
        original_set_detail(self, request_id, chart, error)
        if error or chart is None:
            return
        _add_detail_delete_button(self)

    HomeScreen.refresh_list = refresh_list_with_delete
    DetailScreen.set_detail = set_detail_with_delete
    HomeScreen.delete_chart = delete_chart
    HomeScreen._delete_patched = True


# ------------------------------------------------------------
# 列表行：追加「删」按钮
# ------------------------------------------------------------
def _add_row_delete_buttons(home):
    try:
        items = home.filtered_items()
    except Exception:
        return
    try:
        children = list(reversed(home.list_layout.children))
    except Exception:
        return
    rows = [child for child in children if isinstance(child, Card)]
    # 条数对不上（空列表提示、或布局未就绪）就不加，避免删错行
    if len(rows) != len(items):
        return
    for row, (key, item) in zip(rows, items):
        if getattr(row, "_has_delete", False):
            continue
        button = make_button(
            "删",
            size_hint=(None, None),
            size=(dp(26), dp(30)),
            font_size=dp(11),
            background_color=(0, 0, 0, 0),
            color=RED,
        )
        button.bind(
            on_release=lambda _btn, chart_key=key: delete_chart(
                home, chart_key
            )
        )
        row.add_widget(button)
        row._has_delete = True


# ------------------------------------------------------------
# 详情页：底部加删除按钮
# ------------------------------------------------------------
def _add_detail_delete_button(detail):
    key = getattr(detail, "_current_key", None)
    if not key:
        return
    button = make_button(
        "删除此时间局",
        height=dp(44),
        font_size=dp(13),
        background_color=(0.90, 0.42, 0.38, 1),
        color=(1, 1, 1, 1),
    )
    button.bind(
        on_release=lambda _btn, chart_key=key: delete_chart(
            detail.manager.get_screen("home"),
            chart_key,
            on_done=lambda: setattr(detail.manager, "current", "home"),
        )
    )
    detail.body.add_widget(button)


# ------------------------------------------------------------
# 删除逻辑（带二次确认）
# ------------------------------------------------------------
def delete_chart(home, key, on_done=None):
    item = home.saved_charts.get(key, {}) or {}
    name = str(item.get("name", "未命名时间局"))

    content = BoxLayout(
        orientation="vertical",
        padding=dp(14),
        spacing=dp(8),
    )
    content.add_widget(
        make_label(
            "确定删除「" + name + "」？",
            font_size=dp(13),
            bold=True,
            color=TEXT,
            height=dp(30),
        )
    )
    content.add_widget(
        make_label(
            "删除后不可恢复。",
            font_size=dp(10.5),
            color=MUTED,
            height=dp(22),
        )
    )
    buttons = BoxLayout(
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
    confirm = make_button(
        "删除",
        height=dp(44),
        font_size=dp(13),
        background_color=RED,
    )
    buttons.add_widget(cancel)
    buttons.add_widget(confirm)
    content.add_widget(buttons)

    popup = Popup(
        title="删除时间局",
        content=content,
        size_hint=(0.86, 0.38),
        auto_dismiss=True,
    )
    cancel.bind(on_release=lambda *_: popup.dismiss())

    def do_delete(*_):
        try:
            home.saved_charts.pop(key, None)
            home.save_saved_charts()
        except Exception as exc:
            try:
                home.location_error = "删除失败：" + str(exc)
            except Exception:
                pass
        popup.dismiss()
        try:
            home.refresh_list()
        except Exception:
            pass
        if on_done is not None:
            try:
                on_done()
            except Exception:
                pass

    confirm.bind(on_release=do_delete)
    popup.open()
