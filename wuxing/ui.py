from datetime import datetime
from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.core.window import Window
from .paipan import build_chart

class WuxingApp(App):
    title = "五行排盘"

    def build(self):
        Window.softinput_mode = "below_target"
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        form = GridLayout(cols=2, size_hint_y=None, row_default_height=dp(44), spacing=dp(6))
        form.add_widget(Label(text="出生日期", halign="left"))
        self.date = TextInput(text="1990-01-01", multiline=False)
        form.add_widget(self.date)
        form.add_widget(Label(text="出生时间", halign="left"))
        self.time = TextInput(text="12:00", multiline=False)
        form.add_widget(self.time)
        form.add_widget(Label(text="经度", halign="left"))
        self.longitude = TextInput(text="-77.49", multiline=False, input_filter="float")
        form.add_widget(self.longitude)
        form.add_widget(Label(text="性别", halign="left"))
        self.sex = Spinner(text="男", values=("男","女"))
        form.add_widget(self.sex)
        root.add_widget(form)

        btn = Button(text="开始排盘", size_hint_y=None, height=dp(48))
        btn.bind(on_release=self.calculate)
        root.add_widget(btn)

        self.output = Label(text="请输入出生资料后点击“开始排盘”。", halign="left", valign="top")
        self.output.bind(size=lambda *_: setattr(self.output, "text_size", self.output.size))
        root.add_widget(self.output)

        return root

    def calculate(self, *_):
        try:
            dt = datetime.strptime(self.date.text.strip()+" "+self.time.text.strip(), "%Y-%m-%d %H:%M")
            lon = float(self.longitude.text.strip())
            chart = build_chart(dt, lon, self.sex.text)

            ps = [chart.year, chart.month, chart.day, chart.hour]
            lines = [
                "【五行排盘】",
                f"出生：{dt:%Y-%m-%d %H:%M}",
                f"经度：{lon:.4f}°",
                f"真太阳时（经度修正）：{chart.true_solar:%Y-%m-%d %H:%M}",
                "",
                f"年柱：{chart.year.ganzhi}  十神：{chart.year.ten_god_gan}  纳音：{chart.year.na_yin}",
                f"月柱：{chart.month.ganzhi}  十神：{chart.month.ten_god_gan}  纳音：{chart.month.na_yin}",
                f"日柱：{chart.day.ganzhi}  日主：{chart.day.gan}  纳音：{chart.day.na_yin}",
                f"时柱：{chart.hour.ganzhi}  十神：{chart.hour.ten_god_gan}  纳音：{chart.hour.na_yin}",
                "",
                "【藏干】",
            ]
            for p in ps:
                lines.append(f"{p.name} {p.ganzhi}：{'、'.join(p.hidden)}")
            lines += [
                "",
                f"【胎元】{chart.fetal}",
                f"【命宫】{chart.life_palace}（辅助取象）",
                "",
                "【五行计数】",
                "、".join(f"{k}{v}" for k,v in chart.wuxing.items()),
                "",
                "【大运】",
            ]
            for x in chart.dayun:
                lines.append(f"{x['序']}. {x['干支']} 约{x['起运岁']}岁起（{x['顺逆']}）")
            if chart.warnings:
                lines += ["", "【复核提示】"] + [f"• {x}" for x in chart.warnings]
            lines += [
                "",
                "注：纳音、胎元、命宫及神煞属于辅助取象；本工具不以它们独立定富贵。",
                "本应用用于传统命理文化研究与娱乐参考，不构成人生决策依据。"
            ]
            self.output.text = "\n".join(lines)
        except Exception as e:
            self.output.text = "排盘失败：\n" + str(e) + "\n\n请检查日期、时间、经度格式。"
