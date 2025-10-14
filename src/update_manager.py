import os, sys, json, shutil, tempfile, zipfile, hashlib
from urllib.request import urlopen, Request

APP_SRC_DIR = os.path.dirname(os.path.abspath(__file__))

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
    for root, dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        target_root = os.path.join(dst_dir, rel) if rel != "." else dst_dir
        os.makedirs(target_root, exist_ok=True)
        for fn in files:
            if fn.lower().endswith(".py"):
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

def check_and_update(manifest_src: str, current_version: str, verify_hash: bool = True) -> str:
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
    os.close(fd)  # đóng handle

    download_to_any(zip_src, tmp_zip)

    if verify_hash and sha:
        if sha256_file(tmp_zip).lower() != sha.lower():
            os.remove(tmp_zip)
            return "Sai checksum! Hủy cập nhật."

    msg = install_from_zip(tmp_zip)
    os.remove(tmp_zip)
    return f"{msg} Cập nhật lên {remote_ver} thành công."
