import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import re
from yt_data_helper import *

class App(tk.Frame):
    def __init__(self):
        super().__init__()
        self.title("YouTube Channel Data")
        self.geometry("700x420")
        self.resizable(True, True)

        self.api_key = tk.StringVar(value="")
        self.max_videos = tk.IntVar(value=5)
        self.status_var = tk.StringVar(value="Sẵn sàng")

        # Layout
        pad = {"padx": 10, "pady": 6}
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Số video tối đa mỗi kênh:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Combobox(
            frm,
            textvariable=self.max_videos,
            values=[str(i) for i in range(1, 51)],
            width=10,
            state="readonly"  # chỉ cho chọn, không nhập tay
        ).grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(frm, text=f"Danh sách kênh (trong {os.path.basename(CONFIG_TXT)}):").grid(row=2, column=0, sticky="w", **pad)
        self.log = tk.Text(frm, height=15, wrap="word", font=("Consolas", 10))
        self.log.grid(row=3, column=0, columnspan=3, sticky="nsew", **pad)

        # Buttons
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=4, column=0, columnspan=3, sticky="e", **pad)
        ttk.Button(btn_frame, text="Chỉnh sửa danh sách", command=self.edit_channels).pack(side="left", padx=5)
        self.run_btn = ttk.Button(btn_frame, text="Cập nhật dữ liệu", command=self.on_run)
        self.run_btn.pack(side="left", padx=5)

        self.status = ttk.Label(self, textvariable=self.status_var, anchor="w")
        self.status.pack(side="bottom", fill="x")

        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(3, weight=1)

        self.after(100, self.auto_prefill)

    # ---------------------- Prefill ----------------------
    def auto_prefill(self):
        try:
            self.load_api()
        except Exception:
            pass
        self.show_channel_list()

    def load_api(self):
        key = read_api_key_from_csv(os.path.join(os.getcwd(), r"manage_channel\api.csv"))
        self.api_key.set(key)

    def show_channel_list(self):
        """Hiển thị danh sách kênh trong log"""
        if not os.path.exists(CONFIG_TXT):
            os.makedirs(os.path.dirname(CONFIG_TXT), exist_ok=True)
            with open(CONFIG_TXT, "w", encoding="utf-8") as f:
                f.write("https://www.youtube.com/@GoogleDevelopers\n")
        with open(CONFIG_TXT, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        self.log.delete("1.0", "end")
        if not lines:
            self.log.insert("end", "(Danh sách kênh trống — nhấn 'Chỉnh sửa' để thêm.)\n")
            return
        self.log.insert("end", "Danh sách kênh cần xử lý:\n")
        for i, line in enumerate(lines, 1):
            self.log.insert("end", f"{i:02d}. {line}\n")
        self.log.see("end")

    def edit_channels(self):
        """Mở cửa sổ chỉnh sửa file config.txt"""
        win = tk.Toplevel(self)
        win.title("Chỉnh sửa danh sách kênh")
        win.geometry("500x500")
        win.grab_set()  # modal
        pad = {"padx": 10, "pady": 6}

        ttk.Label(win, text="Mỗi dòng là 1 kênh (URL / @handle / Channel ID):").pack(anchor="w", **pad)
        text = tk.Text(win, wrap="none", font=("Consolas", 10))
        text.pack(fill="both", expand=True, padx=10, pady=5)

        # Load content
        if os.path.exists(CONFIG_TXT):
            with open(CONFIG_TXT, "r", encoding="utf-8") as f:
                text.insert("1.0", f.read())

        def save_and_close():
            content = text.get("1.0", "end").strip()
            os.makedirs(os.path.dirname(CONFIG_TXT), exist_ok=True)
            with open(CONFIG_TXT, "w", encoding="utf-8") as f:
                f.write(content + "\n" if content else "")
            self.log_write("Đã lưu danh sách kênh.")
            self.show_channel_list()
            win.destroy()

        ttk.Button(win, text="💾 Lưu", command=save_and_close).pack(pady=10)

    # ---------------------- UI helpers ----------------------
    def set_busy(self, busy: bool):
        self.run_btn.configure(state=("disabled" if busy else "normal"))
        self.config(cursor="watch" if busy else "")

    def log_write(self, s: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.insert("end", f"[{ts}] {s}\n")
        self.log.see("end")

    # ---------------------- Main ----------------------
    def on_run(self):
        if not self.api_key.get():
            try:
                self.load_api()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không nạp được API key: {e}")
                return

        if not os.path.exists(CONFIG_TXT):
            messagebox.showwarning("Thiếu file", f"Không tìm thấy file: {CONFIG_TXT}")
            return

        with open(CONFIG_TXT, "r", encoding="utf-8") as f:
            channels = [ln.strip() for ln in f if ln.strip()]

        if not channels:
            messagebox.showwarning("Thiếu dữ liệu", "Danh sách kênh trống, hãy thêm trong 'Chỉnh sửa danh sách'.")
            return

        self.set_busy(True)
        self.status_var.set("Đang chạy...")
        self.log_write(f"Bắt đầu lấy dữ liệu cho {len(channels)} kênh...")

        threading.Thread(target=self.worker_multi, args=(channels,), daemon=True).start()

    def worker_multi(self, channels: list[str]):
        total = len(channels)
        for idx, text in enumerate(channels, start=1):
            self.log_write(f"\n----- ({idx}/{total}) {text} -----")
            try:
                self.fetch_single_channel(text)
            except Exception as e:
                self.log_write(f"LỖI ({text}): {e}")

        self.status_var.set("Hoàn tất tất cả")
        self.set_busy(False)
        messagebox.showinfo("Xong", f"Đã xử lý {total} kênh, kiểm tra file CSV trong thư mục hiện tại.")

    def fetch_single_channel(self, text: str):
        """Lấy dữ liệu 1 kênh"""
        handle = channel_id = username = None
        if text.startswith("@"):
            handle = text
        elif text.startswith("UC"):
            channel_id = text
        elif "youtube.com" in text:
            h, cid, un = parse_channel_from_url(text)
            handle, channel_id, username = h, cid, un
        else:
            username = text

        ch = get_channel_resource(
            api_key=self.api_key.get(),
            handle=handle,
            channel_id=channel_id,
            username=username,
        )

        ch_snip = ch.get("snippet", {})
        ch_stats = ch.get("statistics", {})
        uploads_id = get_uploads_playlist_id(ch)

        self.log_write(f"Kênh: {ch_snip.get('title')} (ID: {ch['id']})")
        self.log_write(f"View: {ch_stats.get('viewCount')} | Video: {ch_stats.get('videoCount')}")

        uploads = list_upload_videos(self.api_key.get(), uploads_id, limit=self.max_videos.get())
        vids = [v["videoId"] for v in uploads]
        self.log_write(f"Đã lấy danh sách {len(vids)} video. Đang lấy chi tiết...")

        detail_map = get_videos_details(self.api_key.get(), vids)

        rows = []
        for v in uploads:
            d = detail_map.get(v["videoId"], {})
            rows.append({
                "channelId": ch["id"],
                "channelTitle": ch_snip.get("title"),
                "videoId": v["videoId"],
                "title": v["title"],
                "publishedAt": v.get("publishedAt"),
                "views": d.get("viewCount"),
                "likes": d.get("likeCount"),
                "comments": d.get("commentCount"),
                "duration": d.get("duration"),
                "durationSec": d.get("durationSec"),
                "categoryId": d.get("categoryId"),
                "tags": "|".join(d.get("tags", [])),
                "position": v.get("position"),
            })

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r'[^0-9A-Za-z_-]+', '_', (ch_snip.get("title") or "channel"))
        fname = f"yt_{safe_title}_{stamp}.csv"
        output_path = os.path.join(os.getcwd(), fname)

        save_csv(output_path, rows)
        self.log_write(f"Đã lưu CSV: {output_path}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
