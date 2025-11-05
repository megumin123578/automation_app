import os
import hashlib
import zipfile
import shutil
import re
import subprocess
import tempfile
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(ROOT_DIR, "temp_build")
TARGET_FILE = os.path.join(ROOT_DIR, "hyperparameter.py")
VERSION = datetime.now().strftime("%Y.%m.%d.%H%M")
OUTPUT_ZIP = os.path.join(ROOT_DIR, f"update_package_{VERSION}.zip")

# Nếu muốn copy kèm một vài file txt vào gói update, liệt kê ở đây:
EXTRA_FILES = ["update_content.txt", "requirement.txt"]  # tồn tại thì sẽ được copy vào gói

def md5_of_file(path):
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

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

def run_pyarmor(out_dir: str):
    print("Đang chạy PyArmor để mã hóa source...")
    cmd = [
        "pyarmor", "gen", "-r",
        "--exclude", "./hyperparameter.py",
        "-O", out_dir, "."
    ]
    # shell=False để truyền tham số an toàn; check=True để raise nếu lỗi
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError("PyArmor thất bại!")

def zip_dir(src_dir: str, zip_path: str):
    files_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for dirpath, _, filenames in os.walk(src_dir):
            for file in filenames:
                full_path = os.path.join(dirpath, file)
                rel_path = os.path.relpath(full_path, src_dir).replace("\\", "/")
                zipf.write(full_path, arcname=rel_path)
                files_count += 1
    print(f"✅ Đã tạo file ZIP: {zip_path}")
    print(f"📦 Tổng số file nén: {files_count}")

def build_package():
    app_version, bumped_file = copy_and_bump_version()
    if not app_version:
        print("Không tạo được version, dừng lại.")
        return

    # Thư mục output tạm cho PyArmor
    temp_out_dir = tempfile.mkdtemp(prefix="obf_out_")

    try:
        # 1) Obfuscate code vào thư mục tạm
        run_pyarmor(temp_out_dir)

        # 2) Thêm hyperparameter.py (đã bump version) vào thư mục tạm
        if bumped_file:
            shutil.copy2(bumped_file, os.path.join(temp_out_dir, "hyperparameter.py"))
            print("📄 Đã chèn hyperparameter.py vào gói tạm")

        # 3) (Tuỳ chọn) Copy thêm các file rời nếu tồn tại
        for fname in EXTRA_FILES:
            src = os.path.join(ROOT_DIR, fname)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(temp_out_dir, fname))
                print(f"➕ Đã thêm {fname}")

        # 4) Nén trực tiếp từ thư mục tạm
        zip_dir(temp_out_dir, OUTPUT_ZIP)

        # 5) Dọn temp bump
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

        print(f"🎯 Hoàn tất build cho phiên bản: {app_version}")
    finally:
        # Dọn staging của PyArmor
        shutil.rmtree(temp_out_dir, ignore_errors=True)

if __name__ == "__main__":
    build_package()
