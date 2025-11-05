import os
import hashlib
import zipfile
import shutil
import re
import subprocess
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(ROOT_DIR, "temp_build")
TARGET_FILE = os.path.join(ROOT_DIR, "hyperparameter.py")
OUT_DIR = os.path.abspath(os.path.join(ROOT_DIR, "../out"))
VERSION = datetime.now().strftime("%Y.%m.%d.%H%M")
OUTPUT_ZIP = os.path.join(ROOT_DIR, f"update_package_{VERSION}.zip")

EXCLUDE_DIRS = {
    ".git", "__pycache__", "venv", ".venv", "node_modules",
    "dist", "build", ".idea", ".vscode", "temp_build"
}
EXCLUDE_EXTS = {".log", ".tmp", ".bak", ".zip"}
EXCLUDE_FILES = {"Thumbs.db", ".DS_Store", "update_manifest.json"}


def md5_of_file(path):
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def should_exclude(name, full_path):
    if name in EXCLUDE_FILES:
        return True
    if name.lower() in ['update_content.txt', 'requirement.txt']:
        return False
    if any(name.endswith(ext) for ext in EXCLUDE_EXTS):
        return True
    if any(x in full_path for x in EXCLUDE_DIRS):
        return True
    return False


def copy_and_bump_version(src_path=TARGET_FILE, dest_dir=TEMP_DIR):
    if not os.path.exists(src_path):
        print(f"Không tìm thấy file: {src_path}")
        return None, None

    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, os.path.basename(src_path))

    with open(src_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r'APP_VERSION\s*=\s*"(\d+\.\d+\.\d+)"', content)
    if not match:
        print("Không tìm thấy APP_VERSION trong file.")
        return None, None

    old_version = match.group(1)
    parts = old_version.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    new_version = ".".join(parts)

    new_content = re.sub(
        r'APP_VERSION\s*=\s*"\d+\.\d+\.\d+"',
        f'APP_VERSION = "{new_version}"',
        content
    )

    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"hyperparameter.py: {old_version} → {new_version}")
    return new_version, dest_path


def run_pyarmor():
    print("Đang chạy PyArmor để mã hóa source...")
    cmd = [
        "pyarmor", "gen", "-r",
        "--exclude", "./hyperparameter.py",
        "-O", OUT_DIR, "."
    ]
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        raise RuntimeError("PyArmor thất bại!")


def create_zip_from_out():
    files_count = 0
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
        for dirpath, dirnames, filenames in os.walk(OUT_DIR):
            for file in filenames:
                full_path = os.path.join(dirpath, file)
                rel_path = os.path.relpath(full_path, OUT_DIR).replace("\\", "/")
                zipf.write(full_path, arcname=rel_path)
                files_count += 1

    print(f"✅ Đã tạo file ZIP: {OUTPUT_ZIP}")
    print(f"📦 Tổng số file nén: {files_count}")


def build_package():
    app_version, temp_file = copy_and_bump_version()
    if not app_version:
        print("Không tạo được version, dừng lại.")
        return

    # 1️ Xóa thư mục out cũ nếu có
    if os.path.exists(OUT_DIR):
        shutil.rmtree(OUT_DIR, ignore_errors=True)

    # 2️ Obfuscate code
    run_pyarmor()

    # 3️ Thêm hyperparameter.py (đã bump version)
    if temp_file:
        shutil.copy2(temp_file, os.path.join(OUT_DIR, "hyperparameter.py"))
        print("📄 Đã chèn hyperparameter.py vào thư mục out")

    # 4️ Nén zip
    create_zip_from_out()

    # 5 Dọn temp
    shutil.rmtree(TEMP_DIR, ignore_errors=True)

    print(f"🎯 Hoàn tất build cho phiên bản: {app_version}")


if __name__ == "__main__":
    build_package()
