import os, sys, json, shutil, tempfile, zipfile, hashlib
from urllib.request import urlopen, Request

APP_SRC_DIR = os.path.dirname(os.path.abspath(__file__))

import subprocess, time

def _extract_to_stage(zip_path: str, stage_dir: str):
    # Dọn thư mục staging rồi giải nén
    if os.path.exists(stage_dir):
        shutil.rmtree(stage_dir, ignore_errors=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(stage_dir)

def _write_apply_script(stage_dir: str) -> str:
    # Tạo script updater độc lập, không import gì từ app
    apply_py = os.path.join(stage_dir, "_apply_update.py")
    code = r'''
import os, sys, time, shutil, subprocess

RETRY_FILE = 120     # số lần retry/1 file
SLEEP_FILE = 0.25    # giây giữa mỗi lần retry/1 file

def copy_with_retry(src, dst):
    for _ in range(RETRY_FILE):
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            return True
        except PermissionError:
            time.sleep(SLEEP_FILE)
        except Exception:
            # thử lại vì có thể file đang bị AV scan/lock tạm
            time.sleep(SLEEP_FILE)
    return False

def copy_tree_retry(src_root, dst_root):
    for root, dirs, files in os.walk(src_root):
        rel = os.path.relpath(root, src_root)
        target = os.path.join(dst_root, rel) if rel != "." else dst_root
        os.makedirs(target, exist_ok=True)
        for d in dirs:
            os.makedirs(os.path.join(target, d), exist_ok=True)
        for f in files:
            if f == "_apply_update.py":
                continue
            sp = os.path.join(root, f)
            dp = os.path.join(target, f)
            if not copy_with_retry(sp, dp):
                # Nếu có file copy mãi không được, thử đợi rồi copy lại cả cây
                # nhưng để đơn giản ta vẫn tiếp tục với file khác
                pass

if __name__ == "__main__":
    # argv: stage_dir, app_root, py_exe, entry_script
    stage_dir    = sys.argv[1]
    app_root     = sys.argv[2]
    py_exe       = sys.argv[3]
    entry_script = sys.argv[4]

    # 1) Đợi tiến trình chính thoát (đơn giản: ngủ ngắn + thử copy với retry từng file)
    # 2) Copy nội dung staging → app_root (retry từng file để né lock tạm thời)
    copy_tree_retry(stage_dir, app_root)

    # 3) Dọn staging
    shutil.rmtree(stage_dir, ignore_errors=True)

    # 4) Khởi động lại app
    try:
        subprocess.Popen([py_exe, entry_script], close_fds=True, cwd=app_root)
    except Exception:
        pass
'''
    with open(apply_py, "w", encoding="utf-8") as f:
        f.write(code)
    return apply_py

def _spawn_updater_and_exit(stage_dir: str):
    py_exe = sys.executable
    entry_script = os.path.abspath(sys.argv[0])  # script hiện tại đang chạy
    apply_py = _write_apply_script(stage_dir)

    creationflags = 0
    if os.name == "nt":
        # Ẩn console cho updater trên Windows
        creationflags = 0x08000000  # CREATE_NO_WINDOW

    subprocess.Popen(
        [py_exe, apply_py, stage_dir, APP_SRC_DIR, py_exe, entry_script],
        close_fds=True,
        creationflags=creationflags
    )

    # Thoát NGAY tiến trình chính để nhả lock (kể cả pyarmor_runtime.pyd)
    os._exit(0)


def _is_url(x: str) -> bool:
    return x.lower().startswith(("http://", "https://"))

def _read_json_any(src: str) -> dict:
    if _is_url(src):
        req = Request(src, headers={"User-Agent":"Updater/1.0"})
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    with open(src, "r", encoding="utf-8") as f:
        return json.load(f)

def download_to_any(src: str, dest_path: str):
    if _is_url(src):
        req = Request(src, headers={"User-Agent":"Updater/1.0"})
        with urlopen(req, timeout=120) as resp, open(dest_path, "wb") as f:
            shutil.copyfileobj(resp, f)
    else:
        shutil.copy2(src, dest_path)

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def extract_zip(zip_path: str, dest_dir: str):
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(dest_dir)

def copy_py_tree(src_dir: str, dst_dir: str):
    ignore_exts = (".pyc", ".pyo")
    for root, dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        target_root = os.path.join(dst_dir, rel) if rel != "." else dst_dir
        os.makedirs(target_root, exist_ok=True)
        for fn in files:
            if not fn.lower().endswith(ignore_exts):
                shutil.copy2(os.path.join(root, fn), os.path.join(target_root, fn))

def install_from_zip(zip_path: str) -> str:
    tmpdir = tempfile.mkdtemp(prefix="app_update_")
    try:
        extract_zip(zip_path, tmpdir)
        root_in_zip = None
        for entry in os.listdir(tmpdir):
            p = os.path.join(tmpdir, entry)
            if os.path.isdir(p) and (os.path.exists(os.path.join(p, "main.py")) or
                                     os.path.exists(os.path.join(p, "update_manager.py"))):
                root_in_zip = p
                break
        if root_in_zip is None:
            root_in_zip = tmpdir
        copy_py_tree(root_in_zip, APP_SRC_DIR)
        return "Installed update successfully."
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def _version_tuple(v: str):
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except:
        return tuple()

def is_newer(remote: str, current: str) -> bool:
    return _version_tuple(remote) > _version_tuple(current)


def check_and_update_safe(manifest_src: str, current_version: str, verify_hash: bool = True) -> str:
    info = _read_json_any(manifest_src)
    remote_ver = info.get("version") or info.get("latest") or ""
    zip_src = info.get("zip_url") or info.get("zip_path")
    sha = info.get("sha256")
    print(f"Đang tải manifest từ: {manifest_src}")

    if not remote_ver or not zip_src:
        return "Manifest không hợp lệ."
    if not is_newer(remote_ver, current_version):
        return f"Đang ở bản mới nhất ({current_version})."

    fd, tmp_zip = tempfile.mkstemp(prefix="update_", suffix=".zip")
    os.close(fd)

    download_to_any(zip_src, tmp_zip)

    if verify_hash and sha:
        if sha256_file(tmp_zip).lower() != sha.lower():
            os.remove(tmp_zip)
            return "Sai checksum! Hủy cập nhật."

    # 1) Giải nén vào thư mục staging nằm cạnh source
    stage_dir = os.path.join(APP_SRC_DIR, f"_update_stage_{remote_ver}")
    _extract_to_stage(tmp_zip, stage_dir)
    os.remove(tmp_zip)

    # 2) Gọi updater rời (sẽ copy sau khi app thoát) và kết thúc app hiện tại
    _spawn_updater_and_exit(stage_dir)

    # (quá trình hiện tại sẽ thoát ở _spawn_updater_and_exit)
    return f"Đã tải bản {remote_ver}. Đang áp dụng cập nhật..."


def check_update_only(manifest_src: str, current_version: str) -> dict:
    info = _read_json_any(manifest_src)
    remote_ver = info.get("version") or info.get("latest") or ""
    zip_src = info.get("zip_url") or info.get("zip_path")
    sha = info.get("sha256")
    print(f"Đang tải manifest từ: {manifest_src}")

    if not remote_ver or not zip_src:
        return {"has_update": False, "error": "Manifest không hợp lệ."}

    if not is_newer(remote_ver, current_version):
        return {"has_update": False, "message": f"Đang ở bản mới nhất ({current_version})."}

    return {
        "has_update": True,
        "latest_version": remote_ver,
        "zip_url": zip_src,
        "sha256": sha,
    }
