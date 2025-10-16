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
from moviepy import VideoFileClip, concatenate_videoclips, vfx
CONFIG_FILE = "ghep music/config.json"
CONFIG_DIR = "ghep music/configs"
LAST_CHANNEL_FILE = "ghep music/last_channel.json"

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


def get_next_output_filename(folder: str) -> str:
    max_index = 0
    pattern = re.compile(r"(\d+)\.mp4$", re.IGNORECASE)

    for filename in os.listdir(folder):
        match = pattern.match(filename)
        if match:
            index = int(match.group(1))
            if index > max_index:
                max_index = index

    next_index = max_index + 1
    return os.path.join(folder, f"{next_index}.mp4")

#musc helper functions
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
):
    output_video = get_next_output_filename(output_dir)
    temp_output = "temp.mp4"

    # === lấy độ dài nhạc và chọn điểm bắt đầu random ===
    bgm_duration = get_audio_duration(bgm_audio)
    if bgm_duration > 10:  # chỉ random nếu nhạc dài hơn 10s
        start_delay = random.uniform(0, bgm_duration - 10)
    else:
        start_delay = 0

    # === lệnh ffmpeg với đoạn random ===
    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,                  # 0:v, 0:a
        "-ss", str(start_delay),            # random start position
        "-i", bgm_audio,                    # 1:a
        "-filter_complex",
        f"[1:a]volume={bgm_volume}[a_bgm];"
        f"[0:a][a_bgm]amix=inputs=2:duration=first:dropout_transition=3[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_video
    ]

    os.makedirs("log", exist_ok=True)
    with open("log/insert_mp3.txt", "w", encoding="utf-8") as log_file:
        try:
            subprocess.run(cmd, check=True, stdout=log_file, stderr=log_file)
        except subprocess.CalledProcessError as e:
            if os.path.exists(temp_output):
                os.remove(temp_output)
            print(f"FFmpeg error: {e}")
            raise

    print(f"Added random BGM from {start_delay:.1f}s → {output_video}")
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


def auto_concat(input_videos, output_path, num_threads = 8):
    normalized_paths = []

    def normalize_and_collect(i, path):
        fixed = f"normalized_{i}.mp4"
        normalize_video(path, fixed)
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
    