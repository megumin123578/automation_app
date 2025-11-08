from datetime import datetime
import os
import time
import re
import subprocess
import shutil
import pathlib
import json
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from moviepy import VideoClip, concatenate_videoclips, VideoFileClip, vfx
import shlex
CONFIG_FILE = "ghep_music/config.json"
CONFIG_DIR = "ghep_music/configs"
LAST_CHANNEL_FILE = "ghep_music/last_channel.json"


import time, gc, threading, os, shutil

def _tmp_root(out_dir): 
    d = os.path.join(out_dir, "_tmp"); os.makedirs(d, exist_ok=True); return d

def make_temp_mp4(out_dir):
    return os.path.join(_tmp_root(out_dir),
        f"concat_{os.getpid()}_{threading.get_ident()}_{int(time.time()*1000)}.mp4")

def safe_remove(path, attempts=10, delay=0.2):
    for _ in range(attempts):
        try: os.remove(path); return True
        except FileNotFoundError: return True
        except (PermissionError, OSError): gc.collect(); time.sleep(delay)
    return False

def list_all_mp4_files(folder_path):
    if not os.path.isdir(folder_path):
        raise ValueError(f"Không tìm thấy thư mục: {folder_path}")
    
    mp4_files = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(".mp4"):
                full_path = os.path.join(root, file)
                mp4_files.append(full_path)
    return mp4_files

def list_all_mp3_files(folder_path):
    if not os.path.isdir(folder_path):
        raise ValueError(f"Không tìm thấy thư mục: {folder_path}")
    
    mp3_files = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(".mp3"):
                full_path = os.path.join(root, file)
                mp3_files.append(full_path)
    return mp3_files


def get_all_random_video_groups(videos, group_size=6):
    """Chia danh sách video thành nhiều nhóm ngẫu nhiên với kích thước group_size"""
    random.shuffle(videos)
    groups = []
    for i in range(0, len(videos), group_size):
        group = videos[i:i+group_size]
        if len(group) == group_size:   # chỉ nhận nhóm đủ size
            groups.append(group)
    return groups


# def get_next_output_filename(folder: str) -> str:
#     max_index = 0
#     pattern = re.compile(r"(\d+)\.mp4$", re.IGNORECASE)

#     for filename in os.listdir(folder):
#         match = pattern.match(filename)
#         if match:
#             index = int(match.group(1))
#             if index > max_index:
#                 max_index = index

#     next_index = max_index + 1
#     return os.path.join(folder, f"{next_index}.mp4")

from typing import Optional
def get_first_vids_name(folder: str, first_video_path: Optional[str]) -> str:
    os.makedirs(folder, exist_ok=True)
    base_name = "output"
    if first_video_path:
        base_name = os.path.splitext(os.path.basename(first_video_path))[0]
    base_name = re.sub(r'[<>:"/\\|?*\n\r]+', "_", base_name).strip(" _.")
    if not base_name:
        base_name = "output"

    out0 = os.path.join(folder, f"{base_name}.mp4")
    if not os.path.exists(out0):
        return out0

    i = 1
    while True:
        cand = os.path.join(folder, f"{base_name}_{i}.mp4")
        if not os.path.exists(cand):
            return cand
        i += 1


def get_audio_duration(bgm_audio: str) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                bgm_audio
            ],
            capture_output=True,
            text=True
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def mix_audio_with_bgm_ffmpeg(
    input_video: str,
    bgm_audio: str,
    output_dir: str,
    bgm_volume: float = 0.5,
    video_volume: float = 0.8
):
    output_video = get_first_vids_name(output_dir, input_video)
    temp_output = "temp.mp4"

    # === lấy độ dài nhạc và chọn điểm bắt đầu random ===
    bgm_duration = get_audio_duration(bgm_audio)
    if bgm_duration > 10:
        start_delay = random.uniform(0, bgm_duration - 10)
    else:
        start_delay = 0

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs("log", exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,               # 0:v, 0:a
        "-ss", str(start_delay),
        "-stream_loop", "-1", "-i", bgm_audio,  # 1:a, lặp vô hạn
        "-filter_complex",
        f"[1:a]volume={bgm_volume}[a_bgm];"
        f"[0:a][a_bgm]amix=inputs=2:duration=first:dropout_transition=3[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",                     # cắt nhạc đúng theo độ dài video
        output_video
    ]

    log_path = "log/insert_mp3.txt"
    with open(log_path, "w", encoding="utf-8") as log_file:
        try:
            subprocess.run(cmd, check=True, stdout=log_file, stderr=log_file)
        except subprocess.CalledProcessError:
            if os.path.exists(temp_output):
                os.remove(temp_output)
            print(f"[ERROR] FFmpeg mix failed, xem log: {log_path}")
            raise

    print(f"[OK] Added random looping BGM from {start_delay:.1f}s → {output_video}")
    return output_video


