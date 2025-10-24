import os
import subprocess
import webview
from data_helper import *

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_DIR = os.path.join(BASE_DIR, "cleaned html")

class API:
    def __init__(self, folder):
        self.folder = folder

    def list_dates(self):
        try:
            dates = [
                d for d in os.listdir(self.folder)
                if os.path.isdir(os.path.join(self.folder, d))
            ]
            dates.sort(reverse=True)
            return dates
        except Exception as e:
            return [f"Lỗi: {e}"]

    def list_tabs(self, date_folder):
        path = os.path.join(self.folder, date_folder)
        try:
            tabs = [
                d for d in os.listdir(path)
                if os.path.isdir(os.path.join(path, d))
            ]
            return sorted(tabs)
        except Exception:
            return []

    def list_files(self, date_folder, tab):
        path = os.path.join(self.folder, date_folder, tab)
        try:
            return [
                f for f in os.listdir(path)
                if f.lower().endswith(".html")
            ]
        except Exception:
            return []

    def load_html(self, date_folder, tab, filename):
        file_path = os.path.join(self.folder, date_folder, tab, filename)
        if not os.path.isfile(file_path):
            return "<h3 style='color:red'>Không tìm thấy file</h3>"
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"<h3 style='color:red'>Lỗi đọc file: {e}</h3>"

    def run_refresh_script(self):
        try:
            result = subprocess.run(
                ["python", REFRESH_SCRIPT],
                capture_output=True,
                text=True,
                check=True
            )
            return f"<pre style='color:green'>Đã chạy xong:\n{result.stdout}</pre>"
        except subprocess.CalledProcessError as e:
            return f"<pre style='color:red'>Lỗi:\n{e.stderr}</pre>"
        except Exception as e:
            return f"<pre style='color:red'>Lỗi không xác định: {e}</pre>"

def on_loaded():
    w = webview.windows[0]
    try:
        w.maximize()
    except:
        # fallback nếu GUI không hỗ trợ maximize
        width, height = w.screen_size
        w.resize(width, height)

if __name__ == "__main__":
    api = API(MAIN_DIR)
    html = generate_index_html()
    webview.create_window(
        "HTML Folder Viewer",
        html=html,
        js_api=api,
        width=1700,
        height=1000,
        resizable=True,
    )
    webview.start(on_loaded, gui="edgechromium" if os.name == "nt" else None)