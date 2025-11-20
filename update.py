import os
import hashlib
import zipfile
import shutil
import re
import subprocess
import tempfile
import json
from datetime import datetime

# ===== CONFIG =====
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(ROOT_DIR, "temp_build")
TARGET_FILE = os.path.join(ROOT_DIR, "hyperparameter.py")
VERSION = datetime.now().strftime("%Y.%m.%d.%H%M")
OUTPUT_ZIP = os.path.join(ROOT_DIR, f"update_package_{VERSION}.zip")
MANIFEST_PATH = os.path.join(ROOT_DIR, "manifest.json")


# Thông tin GitHub (để tạo link zip_url)
GITHUB_REPO = "megumin123578/upload-short-with-gpm-handle-excel-file"

EXTRA_FILES = ["update_content.txt", "assets", 'main.exe','gemini.key']  # tồn tại thì copy vào gói


# ===== UTILS =====
def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


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
    print(f"Đã tạo file ZIP: {zip_path}")
    print(f"Tổng số file nén: {files_count}")


def update_manifest(version, zip_path):
    """Tự động cập nhật manifest.json với version, zip_url, sha256"""
    sha256 = sha256_of_file(zip_path)
    zip_name = os.path.basename(zip_path)

    zip_url = (
        f"https://github.com/{GITHUB_REPO}/releases/download/"
        f"v{version}/{zip_name}"
    )

    data = {
        "version": version,
        "zip_url": zip_url,
        "sha256": sha256
    }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("\nĐã cập nhật manifest.json:")
    print(json.dumps(data, indent=2, ensure_ascii=False))


def build_package():
    app_version, bumped_file = copy_and_bump_version()
    if not app_version:
        print("Không tạo được version, dừng lại.")
        return

    temp_out_dir = tempfile.mkdtemp(prefix="obf_out_")

    try:
        run_pyarmor(temp_out_dir)

        if bumped_file:
            shutil.copy2(bumped_file, os.path.join(temp_out_dir, "hyperparameter.py"))
            print("Đã chèn hyperparameter.py vào gói tạm")

        for fname in EXTRA_FILES:
            src = os.path.join(ROOT_DIR, fname)
            dest = os.path.join(temp_out_dir, fname)
            if not os.path.exists(src):
                print(f"Bỏ qua vì không tìm thấy: {src}")
                continue
            if os.path.isfile(src):
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(src, dest)
                print(f"Đã thêm file: {fname}")
            elif os.path.isdir(src):
                shutil.copytree(src, dest, dirs_exist_ok=True)
                print(f"Đã thêm thư mục: {fname}")

        zip_dir(temp_out_dir, OUTPUT_ZIP)
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

        # Cập nhật manifest.json sau khi build
        update_manifest(app_version, OUTPUT_ZIP)

        print(f"\nHoàn tất build cho phiên bản: {app_version}")
    finally:
        shutil.rmtree(temp_out_dir, ignore_errors=True)


if __name__ == "__main__":
    build_package()