def mix_audio_at_end_ffmpeg(
    input_video: str,
    bgm_audio: str,
    output_dir: str,
    mix_length: int = 15,      # số giây cuối để chèn nhạc
    bgm_volume: float = 0.6,   # âm lượng nhạc nền
    outro_volume: float = 0.2, # âm lượng phần cuối của video gốc
    video_volume: float = 1.0, # âm lượng tổng thể video gốc (slider mới)
):
    os.makedirs(output_dir, exist_ok=True)
    output_video = get_first_vids_name(output_dir, input_video)
    log_path = "log/mix_end_bgm.txt"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def get_duration(file):
        """Lấy độ dài video/audio (giây)."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", file
                ],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    video_dur = get_duration(input_video)
    bgm_dur = get_duration(bgm_audio)

    if video_dur <= 0:
        raise ValueError(f"Không thể đọc độ dài video: {input_video}")
    if bgm_dur <= 0:
        raise ValueError(f"Không thể đọc độ dài nhạc nền: {bgm_audio}")

    # Tính toán vị trí chèn outro
    mix_length = min(mix_length, video_dur)
    mix_start = max(0, video_dur - mix_length)

    if bgm_dur > mix_length:
        bgm_start = random.uniform(0, bgm_dur - mix_length)
    else:
        bgm_start = 0.0

    # ==== FILTER COMPLEX ====
    # - [0:a]volume=video_volume: điều chỉnh âm video gốc
    # - [a_vid_end]volume=outro_volume: làm nhỏ phần cuối
    # - [1:a]volume=bgm_volume: điều chỉnh âm nhạc nền
    # - Ghép lại [a_pre] + [a_mix] → [aout]
    filter_complex = (
        f"[0:a]volume={video_volume},asplit=2[a0][a1];"
        f"[a0]atrim=0:{mix_start}[a_pre];"
        f"[a1]atrim={mix_start}:{video_dur},asetpts=PTS-STARTPTS,volume={outro_volume}[a_vid_end];"
        f"[1:a]volume={bgm_volume},apad[a_bgm];"
        f"[a_vid_end][a_bgm]amix=inputs=2:duration=first:dropout_transition=2[a_mix];"
        f"[a_pre][a_mix]concat=n=2:v=0:a=1[aout]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-ss", str(bgm_start), "-t", str(mix_length), "-i", bgm_audio,
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest",
        output_video
    ]

    with open(log_path, "w", encoding="utf-8") as log_file:
        try:
            subprocess.run(cmd, check=True, stdout=log_file, stderr=log_file)
        except subprocess.CalledProcessError:
            print(f"[ERROR] FFmpeg mix failed, xem log: {log_path}")
            raise

    print(f"[OK] Đã chèn nhạc vào {mix_length:.1f}s cuối video.")
    print(f"[OUT] {output_video}")
    return output_video


def read_used_source_videos(log_path: str):
    used_files = []
    if not os.path.exists(log_path):
        return used_files
    
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            parts = line.split(":", 1)
            if len(parts) < 2:
                continue
            content = parts[1].strip()

            if "+ BGM:" in content:
                content = content.split("+ BGM:")[0].strip()
            #split by comma
            inputs = [p.strip() for p in content.split(",") if p.strip()]
            used_files.extend(inputs)
    
    return used_files

def read_log_info(log_path: str):
    used_inputs = set()
    done_count = 0
    if not os.path.exists(log_path):
        return used_inputs, done_count

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            done_count += 1
            # bỏ phần "xxx.mp4:"
            content = line.split(":", 1)[1]
            if "+ BGM:" in content:
                content = content.split("+ BGM:")[0]
            # tách file input
            inputs = [p.strip() for p in content.split(",") if p.strip()]
            used_inputs.update(inputs)
    return used_inputs, done_count



def normalize_video(
    input_path,
    output_path,
    width=1080,
    height=1920,
    fps=60,
    use_nvenc=True,
    cq=23,               # NVENC dùng -cq; x264 dùng -crf
    v_bitrate="12M",
    a_bitrate="160k",
    nvenc_preset="p4",   
):
    # Path chuẩn/Unicode OK
    in_p  = pathlib.Path(input_path)
    out_p = pathlib.Path(output_path)
    if not in_p.exists():
        raise FileNotFoundError(f"Input không tồn tại: {in_p}")

    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg không có trong PATH")

    # Chọn NVENC nếu có đủ điều kiện
    use_nv = bool(use_nvenc and has_encoder("h264_nvenc"))
    
    if use_nv and not nvenc_supports_preset(nvenc_preset):
        
        nvenc_preset = "medium"

    vf = f"fps={fps},scale={width}:{height}:flags=lanczos"

    if use_nv:
        video_args = [
            "-c:v", "h264_nvenc",
            "-profile:v", "main",
            "-rc", "vbr",
            "-cq", str(int(cq)),
            "-b:v", v_bitrate,
            "-maxrate", v_bitrate,
            "-bufsize", "24M",
            "-preset", nvenc_preset,     # p1..p7 nếu hỗ trợ, else 'medium'
        ]
    else:
        video_args = [
            "-c:v", "libx264",
            "-preset", "medium",
            "-profile:v", "main",
            "-level", "4.2",
            "-crf", str(int(cq) if isinstance(cq, int) else 20),
            "-maxrate", v_bitrate,
            "-bufsize", "16M",
        ]

    cmd = [
        "ffmpeg", "-y",
        "-fflags", "+genpts",
        "-i", str(in_p),
        "-vf", vf,
        *video_args,
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-ar", "48000",
        "-b:a", a_bitrate,
        str(out_p)
    ]

    try:
        run_ffmpeg(cmd)
    except subprocess.CalledProcessError:
        
        if use_nv:
            print("⚠ NVENC failed → fallback libx264")
            video_args = [
                "-c:v", "libx264",
                "-preset", "medium",
                "-profile:v", "main",
                "-level", "4.2",
                "-crf", str(int(cq) if isinstance(cq, int) else 20),
                "-maxrate", v_bitrate,
                "-bufsize", "16M",
            ]
            cmd2 = [
                "ffmpeg", "-y",
                "-fflags", "+genpts",
                "-i", str(in_p),
                "-vf", vf,
                *video_args,
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-c:a", "aac",
                "-ar", "48000",
                "-b:a", a_bitrate,
                str(out_p)
            ]
            run_ffmpeg(cmd2)
        else:
            raise

def concat_video(video_paths, output_path):
    list_file = "temp.txt"
    with open(list_file, 'w', encoding='utf-8') as f:
        for path in video_paths:
            abs_path = os.path.abspath(path).replace("\\", "/")
            f.write(f"file '{abs_path}'\n")

    command = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output_path
    ]
    with open("log/ffmpeg_log.txt", "w", encoding="utf-8") as log_file:
        subprocess.run(
            command,
            check=True,
            stdout=log_file,
            stderr=log_file
        )
    os.remove(list_file)


def auto_concat(input_videos, output_path,
                num_threads=8, width=1080, height=1920,
                fps=60, use_nvenc=True, cq=23,
                v_bitrate="12M", a_bitrate="160k",
                nvenc_preset="p4"):
    normalized_paths = []

    def normalize_and_collect(i, path):
        fixed = f"normalized_{i}.mp4"
        normalize_video(path, fixed, width, height, fps, use_nvenc, cq, v_bitrate, a_bitrate, nvenc_preset)
        return fixed

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(normalize_and_collect, i, path) for i, path in enumerate(input_videos)]
        for future in futures:
            normalized_paths.append(future.result())

    concat_video(normalized_paths, output_path)

    for path in normalized_paths:
        os.remove(path)

def run_ffmpeg(cmd: list):
    try:
        p = subprocess.run(cmd, check=True, text=True,
                           capture_output=True, encoding="utf-8", errors="ignore")
        return p
    except subprocess.CalledProcessError as e:
        print("FFmpeg FAILED")
        print("CMD:", " ".join(cmd))
        print("STDERR:\n", e.stderr)  # <-- xem lỗi thật ở đây
        raise

def has_encoder(name="h264_nvenc"):
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                             capture_output=True, text=True, encoding="utf-8", errors="ignore").stdout.lower()
        return name.lower() in out
    except Exception:
        return False

def nvenc_supports_preset(preset: str) -> bool:
    try:
        out = subprocess.run(["ffmpeg", "-h", "encoder=h264_nvenc"],
                             capture_output=True, text=True, encoding="utf-8", errors="ignore").stdout.lower()
        return f"preset    {preset}".lower() in out or f"-preset {preset}".lower() in out
    except Exception:
        return False
    

def _atempo_chain(speed: float) -> str:
    chain = []
    s = float(speed)
    while s > 2.0:
        chain.append("atempo=2.0")
        s /= 2.0
    chain.append(f"atempo={s:.6g}")
    return ",".join(chain)

def concat_reverse(
    inputs: list[str],
    out_dir: str,
    width: int, height: int, fps: int,
    use_nvenc: bool = True,
    cq: int = 23,
    v_bitrate: str = "12M",
    a_bitrate: str = "160k",
    preset: str = "p4",
    speed_reverse: float = 3.0) -> str:
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"pal_{int(time.time()*1000)}.mp4")

    # inputs
    cmd = ["ffmpeg", "-y"]
    for p in inputs:
        cmd += ["-i", p]

    # build filter graph
    n = len(inputs)
    v_labels = []
    a_labels = []
    fc_parts = []

    # chuẩn hoá từng input: scale + fps + định dạng cho video, aformat cho audio
    for i in range(n):
        v_in = f"[{i}:v]"
        a_in = f"[{i}:a]"
        v_i = f"[v{i}]"
        a_i = f"[a{i}]"
        fc_parts.append(
            f"{v_in}scale={width}:{height}:flags=lanczos,fps={fps},format=yuv420p{v_i}"
        )
        # Ép audio về stereo/44100 để concat ổn định (nếu input nào không có audio, ffmpeg sẽ báo lỗi;
        # nếu có thể gặp clip mute hoàn toàn, nên bổ sung anullsrc ngoài luồng)
        fc_parts.append(
            f"{a_in}aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo{a_i}"
        )
        v_labels.append(v_i)
        a_labels.append(a_i)

    # concat N clip thành một stream [V][A]
    fc_parts.append(
        f"{''.join(v_labels)}{''.join(a_labels)}concat=n={n}:v=1:a=1[V][A]"
    )

    # tách forward/reverse và ghép lại (video)
    # reverse rồi tua nhanh bằng setpts=PTS/speed_reverse
    fc_parts.append("[V]split[VF][VR]")
    fc_parts.append(f"[VR]reverse,setpts=PTS/{speed_reverse}[VR2]")
    fc_parts.append("[VF][VR2]concat=n=2:v=1:a=0[VOUT]")

    # audio: reverse + atempo cho khớp tốc độ rồi concat lại
    fc_parts.append("[A]asplit[AF][AR]")
    fc_parts.append(f"[AR]areverse,{_atempo_chain(speed_reverse)}[AR2]")
    fc_parts.append("[AF][AR2]concat=n=2:v=0:a=1[AOUT]")

    filter_complex = ";".join(fc_parts)
    cmd += ["-filter_complex", filter_complex, "-map", "[VOUT]", "-map", "[AOUT]"]

    # encoder
    if use_nvenc:
        cmd += ["-c:v", "h264_nvenc", "-preset", preset, "-cq", str(cq), "-b:v", v_bitrate]
    else:
        # libx264 dùng CRF gần tương đương CQ
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(cq)]
    cmd += ["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", a_bitrate, "-movflags", "+faststart", out]

    log_path = "log/concat_reverse_single.txt"
    os.makedirs("log", exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as lf:
        subprocess.run(cmd, check=True, stdout=lf, stderr=lf)
    return out

def _has_audio_stream(path: str) -> bool:
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=index",
                "-of", "csv=p=0",
                path,
            ],
            stderr=subprocess.STDOUT,
        )
        return bool(out.strip())
    except Exception:
        return False


def loop_video_to_duration(
    src: str,
    dst: str,
    target_seconds: float,
    *,
    vol: float = 1.0,
    use_nvenc: bool = True,
    nvenc_preset: str = "p4",
    cq: int = 23,
    v_bitrate: str = "12M",
    fps: int = 60,
    a_bitrate: str = "160k",
    on_progress=None,
):
    # tổng thời lượng cần lặp
    t = max(1, int(target_seconds))
    t_float = max(0.001, float(target_seconds))

    has_audio = _has_audio_stream(src)

    # Base args + bật kênh progress
    args = [
        "ffmpeg", "-hide_banner", "-y",
        "-progress", "pipe:1",    # xuất tiến trình ra stdout
        "-nostats",               # tránh spam
        "-loglevel", "error",     # chỉ log lỗi
        "-stream_loop", "-1", "-i", src,
        "-t", str(t),
    ]

    # Video codec
    if use_nvenc:
        args += [
        "-c:v","h264_nvenc",
        "-preset", nvenc_preset,
        "-rc","cbr_hq",
        "-b:v", v_bitrate,
        "-maxrate", v_bitrate,
        "-minrate", v_bitrate,   
        "-bufsize", _double_bitrate(v_bitrate),
        "-r", str(int(fps)),
        "-pix_fmt", "yuv420p",
    ]
    else:
        args += [
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", str(int(cq)),
            "-r", str(int(fps)),
        ]

    # Audio
    if has_audio:
        if abs(vol - 1.0) > 1e-6:
            args += ["-filter:a", f"volume={vol}"]
        args += ["-c:a", "aac", "-b:a", a_bitrate]
    else:
        args += ["-an"]

    # Output cuối cùng
    args += ["-movflags", "+faststart", dst]

    # Bắn 0% ngay khi bắt đầu
    if on_progress:
        try:
            on_progress(0.0)
        except Exception:
            pass

    # Chạy ffmpeg và parse tiến trình
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # gộp để dễ debug nếu lỗi
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="ignore",
    )

    last_pct = -1.0
    tail = []  # giữ vài dòng cuối để hiển thị khi lỗi
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue

            # giữ tail để report khi ffmpeg fail
            tail.append(line)
            if len(tail) > 50:
                tail.pop(0)

            # Dạng 1: out_time_ms=123456789
            if line.startswith("out_time_ms="):
                try:
                    out_ms = int(line.split("=", 1)[1])
                    sec = out_ms / 1_000_000.0
                    pct = max(0.0, min(100.0, (sec / t_float) * 100.0))
                except Exception:
                    continue

            # Dạng 2 (fallback): out_time=HH:MM:SS.micro
            elif line.startswith("out_time="):
                try:
                    ts = line.split("=", 1)[1]
                    # HH:MM:SS[.micro]
                    hms, dot, micro = ts.partition(".")
                    h, m, s = hms.split(":")
                    sec = int(h) * 3600 + int(m) * 60 + float(s + (("." + micro) if dot else ""))
                    pct = max(0.0, min(100.0, (sec / t_float) * 100.0))
                except Exception:
                    continue
            else:
                continue

            # Giảm tần suất cập nhật để UI mượt
            if on_progress and (pct - last_pct >= 0.5 or pct in (0.0, 100.0)):
                try:
                    on_progress(pct)
                except Exception:
                    pass
                last_pct = pct

        ret = proc.wait()
    finally:
        # đảm bảo đóng stdout
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass

    if ret != 0:
        raise RuntimeError(
            "ffmpeg failed (returncode={}):\n{}".format(ret, "\n".join(tail))
        )

    # đảm bảo gọi 100%
    if on_progress:
        try:
            on_progress(100.0)
        except Exception:
            pass

def _double_bitrate(s: str) -> str:
    # "12M" -> "24M", "8000k" -> "16000k"
    m = re.match(r"^(\d+)([kKmM])$", s)
    if not m: return s
    n, suf = int(m.group(1)), m.group(2)
    return f"{n*2}{suf}"