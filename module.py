
import itertools
from hyperparameter import CHANNEL_HEADER_HINTS
import os
import csv
import json
import threading
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import openai
from tkcalendar  import DateEntry
import sys,subprocess
import tkinter.simpledialog as sd
import re

CONFIG_FILE = "config.json"
USED_LOG_FILE = "log.txt"
CONFIG_PATH = "config_dir"
GROUP_SETTINGS_PATH =  "group_settings.json"

def load_group_settings():
    if not os.path.exists(GROUP_SETTINGS_PATH):
        return {}
    try:
        with open(GROUP_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_group_settings(new_data: dict):
    os.makedirs(os.path.dirname(GROUP_SETTINGS_PATH), exist_ok=True)

    # --- B1: đọc dữ liệu cũ nếu có ---
    old_data = {}
    if os.path.exists(GROUP_SETTINGS_PATH):
        try:
            with open(GROUP_SETTINGS_PATH, "r", encoding="utf-8") as f:
                old_data = json.load(f)
        except Exception:
            old_data = {}

    # --- B2: merge (ghi đè key trùng, giữ key cũ nếu chưa có) ---
    merged = old_data.copy()
    for group, group_val in new_data.items():
        if group not in merged:
            merged[group] = {}
        if isinstance(group_val, dict):
            merged[group].update(group_val)
        else:
            merged[group] = group_val

    # --- B3: ghi ra file ---
    with open(GROUP_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)


def list_group_csvs(groups_dir: str):
    if not os.path.isdir(groups_dir):
        return []
    files = []
    for name in os.listdir(groups_dir):
        p = os.path.join(groups_dir, name)
        nl = name.lower()
        if os.path.isfile(p) and nl.endswith(".csv"):
            if "__assignments_" in nl or nl.startswith("assignments_"):
                continue
            files.append(name)
    return sorted(files)

def read_channels_from_csv(csv_path: str):
    channels = []
    if not os.path.isfile(csv_path):
        return channels
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return channels

    header = [c.strip() for c in rows[0]] if rows and rows[0] else []
    col_idx = None
    if header:
        lower_header = [h.lower() for h in header]
        for hint in CHANNEL_HEADER_HINTS:
            if hint in lower_header:
                col_idx = lower_header.index(hint)
                break

    start_row = 1 if col_idx is not None else 0
    for row in rows[start_row:]:
        if not row:
            continue
        if col_idx is not None and col_idx < len(row):
            v = (row[col_idx] or "").strip()
            if v:
                channels.append(v)
        else:
            first = next((c.strip() for c in row if c and c.strip()), "")
            if first:
                channels.append(first)
    return channels

def normalize_lines(s: str):
    return [ln.strip() for ln in s.splitlines() if ln.strip()]

def assign_pairs(channels, titles, descs, mode="titles"):

    if not channels:
        raise ValueError("No channels found in selected CSV.")
    if not titles:
        raise ValueError("No titles provided.")

    if len(descs) <= 1:
        desc_cycle = itertools.cycle([descs[0] if descs else ""])
    else:
        desc_cycle = itertools.cycle(descs)

    if mode == "titles":
        ch_cycle = itertools.cycle(channels)
        out = []
        for title in titles:
            ch = next(ch_cycle)
            d = next(desc_cycle)
            out.append((ch, title, d))
        return out
    else:  # mode == "channels"
        title_cycle = itertools.cycle(titles)
        out = []
        for ch in channels:
            t = next(title_cycle)
            d = next(desc_cycle)
            out.append((ch, t, d))
        return out
    
# module.py
def load_group_dirs(config_path=CONFIG_PATH) -> dict:
    group_to_dir = {}
    if not os.path.isfile(config_path):
        return group_to_dir
    with open(config_path, "r", encoding="utf-8") as f:
        for line in f:
            if ":" not in line:
                continue
            name, path = line.strip().split(":", 1)
            # -- chuẩn hóa khóa: bỏ .csv
            key = os.path.splitext(name.strip())[0]
            # -- chuẩn hóa path
            norm_path = os.path.abspath(path.strip().replace("\\", "/"))
            group_to_dir[key] = norm_path
            # (tùy chọn) giữ thêm khóa cũ để tương thích 2 chiều
            group_to_dir[key + ".csv"] = norm_path
    return group_to_dir

def load_used_videos():
    if not os.path.exists(USED_LOG_FILE):
        return set()
    with open(USED_LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def get_mp4_filename(path: str) -> str:
    if not path:
        return ""
    safe_path = str(path).replace("\\", "/")
    filename = os.path.basename(safe_path)
    return filename if filename.lower().endswith(".mp4") else ""


def save_group_config(group_name: str, move_folder: str):
    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = {}

    data[group_name] = move_folder
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_group_config(group_name: str) -> str:
    if not os.path.exists(CONFIG_FILE):
        return ""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(group_name, "")
    except:
        return ""
    
