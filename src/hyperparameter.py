import os

APP_VERSION = "1.0.20"
UPDATE_MANIFEST = "https://ghproxy.net/https://raw.githubusercontent.com/megumin123578/upload-short-with-gpm-handle-excel-file/main/manifest.json"
APP_TITLE = "AUTO GENERATE UPLOAD SHORT YOUTUBE"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # lấy thư mục gốc
GROUPS_DIR = os.path.join(BASE_DIR, "group")
OUTPUT_DIR = os.path.join(BASE_DIR, "upload")
EXCEL_DIR = os.path.join(BASE_DIR, "upload_data.xlsx")


CHANNEL_HEADER_HINTS = [
    "channel", "kênh", "kenh", "channel_id", "channel name", "channel_name", "name", "id"
]


