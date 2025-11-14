import os
import hashlib
import zipfile
import shutil
import re
import tempfile
import json
from datetime import datetime

# ===== CONFIG =====
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_FILE = os.path.join(ROOT_DIR, "hyperparameter.py")
VERSION = datetime.now().strftime("%Y.%m.%d.%H%M")
OUTPUT_ZIP = os.path.join(ROOT_DIR, f"update_package_{VERSION}.zip")
MANIFEST_PATH = os.path.join(ROOT_DIR, "manifest.json")

GITHUB_REPO = "megumin123578/upload-short-with-gpm-handle-excel-file"

# ====== CALC SHA256 ======
def sha256_of_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ===== BUMP VERSION =====
def bump_hyperparameter(src_path=TARGET_FILE):
    if not os.path.exists(src_path):
        print("Không tìm thấy hyperparameter.py")
        return None, None

    temp_dir = tempfile.mkdtemp(prefix="hyper_")
    dest_path = os.path.join(temp_dir, "hyperparameter.py")

    with open(src_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r'APP_VERSION\s*=\s*"(\d+\.\d+\.\d+)"', content)
    if not match:
        print("Không tìm thấy APP_VERSION")
        return None, None

    old_ver = match.group(1)
    parts = old_ver.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    new_ver = ".".join(parts)

    new_content = re.sub(
        r'APP_VERSION\s*=\s*"\d+\.\d+\.\d+"',
        f'APP_VERSION = "{new_ver}"',
        content
    )

    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"hyperparameter.py: {old_ver} → {new_ver}")
    return new_ver, dest_path


# ===== OBFUSCATOR =====
def obfuscate_source(text: str) -> str:
    import zlib, base64
    data = zlib.compress(text.encode("utf-8"), level=9)
    b64 = base64.b64encode(data).decode("ascii")

    return f"""# -*- coding: utf-8 -*-
import zlib as _z, base64 as _b
_c=_z.decompress(_b.b64decode({b64!r}))
exec(compile(_c, __file__, 'exec'), globals(), globals())
"""


# ===== COPY & OBFUSCATE PY ONLY =====
def copy_and_obfuscate_py(src_root, dst_root, bumped_file_path):
    for dirpath, dirnames, filenames in os.walk(src_root):

        # bỏ qua thư mục build, cache, assets
        dirnames[:] = [
            d for d in dirnames
            if d not in (".git", "__pycache__", "assets", "temp_build")
        ]

        rel = os.path.relpath(dirpath, src_root)
        out_dir = os.path.join(dst_root, rel if rel != "." else "")
        os.makedirs(out_dir, exist_ok=True)

        for fname in filenames:
            if not fname.endswith(".py"):
                continue

            src = os.path.join(dirpath, fname)
            dst = os.path.join(out_dir, fname)

            # hyperparameter.py dùng bản đã bump
            if os.path.abspath(src) == os.path.abspath(TARGET_FILE):
                shutil.copy2(bumped_file_path, dst)
                print("Copied bumped hyperparameter.py")
                continue

            # đọc & obfuscate
            try:
                with open(src, "r", encoding="utf-8") as f:
                    code = f.read()
            except UnicodeDecodeError:
                with open(src, "r", encoding="latin-1") as f:
                    code = f.read()

            obf = obfuscate_source(code)
            with open(dst, "w", encoding="utf-8") as f:
                f.write(obf)

            print("Obfuscated:", os.path.relpath(dst, dst_root))


# ===== ZIP =====
def zip_dir(src_dir, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, filenames in os.walk(src_dir):
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, src_dir).replace("\\", "/")
                z.write(full, rel)
    print("Đã tạo ZIP:", zip_path)


# ===== UPDATE MANIFEST =====
def update_manifest(version, zip_path):
    sha = sha256_of_file(zip_path)
    name = os.path.basename(zip_path)

    data = {
        "version": version,
        "zip_url": f"https://github.com/{GITHUB_REPO}/releases/download/v{version}/{name}",
        "sha256": sha
    }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("manifest.json updated")


# ===== MAIN BUILD =====
def build_package():
    version, bumped_file = bump_hyperparameter()
    if not version:
        return

    temp_dir = tempfile.mkdtemp(prefix="pyonly_")

    print("Copy + obfuscate .py files ONLY...")
    copy_and_obfuscate_py(ROOT_DIR, temp_dir, bumped_file)

    print("Zipping package...")
    zip_dir(temp_dir, OUTPUT_ZIP)

    update_manifest(version, OUTPUT_ZIP)

    shutil.rmtree(temp_dir, ignore_errors=True)
    print("DONE → version:", version)


if __name__ == "__main__":
    build_package()
