# main.py
import os
import sys
import faulthandler
import traceback


def _pick_log_dir():
    """找一个可写目录存放日志（iOS 上通常是 App 的 Documents）。"""
    candidates = []
    try:
        candidates.append(os.path.expanduser("~/Documents"))
    except Exception:
        pass
    try:
        candidates.append(os.path.join(os.path.expanduser("~"), "Documents"))
    except Exception:
        pass
    try:
        candidates.append(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        pass
    for path in candidates:
        if not path:
            continue
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, ".write_probe")
            with open(probe, "w", encoding="utf-8") as fh:
                fh.write("ok")
            os.remove(probe)
            return path
        except Exception:
            continue
    return "."


LOG_DIR = _pick_log_dir()
LOG_PATH = os.path.join(LOG_DIR, "wuxing_error.log")

try:
    _log_file = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
except Exception:
    _log_file = sys.__stderr__

sys.stdout = _log_file
sys.stderr = _log_file

try:
    faulthandler.enable(file=_log_file, all_threads=True)
except Exception:
    pass


def _log(message):
    try:
        _log_file.write(str(message) + "\n")
        _log_file.flush()
    except Exception:
        pass


def _excepthook(exc_type, exc_value, exc_tb):
    _log("=" * 60)
    _log("未捕获异常：")
    _log("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
    _log("=" * 60)


sys.excepthook = _excepthook

_log("=" * 60)
_log("App 启动")
_log("Python: " + sys.version.replace("\n", " "))
_log("日志路径: " + LOG_PATH)

try:
    from wuxing.ui import WuxingApp
except Exception:
    _log("导入 wuxing.ui 失败：")
    _log(traceback.format_exc())
    raise

if __name__ == "__main__":
    try:
        WuxingApp().run()
    except Exception:
        _log("App 运行异常退出：")
        _log(traceback.format_exc())
        raise
    finally:
        _log("App 退出")
        try:
            _log_file.flush()
        except Exception:
            pass