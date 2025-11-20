# assign_mixin.py
from imports import *

class AssignMixin:
    # ====== BUILD PAGES / UI CHÍNH CỦA ASSIGN ======
    def _build_assign_page(self):
        page = ttk.Frame(self._content)
        self.pages["assign"] = page

        self._build_header(parent=page)
        self._build_inputs(parent=page)
        self._build_preview(parent=page)
        self._build_footer(parent=page)

    # BUILD SECTIONS
    def _build_header(self, parent):
        frm = ttk.Frame(parent, padding=(10, 10, 10, 0))
        frm.pack(fill=tk.X)

        ttk.Label(frm, text="Group:").grid(row=0, column=0, sticky="w")
        self.group_combo = ttk.Combobox(frm, textvariable=self.group_file_var, state="readonly", width=48)
        self.group_combo.grid(row=0, column=1, sticky="w", padx=6)
        def _on_group_change(event=None):
            group = self.group_file_var.get().strip()
            if group:
                last_group_path = os.path.join(os.path.dirname(__file__), "last_group.txt")
                with open(last_group_path, "w", encoding="utf-8") as f:
                    f.write(group)
            self._load_channels()

        self.group_combo.bind("<<ComboboxSelected>>", _on_group_change)


        self.channel_count_lbl = ttk.Label(frm, text="0 channels")
        self.channel_count_lbl.grid(row=0, column=4, sticky="w", padx=(12, 0))
        frm.columnconfigure(1, weight=1)

        # Distribution mode
        frm2 = ttk.Frame(parent, padding=(10, 6, 10, 0))
        frm2.pack(fill=tk.X)
    
        ttk.Label(frm2, text="Distribution mode:").pack(side=tk.LEFT)
        ttk.Radiobutton(frm2, text="Profile", variable=self.mode_var, value="titles").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Radiobutton(frm2, text="Channel", variable=self.mode_var, value="channels").pack(side=tk.LEFT, padx=(8, 0))

        # --- slot riêng cho label + combobox profile ---
        self.profile_slot = ttk.Frame(frm2)  # luôn dùng pack cho frm2, grid bên trong slot
        ttk.Label(self.profile_slot, text="Select channel:").grid(row=0, column=0, padx=(16,6))
        self.profile_combo = ttk.Combobox(
            self.profile_slot, state='readonly', width=40,
            textvariable=self.selected_profile_var, values=[]
        )
        self.profile_combo.grid(row=0, column=1)
        self.profile_slot.pack_forget()  # ẩn cả slot lúc đầu

        self._build_monetize_toggle(self.profile_slot)  # monetization toggle
        self._mon_label.grid(row=0, column=2, padx=(16, 6))
        self._mon_container.grid(row=0, column=3, padx=(0, 0))
        
        # auto refresh preview khi chọn profile
        def _on_profile_change(*_):
            group = self.group_file_var.get().strip()
            profile = self.selected_profile_var.get().strip()
            if not group or not profile:
                return

            val = (
                self._group_settings.get(group, {})
                .get(profile, {})
                .get("monetization", False)
            )
            self.monetization_var.set(val)
            self._monetization_vars[profile] = val

            # set move_folder_var theo JSON, fallback legacy
            mf = ""
            if self.mode_var.get() == "channels":
                mf = self._group_settings.get(group, {}).get(profile, {}).get("move_folder", "")
            else:
                mf = self._group_settings.get(group, {}).get("__group__", {}).get("move_folder", "")
            if not mf:
                mf = load_group_config(group) or load_group_config(group + ".csv") or ""
            self.move_folder_var.set(mf)

            cur_map = self._get_mapped_folder(group, profile)
            self._set_status(f"Profile '{profile}' selected | mapped: {cur_map or '(none)'}")
            self._schedule_preview()
            self._render_monetize_toggle()
            self._refresh_channel_stats_label()

        self.selected_profile_var.trace_add('write', _on_profile_change)

        # show/hide theo mode
        self.mode_var.trace_add('write', lambda *a: self._on_mode_change())
        self._on_mode_change()

        # Date/Time controls (apply to ALL rows)
        frm3 = ttk.Frame(parent, padding=(10, 6, 10, 0))
        frm3.pack(fill=tk.X)

        ttk.Label(frm3, text="Publish date:").pack(side=tk.LEFT)

        self.date_entry = DateEntry(
            frm3,
            width=12,
            date_pattern="mm/dd/yyyy",
            state="readonly"
        )
        self.date_entry.set_date(datetime.date.today())
        self.date_entry.pack(side=tk.LEFT, padx=(6, 16))

        ttk.Label(frm3, text="Publish time:").pack(side=tk.LEFT)

        hours = [f"{i:02d}" for i in range(24)]
        minutes = [f"{i:02d}" for i in range(0, 60, 5)]

        cb_h = ttk.Combobox(frm3, values=hours, width=3, textvariable=self.time_h_var, state="readonly")
        cb_h.pack(side=tk.LEFT, padx=(6, 2))
        ttk.Label(frm3, text=":").pack(side=tk.LEFT)
        cb_m = ttk.Combobox(frm3, values=minutes, width=3, textvariable=self.time_m_var, state="readonly")
        cb_m.pack(side=tk.LEFT, padx=(2, 12))

        ttk.Label(frm3, text="Step (min):").pack(side=tk.LEFT)
        sp_step = tk.Spinbox(frm3, from_=0, to=1440, increment=5, width=5, textvariable=self.step_min_var)
        sp_step.pack(side=tk.LEFT, padx=(6, 12))

        ttk.Button(frm3, text="Apply", command=self._apply_date_time_all).pack(side=tk.LEFT, padx=(12, 0))

        #refresh button
        def _refresh_random_paths():
            group = self.group_file_var.get().strip() #load group
            profile = self.selected_profile_var.get().strip() if self.mode_var.get() == "channels" else None
            folder = self._get_mapped_folder(group, profile)
            if not folder or not os.path.isdir(folder):
                messagebox.showwarning("No folder", f"Map folder isn't working: {folder or '(none)'}")
                return

            used_paths = load_used_videos()
            session_used = set()
            items = self.tree.selection() or self.tree.get_children()

            for iid in items:
                vals = list(self.tree.item(iid, "values"))
                vals += [""] * max(0, 6 - len(vals))
                ch, _, title, desc, pd, pt = vals
                new_dir = get_random_unused_mp4(folder, used_paths | session_used)
                if new_dir:
                    session_used.add(new_dir)
                    self.tree.item(iid, values=(ch, new_dir, title, desc, pd, pt))

            # Cập nhật self._last_assignments
            if self._last_assignments:
                rows = []
                for iid in self.tree.get_children():
                    rows.append(self.tree.item(iid, "values"))
                self._last_assignments = rows

            self._set_status(f"Refreshed random videos for {len(items)} row(s).")
        # ttk.Button(frm3, text="Refresh", command=_refresh_random_paths).pack(side=tk.RIGHT, padx=(10,0))
        self.bind_all("<F5>", lambda e: _refresh_random_paths())
        ttk.Button(frm3, text="Clear", command=self._clear_inputs).pack(side=tk.RIGHT, padx=(0, 10))
        


    def _build_inputs(self, parent):
        container = ttk.Frame(parent, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        # ======== HÀNG NÚT AI (grid) ========
        top_row = ttk.Frame(container)
        top_row.pack(fill="x", pady=(0, 8))

        btn_ai_title = ttk.Button(top_row, text="Generate", command=self._ai_generate_titles_and_descs)
        btn_ai_title.pack(side="left", padx=6)
        # ======== PANED WINDOW (pack) ========
        paned = tk.PanedWindow(container, orient=tk.HORIZONTAL,
                            sashrelief=tk.RAISED, sashwidth=6)
        paned.pack(fill=tk.BOTH, expand=True)

        def make_section(label_text):
            frame = ttk.Frame(paned)
            ttk.Label(frame, text=label_text).pack(anchor="w")
            txt = tk.Text(frame, height=12, wrap=tk.WORD)
            txt.pack(fill=tk.BOTH, expand=True)
            return frame, txt

        f1, self.txt_titles = make_section("Titles (one per line)")
        f2, self.txt_descs = make_section("Descriptions (1 line all or multi)")
        f3, self.txt_dates = make_section("Date (MM/DD/YYYY)")
        f4, self.txt_times = make_section("Time (HH:MM)")

        self._inputs_paned = paned
        self._inputs_panes = (f1, f2, f3, f4)

        for w in (self.txt_titles, self.txt_descs, self.txt_dates, self.txt_times):
            w.bind("<Control-a>", lambda e, widget=w:
                (widget.tag_add("sel", "1.0", "end-1c"), "break"))

        # Add frames into paned
        paned.add(f1)
        paned.add(f2)
        paned.add(f3)
        paned.add(f4)

    def _build_preview(self, parent):
        frm = ttk.Frame(parent, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        cols = ("channel", "directory", "title", "description", "publish_date", "publish_time")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", height=12)

        for col in cols:
            self.tree.heading(col, text=col.capitalize())
            if col == "description":
                self.tree.column(col, width=420, anchor="w")
            elif col == "title":
                self.tree.column(col, width=300, anchor="w")
            elif col == "channel":
                self.tree.column(col, width=200, anchor="w")
            elif col == "publish_date":
                self.tree.column(col, width=120, anchor="w")
            elif col == "publish_time":
                self.tree.column(col, width=100, anchor="w")
            elif col == "directory":
                self.tree.column(col, width=240, anchor="w")

        vsb = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=vsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.LEFT, fill=tk.Y)

        # bindings
        self.tree.bind("<Button-1>", self._on_tree_single_click)  # 1 click: chỉ chọn / bỏ chọn
        self.tree.bind("<Double-1>", self._on_tree_click)         # 2 click: edit ô (inline)
        self.tree.bind("<Delete>", self._delete_selected_rows)
        self.tree.bind("<Button-3>", self._show_tree_menu)        # chuột phải -> menu Edit/Delete
        self.tree.bind("<Control-a>", self._select_all)
        self.tree.bind("<Control-A>", self._select_all)
        self.tree.bind('<Escape>', self._clear_selection)
        self.bind_all("<Button-1>", self._global_click, add="+")

    def _build_footer(self, parent):
        bar = ttk.Frame(parent, relief=tk.SUNKEN, padding=6)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.move_folder_var = tk.StringVar(value="")

        ttk.Label(bar, text="Save to:").pack(side=tk.LEFT, padx=(0, 4))
        ent = ttk.Entry(bar, textvariable=self.move_folder_var, width=50)
        ent.pack(side=tk.LEFT, padx=(0, 4))

        def choose_folder():
            folder = filedialog.askdirectory(title="Chọn thư mục lưu video mới")
            if not folder:
                return
            folder = os.path.abspath(folder)
            self.move_folder_var.set(folder)

            group = self.group_file_var.get().strip()
            profile = self.selected_profile_var.get().strip()
            if not group:
                return

            # --- LƯU VÀO JSON: _group_settings ---
            if group not in self._group_settings:
                self._group_settings[group] = {}

            if self.mode_var.get() == "channels" and profile:
                self._group_settings[group].setdefault(profile, {})
                self._group_settings[group][profile]["move_folder"] = folder
            else:
                self._group_settings[group].setdefault("__group__", {})
                self._group_settings[group]["__group__"]["move_folder"] = folder

            self._group_settings[group]["__meta__"] = {
                "mode": self.mode_var.get(),
                "last_profile": profile
            }
            save_group_settings(self._group_settings)


            key = f"{group}|{profile}" if (self.mode_var.get() == "channels" and profile) else group
            save_group_config(key, folder)

            self._set_status(f"Save to → {folder}")

        ttk.Button(bar, text="Browse", command=choose_folder).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bar, text="Combine", command=self._combine_excels).pack(side=tk.RIGHT)
        ttk.Button(bar, text="Save", command=self._save_excel).pack(side=tk.RIGHT, padx=(0,8))
        

    
