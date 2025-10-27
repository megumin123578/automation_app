import os
import threading
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import openai
from tkcalendar  import DateEntry
from openpyxl.styles import Font
from random_vids import get_random_unused_mp4
import glob
from ui_theme import setup_theme
from excel_helper import save_assignments_to_excel, combine_excels
import tkinter.simpledialog as sd
from update_manager import check_and_update, install_from_zip
import sys,subprocess
from module import *
from hyperparameter import *
from ghep_music.concat_page import ConcatPage
from thong_ke.stats_page import StatisticsPage

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        style = ttk.Style()
        style.theme_use("clam")
        setup_theme(style, self)

        self.title(APP_TITLE)
        self.state("zoomed")
        self.minsize(1000, 600)

        # ====== STATE ======
        self.group_file_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value="titles")  # titles (Repeat) | channels (No Repeat)
        self.status_var = tk.StringVar(value="Ready.")
        self._channels_cache = []
        self._last_assignments = None

        self.date_entry = None
        now = datetime.datetime.now()
        self.time_h_var = tk.StringVar(value=f"{now.hour:02d}")
        self.time_m_var = tk.StringVar(value=f"{now.minute:02d}")
        self.step_min_var = tk.IntVar(value=0)

        # ====== MENUBAR (Profiles + Help) ======
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        profiles_menu = tk.Menu(menubar, tearoff=0)
        profiles_menu.add_command(label="Manage Profiles", command=self._open_profile_manager)
        profiles_menu.add_command(label="Add Group", command=self._add_group)
        profiles_menu.add_command(label="Delete Group", command=self._delete_group)
        profiles_menu.add_command(label="Map Group Folder...", command=self._map_group_folder)
        menubar.add_cascade(label="Profiles", menu=profiles_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Check for Updates (Default)...", command=self._check_for_updates)
        help_menu.add_separator()
        help_menu.add_command(label=f"About (v{APP_VERSION})",
                               command=lambda: messagebox.showinfo("About", "Update concat file name saved, update apply date time"))
        menubar.add_cascade(label="Help", menu=help_menu)

        self._build_shell()

        # ====== PAGES ======
        self.pages = {}
        self._build_assign_page()      # giao diện phân phối nhóm
        self._build_concat_page()      # trang ghép video + nhạc
        self._build_manage_page()      # trang quản lý kênh
        self._build_statistics_page()  # trang thống kê

        # Hiển thị page mặc định
        self._show_page("assign")

        # Khởi động dữ liệu + preview binding
        self._refresh_group_files()
        self._bind_text_preview()

        # Auto check update sau khi UI sẵn sàng
        self.after(1500, self._auto_check_update)

    # =========================
    # Shell: Sidebar + Content
    # =========================
    def _build_shell(self):
        # container chính
        self._root_container = ttk.Frame(self)
        self._root_container.pack(fill="both", expand=True)

        # Sidebar
        self._sidebar = tk.Frame(self._root_container, width=220)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        # Content
        self._content = ttk.Frame(self._root_container)
        self._content.pack(side="right", fill="both", expand=True)

        # Sidebar buttons
        self._nav_buttons = {}
        def add_btn(text, key, cmd):
            b = tk.Button(self._sidebar, text=text, anchor="w", relief="flat",
                          pady=10, padx=12, font=("Segoe UI", 10, "bold"),
                          command=lambda: (cmd(), self._highlight_nav(key)))
            b.pack(fill="x")
            self._nav_buttons[key] = b

        add_btn("Auto Upload", "assign", lambda: self._show_page("assign"))
        add_btn("Concatenation", "concat", lambda: self._show_page("concat"))
        add_btn("Manage Channels", "manage", lambda: self._show_page("manage"))
        add_btn("Statistics", "stats", lambda: self._show_page("stats"))

        # Status bar
        bar = ttk.Frame(self, relief=tk.SUNKEN, padding=6)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(bar, textvariable=self.status_var).pack(side=tk.LEFT)

    def _highlight_nav(self, active_key):
        for k, btn in self._nav_buttons.items():
            if k == active_key:
                btn.configure(bg="#E6F0FF", fg="#000000") 
            else:
                btn.configure(bg=self._sidebar.cget("bg"), fg="#ffffff")  


    def _show_page(self, key: str):
        for k, f in self.pages.items():
            f.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        self._highlight_nav(key)

    # =========================
    # PAGES
    # =========================
    def _build_assign_page(self):
        page = ttk.Frame(self._content)
        self.pages["assign"] = page

        # ---- Build giao diện cũ vào page này ----
        # Header / Inputs / Preview / Footer sẽ build vào `page`
        self._build_header(parent=page)
        self._build_inputs(parent=page)
        self._build_preview(parent=page)
        self._build_footer(parent=page)

    def _build_concat_page(self):
        page = ttk.Frame(self._content)       # khung trang
        self.pages["concat"] = page

        # Nhúng UI concat vào đây:
        self.concat_page = ConcatPage(page)   # truyền parent là 'page'
        self.concat_page.pack(fill="both", expand=True)


    def _build_manage_page(self):
        page = ttk.Frame(self._content, padding=16)
        self.pages["manage"] = page

        ttk.Label(page, text="Manage channel", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(page, text="Manage channel",
                  padding=(0, 8)).pack(anchor="w")

        ttk.Button(page, text="Open manage channel app",
                   command=self._open_manage_channel_window).pack(anchor="w", pady=6)

    def _build_statistics_page(self):
        page = ttk.Frame(self._content)
        self.pages["stats"] = page

        self.stats_page = StatisticsPage(page)  # nhúng trang thống kê
        self.stats_page.pack(fill="both", expand=True)

    # =========================
    #      BUILD SECTIONS     #
    # =========================
    def _build_header(self, parent):
        frm = ttk.Frame(parent, padding=(10, 10, 10, 0))
        frm.pack(fill=tk.X)

        ttk.Label(frm, text="Group:").grid(row=0, column=0, sticky="w")
        self.group_combo = ttk.Combobox(frm, textvariable=self.group_file_var, state="readonly", width=48)
        self.group_combo.grid(row=0, column=1, sticky="w", padx=6)
        self.group_combo.bind("<<ComboboxSelected>>", lambda e: self._load_channels())

        self.channel_count_lbl = ttk.Label(frm, text="0 channels")
        self.channel_count_lbl.grid(row=0, column=4, sticky="w", padx=(12, 0))
        frm.columnconfigure(1, weight=1)

        # Distribution mode
        frm2 = ttk.Frame(parent, padding=(10, 6, 10, 0))
        frm2.pack(fill=tk.X)
        ttk.Label(frm2, text="Distribution mode:").pack(side=tk.LEFT)
        ttk.Radiobutton(frm2, text="Profile", variable=self.mode_var, value="titles").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Radiobutton(frm2, text="Channel", variable=self.mode_var, value="channels").pack(side=tk.LEFT, padx=(8, 0))

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
        cb_m = ttk.Combobox(frm3, values=minutes, width=3, textvariable=self.time_m_var, state="normal")
        cb_m.pack(side=tk.LEFT, padx=(2, 12))

        ttk.Label(frm3, text="Step (min):").pack(side=tk.LEFT)
        sp_step = tk.Spinbox(frm3, from_=0, to=1440, increment=5, width=5, textvariable=self.step_min_var)
        sp_step.pack(side=tk.LEFT, padx=(6, 12))

        ttk.Button(frm3, text="Apply", command=self._apply_date_time_all).pack(side=tk.LEFT, padx=(12, 0))

    def _build_inputs(self, parent):
        frm = ttk.Frame(parent, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        # Titles
        left = ttk.Frame(frm)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        ttk.Label(left, text="Titles (one per line)").pack(anchor="w")
        self.txt_titles = tk.Text(left, height=12, wrap=tk.WORD)
        self.txt_titles.pack(fill=tk.BOTH, expand=True)

        # Descriptions
        mid = ttk.Frame(frm)
        mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        ttk.Label(mid, text="Descriptions (1 line for all, or multiple lines)").pack(anchor="w")
        self.txt_descs = tk.Text(mid, height=12, wrap=tk.WORD)
        self.txt_descs.pack(fill=tk.BOTH, expand=True)

        # Times
        right = ttk.Frame(frm)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        ttk.Label(right, text="Time (HH:MM or per line)").pack(anchor="w")
        self.txt_times = tk.Text(right, height=12, wrap=tk.WORD)
        self.txt_times.pack(fill=tk.BOTH, expand=True)

        # Buttons
        btns = ttk.Frame(parent, padding=(10, 0, 10, 0))
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Clear Inputs", command=self._clear_inputs).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Generate titles and des", command=self._generate_titles_descs).pack(side=tk.LEFT, padx=6)

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
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Delete>", self._delete_selected_rows)
        self.tree.bind("<Button-3>", self._show_tree_menu)

        btns = ttk.Frame(parent, padding=(10, 0, 10, 10))
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Save Excel", command=self._save_excel).pack(side=tk.LEFT)

    def _build_footer(self, parent):
        bar = ttk.Frame(parent, relief=tk.SUNKEN, padding=6)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.move_folder_var = tk.StringVar(value="")

        ttk.Label(bar, text="Save to:").pack(side=tk.LEFT, padx=(0, 4))
        ent = ttk.Entry(bar, textvariable=self.move_folder_var, width=50)
        ent.pack(side=tk.LEFT, padx=(0, 4))

        def choose_folder():
            folder = filedialog.askdirectory(title="Chọn thư mục lưu video mới")
            if folder:
                self.move_folder_var.set(folder)
                group_name = self.group_file_var.get().strip()
                if group_name:
                    save_group_config(group_name, folder)

        ttk.Button(bar, text="Browse", command=choose_folder).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bar, text="Combine", command=self._combine_excels).pack(side=tk.RIGHT)

    # =========================
    # Logic gốc (không đổi)
    # =========================
    def _schedule_preview(self):
        if hasattr(self, "_preview_job"):
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(500, self._preview)

    def _bind_text_preview(self):
        def on_change(event):
            event.widget.edit_modified(False)
            self._schedule_preview()
        self.txt_titles.bind("<<Modified>>", on_change)
        self.txt_descs.bind("<<Modified>>", on_change)
        self.txt_times.bind("<<Modified>>", on_change)

    def _refresh_group_files(self):
        files = list_group_csvs(GROUPS_DIR)
        groups = [os.path.splitext(f)[0] for f in files]

        self.group_combo["values"] = groups
        cur = self.group_file_var.get()

        if not groups:
            self.group_file_var.set("")
            self.channel_count_lbl.config(text="0 channels")
            self._set_status(f"No CSV files in: {GROUPS_DIR}")
            return

        if cur not in groups:
            self.group_file_var.set(groups[0])

        self._load_channels()

    def _load_channels(self):
        name = self.group_file_var.get().strip()
        if not name:
            return
        csv_path = os.path.join(GROUPS_DIR, name + ".csv")
        channels = read_channels_from_csv(csv_path)
        self._channels_cache = channels
        self.channel_count_lbl.config(text=f"{len(channels)} channels")

        group_dirs = load_group_dirs()
        mapped_dir = group_dirs.get(name) or group_dirs.get(f"{name}.csv") or ""
        mapped_note = f" | mapped: {mapped_dir}" if mapped_dir else " | mapped: (none)"
        self._set_status(f"Loaded {len(channels)} channels from {name}{mapped_note}")

        last_folder = load_group_config(name + ".csv")
        self.move_folder_var.set(last_folder)

    def _clear_inputs(self):
        self.txt_titles.delete("1.0", tk.END)
        self.txt_descs.delete("1.0", tk.END)
        self.tree.delete(*self.tree.get_children())
        self._last_assignments = None
        self._set_status("Cleared inputs & preview.")

    def _preview(self):
        group_file = self.group_file_var.get().strip()
        if not group_file:
            messagebox.showwarning("Missing CSV", "Please select a group CSV")
            return

        titles = normalize_lines(self.txt_titles.get("1.0", tk.END))
        descs = normalize_lines(self.txt_descs.get("1.0", tk.END))
        times = normalize_lines(self.txt_times.get("1.0", tk.END))
        channels = self._channels_cache
        mode = self.mode_var.get()

        if not titles and not descs:
            self.tree.delete(*self.tree.get_children())
            self._last_assignments = None
            self._set_status("Inputs empty → preview cleared.")
            return

        try:
            assignments = assign_pairs(channels, titles, descs, mode=mode)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        group_dirs = load_group_dirs()
        key = self.group_file_var.get().strip()
        folder_path = group_dirs.get(key) or group_dirs.get(f"{key}.csv")

        used_paths = load_used_videos()
        session_used = set()
        self.tree.delete(*self.tree.get_children())
        extended = []
        try:
            selected_date = self.date_entry.get_date().strftime('%m/%d/%Y')
        except Exception:
            selected_date = datetime.date.today().strftime('%m/%d/%Y')

        for i, (ch, t, d) in enumerate(assignments):
            pt = times[i] if i < len(times) else ""
            pd = selected_date if pt else ""

            if folder_path and os.path.isdir(folder_path):
                directory = get_random_unused_mp4(folder_path, used_paths | session_used)
                if directory:
                    session_used.add(directory)
            else:
                directory = ""

            self.tree.insert("", tk.END, values=(ch, directory, t, d, pd, pt))
            extended.append((ch, directory, t, d, pd, pt))

        self._last_assignments = extended
        self._set_status(f"Previewed {len(assignments)} rows")

    def _save_excel(self):
        if not self._last_assignments:
            messagebox.showwarning("Nothing to save", "Click Preview first.")
            return

        def worker():
            try:
                base = os.path.splitext(self.group_file_var.get().strip())[0] or "group"
                out_name = f"{base}.xlsx"
                out_path = os.path.join(OUTPUT_DIR, out_name)
                save_assignments_to_excel(self._last_assignments, out_path)
                self._set_status(f"Saved Excel: {out_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save Excel:\n{e}")

        threading.Thread(target=worker, daemon=True).start()

    def _set_status(self, msg: str):
        self.after(0, lambda: self.status_var.set(msg))

    def _on_tree_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        index = self.tree.index(item_id)
        self._edit_row_dialog(item_id, index)

    def _edit_row_dialog(self, item_id, index):
        vals = list(self.tree.item(item_id, "values"))
        vals += [""] * max(0, 6 - len(vals))
        ch_cur, dir_cur, title_cur, desc_cur, pd_cur, pt_cur = vals

        win = tk.Toplevel(self)
        win.title("Edit row")
        win.transient(self)
        win.grab_set()

        frm = ttk.Frame(win, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Profile:").grid(row=0, column=0, sticky="e", padx=6, pady=4)
        ent_ch = ttk.Combobox(frm, values=[c for c in self._channels_cache], state="readonly", width=60)
        ent_ch.grid(row=0, column=1, sticky="we")
        ent_ch.set(ch_cur)

        ttk.Label(frm, text="Directory:").grid(row=1, column=0, sticky="e", padx=6, pady=4)
        ent_dir = ttk.Entry(frm, width=60)
        ent_dir.grid(row=1, column=1, sticky="we")
        ent_dir.insert(0, dir_cur)

        ttk.Label(frm, text="Title:").grid(row=2, column=0, sticky="e", padx=6, pady=4)
        ent_title = ttk.Entry(frm, width=60)
        ent_title.grid(row=2, column=1, sticky="we")
        ent_title.insert(0, title_cur)

        ttk.Label(frm, text="Description:").grid(row=3, column=0, sticky="ne", padx=6, pady=4)
        txt_desc = tk.Text(frm, width=60, height=6, wrap=tk.WORD)
        txt_desc.grid(row=3, column=1, sticky="we")
        txt_desc.insert("1.0", desc_cur)

        import datetime as _dt
        if pd_cur:
            try:
                init_date = _dt.datetime.strptime(pd_cur, "%m/%d/%Y").date()
            except Exception:
                init_date = _dt.date.today()
        else:
            init_date = _dt.date.today()

        ttk.Label(frm, text="Publish date:").grid(row=4, column=0, sticky="e", padx=6, pady=4)
        ent_pd = DateEntry(frm, width=12, date_pattern="mm/dd/yyyy")
        ent_pd.grid(row=4, column=1, sticky="w")
        ent_pd.set_date(init_date)

        ttk.Label(frm, text="Publish time:").grid(row=5, column=0, sticky="e", padx=6, pady=4)
        try:
            h_cur, m_cur = (pt_cur.split(":") if pt_cur else ("", ""))
        except Exception:
            h_cur, m_cur = ("", "")

        hours = [f"{i:02d}" for i in range(24)]
        minutes = [f"{i:02d}" for i in range(0, 60, 5)]

        cb_h = ttk.Combobox(frm, values=hours, width=3, state="readonly")
        cb_h.grid(row=5, column=1, sticky="w", padx=(0, 2))
        cb_h.set(h_cur if h_cur in hours else "00")
        ttk.Label(frm, text=":").grid(row=5, column=1, padx=(50, 0), sticky="w")
        cb_m = ttk.Combobox(frm, values=minutes, width=3, state="readonly")
        cb_m.grid(row=5, column=1, padx=(65, 0), sticky="w")
        cb_m.set(m_cur if m_cur in minutes else "00")

        frm.columnconfigure(1, weight=1)

        def on_save():
            ch = ent_ch.get().strip()
            directory = ent_dir.get().strip()
            t = ent_title.get().strip()
            d = txt_desc.get("1.0", tk.END).strip()
            pd = ent_pd.get_date().strftime("%m/%d/%Y")
            pt = f"{cb_h.get()}:{cb_m.get()}"
            if not ch or not t:
                messagebox.showwarning("Missing", "Channel và Title không được để trống.")
                return
            new_vals = (ch, directory, t, d, pd, pt)
            self.tree.item(item_id, values=new_vals)
            if 0 <= index < len(self._last_assignments):
                self._last_assignments[index] = new_vals
            self._set_status(f"Updated row {index+1}.")
            win.destroy()

        btns = ttk.Frame(win, padding=(0, 8))
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Save", command=on_save).pack(side=tk.LEFT)
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=6)

        win.update_idletasks()
        w = win.winfo_width(); h = win.winfo_height()
        sw = win.winfo_screenwidth(); sh = win.winfo_screenheight()
        x = (sw // 2) - (w // 2); y = (sh // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.bind("<Return>", lambda e: on_save()); win.bind("<Escape>", lambda e: win.destroy())
        ent_title.focus_set()

    def _apply_date_time_all(self):
        if hasattr(self.date_entry, "get_date"):
            try:
                d = self.date_entry.get_date()
                date_str = d.strftime("%m/%d/%Y")
            except Exception:
                date_str = str(self.date_entry.get()).strip()
        else:
            date_str = str(self.date_entry.get()).strip()

        try:
            datetime.datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            messagebox.showerror("Invalid date", "Định dạng ngày phải là MM/DD/YYYY.")
            return

        hh = self.time_h_var.get().strip()
        mm = self.time_m_var.get().strip()
        step = self.step_min_var.get()

        if not (hh.isdigit() and mm.isdigit()):
            messagebox.showerror("Invalid time", "Giờ/Phút phải là số.")
            return
        h, m = int(hh), int(mm)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            messagebox.showerror("Invalid time", "Giờ phải 00-23, phút 00-59.")
            return

        try:
            step = int(step)
        except Exception:
            messagebox.showerror("Invalid step", "Step (min) phải là số nguyên.")
            return
        if step < 0:
            messagebox.showerror("Invalid step", "Step (min) không được âm.")
            return

        selected_items = self.tree.selection()
        if not selected_items:
            selected_items = self.tree.get_children()

        base_dt = datetime.datetime(2000, 1, 1, h, m)

        for i, iid in enumerate(selected_items):
            tm = (base_dt + datetime.timedelta(minutes=step * i)).time()
            time_str = f"{tm.hour:02d}:{tm.minute:02d}"
            vals = list(self.tree.item(iid, "values"))
            vals += [""] * max(0, 6 - len(vals))
            ch, directory, t, desc, _, _ = vals
            new_vals = (ch, directory, t, desc, date_str, time_str)
            self.tree.item(iid, values=new_vals)
            if self._last_assignments:
                try:
                    index = self.tree.index(iid)
                    if 0 <= index < len(self._last_assignments):
                        self._last_assignments[index] = new_vals
                except Exception:
                    pass

        self._set_status(f"Đã áp dụng ngày {date_str} cho {len(selected_items)} dòng được chọn.")

    def _combine_excels(self):
        input_dir = OUTPUT_DIR
        move_folder = self.move_folder_var.get().strip()
        # Repeat / No Repeat
        if self.mode_var.get() == "channels":
            output_file = EXCEL_DIR_NP
        else:
            output_file = EXCEL_DIR
        try:
            count, files = combine_excels(input_dir, output_file, move_folder, get_mp4_filename)
            if count == 0:
                messagebox.showwarning("No files", f"Không tìm thấy file Excel nào trong:\n{input_dir}")
                return
            self._set_status(f"Combined {count} files → {output_file}")
            messagebox.showinfo("Done", "Combined successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Lỗi khi combine:\n{e}")

    def _delete_selected_rows(self, event=None):
        items = self.tree.selection()
        if not items:
            return
        confirm = messagebox.askyesno("Confirm delete", f"Delete {len(items)} row(s)?")
        if not confirm:
            return
        for item_id in items:
            index = self.tree.index(item_id)
            self.tree.delete(item_id)
            if self._last_assignments and 0 <= index < len(self._last_assignments):
                self._last_assignments.pop(index)
        self._set_status(f"Deleted {len(items)} row(s).")

    def _show_tree_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        if item_id not in self.tree.selection():
            self.tree.selection_set(item_id)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Delete", command=lambda: self._delete_selected_rows())
        menu.post(event.x_root, event.y_root)

    def _open_profile_manager(self):
        group_file = self.group_file_var.get().strip()
        if not group_file:
            messagebox.showwarning("No group", "Hãy chọn một group CSV trước.")
            return
        csv_path = os.path.join(GROUPS_DIR, f"{group_file}.csv")

        win = tk.Toplevel(self)
        win.title(f"Profile Manager - {group_file}")
        win.transient(self)
        win.grab_set()

        frm = ttk.Frame(win, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Danh sách channel (mỗi dòng 1 channel):").pack(anchor="w")
        txt = tk.Text(frm, width=50, height=20)
        txt.pack(fill=tk.BOTH, expand=True)

        for ch in self._channels_cache:
            txt.insert(tk.END, ch + "\n")

        def save_profiles():
            lines = [line.strip() for line in txt.get("1.0", tk.END).splitlines() if line.strip()]
            if not lines:
                messagebox.showwarning("Empty", "Danh sách channel không được để trống.")
                return
            with open(csv_path, "w", encoding="utf-8") as f:
                for ch in lines:
                    f.write(ch + "\n")
            self._channels_cache = lines
            self.channel_count_lbl.config(text=f"{len(lines)} channels")
            self._set_status(f"Saved {len(lines)} channels to {group_file}")
            win.destroy()

        btns = ttk.Frame(win, padding=6)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Save", command=save_profiles).pack(side=tk.LEFT)
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=6)

        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x, y = (sw // 2) - (w // 2), (sh // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

    def _add_group(self):
        name = sd.askstring("Add Group", "Enter new group name:")
        if not name:
            return
        if name.lower().endswith(".csv"):
            name = name[:-4]
        filename = name + ".csv"
        path = os.path.join(GROUPS_DIR, filename)
        if os.path.exists(path):
            messagebox.showwarning("Exists", f"Group '{name}' already exists")
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
            self._set_status(f"Created new group: {name}")
            self._refresh_group_files()
            self.group_file_var.set(name)
            self._load_channels()
        except Exception as e:
            messagebox.showerror("Error", f"Error when creating group:\n{e}")

    def _delete_group(self):
        name = self.group_file_var.get().strip()
        if not name:
            messagebox.showwarning("No group", "Select a group to delete first.")
            return
        confirm = messagebox.askyesno("Confirm delete", f"Delete group '{name}' ?")
        if not confirm:
            return
        path = os.path.join(GROUPS_DIR, name + '.csv')
        try:
            if os.path.exists(path):
                os.remove(path)
            self._set_status(f"Deleted group: '{name}'")
            self._refresh_group_files()
        except Exception as e:
            messagebox.showerror("Error", f'Error when deleting group: \n{e}')

    def _map_group_folder(self):
        name = self.group_file_var.get().strip()
        if not name:
            messagebox.showwarning("No group", "Select group first.")
            return
        folder = filedialog.askdirectory(title=f"Select folder for group '{name}'")
        if not folder:
            return
        folder = os.path.abspath(folder)
        lines = []
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if ":" not in line:
                        continue
                    k, _ = line.split(":", 1)
                    k = k.strip()
                    if k in (name, f"{name}.csv"):
                        continue
                    lines.append(line)
        lines.append(f"{name}:{folder}")
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + ("\n" if lines else ""))
            self._set_status(f"Mapped '{name}' → {folder}")
        except Exception as e:
            messagebox.showerror("Error", f"Error when write:\n{e}")
            return
        self._load_channels()

    def _check_for_updates(self):
        def worker():
            try:
                self._set_status("Checking for updates...")
                msg = check_and_update(UPDATE_MANIFEST, APP_VERSION, verify_hash=True)
                print(f"Update from {UPDATE_MANIFEST}")
                self._set_status(msg)
                if msg.startswith("Installed update"):
                    if messagebox.askyesno("Update installed", "Khởi động lại để áp dụng?"):
                        self._restart_app()
            except Exception as e:
                print(f"Update from {UPDATE_MANIFEST}")
                messagebox.showerror("Update error", str(e))
                self._set_status("Update failed.")
        threading.Thread(target=worker, daemon=True).start()

    def _restart_app(self):
        python = sys.executable
        script = os.path.abspath(sys.argv[0])
        args = sys.argv[1:]
        subprocess.Popen([python, script] + args, shell=False)
        self.destroy()
        sys.exit(0)

    def _open_concat_window(self):
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ghep music/concat_tool.py")
        if not os.path.exists(script_path):
            messagebox.showerror("Not found", f"can't find file: \n{script_path}")
            return
        subprocess.Popen([sys.executable, script_path], shell=False)

    def _open_manage_channel_window(self):
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manage_channel\data\manage_page.py")
        if not os.path.exists(script_path):
            messagebox.showerror("Not found", f"can't find file: \n{script_path}")
            return
        subprocess.Popen([sys.executable, script_path], shell=False)

    def __open_statistics_channel_window(self):
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thong_ke\crawl_data.py")
        if not os.path.exists(script_path):
            messagebox.showerror("Not found", f"can't find file: \n{script_path}")
            return
        subprocess.Popen([sys.executable, script_path], shell=False)

    def _auto_check_update(self):
        def worker():
            try:
                self._set_status("Checking for new version...")
                msg = check_and_update(UPDATE_MANIFEST, APP_VERSION, verify_hash=True)
                if msg.startswith("Installed update"):
                    self._set_status("Update successfully.")
                    if messagebox.askyesno("Notice", "Have new version to update, do you want to update ?"):
                        self._restart_app()
                elif "New version" in msg or "update available" in msg.lower():
                    self._set_status("Have new version")
                    if messagebox.askyesno("Have new version", f"{msg}\n\nDo you want to update?"):
                        try:
                            install_from_zip("update.zip")
                            self._set_status("Installed new version.")
                            if messagebox.askyesno("Done", "Updated restart app to apply ?"):
                                self._restart_app()
                        except Exception as e:
                            messagebox.showerror("Error", f"Can't update this version:\n{e}")
                else:
                    self._set_status("You are up to date")
            except Exception as e:
                self._set_status(f"Inspect the Eror: {e}")
                print("Update error:", e)
        threading.Thread(target=worker, daemon=True).start()

    def _generate_titles_descs(self):
        try:
            # fix nhỏ: self.group_file_var.get() (không phải self.group_file_var())
            topic = self.group_file_var.get().strip() or "Short videos youtube"
            prompt = f"Create 10 titles mesmerizing and 10 short description for {topic}"

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
            )
            text = response["choices"][0]["message"]["content"]
            self.txt_titles.delete("1.0", tk.END)
            self.txt_descs.delete("1.0", tk.END)
            self.txt_titles.insert(tk.END, text)
            self._set_status("Generated tiles and description.")
        except Exception as e:
            messagebox.showerror("Error", f"Error when generate content: {e}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
