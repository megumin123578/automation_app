
import time
from helper import *

class ConcatApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ghép Short Tự Động")
        self.geometry("1000x480")  
        self.minsize(900,580)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Accent.TButton", foreground="blue")

        self.start_time = None
        self.elapsed_times = []

        # State
        self.input_folder = tk.StringVar()
        self.save_folder = tk.StringVar()
        self.bgm_folder = tk.StringVar()
        self.group_size_var = tk.IntVar(value=6)
        self.bgm_volume_var = tk.DoubleVar(value=0.5)
        self.limit_videos_var = tk.IntVar(value=0)

        self.mp3_list: list[str] = []
        self.total_mp4 = tk.StringVar(value="0")
        self.num_groups = tk.StringVar(value="0")
        self.groups_done = tk.StringVar(value="0")
        self.status_var = tk.StringVar(value="Idle")
        self.last_output_var = tk.StringVar(value="(chưa có)")

        self.groups: list[list[str]] = []
        self.stop_flag = threading.Event()
        self.worker: threading.Thread | None = None
        self.log_q: queue.Queue[str] = queue.Queue()

        self._build_ui()
        self._layout()

        self.load_config()
        if self.input_folder.get():
            self.reload_groups()

    # ================= UI =================
    def _build_ui(self):
        self.frm_top = ttk.LabelFrame(self, text="⚙️ Cấu hình", padding=10)

        # ===== Dòng 1: Tham số cơ bản =====
        ttk.Label(self.frm_top, text="Videos/group:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.combo_group_size = ttk.Combobox(
            self.frm_top, textvariable=self.group_size_var,
            values=list(range(2, 101)), width=6, state="readonly"
        )
        self.combo_group_size.grid(row=0, column=1, sticky="w", pady=4)
        self.combo_group_size.bind("<<ComboboxSelected>>", self._on_group_size_change)

        ttk.Label(self.frm_top, text="Total videos to export:").grid(row=0, column=2, sticky="e", padx=4)
        #chọn lượng video
        limit_display = ["All"] + [str(i) for i in range(1, 101)]
        self.combo_limit_videos = ttk.Combobox(
            self.frm_top, width=8, state="readonly",
            textvariable=tk.StringVar()
        )
        self.combo_limit_videos['values'] = limit_display
        self.combo_limit_videos.current(0) 


        def on_limit_change(event=None):
            val = self.combo_limit_videos.get()
            if val == "Ghép hết":
                self.limit_videos_var.set(0)
            else:
                self.limit_videos_var.set(int(val))

        self.combo_limit_videos.bind("<<ComboboxSelected>>", on_limit_change)
        self.combo_limit_videos.grid(row=0, column=3, sticky="w")


        ttk.Label(self.frm_top, text="Volume:").grid(row=0, column=4, sticky="e", padx=4)
        self.slider_volume = ttk.Scale(self.frm_top, from_=0.0, to=1.0, orient="horizontal",
                                       variable=self.bgm_volume_var, length=120)
        self.slider_volume.grid(row=0, column=5, sticky="w", padx=2)

        self.lbl_volume = ttk.Label(self.frm_top, width=5)
        self.lbl_volume.grid(row=0, column=6, sticky="w")

        self.frm_top.columnconfigure(6, weight=1)

        #reload button
        self.btn_reload = ttk.Button(self.frm_top, text="↻",width=3, command=self.reload_groups, style="Accent.TButton")
        self.btn_reload.grid(row=0, column=7, sticky="w", padx=8)
        
        # cập nhật label âm lượng
        self.bgm_volume_var.trace_add("write", self._update_volume_label)

        # ===== chọn thư mục =====
        self._add_folder_row("📁 Source folder:", self.input_folder, 1, reload=True)
        self._add_folder_row("💾 Save folder:", self.save_folder, 2)
        self._add_folder_row("🎵 Music folder:", self.bgm_folder, 3, bgm=True)

        # ===== các nút thao tác =====
        self.frm_buttons = ttk.Frame(self.frm_top)
        self.btn_concat = ttk.Button(self.frm_buttons, text="▶ Start", command=self.start_concat)
        self.btn_stop = ttk.Button(self.frm_buttons, text="■ Stop", command=self.stop_concat, state=tk.DISABLED)
        self.btn_open = ttk.Button(self.frm_buttons, text="📂 Open save folder", command=self.open_output_folder)
        self.btn_clear = ttk.Button(self.frm_buttons, text="🗑 Delete log", command=self.clear_log)

        self.progress = ttk.Progressbar(self.frm_buttons, orient="horizontal", mode="determinate", length=280)
        self.lbl_status = ttk.Label(self.frm_buttons, textvariable=self.status_var, width=15, anchor="w")

        for i, btn in enumerate([self.btn_concat, self.btn_stop, self.btn_open, self.btn_clear]):
            btn.grid(row=0, column=i, padx=6, pady=6)
        self.progress.grid(row=0, column=4, sticky="we", padx=6)
        self.lbl_status.grid(row=0, column=5, sticky="w", padx=6)
        self.frm_buttons.grid(row=5, column=0, columnspan=7, pady=(6, 4), sticky="we")
        


        # ===== Log + Thống kê =====
        self.frm_logstats = ttk.LabelFrame(self, text="📜 Log", padding=8)

        # --- Khung thống kê ---
        stats_frame = ttk.Frame(self.frm_logstats)
        stats_frame.pack(fill="x", pady=(0, 6))

        ttk.Label(stats_frame, text="Total videos remain:").grid(row=0, column=0, sticky="e", padx=6)
        ttk.Label(stats_frame, textvariable=self.total_mp4).grid(row=0, column=1, sticky="w")

        ttk.Label(stats_frame, text="Groups remain:").grid(row=0, column=2, sticky="e", padx=6)
        ttk.Label(stats_frame, textvariable=self.num_groups).grid(row=0, column=3, sticky="w")

        ttk.Label(stats_frame, text="Done:").grid(row=0, column=4, sticky="e", padx=6)
        ttk.Label(stats_frame, textvariable=self.groups_done).grid(row=0, column=5, sticky="w")

        # --- Khung log ---
        log_frame = ttk.Frame(self.frm_logstats)
        log_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self.txt_log = tk.Text(
            log_frame,
            height=12,
            wrap="word",
            state="disabled",
            bg="#1e1e1e",
            fg="#dcdcdc",
            font=("Consolas", 12),
            yscrollcommand=scrollbar.set
        )
        self.txt_log.pack(fill="both", expand=True)
        scrollbar.config(command=self.txt_log.yview)

        # Tag cho link
        self.txt_log.tag_configure("link", foreground="#4ea3ff", underline=True)



    def _add_folder_row(self, label, var, row, reload=False, bgm=False):
        ttk.Label(self.frm_top, text=label).grid(row=row, column=0, sticky="e", padx=4, pady=3)
        entry = ttk.Entry(self.frm_top, textvariable=var, width=60)
        entry.grid(row=row, column=1, columnspan=4, sticky="we", padx=4)
        btn = ttk.Button(self.frm_top, text="Select folder", width=15,
                         command=lambda: self._choose_folder(var, reload=reload, bgm=bgm))
        btn.grid(row=row, column=5, columnspan=2, sticky="w", padx=4)

    def _layout(self):
        self.frm_top.pack(fill="x", padx=10, pady=8)
        self.frm_logstats.pack(fill="both", expand=True, padx=10, pady=(4, 10))
    
    def _update_volume_label(self, *args):
        val = self.bgm_volume_var.get()
        self.lbl_volume.config(text=f"{val * 100:.0f}")

    def _append_log(self, text: str):
    
        self.txt_log.configure(state="normal")

        if text.startswith("Đã ghép xong: "):
            path = text.replace("Đã ghép xong: ", "").strip()
            tag_name = f"link_{hash(path)}"
            self.txt_log.insert("end", "Đã ghép xong: ")
            self.txt_log.insert("end", path + "\n", tag_name)
            # Style
            self.txt_log.tag_configure(tag_name, foreground="#03fc13", underline=True)
            self.txt_log.tag_bind(tag_name, "<Enter>", lambda e: self.txt_log.config(cursor="hand2"))
            self.txt_log.tag_bind(tag_name, "<Leave>", lambda e: self.txt_log.config(cursor=""))
            self.txt_log.tag_bind(tag_name, "<Button-1>", lambda e, p=path: self._open_video_path(p))
        else:
            self.txt_log.insert("end", text + "\n")

        self.txt_log.see("end")  #auto scroll
        self.txt_log.configure(state="disabled")

    def _open_video_path(self, path: str): #open video when click
        if os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as e:
                messagebox.showerror("Lỗi mở video", f"Không thể mở:\n{path}\n\n{e}")
        else:
            messagebox.showwarning("Không tìm thấy", f"File không tồn tại:\n{path}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.input_folder.set(cfg.get("input_folder", ""))
                self.save_folder.set(cfg.get("save_folder", ""))
                self.bgm_folder.set(cfg.get("bgm_folder", ""))
                self.group_size_var.set(cfg.get("group_size", 2))
                self.bgm_volume_var.set(cfg.get("bgm_volume", 0.5))
                if self.bgm_folder.get():
                    self.mp3_list = list_all_mp3_files(self.bgm_folder.get())
            except Exception as e:
                messagebox.showwarning("Config", f"Lỗi đọc config: {e}")

    def save_config(self):
        cfg = {
            "input_folder": self.input_folder.get(),
            "save_folder": self.save_folder.get(),
            "bgm_folder": self.bgm_folder.get(),
            "group_size": self.group_size_var.get(),
            "bgm_volume": self.bgm_volume_var.get(),
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Config", f"Lỗi lưu config: {e}")

    def reload_groups(self):
        folder = self.input_folder.get()
        if not folder or not os.path.isdir(folder):
            return
        try:
            all_videos = list_all_mp4_files(folder)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Đọc video lỗi: {e}")
            return

        # loại bỏ video đã dùng trong log
        used_videos = set()
        log_dir = os.path.abspath("log")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "log.txt")

        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            for p in data.get("inputs", []):
                                used_videos.add(os.path.abspath(p))
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                messagebox.showwarning("Log", f"Lỗi đọc log: {e}")

        # bỏ video đã dùng
        all_videos = [v for v in all_videos if os.path.abspath(v) not in used_videos]

        gsize = self.group_size_var.get() or 6
        all_groups = get_all_random_video_groups(all_videos, group_size=gsize)

        # Giới hạn số lượng nhóm cần ghép
        limit_groups = self.limit_videos_var.get()
        if limit_groups > 0:
            self.groups = all_groups[:limit_groups]
        else:
            self.groups = all_groups

        self.total_mp4.set(str(len(all_videos)))
        self.num_groups.set(str(len(self.groups)))
        self.save_config()


    
    def _choose_folder(self, var: tk.StringVar, reload=False, bgm=False):
        folder = filedialog.askdirectory(title="Select folder")
        if folder:
            var.set(folder)
            if reload:
                self.reload_groups()
            if bgm:
                try:
                    self.mp3_list = list_all_mp3_files(folder)
                    messagebox.showinfo("OK", f"Đã load {len(self.mp3_list)} file mp3.")
                except Exception as e:
                    messagebox.showerror("Lỗi", f"Không đọc được mp3: {e}")
            self.save_config()   # lưu lại khi chọn mới

    def start_concat(self):
        self.start_time = time.time()
        self.elapsed_times.clear()
        if self.worker and self.worker.is_alive():
            return messagebox.showinfo("Đang chạy", "Tiến trình đang chạy.")
        if not self.groups:
            return messagebox.showwarning("Đã chạy hết toàn bộ", "Hãy xóa log để gen lại.")
        out_dir = self.save_folder.get()
        if not out_dir:
            return messagebox.showwarning("Thiếu thư mục lưu", "Chọn thư mục lưu")
        os.makedirs(out_dir, exist_ok=True)

        
        
        limit_groups = self.limit_videos_var.get()
        todo_groups = self.groups
        if limit_groups > 0:
            todo_groups = self.groups[:limit_groups]

        self.stop_flag.clear()
        self.btn_concat.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_var.set("Working...")

        self.progress['maximum'] = len(todo_groups)
        self.progress['value'] = 0
        self.groups_done.set("0")

        self.worker = threading.Thread(target=self._do_concat_worker, args=(todo_groups, out_dir), daemon=True)
        self.worker.start()
        self.after(200, self._poll_worker)

    def stop_concat(self):
        self.stop_flag.set()

    def _do_concat_worker(self, todo: list[list[str]], out_dir: str):
        log_dir = os.path.abspath("log")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "log.txt")

        with open(log_path, "a", encoding="utf-8") as f_log:
            for group in todo:
                if self.stop_flag.is_set():
                    break
                start_group_time = time.time()
                temp = "temp.mp4"
                try:
                    auto_concat(group, temp)
                    bg_audio = random.choice(self.mp3_list) if self.mp3_list else None
                    if bg_audio and os.path.isfile(bg_audio):
                        output = mix_audio_with_bgm_ffmpeg(temp, bg_audio, out_dir, self.bgm_volume_var.get())
                    else:
                        output = get_next_output_filename(out_dir)
                        shutil.copy2(temp, output)
                        bg_audio = None

                    # ghi log JSON
                    log_entry = {
                        "output": os.path.abspath(output),
                        "inputs": [os.path.abspath(p) for p in group],
                        "bgm": os.path.abspath(bg_audio) if bg_audio else None
                    }
                    f_log.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                    self.after(0, lambda path=output: self.last_output_var.set(path))
                    self.after(0, lambda path=output: self._append_log(f"Đã ghép xong: {path}"))


                except Exception as e:
                    log_entry = {
                        "error": str(e),
                        "inputs": [os.path.abspath(p) for p in group]
                    }
                    f_log.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

                finally:
                    if os.path.exists(temp):
                        os.remove(temp)

                f_log.flush()
                elapsed = time.time() - start_group_time
                self.elapsed_times.append(elapsed)
                self._enqueue(self._update_progress)


    def _update_progress(self):
        self.progress['value'] += 1
        done = self.progress['value']
        total = self.progress['maximum']
        percent = (done / total) * 100

        avg_time = sum(self.elapsed_times) / len(self.elapsed_times) if self.elapsed_times else 0
        remaining_groups = total - done
        eta_seconds = avg_time * remaining_groups
        elapsed_total = time.time() - self.start_time if self.start_time else 0

        # định dạng thời gian
        def fmt_time(t):
            m, s = divmod(int(t), 60)
            return f"{m}m{s}s" if m else f"{s}s"

        eta_str = fmt_time(eta_seconds)
        elapsed_str = fmt_time(elapsed_total)
        avg_str = f"{avg_time:.1f}s/nhóm" if avg_time else "--"

        # ghi log thay vì hiển thị ở label
        log_text = f"[Tiến trình] {percent:.1f}% | Còn lại: {eta_str} | Đã chạy: {elapsed_str} | TB: {avg_str}"
        self._append_log(log_text)

        self.groups_done.set(str(done))



    def _on_done(self):
        self.btn_concat.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_var.set("Hoàn thành" if not self.stop_flag.is_set() else "Đã dừng")
        self.reload_groups()

    def _poll_worker(self):
        if self.worker and self.worker.is_alive():
            self.after(200, self._poll_worker)
        else:
            self._on_done()

    def _enqueue(self, fn):
        self.after(0, fn)

    def open_output_folder(self):
        path = self.save_folder.get()
        if path and os.path.isdir(path):
            os.startfile(path)


    def clear_log(self):
        log_dir = os.path.abspath("log")
        log_path = os.path.join(log_dir, "log.txt")

        if not os.path.exists(log_path):
            messagebox.showinfo("Xóa log", "Không có file log để xóa.")
            return

        confirm = messagebox.askyesno("Xóa log", "Bạn có chắc muốn xóa toàn bộ dữ liệu log?")
        if confirm:
            try:
                os.remove(log_path)
                messagebox.showinfo("Xóa log", "Đã xóa dữ liệu log.")
                # Reload lại nhóm vì có thể còn video
                self.reload_groups()
            except Exception as e:
                messagebox.showerror("Xóa log", f"Lỗi khi xóa log: {e}")

    def _on_group_size_change(self, event=None):
        try:
            gsize = int(self.combo_group_size.get())
            self.group_size_var.set(gsize)
            self.reload_groups()
        except ValueError:
            pass

if __name__ == '__main__':
    ConcatApp().mainloop()
