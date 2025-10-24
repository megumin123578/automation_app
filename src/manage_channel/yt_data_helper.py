import csv
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests

API_BASE = "https://www.googleapis.com/youtube/v3"
CONFIG_TXT = os.path.join(os.getcwd(), r"manage_channel\config.txt")


def http_get(endpoint: str, params: Dict) -> Dict:
    url = f"{API_BASE}/{endpoint}"
    r = requests.get(url, params=params, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
    return r.json()


def parse_channel_from_url(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    (handle, channel_id, username) tùy URL.
    """
    m = re.search(r"youtube\.com/@([^/?#]+)", url, re.I)
    if m:
        handle = m.group(1)
        if not handle.startswith("@"):
            handle = "@" + handle
        return handle, None, None

    m = re.search(r"youtube\.com/channel/(UC[0-9A-Za-z_-]{20,})", url, re.I)
    if m:
        return None, m.group(1), None

    m = re.search(r"youtube\.com/user/([^/?#]+)", url, re.I)
    if m:
        return None, None, m.group(1)

    m = re.search(r"youtube\.com/c/([^/?#]+)", url, re.I)
    if m:
        # thử coi như handle (nhiều kênh đã có @ tương ứng)
        return "@" + m.group(1), None, None

    return None, None, None

def get_channel_resource(
    api_key: str,
    handle: Optional[str] = None,
    channel_id: Optional[str] = None,
    username: Optional[str] = None,
) -> Dict:
    params = {
        "part": "snippet,statistics,contentDetails,brandingSettings",
        "key": api_key,
        "maxResults": 1,
    }
    if handle:
        params["forHandle"] = handle.lstrip("@")
    elif channel_id:
        params["id"] = channel_id
    elif username:
        params["forUsername"] = username
    else:
        raise ValueError("Thiếu handle/channel_id/username")

    data = http_get("channels", params)
    items = data.get("items", [])
    if items:
        return items[0]

    # Fallback: dùng search.list để tìm channel
    q = (handle or username or channel_id or "").lstrip("@")
    if q:
        search = http_get("search", {
            "key": api_key, "part": "snippet",
            "q": q, "type": "channel", "maxResults": 1
        })
        sitems = search.get("items", [])
        if sitems:
            cid = sitems[0]["snippet"]["channelId"]
            return get_channel_resource(api_key, channel_id=cid)

    raise RuntimeError("Không tìm thấy kênh phù hợp.")


def get_uploads_playlist_id(channel: Dict) -> str:
    try:
        return channel["contentDetails"]["relatedPlaylists"]["uploads"]
    except KeyError:
        raise RuntimeError("Không lấy được uploads playlist ID từ channel.contentDetails.")

def list_upload_videos(api_key: str, uploads_playlist_id: str, limit: int = 50) -> List[Dict]:
    results = []
    page_token = None
    while True:
        params = {
            "key": api_key,
            "part": "snippet,contentDetails",
            "playlistId": uploads_playlist_id,
            "maxResults": min(50, max(1, limit - len(results))),
        }
        if page_token:
            params["pageToken"] = page_token
        resp = http_get("playlistItems", params)
        for it in resp.get("items", []):
            results.append({
                "videoId": it["contentDetails"]["videoId"],
                "publishedAt": it["contentDetails"].get("videoPublishedAt") or it["snippet"].get("publishedAt"),
                "title": it["snippet"]["title"],
                "description": it["snippet"].get("description", ""),
                "position": it["snippet"].get("position"),
            })
            if len(results) >= limit:
                return results

        page_token = resp.get("nextPageToken")
        if not page_token or len(results) >= limit:
            break
        time.sleep(0.05)
    return results

def parse_iso8601_duration(duration: str) -> int:
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not m:
        return 0
    h = int(m.group(1) or 0)
    mm = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    return h*3600 + mm*60 + s

def chunked(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]


def get_videos_details(api_key: str, video_ids: List[str]) -> Dict[str, Dict]:
    out = {}
    for batch in chunked(video_ids, 50):
        resp = http_get("videos", {
            "key": api_key,
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(batch)
        })
        for it in resp.get("items", []):
            vid = it["id"]
            dur = it.get("contentDetails", {}).get("duration", "")
            out[vid] = {
                "duration": dur,
                "durationSec": parse_iso8601_duration(dur),
                "viewCount": int(it.get("statistics", {}).get("viewCount", 0) or 0),
                "likeCount": int(it.get("statistics", {}).get("likeCount", 0) or 0),
                "commentCount": int(it.get("statistics", {}).get("commentCount", 0) or 0),
                "categoryId": it.get("snippet", {}).get("categoryId"),
                "tags": it.get("snippet", {}).get("tags", []),
            }
        time.sleep(0.05)
    return out

def save_csv(path: str, rows: List[Dict]):
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def iso_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

# ---------------------- Read API key ----------------------
def read_api_key_from_csv(csv_path: str) -> str:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Không thấy {csv_path}")
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            for cell in row:
                s = (cell or "").strip()
                if not s:
                    continue
                if s.upper() == "API":
                    continue
                return s
    raise RuntimeError("Không tìm thấy API key hợp lệ trong api.csv (chỉ 1 dòng, là API key).")