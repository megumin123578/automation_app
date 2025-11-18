from .helper import *

class ConcatPage(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self._loading = False

        # Configure style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), foreground="#ffffff", background="#4CAF50", padding=6)
        style.configure("Stop.TButton", font=("Segoe UI", 10, "bold"), foreground="#ffffff", background="#F44336", padding=6)
        style.configure("Secondary.TButton", font=("Segoe UI", 10), foreground="#ffffff", background="#2196F3", padding=6)
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TEntry", font=("Segoe UI", 10))
        style.configure("TCombobox", font=("Segoe UI", 10))

        style.configure("NvencOn.TButton", font=("Segoe UI", 10, "bold"), foreground="#ffffff", background="#4CAF50")
        style.map("NvencOn.TButton", background=[("active", "#45a049")])

        style.configure("NvencOff.TButton", font=("Segoe UI", 10, "bold"), foreground="#ffffff", background="#d32f2f")
        style.map("NvencOff.TButton", background=[("active", "#b71c1c")])
        style.configure(
            "Advanced.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground="#ffffff",
            background="#D13BFF",
            padding=6,
        )
        style.map(
            "Advanced.TButton",
            background=[("active", "#8BC34A")]
        )

        style.configure(
            "Advanced.On.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground="#ffffff",
            background="#8BC34A",   
            padding=6,
        )
        style.map(
            "Advanced.On.TButton",
            background=[("active", "#D13BFF")]
        )


        self.start_time = None
        self.elapsed_times = []

        # State
        self.input_folder = tk.StringVar()
        self.save_folder = tk.StringVar()
        self.bgm_folder = tk.StringVar()
        self.group_size_var = tk.IntVar(value=6)
        self.bgm_volume_var = tk.DoubleVar(value=0.5)
        self.video_volume_var = tk.DoubleVar(value=0.2)
        self.main_video_volume_var = tk.DoubleVar(value=1.0)
        self.limit_videos_var = tk.IntVar(value=0)
        
        self.concat_mode = tk.StringVar(value="Concat with music background")

        # ==== Video settings ====
        self.resolution_var = tk.StringVar(value="1080x1920")
        self.fps_var = tk.IntVar(value=60)
        self.use_nvenc_var = tk.BooleanVar(value=True)
        self.cq_var = tk.IntVar(value=23)
        self.v_bitrate_var = tk.StringVar(value="12M")
        self.a_bitrate_var = tk.StringVar(value="160k")
        self.nvenc_preset_var = tk.StringVar(value="p4")

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
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.selected_channel = tk.StringVar()

        self._advanced = False
        self.time_limit_min_var = tk.StringVar(value="0")
        self.time_limit_sec_var = tk.StringVar(value="0")
        self._dur_cache: dict[str, float] = {}

        self.outro_mode_var = tk.StringVar(value="By group count")
        self.outro_duration_var = tk.IntVar(value=15)

        self._tag_id = 0

        self._build_ui()
        self._layout()
        self.bind("<Delete>", self._on_global_delete) 

        self.load_last_channel()
        if self.input_folder.get():
            self.reload_groups()

    def _build_ui(self):
        self.frm_top = ttk.LabelFrame(self, text="⚙️ Configuration", padding=(10, 10))
        # Channel selection + Concat mode cùng hàng
        channel_frame = ttk.Frame(self.frm_top)
        channel_frame.grid(row=0, column=0, columnspan=4, sticky="we", pady=5)
        for c in (1, 2, 4, 6, 7):
            channel_frame.grid_columnconfigure(c, weight=1)

        ttk.Label(channel_frame, text="Profile:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="e", padx=5)
        self.combo_channel = ttk.Combobox(
            channel_frame, textvariable=self.selected_channel, values=self._list_channels(),
            width=25, state="readonly", font=("Segoe UI", 10)
        )
        self.combo_channel.grid(row=0, column=1, sticky="ew", padx=5)
        self.combo_channel.bind("<<ComboboxSelected>>", self._on_channel_change)
        self._add_right_click_menu(self.combo_channel,[("🗑 Delete Channel", self._clear_channel_selection),])

        # --- Input để nhập tên channel mới ---
        self.entry_new_channel = ttk.Entry(channel_frame, width=20, font=("Segoe UI", 10))
        self.entry_new_channel.grid(row=0, column=2, sticky="ew", padx=5)

        def on_focus_in(e):
            if self.entry_new_channel.get() == "Enter channel name...":
                self.entry_new_channel.delete(0, "end")

        def on_focus_out(e):
            if not self.entry_new_channel.get().strip():
                self.entry_new_channel.insert(0, "Enter channel name...")

        self.entry_new_channel.insert(0, "Enter channel name...")
        self.entry_new_channel.bind("<FocusIn>", on_focus_in)
        self.entry_new_channel.bind("<FocusOut>", on_focus_out)
        self.entry_new_channel.bind("<Return>", self._create_channel_from_entry)

        # --- Concat mode ngay cạnh ---
        ttk.Label(channel_frame, text="Concat mode:", font=("Segoe UI", 10, "bold")).grid(row=0, column=3, sticky="e", padx=(15,5))
        self.combo_mode = ttk.Combobox(
            channel_frame, textvariable=self.concat_mode, state="readonly", width=60,justify='center', font=("Segoe UI", 10),
            values=[
                "Concat with music background",
                "Concat with outro music",
                "Normal concat (no music)",
                "Concat and Reverse",
                "Concat with time limit",
                "Loop",
            ]
        )
        self.combo_mode.grid(row=0, column=4, sticky="ew", padx=5)
        self.combo_mode.current(0)
        self.combo_mode.bind("<<ComboboxSelected>>", lambda e: (self.save_channel_config(), self._update_mode_visibility(), self.reload_groups()))

        self.btn_advanced = ttk.Button(
            channel_frame, text="Advanced ▸",style="Advanced.TButton",
            command=self._toggle_advanced
        )
        self.btn_advanced.grid(row=0, column=8, sticky="w", padx=8)

        # Parameters frame
        param_frame = ttk.Frame(self.frm_top)
        param_frame.grid(row=1, column=0, columnspan=4, sticky="we", pady=5)
        param_frame.grid_columnconfigure(5, weight=1)   
        param_frame.grid_columnconfigure(1, weight=0)  

        self.lbl_group_size = ttk.Label(param_frame, text="Videos per Group:", font=("Segoe UI", 10, "bold"))
        self.lbl_group_size.grid(row=0, column=0, sticky="e", padx=5)
        self.combo_group_size = ttk.Combobox(
            param_frame, textvariable=self.group_size_var, values=list(range(2, 101)),
            width=6, state="readonly", font=("Segoe UI", 10)
        )
        self.combo_group_size.grid(row=0, column=1, sticky="w", padx=5)
        self.combo_group_size.bind("<<ComboboxSelected>>", self._on_group_size_change)

        ttk.Label(param_frame, text="Total Videos to Export:", font=("Segoe UI", 10, "bold"))\
            .grid(row=0, column=2, sticky="e", padx=(10, 4))
        
        limit_display = ["All"] + [str(i) for i in range(1, 101)]
        self.limit_videos_display = tk.StringVar(value="All")  # StringVar để hiển thị
        self.combo_limit_videos = ttk.Combobox(
            param_frame, width=8, state="readonly",
            textvariable=self.limit_videos_display, values=limit_display
        )
        self.combo_limit_videos.grid(row=0, column=3, sticky="w", padx=(0, 5))
        self.combo_limit_videos.set("All")  # hiển thị "All"

        def on_limit_change(event=None):
            val = self.combo_limit_videos.get()
            self.limit_videos_var.set(0 if val == "All" else int(val))
            self.reload_groups()
            self.save_channel_config()
        self.combo_limit_videos.bind("<<ComboboxSelected>>", on_limit_change)
        self.combo_limit_videos.grid(row=0, column=3, sticky="ew", padx=5)

        # --- Time limit (minutes) - chỉ hiện ở "Concat with time limit"
        self.lbl_time_limit = ttk.Label(param_frame, text="Time limit (min):", font=("Segoe UI", 10, "bold"))
        self.lbl_time_limit.grid(row=0, column=4, sticky="e", padx=(15,5))

        self.combo_time_limit = ttk.Combobox(
            param_frame, textvariable=self.time_limit_min_var, state="normal",
            width=6, values=list(range(0, 1000))
        )
        self.combo_time_limit.grid(row=0, column=5, sticky="w", padx=5)
        self.lbl_time_limit.grid_configure(column=7)
        self.combo_time_limit.grid_configure(column=8)

        #---- Second selection ------
        self.combo_time_limit_sec = ttk.Combobox(
            param_frame, textvariable=self.time_limit_sec_var, state='normal',
            width=6, values=list(range(0,60))
        )
        self.combo_time_limit_sec.grid(row=0, column=10, sticky='w', padx=5)

        def select_all_text(event):
            event.widget.selection_range(0, 'end')
            return 'break'  # tránh behavior mặc định

        self.combo_time_limit.bind("<FocusIn>", select_all_text)
        self.combo_time_limit_sec.bind("<FocusIn>", select_all_text)
        self.combo_time_limit.bind("<<ComboboxSelected>>", lambda e: self.save_channel_config())
        self.combo_time_limit_sec.bind("<<ComboboxSelected>>", lambda e: self.save_channel_config())

        def _commit_time_limit(event=None):
            if getattr(self, "_loading", False):
                return
            m = (self.time_limit_min_var.get() or "").strip()
            s = (self.time_limit_sec_var.get() or "").strip()

            m = "0" if not m.isdigit() else m
            s = "0" if not s.isdigit() else s

            m_i = min(int(m), 999)
            s_i = min(int(s), 59)

            self.time_limit_min_var.set(str(m_i))
            self.time_limit_sec_var.set(str(s_i))
            self.save_channel_config()
        
        self.combo_time_limit.bind("<FocusOut>", _commit_time_limit)
        self.combo_time_limit_sec.bind("<FocusOut>", _commit_time_limit)
        self.combo_time_limit.bind("<Return>", _commit_time_limit)
        self.combo_time_limit_sec.bind("<Return>", _commit_time_limit)
        self.time_limit_min_var.trace_add("write", self._on_time_limit_var_changed)
        self.time_limit_sec_var.trace_add("write", self._on_time_limit_var_changed)

        self.slider_volume = ttk.Scale(param_frame, from_=0.0, to=1.0, orient="horizontal", variable=self.bgm_volume_var, length=120)
        self.slider_volume.grid(row=0, column=5, sticky="ew", padx=5)
        self.lbl_volume = ttk.Label(param_frame, text=f"{self.bgm_volume_var.get() * 100:.0f}%", width=5)
        self.lbl_volume.grid(row=0, column=6, sticky="ew", padx=5)

        # --- Main Video Volume Slider ---
        self.lbl_main_video_vol = ttk.Label(param_frame, text="Video Volume:", font=("Segoe UI", 10, "bold"))
        self.lbl_main_video_vol.grid(row=2, column=4, sticky="e", padx=5)

        self.slider_main_video_vol = ttk.Scale(
            param_frame, from_=0.0, to=2.0, orient="horizontal", variable=self.main_video_volume_var, length=120
        )
        self.slider_main_video_vol.grid(row=2, column=5, sticky="ew", padx=5)

        self.lbl_main_video_vol_value = ttk.Label(param_frame, text=f"{self.main_video_volume_var.get() * 100:.0f}%", width=5)
        self.lbl_main_video_vol_value.grid(row=2, column=6, sticky="ew", padx=5)

        # --- Video Volume Slider ---
        self.lbl_video_vol = ttk.Label(param_frame, text="Outro Volume:", font=("Segoe UI", 10, "bold"))
        self.lbl_video_vol.grid(row=1, column=4, sticky="e", padx=5)

        self.slider_video_vol = ttk.Scale(
            param_frame, from_=0.0, to=1.0, orient="horizontal", variable=self.video_volume_var, length=120
        )
        self.slider_video_vol.grid(row=1, column=5, sticky="ew", padx=5)

        self.lbl_video_vol_value = ttk.Label(param_frame, text=f"{self.video_volume_var.get() * 100:.0f}%", width=5)
        self.lbl_video_vol_value.grid(row=1, column=6, sticky="w", padx=5)

        # --- Outro Length (seconds) ---
        self.lbl_outro_dur = ttk.Label(param_frame, text="Outro length (s):", font=("Segoe UI", 10, "bold"))
        self.lbl_outro_dur.grid(row=1, column=7, sticky="e", padx=5)

        self.cbo_outro_dur = ttk.Combobox(
            param_frame, textvariable=self.outro_duration_var, state="readonly", width=6,
            values= [5, 10, 12, 15, 20, 30, 45, 60, 90, 120]
        )
        self.cbo_outro_dur.grid(row=1, column=8, sticky="w", padx=5)
        # lưu config khi đổi lựa chọn
        self.cbo_outro_dur.bind("<<ComboboxSelected>>", lambda e: self.save_channel_config())

        self.video_volume_var.trace_add("write", self._update_video_volume_label)
        self.bgm_volume_var.trace_add("write", self._update_volume_label)

        self.lbl_bgm_text = ttk.Label(param_frame, text="BGM Volume:", font=("Segoe UI", 10, "bold"))
        self.lbl_bgm_text.grid(row=0, column=4, sticky="e", padx=5)

        # --- Outro Mode ---
        self.lbl_outro_mode = ttk.Label(channel_frame, text="Outro mode:", font=("Segoe UI", 10, "bold"))
        self.lbl_outro_mode.grid(row=0, column=5, sticky="e", padx=(10, 5))
        self.combo_outro_mode = ttk.Combobox(
            channel_frame,
            textvariable=self.outro_mode_var,
            state="readonly",
            width=15,
            values=["By group count", "By time limit"]
        )
        self.combo_outro_mode.grid(row=0, column=6, sticky="ew", padx=5)
        self.combo_outro_mode.bind("<<ComboboxSelected>>", lambda e: (self.save_channel_config(), self._update_mode_visibility()))

        # self.btn_reload = ttk.Button(param_frame, text="↻ Reload", style="Accent.TButton", command=self.reload_groups)
        # self.btn_reload.grid(row=0, column=7, sticky="w", padx=5)

        # --- Video Settings Frame ---
        self.video_frame = ttk.LabelFrame(self.frm_top, text="🎬 Video Settings", padding=(10,5))
        self.video_frame.grid(row=2, column=0, columnspan=4, sticky="we", pady=5)
        for c in (1,3,5,6):
            self.video_frame.grid_columnconfigure(c, weight=1)

        # Preset lists
        cq_values = [10, 12, 15, 17, 18, 20, 21, 22, 23, 24, 25, 28, 30, 32, 35, 40]
        v_bitrate_values = ["4M", "6M", "8M", "10M", "12M", "15M", "20M", "25M", "30M","35M","45M","55M","68M","85M","100M","120M"]
        a_bitrate_values = ["96k", "128k", "160k", "192k", "256k", "320k"]

        # Hàng 1
        ttk.Label(self.video_frame, text="Resolution:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="e", padx=5)
        ttk.Combobox(
            self.video_frame, textvariable=self.resolution_var, width=10, state="readonly",
            values=[
                "1080x1920","1920x1080","720x1280","1280x720",
                "1440x2560","2560x1440",     # 2K
                "2160x3840","3840x2160"      # 4K
            ]
        ).grid(row=0, column=1, sticky="w")

        ttk.Label(self.video_frame, text="FPS:", font=("Segoe UI", 10, "bold")).grid(row=0, column=2, sticky="e", padx=5)
        ttk.Combobox(self.video_frame, textvariable=self.fps_var, width=5, state="readonly",
                    values=[24, 30, 60, 120]).grid(row=0, column=3, sticky="w")

        ttk.Label(self.video_frame, text="CQ / CRF:", font=("Segoe UI", 10, "bold")).grid(row=0, column=4, sticky="e", padx=5)
        self.cbo_cq = ttk.Combobox(self.video_frame, textvariable=self.cq_var, width=5, state="readonly", values=cq_values)
        self.cbo_cq.grid(row=0, column=5, sticky="w")

        self.btn_nvenc = ttk.Button(
            self.video_frame,
            text="🟢 NVENC ON" if self.use_nvenc_var.get() else "🔴 NVENC OFF",
            style="Secondary.TButton",
            command=self._toggle_nvenc
        )
        self.btn_nvenc.grid(row=0, column=6, padx=(10,0), sticky="w")
        self.use_nvenc_var.trace_add("write", self._update_nvenc_button)

        # Hàng 2
        ttk.Label(self.video_frame, text="Video Bitrate:", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="e", padx=5)
        self.cbo_vbit = ttk.Combobox(self.video_frame, textvariable=self.v_bitrate_var, width=8, state="readonly", values=v_bitrate_values)
        self.cbo_vbit.grid(row=1, column=1, sticky="w")

        ttk.Label(self.video_frame, text="Audio Bitrate:", font=("Segoe UI", 10, "bold")).grid(row=1, column=2, sticky="e", padx=5)
        self.cbo_abit = ttk.Combobox(self.video_frame, textvariable=self.a_bitrate_var, width=8, state="readonly", values=a_bitrate_values)
        self.cbo_abit.grid(row=1, column=3, sticky="w")

        ttk.Label(self.video_frame, text="Preset:", font=("Segoe UI", 10, "bold")).grid(row=1, column=4, sticky="e", padx=5)
        ttk.Combobox(self.video_frame, textvariable=self.nvenc_preset_var, width=6, state="readonly",
                    values=["p1","p2","p3","p4","p5","p6","p7","medium"]).grid(row=1, column=5, sticky="w")

        # ẨN mặc định (giữ logic Advanced)
        self.video_frame.grid_remove()

        # Đảm bảo giá trị hiện tại được chọn ngay cả khi không nằm trong preset
        if self.cq_var.get() not in cq_values:
            self.cbo_cq["values"] = [self.cq_var.get()] + cq_values
        if self.v_bitrate_var.get() and self.v_bitrate_var.get() not in v_bitrate_values:
            self.cbo_vbit["values"] = [self.v_bitrate_var.get()] + v_bitrate_values
        if self.a_bitrate_var.get() and self.a_bitrate_var.get() not in a_bitrate_values:
            self.cbo_abit["values"] = [self.a_bitrate_var.get()] + a_bitrate_values

        # Folder selection
        folder_frame = ttk.LabelFrame(self.frm_top, text="📁 Folders", padding=(10, 5))
        folder_frame.grid(row=3, column=0, columnspan=4, sticky="we", pady=5)
        folder_frame.grid_columnconfigure(1, weight=1)
        folder_frame.grid_columnconfigure(2, weight=1)
        self._add_folder_row("Source Folder:", self.input_folder, 0, folder_frame, reload=True)
        self._add_folder_row("Save Folder:", self.save_folder, 1, folder_frame)
        self.music_widgets = self._add_folder_row("Music Folder:", self.bgm_folder, 2, folder_frame, bgm=True)

        # Action buttons and progress
        action_frame = ttk.Frame(self.frm_top)
        action_frame.grid(row=4, column=0, columnspan=4, sticky="we", pady=10)
        action_frame.grid_columnconfigure(4, weight=1)
        action_frame.grid_columnconfigure(5, weight=1)
        self.btn_concat = ttk.Button(action_frame, text="▶ Start", style="Accent.TButton", command=self.start_concat)
        self.btn_concat.grid(row=0, column=0, padx=5)
        self.btn_stop = ttk.Button(action_frame, text="■ Stop", style="Stop.TButton", command=self.stop_concat, state=tk.DISABLED)
        self.btn_stop.grid(row=0, column=1, padx=5)
        self.btn_open = ttk.Button(action_frame, text="📂 Open Folder", style="Secondary.TButton", command=self.open_output_folder)
        self.btn_open.grid(row=0, column=2, padx=5)
        self.btn_clear = ttk.Button(action_frame, text="🗑 Clear Log", style="Secondary.TButton", command=self.clear_log)
        self.btn_clear.grid(row=0, column=3, padx=5)
        
        self.progress = ttk.Progressbar(action_frame, orient="horizontal", mode="determinate", length=300)
        self.progress.grid(row=0, column=4, padx=5, sticky="ew")

        self.progress_infor_var = tk.StringVar(value='')
        self.lbl_progress_info = ttk.Label(
            action_frame, textvariable=self.progress_infor_var, font=("Segoe UI",9, "italic")
        )
        self.lbl_progress_info.grid(row=1, column=4, columnspan=2, padx=5, pady=(3,0), sticky='w')
        self.lbl_status = ttk.Label(action_frame, textvariable=self.status_var, font=("Segoe UI", 10, "italic"))
        self.lbl_status.grid(row=0, column=5, padx=5, sticky="ew")

        #Job progress
        self.job_info_var = tk.StringVar(value='')
        self.progress_job = ttk.Progressbar(action_frame, orient="horizontal", mode='determinate', length=300, maximum=100, value=0)
        self.progress_job.grid(row=2, column=4, padx=5, sticky='ew')

        self.lbl_job_info = ttk.Label(action_frame, textvariable=self.job_info_var, font=("Segoe UI",9, "italic"))
        self.lbl_job_info.grid(row=3, column=4, columnspan=2, padx=5, pady=(3,0), sticky='w')

        self.progress_job.grid_remove()
        self.lbl_job_info.grid_remove()

        # Log and stats frame
        self.frm_logstats = ttk.LabelFrame(self, text="📜 Log & Statistics", padding=(10, 10))
        stats_frame = ttk.Frame(self.frm_logstats)
        stats_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(stats_frame, text="Total Videos:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="e", padx=5)
        ttk.Label(stats_frame, textvariable=self.total_mp4).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(stats_frame, text="Groups Remaining:", font=("Segoe UI", 10, "bold")).grid(row=0, column=2, sticky="e", padx=5)
        ttk.Label(stats_frame, textvariable=self.num_groups).grid(row=0, column=3, sticky="w", padx=5)
        ttk.Label(stats_frame, text="Groups Done:", font=("Segoe UI", 10, "bold")).grid(row=0, column=4, sticky="e", padx=5)
        ttk.Label(stats_frame, textvariable=self.groups_done).grid(row=0, column=5, sticky="w", padx=5)

        log_frame = ttk.Frame(self.frm_logstats)
        log_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.txt_log = tk.Text(
            log_frame, height=12, wrap="word", state="disabled", font=("Consolas", 11),
            bg="#1e1e1e", fg="#dcdcdc", borderwidth=1, relief="solid", insertbackground="#ffffff"
        )
        self.txt_log.pack(fill="both", expand=True)
        scrollbar.config(command=self.txt_log.yview)
        self.txt_log.tag_configure("link", foreground="#1E90FF", underline=True)

        self.main_video_volume_var.trace_add("write", self._update_main_video_volume_label)

    def _add_folder_row(self, label, var, row, parent, reload=False, bgm=False):
        lbl = ttk.Label(parent, text=label)
        lbl.grid(row=row, column=0, sticky="e", padx=5, pady=3)

        entry = ttk.Entry(parent, textvariable=var, width=50, font=("Segoe UI", 10))
        entry.grid(row=row, column=1, columnspan=2, sticky="we", padx=5, pady=3)
        self._add_right_click_menu(entry, [("❌ Clear Path", lambda v=var: v.set(""))])

        btn = ttk.Button(parent, text="Browse", style="Secondary.TButton",
                        command=lambda: self._choose_folder(var, reload=reload, bgm=bgm))
        btn.grid(row=row, column=3, sticky="w", padx=5, pady=3)

        return (lbl, entry, btn)   # <-- TRẢ VỀ CÁC WIDGET

    def _layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=2)
        self.grid_columnconfigure(0, weight=1)
        self.frm_top.grid(row=0, column=0, sticky="nsew", padx=15, pady=(10, 5))
        self.frm_logstats.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 10))
        self.frm_top.columnconfigure(0, weight=1)
        self.frm_logstats.columnconfigure(0, weight=1)

    def _update_volume_label(self, *args):
        val = self.bgm_volume_var.get()
        self.lbl_volume.config(text=f"{val * 100:.0f}%")
        self.save_channel_config()

    def _append_log(self, text: str):
        self.txt_log.configure(state="normal")
        if text.startswith("Đã ghép xong: "):
            path = text.replace("Đã ghép xong: ", "").strip()
            self._tag_id += 1
            tag_name = f"link_{self._tag_id}"

            # In tiền tố + path, nhưng path có tag riêng
            self.txt_log.insert("end", "Đã ghép xong: ")
            self.txt_log.insert("end", path + "\n", tag_name)

            # Trang điểm tag + bind sự kiện click
            self.txt_log.tag_configure(tag_name, foreground="#32CD32", underline=True)
            self.txt_log.tag_bind(tag_name, "<Enter>",  lambda e: self.txt_log.config(cursor="hand2"))
            self.txt_log.tag_bind(tag_name, "<Leave>",  lambda e: self.txt_log.config(cursor=""))
            self.txt_log.tag_bind(tag_name, "<Button-1>", lambda e, p=path: self._open_video_path(p))
        else:
            self.txt_log.insert("end", text + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def reload_groups(self):
        folder = self.input_folder.get()
        if not folder or not os.path.isdir(folder):
            self.groups = []
            self.total_mp4.set("0")
            if self.concat_mode.get() in ("Concat with time limit", "Loop"):
                planned = self.limit_videos_var.get() or 1
                self.num_groups.set(str(planned))
            else:
                self.num_groups.set("0")

            return

        try:
            all_videos = list_all_mp4_files(folder)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Đọc video lỗi: {e}")
            return

        used_videos = self._get_used_videos_from_log()
        all_videos = [v for v in all_videos if os.path.abspath(v) not in used_videos]
        gsize = self.group_size_var.get() or 6
        all_groups = get_all_random_video_groups(all_videos, group_size=gsize)

        limit_groups = self.limit_videos_var.get()
        if limit_groups > 0:
            self.groups = all_groups[:limit_groups]
        else:
            self.groups = all_groups

        self.total_mp4.set(str(len(all_videos)))

        #hiển thị Remaining theo mode:
        mode = self.concat_mode.get()
        if mode == "Concat with time limit":
            planned = limit_groups or 1  # time limit chỉ tạo theo thời lượng
            self.num_groups.set(str(planned))
        elif mode == "Loop":
            # Mỗi video là một job, nên đếm số video chưa dùng
            remaining = len([v for v in all_videos if os.path.abspath(v) not in used_videos])
            if limit_groups > 0:
                remaining = min(remaining, limit_groups)
            self.num_groups.set(str(remaining))
        else:
            self.num_groups.set(str(len(self.groups)))

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
            self.save_channel_config()

    def start_concat(self):
        self.start_time = time.time()
        self.elapsed_times.clear()
        mode = self.concat_mode.get()
        if self.worker and self.worker.is_alive():
            return messagebox.showinfo("Đang chạy", "Tiến trình đang chạy.")
        if mode not in ("Loop") and not self.groups:
            return messagebox.showwarning("Đã chạy hết toàn bộ", "Hãy xóa log để gen lại.")
        out_dir = self.save_folder.get()
        if not out_dir:
            return messagebox.showwarning("Thiếu thư mục lưu", "Chọn thư mục lưu")
        os.makedirs(out_dir, exist_ok=True)
        limit_groups = self.limit_videos_var.get()
        mode = self.concat_mode.get()

        
        if mode == "Loop":
            folder = self.input_folder.get()
            all_videos = list_all_mp4_files(folder) if folder and os.path.isdir(folder) else []
            used_global = self._get_used_videos_from_log()
            pool = [v for v in all_videos if os.path.abspath(v) not in used_global]

            count = limit_groups if limit_groups > 0 else len(pool)
            if count <= 0:
                return messagebox.showwarning("Không còn video", "Hết clip để chạy Loop (hoặc chưa chọn nguồn).")
            todo_groups = [[] for _ in range(count)]

        elif mode == "Concat with time limit":
            count = limit_groups if limit_groups > 0 else 1
            todo_groups = [[] for _ in range(count)]

        else:
            todo_groups = self.groups
            if limit_groups > 0:
                todo_groups = self.groups[:limit_groups]


        self.stop_flag.clear()
        self.btn_concat.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_var.set("Working...")
        self.progress['maximum'] = len(todo_groups)
        self.progress['value'] = 0
        self.progress_infor_var.set("Bắt đầu...")
        self.groups_done.set("0")
        self.worker = threading.Thread(target=self._do_concat_worker, args=(todo_groups, out_dir), daemon=True)
        self.worker.start()
        self.after(1000, self._poll_worker)

    def stop_concat(self):
        self.stop_flag.set()
        self.status_var.set("Stop")

    def _encode_group_to_temp(self, group: list[str], temp: str):
        width, height = map(int, self.resolution_var.get().split("x"))

        auto_concat(
            group, temp,
            num_threads=8,
            width=width,
            height=height,
            fps=self.fps_var.get(),
            use_nvenc=self.use_nvenc_var.get(),
            cq=self.cq_var.get(),
            v_bitrate=self.v_bitrate_var.get(),
            a_bitrate=self.a_bitrate_var.get(),
            nvenc_preset=self.nvenc_preset_var.get(),
        )

    #==============Switch mode================
    def _do_concat_worker(self, todo: list[list[str]], out_dir: str):
        log_dir = os.path.abspath("log")
        os.makedirs(log_dir, exist_ok=True)
        ch = self.selected_channel.get().strip() or 'default'
        log_path = os.path.join(log_dir, f"{ch}.txt")
        with open(log_path, "a", encoding="utf-8") as f_log:
            used_global = self._get_used_videos_from_log()  # đã dùng từ trước
            used_this_run = set()                            # dùng trong phiên chạy hiện tại
            for idx, group in enumerate(todo, 1):
                if self.stop_flag.is_set():
                    break
                start_group_time = time.time()
                temp = f"temp_{threading.get_ident()}.mp4"
                tmp_out = None
                output = None

                try:
                    mode = self.concat_mode.get()
                    total_jobs = len(todo)
                    if mode == "Loop":
                        self._enqueue(lambda i=idx, t=total_jobs: self._job_progress_start(i, t))
                    output = None

                    #++++++++++++++++LOGIC+++++++++++++++++++++
                    if mode == "Concat with music background":
                        self._encode_group_to_temp(group, temp)
                        bg_audio = random.choice(self.mp3_list) if self.mp3_list else None
                        desired = get_first_vids_name(out_dir, group[0])
                        bg_vol = float(self.bgm_volume_var.get())
                        if bg_audio and os.path.isfile(bg_audio) and bg_vol > 0:
                            tmp = mix_audio_with_bgm_ffmpeg(
                                temp, bg_audio, out_dir,
                                bgm_volume=self.bgm_volume_var.get(),
                                video_volume=self.main_video_volume_var.get()
                            )
                            # đổi tên file mix ra thành desired
                            if os.path.abspath(tmp) != os.path.abspath(desired):
                                shutil.move(tmp, desired)
                            output = desired
                        else:
                            output = desired
                            shutil.copy2(temp, output)
                        
                        used_this_run.update(os.path.abspath(p) for p in group)
                    
                    elif mode == "Concat with outro music":
                        outro_mode = self.outro_mode_var.get()
                        if outro_mode == "By time limit":
                            folder = self.input_folder.get()
                            all_videos = list_all_mp4_files(folder)
                            pool = [v for v in all_videos if os.path.abspath(v) not in (used_global | used_this_run)]
                            target_seconds = float(self.time_limit_min_var.get()) * 60.0 + float(self.time_limit_sec_var.get())
                            group = self._pick_videos_for_time(pool, target_seconds)
                            if not group:
                                self.after(0, lambda: self._append_log("Hết clip phù hợp cho Outro Time Limit."))
                                break

                        self._encode_group_to_temp(group, temp)
                        bg_audio = random.choice(self.mp3_list) if self.mp3_list else None
                        desired = get_first_vids_name(out_dir, group[0]) 
                        bg_vol = float(self.bgm_volume_var.get())
                        if bg_audio and os.path.isfile(bg_audio) and bg_vol > 0:
                            tmp = mix_audio_at_end_ffmpeg(
                                temp, bg_audio, out_dir, self.outro_duration_var.get(),
                                bgm_volume=self.bgm_volume_var.get(),
                                outro_volume=self.video_volume_var.get(),
                                video_volume=self.main_video_volume_var.get()
                            )
                            if os.path.abspath(tmp) != os.path.abspath(desired):
                                shutil.move(tmp, desired)
                            output = desired
                        else:
                            output = desired
                            shutil.copy2(temp, output)

                        used_this_run.update(os.path.abspath(p) for p in group)

                    elif mode == "Normal concat (no music)":
                        self._encode_group_to_temp(group, temp)
                        output = get_first_vids_name(out_dir, group[0])
                        shutil.copy2(temp, output)

                        used_this_run.update(os.path.abspath(p) for p in group)

                    elif mode == "Concat and Reverse":
                        base = concat_reverse(
                            group, out_dir,
                            width=int(self.resolution_var.get().split("x")[0]),
                            height=int(self.resolution_var.get().split("x")[1]),
                            fps=self.fps_var.get(),
                            use_nvenc=self.use_nvenc_var.get(),
                            cq=self.cq_var.get(),
                            v_bitrate=self.v_bitrate_var.get(),
                            a_bitrate=self.a_bitrate_var.get(),
                            preset=self.nvenc_preset_var.get(),
                            speed_reverse=3.0
                        )

                        bg_audio = random.choice(self.mp3_list) if self.mp3_list else None
                        desired = get_first_vids_name(out_dir, group[0])
                        if bg_audio and os.path.isfile(bg_audio):
                            tmp = mix_audio_with_bgm_ffmpeg(
                                base, bg_audio, out_dir,
                                bgm_volume=self.bgm_volume_var.get(),
                                video_volume=self.main_video_volume_var.get()
                            )
                            try: os.remove(base)
                            except: pass
                            if os.path.abspath(tmp) != os.path.abspath(desired):
                                shutil.move(tmp, desired)
                            output = desired
                        else:
                            shutil.move(base, desired)
                            output = desired

                    elif mode == "Concat with time limit":
                        # 1) Lấy pool còn lại (không trùng với log cũ + phiên này)
                        folder = self.input_folder.get()
                        all_videos = list_all_mp4_files(folder)
                        pool = [v for v in all_videos if os.path.abspath(v) not in (used_global | used_this_run)]

                        # 2) Chọn ngẫu nhiên tới gần target mà không quá dài
                        target_seconds = float(self.time_limit_min_var.get()) * 60.0 + float(self.time_limit_sec_var.get())
                        group = self._pick_videos_for_time(pool, target_seconds)
                        if not group:
                            # Hết clip phù hợp -> thoát hẳn vòng lặp
                            self.after(0, lambda: self._append_log("Hết clip phù hợp cho Time Limit."))
                            break

                        # 3) Ghép + mix BGM (giống 'Concat with music background')
                        self._encode_group_to_temp(group, temp)
                        bg_audio = random.choice(self.mp3_list) if self.mp3_list else None
                        desired = get_first_vids_name(out_dir, group[0]) 
                        bg_vol = float(self.bgm_volume_var.get())
                        if bg_audio and os.path.isfile(bg_audio) and bg_vol > 0:
                            tmp = mix_audio_with_bgm_ffmpeg(
                                temp, bg_audio, out_dir,
                                bgm_volume=self.bgm_volume_var.get(),
                                video_volume=self.main_video_volume_var.get()
                            )
                            if os.path.abspath(tmp) != os.path.abspath(desired):
                                shutil.move(tmp, desired)
                            output = desired
                        else:
                            output = desired
                            shutil.copy2(temp, output)

                        # 4) Đánh dấu đã dùng để lần xuất kế tiếp không trùng
                        used_this_run.update(os.path.abspath(p) for p in group)
                    
                    elif mode == "Loop":
                        folder = self.input_folder.get()
                        all_videos = list_all_mp4_files(folder)
                        # chỉ lấy clip chưa dùng (log cũ + phiên hiện tại)
                        pool = [v for v in all_videos if os.path.abspath(v) not in (used_global | used_this_run)]

                        # chọn đúng 1 video
                        if not pool:
                            self.after(0, lambda: self._append_log("Hết clip phù hợp cho Loop mode."))
                            self._enqueue(self._job_progress_stop)
                            break
    

                        one_video = random.choice(pool)
                        group = [one_video]

                        # thời lượng mục tiêu (nếu = 0 thì chỉ copy y như cũ)
                        target_seconds = float(self.time_limit_min_var.get()) * 60.0 + float(self.time_limit_sec_var.get())
                        desired = get_first_vids_name(out_dir, one_video)

                        def _cb(p):
                            self._enqueue(lambda: self._job_progress_update(p))
                        try:
                            if target_seconds > 0:
                                # LẶP đúng 1 video duy nhất tới thời lượng mục tiêu
                                self._loop_video_to_duration(
                                    src=one_video,
                                    dst=desired,
                                    target_seconds=target_seconds,
                                    progress_cb = _cb
                                )
                            else:
                                # Không set time limit -> copy nguyên bản
                                shutil.copy2(one_video, desired)

                            output = desired
                            used_this_run.update(os.path.abspath(p) for p in group)

                        except Exception as e:
                            # fallback copy nếu lặp lỗi
                            try:
                                shutil.copy2(one_video, desired)
                                output = desired
                                used_this_run.update(os.path.abspath(p) for p in group)
                            except Exception:
                                raise e


                    log_entry = {
                        "output": os.path.abspath(output),
                        "inputs": [os.path.abspath(p) for p in group],
                        "mode": mode
                    }
                    if mode in ("Concat with time limit", "Loop"):
                        log_entry["time_limit_min"] = int(self.time_limit_min_var.get() or 0)
                        log_entry["time_limit_sec"] = int(self.time_limit_sec_var.get() or 0)
                    f_log.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                    self.after(0, lambda path=output: self.last_output_var.set(path))
                    self.after(0, lambda path=output: self._append_log(f"Đã ghép xong: {path}"))
                    if mode == "Loop":
                        self._enqueue(self._job_progress_done)

                except Exception as e:
                    log_entry = {"error": str(e), "inputs": [os.path.abspath(p) for p in group]}
                    f_log.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                finally:
                    time.sleep(0.5)
                    if os.path.exists(temp):
                        safe_remove(temp)

                f_log.flush()
                elapsed = time.time() - start_group_time
                self.elapsed_times.append(elapsed)
                self._enqueue(self._update_progress)

    def _update_progress(self):
        self.progress['value'] += 1
        done = self.progress['value']
        total = self.progress['maximum']
        remaining = max(total - done, 0)

        # cập nhật số nhóm còn lại
        self.num_groups.set(str(remaining))
        self.groups_done.set(str(done))

        percent = (done / total) * 100
        avg_time = sum(self.elapsed_times) / len(self.elapsed_times) if self.elapsed_times else 0
        eta_seconds = avg_time * remaining
        elapsed_total = time.time() - self.start_time if self.start_time else 0

        def fmt_time(t):
            m, s = divmod(int(t), 60)
            return f"{m}m{s}s" if m else f"{s}s"

        eta_str = fmt_time(eta_seconds)
        elapsed_str = fmt_time(elapsed_total)
        avg_str = f"{avg_time:.1f}s/nhóm" if avg_time else "--"
        log_text = f"[Tiến trình] {percent:.1f}% | Còn lại: {eta_str} | Đã chạy: {elapsed_str} | TB: {avg_str}"
        self.progress_infor_var.set(log_text)

    ####second progress bar for job####
    def _job_progress_start(self, i=None, total=None):
        self.progress_job.configure(mode="determinate", maximum=100, value=0)
        self.job_info_var.set(f"Đang xử lý job {i}/{total}…" if (i and total) else "Đang xử lý job…")
        self.progress_job.grid()
        self.lbl_job_info.grid()

    def _job_progress_update(self, percent: float):
        # clamp và cập nhật label
        p = 0.0 if percent is None else max(0.0, min(100.0, float(percent)))
        self.progress_job.configure(value=p)
        self.job_info_var.set(f"Đang xử lý: {p:.0f}%")

    def _job_progress_done(self, text="Xong 1 job ✓"):
        self.progress_job.configure(value=100)
        self.job_info_var.set(text)
        self.after(300, lambda: self.progress_job.configure(value=0))

    def _job_progress_stop(self):
        self.progress_job.configure(value=0)
        self.job_info_var.set("")

    def _on_done(self):
        self.btn_concat.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_var.set("Hoàn thành" if not self.stop_flag.is_set() else "Đã dừng")
        self.progress_infor_var.set("" if not self.stop_flag.is_set() else "Đã dừng")

        self.progress_job.configure(value=0)
        self.job_info_var.set("")
        self.reload_groups()

    def _poll_worker(self):
        if self.worker and self.worker.is_alive():
            self.after(500, self._poll_worker)
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
        ch = self.selected_channel.get().strip() or 'default'
        log_path = os.path.join(log_dir, f"{ch}.txt")
        if not os.path.exists(log_path):
            messagebox.showinfo("Xóa log", "Không có file log để xóa.")
            return
        confirm = messagebox.askyesno("Xóa log", "Bạn có chắc muốn xóa toàn bộ dữ liệu log?")
        if confirm:
            try:
                os.remove(log_path)
                messagebox.showinfo("Xóa log", "Đã xóa dữ liệu log.")
                self.reload_groups()
            except Exception as e:
                messagebox.showerror("Xóa log", f"Lỗi khi xóa log: {e}")

    def _on_group_size_change(self, event=None):
        try:
            gsize = int(self.combo_group_size.get())
            self.group_size_var.set(gsize)
            self.reload_groups()
            self.save_channel_config()
        except ValueError:
            pass

    def _list_channels(self):
        files = [f[:-5] for f in os.listdir(CONFIG_DIR) if f.endswith(".json")]
        return sorted(files) if files else []

    def _open_video_path(self, path: str):
        if os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as e:
                messagebox.showerror("Lỗi mở video", f"Không thể mở:\n{path}\n\n{e}")
        else:
            messagebox.showwarning("Không tìm thấy", f"File không tồn tại:\n{path}")

    def _on_channel_change(self, event=None):
        ch = self.selected_channel.get()
        if ch:
            self.load_channel_config(ch)
            self.save_last_channel(ch)
            self.save_channel_config()

    def load_last_channel(self):
        if os.path.exists(LAST_CHANNEL_FILE):
            with open(LAST_CHANNEL_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            last = cfg.get("last_channel", "")
            if last and os.path.exists(os.path.join(CONFIG_DIR, f"{last}.json")):
                self.selected_channel.set(last)
                self.combo_channel["values"] = self._list_channels()
                self.load_channel_config(last)
                if self.bgm_folder.get() and os.path.isdir(self.bgm_folder.get()):
                    self.mp3_list = list_all_mp3_files(self.bgm_folder.get())

    def save_last_channel(self, name=None):
        cfg = {"last_channel": name or self.selected_channel.get()}
        with open(LAST_CHANNEL_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

    def load_channel_config(self, name):
        path = os.path.join(CONFIG_DIR, f"{name}.json")
        if not os.path.exists(path):
            return
        try:
            self._loading = True
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

            self.input_folder.set(cfg.get("input_folder", ""))
            self.save_folder.set(cfg.get("save_folder", ""))
            self.bgm_folder.set(cfg.get("bgm_folder", ""))
            group_size = cfg.get("group_size")
            if group_size is None or group_size < 2:
                group_size = 2
            self.group_size_var.set(group_size)
            self.bgm_volume_var.set(cfg.get("bgm_volume", 0.5))
            self.limit_videos_var.set(cfg.get("limit_videos", 0))
            #đồng bộ hiển thị
            lv = self.limit_videos_var.get()
            self.combo_limit_videos.set("All" if lv == 0 else str(lv))
            self.concat_mode.set(cfg.get('concat_mode','Concat with music background'))
            self.combo_mode.set(self.concat_mode.get())
            if self.concat_mode.get() == "Concat with outro music":
                self.video_volume_var.set(cfg.get("video_volume", 0.2))
                
            else:
                self.video_volume_var.set(0.2)
            self.main_video_volume_var.set(cfg.get("main_video_volume", 1.0))
            vs = cfg.get("video_settings", {})
            self.resolution_var.set(vs.get("resolution", "1080x1920"))
            self.fps_var.set(vs.get("fps", 60))
            self.use_nvenc_var.set(vs.get("use_nvenc", True))
            self.cq_var.set(vs.get("cq", 23))
            self.v_bitrate_var.set(vs.get("v_bitrate", "12M"))
            self.a_bitrate_var.set(vs.get("a_bitrate", "160k"))
            self.nvenc_preset_var.set(vs.get("nvenc_preset", "p4"))
            self.time_limit_min_var.set(str(vs.get("time_limit_min", 0)))
            self.time_limit_sec_var.set(str(vs.get("time_limit_sec", 0)))
            self.outro_mode_var.set(cfg.get('outro_mode', 'By group count'))
            self.combo_outro_mode.set(self.outro_mode_var.get())
            self.outro_duration_var.set(int(cfg.get("outro_duration",15)))
            odv = self.outro_duration_var.get()
            if str(odv) not in [str(v) for v in self.cbo_outro_dur["values"]]:
                self.cbo_outro_dur["values"] = [odv] + list(self.cbo_outro_dur["values"])

            self._update_mode_visibility()


        except Exception as e:
            messagebox.showerror("Load config", f"Lỗi đọc {path}: {e}")
        
        finally:
            self._loading = False
        
        if self.bgm_folder.get() and os.path.isdir(self.bgm_folder.get()):
            try:
                self.mp3_list = list_all_mp3_files(self.bgm_folder.get())
                print(f"[INFO] Loaded {len(self.mp3_list)} mp3 files from {self.bgm_folder.get()}")
            except Exception as e:
                print(f"[WARN] Could not read mp3 folder: {e}")

        self._update_mode_visibility()

    def save_channel_config(self):
        if getattr(self, "_loading", False):
            return
        ch = self.selected_channel.get()
        if not ch:
            return messagebox.showwarning("Chưa chọn channel", "Hãy chọn hoặc tạo channel trước.")
        path = os.path.join(CONFIG_DIR, f"{ch}.json")
        cfg = {
            "input_folder": self.input_folder.get(),
            "save_folder": self.save_folder.get(),
            "bgm_folder": self.bgm_folder.get(),
            "group_size": self.group_size_var.get(),
            "bgm_volume": self.bgm_volume_var.get(),
            "limit_videos": self.limit_videos_var.get(),
            "concat_mode": self.concat_mode.get(),
            "main_video_volume": self.main_video_volume_var.get(),
            "video_volume": self.video_volume_var.get(),
            "outro_mode": self.outro_mode_var.get(),
            "outro_duration": int(self.outro_duration_var.get() or 15),
            "video_settings": {
                "resolution": self.resolution_var.get(),
                "fps": self.fps_var.get(),
                "use_nvenc": self.use_nvenc_var.get(),
                "cq": self.cq_var.get(),
                "v_bitrate": self.v_bitrate_var.get(),
                "a_bitrate": self.a_bitrate_var.get(),
                "nvenc_preset": self.nvenc_preset_var.get(),
                "time_limit_min": int(self.time_limit_min_var.get() or 0),
                "time_limit_sec": int(self.time_limit_sec_var.get() or 0),   
            }
        }
        # Chỉ lưu video_volume khi đang ở chế độ outro
        if self.concat_mode.get() == "Concat with outro music":
            cfg["video_volume"] = self.video_volume_var.get()
            
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

    def _create_channel_from_entry(self, event=None):
        name = self.entry_new_channel.get().strip()
        if not name:
            return
        path = os.path.join(CONFIG_DIR, f"{name}.json")
        if os.path.exists(path):
            messagebox.showwarning("Duplicated", f"Channel '{name}' đã tồn tại!")
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2, ensure_ascii=False)
            self.combo_channel["values"] = self._list_channels()
            self.selected_channel.set(name)
            self.load_channel_config(name)
            self.save_last_channel(name)
            self.save_channel_config()
            messagebox.showinfo("Thành công", f"Đã tạo channel mới: {name}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể tạo channel '{name}': {e}")
        finally:
            self.entry_new_channel.delete(0, 'end')

    def _add_right_click_menu(self, widget, menu_items: list[tuple[str, callable]]):
        menu = tk.Menu(self.winfo_toplevel(), tearoff=0)
        for label, command in menu_items:
            menu.add_command(label=label, command=command)

        def show_menu(event=None):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        # Hiện menu khi bấm chuột phải
        widget.bind("<Button-3>", show_menu)
        try:
            for child in widget.winfo_children():
                child.bind("<Button-3>", show_menu)
        except Exception:
            pass

    def _clear_channel_selection(self):
        ch = self.selected_channel.get().strip()
        if not ch:
            return messagebox.showwarning("Chưa chọn", "Chưa chọn channel để xoá.")

        confirm = messagebox.askyesno("Xác nhận xoá", f"Xoá channel '{ch}' khỏi danh sách?")
        if not confirm:
            return

        # Xoá file JSON của channel
        path = os.path.join(CONFIG_DIR, f"{ch}.json")
        if os.path.exists(path):
            os.remove(path)

        # Lấy lại danh sách channel còn lại
        channels = self._list_channels()
        if channels:
            next_ch = channels[0]
            self.selected_channel.set(next_ch)
            self.combo_channel["values"] = channels
            self.load_channel_config(next_ch)
            self.save_last_channel(next_ch)
        else:
            # Không còn channel nào
            self.selected_channel.set("")
            self.combo_channel["values"] = []
            messagebox.showinfo("Đã xoá", f"Đã xoá '{ch}'. Hiện không còn channel nào.")

    def _on_global_delete(self, event=None):
        if self.selected_channel.get():
            self._clear_channel_selection()
        widget = self.focus_get()
        if isinstance(widget, ttk.Entry):
            widget.delete(0, "end")

    def _update_mode_visibility(self):
        mode = self.concat_mode.get()

        # Mặc định hiển thị BGM volume (trừ "Normal no music")
        self.lbl_bgm_text.grid()
        self.slider_volume.grid()
        self.lbl_volume.grid()

        # Time limit controls
        if (
                mode == "Concat with time limit"
                or (mode == "Concat with outro music" and self.outro_mode_var.get() == "By time limit")
                or mode == "Loop"
            ):
            self._show_time_limit(True)
            self._show_group_size(False)  # không dùng group size
        else:
            self._show_time_limit(False)
            # Reverse ép group size = 1, còn lại hiện bình thường
            if mode == "Concat and Reverse":
                self.group_size_var.set(1)
                self.combo_group_size.set("1")
                self.reload_groups()
                self._show_group_size(False)
            else:
                self._show_group_size(True)

        # Outro volume
        if mode == "Concat with outro music":
            self.lbl_video_vol.grid()
            self.slider_video_vol.grid()
            self.lbl_video_vol_value.grid()
            self.lbl_outro_mode.grid()
            self.combo_outro_mode.grid()
            self.lbl_outro_dur.grid()
            self.cbo_outro_dur.grid()
        else:
            self.lbl_video_vol.grid_remove()
            self.slider_video_vol.grid_remove()
            self.lbl_video_vol_value.grid_remove()
            self.lbl_outro_mode.grid_remove()
            self.combo_outro_mode.grid_remove()
            self.lbl_outro_dur.grid_remove()
            self.cbo_outro_dur.grid_remove()

        # Normal concat: ẩn BGM + Music Folder, dời Main Video Volume lên hàng 0
        if mode in ("Normal concat (no music)", "Loop"): 
            self.lbl_bgm_text.grid_remove()
            self.slider_volume.grid_remove()
            self.lbl_volume.grid_remove()
            for w in self.music_widgets:
                w.grid_remove()
            self.lbl_main_video_vol.grid_configure(row=0, column=4, sticky="e", padx=5)
            self.slider_main_video_vol.grid_configure(row=0, column=5, sticky="ew", padx=5)
            self.lbl_main_video_vol_value.grid_configure(row=0, column=6, sticky="w", padx=5)
        else:
            for w in self.music_widgets:
                w.grid()
            self.lbl_main_video_vol.grid_configure(row=2, column=4, sticky="e", padx=5)
            self.slider_main_video_vol.grid_configure(row=2, column=5, sticky="ew", padx=5)
            self.lbl_main_video_vol_value.grid_configure(row=2, column=6, sticky="w", padx=5)

        if mode == "Loop":
            self.progress_job.grid()
            self.lbl_job_info.grid()
        else:
            self.progress_job.grid_remove()
            self.lbl_job_info.grid_remove()
    
    def _show_time_limit(self, visible=True):
        widgets = [self.lbl_time_limit, self.combo_time_limit, self.combo_time_limit_sec]
        for w in widgets:
            w.grid() if visible else w.grid_remove()


    def _toggle_advanced(self):
        self._advanced = not self._advanced

        if self._advanced:
            self.video_frame.grid()
            self.btn_advanced.configure(text="Advanced ▾", style="Advanced.On.TButton")
        else:
            self.video_frame.grid_remove()
            self.btn_advanced.configure(text="Advanced ▸", style="Advanced.TButton")


    def _toggle_nvenc(self):
        self.use_nvenc_var.set(not self.use_nvenc_var.get())

    def _update_nvenc_button(self, *args):
        if self.use_nvenc_var.get():
            self.btn_nvenc.config(text="NVENC ON", style="NvencOn.TButton")
        else:
            self.btn_nvenc.config(text="NVENC OFF", style="NvencOff.TButton")


    def _show_group_size(self, visible=True):
        widgets = [self.lbl_group_size, self.combo_group_size]
        for w in widgets:
            w.grid() if visible else w.grid_remove()

    def _update_video_volume_label(self, *args):
        val = self.video_volume_var.get()
        self.lbl_video_vol_value.config(text=f"{val * 100:.0f}%")
        self.save_channel_config()

    def _update_main_video_volume_label(self, *args):
        val = self.main_video_volume_var.get()
        self.lbl_main_video_vol_value.config(text=f"{val * 100:.0f}%")
        self.save_channel_config()
    
    def _get_video_duration(self, path: str) -> float:
        """Lấy duration (giây) bằng ffprobe, có cache."""
        if path in self._dur_cache:
            return self._dur_cache[path]
        try:
            # ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "file"
            import subprocess, shlex
            cmd = f'ffprobe -v error -select_streams v:0 -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{path}"'
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
            dur = float(out.decode().strip())
            if dur < 0:
                dur = 0.0
        except Exception:
            dur = 0.0
        self._dur_cache[path] = dur
        return dur

    def _pick_videos_for_time(self, pool: list[str], target_seconds: float) -> list[str]:
        import random
        random.shuffle(pool)
        selected, total = [], 0.0

        # bước 1: add đến khi đạt/qua target
        for p in pool:
            d = self._get_video_duration(p)
            if d <= 0:
                continue
            selected.append(p)
            total += d
            if total >= target_seconds:
                break
        if not selected:
            return []
        
        overshoot = total - target_seconds
        limit_over = max(60.0, 0.5 * target_seconds)  # không quá dài

        if overshoot <= limit_over:
            return selected
        last = selected[-1]
        last_d = self._get_video_duration(last)
        need_reduce = overshoot
        candidates = [p for p in pool if p not in selected]
        best = None
        best_gap = None
        for c in candidates:
            cd = self._get_video_duration(c)
            if 0 < cd < last_d and (last_d - cd) >= need_reduce - limit_over:
                gap = last_d - cd
                if best is None or gap < best_gap:
                    best = c
                    best_gap = gap
        if best:
            selected[-1] = best  # thay
            return selected
        return selected
    
    def _get_used_videos_from_log(self) -> set[str]:
        used_videos = set()
        log_dir = os.path.abspath("log")
        os.makedirs(log_dir, exist_ok=True)
        ch = self.selected_channel.get().strip() or 'default'
        log_path = os.path.join(log_dir, f"{ch}.txt")
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
        return used_videos

    def _loop_video_to_duration(self, src: str, dst: str, target_seconds: float, progress_cb=None):
        loop_video_to_duration(
            src=src,
            dst=dst,
            target_seconds=target_seconds,
            vol=float(self.main_video_volume_var.get()),
            use_nvenc=self.use_nvenc_var.get(),
            nvenc_preset=self.nvenc_preset_var.get(),
            cq=int(self.cq_var.get()),
            v_bitrate=self.v_bitrate_var.get(),
            fps=int(self.fps_var.get()),
            a_bitrate=self.a_bitrate_var.get(),
            on_progress=progress_cb
        )    
    
    def _on_time_limit_var_changed(self, *_):
        if getattr(self, "_loading", False):
            return
        self.save_channel_config()

