import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
import datetime, threading, time, requests, csv, os

API_URL = "https://smmstore.pro/api/v2"
API_KEY = "0f06dab474e72deb25b69026871433af"
CSV_PATH = "orders/orders.csv"


def api_request(params: dict):
    params["key"] = API_KEY
    try:
        r = requests.post(API_URL, data=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


class OrdersPage(tk.Frame):
    def __init__(self, parent=None):
        super().__init__(parent)

        # ===== TITLE =====
        ttk.Label(self, text="📦 SMMStore Auto Scheduler",
                  font=("Segoe UI", 16, "bold")).pack(pady=(2, 0))

        # ===== BALANCE =====
        self.balance_var = tk.StringVar(value="Loading balance...")
        ttk.Label(self, textvariable=self.balance_var,
                  font=("Segoe UI", 12, "bold"),
                  foreground="#0078D4").pack(pady=(0, 2))

        # ===== FORM =====
        form = ttk.LabelFrame(self, text="Order Information", padding=2)
        form.pack(fill="x", expand=False, padx=10, pady=(0, 2))

        # Cấu hình cột lưới
        for c in range(8):
            form.grid_columnconfigure(c, weight=0)
        form.grid_columnconfigure(1, weight=1, minsize=520)

        # ===== SEARCH BAR (HÀNG 0) =====
        ttk.Label(form, text="Search Bar:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(form, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, columnspan=6, sticky="we", pady=(0, 3))

        self.search_entry = search_entry

        # realtime + Enter
        self.search_var.trace_add('write', lambda *_: self._live_search_service())
        search_entry.bind("<Return>", lambda event: self._search_service())
        ttk.Button(form, text="Clear", command=self._clear_search).grid(row=0, column=7, sticky="e", padx=(5, 0))

        # ===== CATEGORY + DATE + TIME (HÀNG 1) =====
        ttk.Label(form, text="Category:").grid(row=1, column=0, sticky="w")
        self.category_var = tk.StringVar()
        self.cb_category = ttk.Combobox(form, textvariable=self.category_var, state="readonly")
        self.cb_category.grid(row=1, column=1, columnspan=2, sticky="we", padx=(0, 12))
        self.cb_category.bind("<<ComboboxSelected>>", self._on_category_selected)

        ttk.Label(form, text="Run Date:").grid(row=1, column=3, sticky="e", padx=(5, 2))
        self.date_entry = DateEntry(form, width=12, date_pattern="mm/dd/yyyy", state="readonly")
        self.date_entry.set_date(datetime.date.today())
        self.date_entry.grid(row=1, column=4, sticky="w")

        ttk.Label(form, text="Time:").grid(row=1, column=5, sticky="e", padx=(5, 2))
        self.hour_var = tk.StringVar(value=f"{datetime.datetime.now().hour:02d}")
        self.min_var = tk.StringVar(value=f"{datetime.datetime.now().minute:02d}")
        time_frame = ttk.Frame(form)
        time_frame.grid(row=1, column=6, sticky="w")
        
        # ====== TIME SELECT ======
        def select_all(event):
            widget = event.widget
            widget.after(1, lambda: widget.selection_range(0, tk.END))

        hour_box = ttk.Combobox(
            time_frame,
            values=[f"{i:02d}" for i in range(24)],
            width=3,
            textvariable=self.hour_var,
            state="normal"
        )
        hour_box.pack(side="left")
        hour_box.bind("<FocusIn>", select_all)
        hour_box.bind("<Button-1>", select_all)

        ttk.Label(time_frame, text=":").pack(side="left")

        min_box = ttk.Combobox(
            time_frame,
            values=[f"{i:02d}" for i in range(0, 60, 5)],
            width=3,
            textvariable=self.min_var,
            state="normal"
        )
        min_box.pack(side="left")
        min_box.bind("<FocusIn>", select_all)
        min_box.bind("<Button-1>", select_all)


        # ===== SERVICE =====
        ttk.Label(form, text="Service:").grid(row=2, column=0, sticky="w")
        self.service_var = tk.StringVar()
        self.cb_service = ttk.Combobox(form, textvariable=self.service_var, state="readonly")
        self.cb_service.grid(row=2, column=1, columnspan=7, sticky="we", pady=(0, 2))

        # ===== LINK =====
        ttk.Label(form, text="Link:").grid(row=3, column=0, sticky="w")
        self.link_var = tk.StringVar()
        self.link_entry = ttk.Entry(form, textvariable=self.link_var)
        self.link_entry.grid(row=3, column=1, columnspan=7, sticky="we", pady=(0, 2))

        # ===== QUANTITY + BUTTONS =====
        ttk.Label(form, text="Quantity:").grid(row=4, column=0, sticky="w")
        self.quantity_var = tk.StringVar(value="1000")
        ttk.Entry(form, textvariable=self.quantity_var, width=15).grid(row=4, column=1, sticky="w", padx=(0, 8))

        btn_frame = ttk.Frame(form)
        btn_frame.grid(row=4, column=5, columnspan=2, sticky="e")
        ttk.Button(btn_frame, text="Submit", command=self.add_schedule).pack(side="left", padx=(0, 4))
        ttk.Button(btn_frame, text="Send Now", command=self.send_now).pack(side="left")

        # ===== QUEUE =====
        ttk.Label(self, text="🧾 Request Queue", font=("Segoe UI", 12, "bold")).pack(pady=(0, 2))
        columns = ("run_time", "service", "link", "quantity", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=10)
        for col in columns:
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, width=180 if col == "link" else 100, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 2))

        # ===== DATA =====
        self.services_by_category = {}
        self.service_id_map = {}

        self.after(200, self.auto_get_balance)
        threading.Thread(target=self._load_services, daemon=True).start()
        self._load_csv()
        self._start_realtime_update()

    # ===== LIVE SEARCH =====

    def _live_search_service(self, *_):
        if hasattr(self, "_search_after_id"):
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(200, self._show_suggestions)

    def _show_suggestions(self):
        keyword = self.search_var.get().strip().lower()
        if not keyword:
            if hasattr(self, "suggest_listbox"):
                self.suggest_listbox.place_forget()
            return

        # Lọc danh sách gợi ý
        filtered = []
        self.service_id_map.clear()
        for cat, services in self.services_by_category.items():
            for s in services:
                name = f"{s['service']} - {s['name']}"
                if keyword in str(s['service']).lower() or keyword in s['name'].lower():
                    filtered.append(name)
                    self.service_id_map[name] = s["service"]

        # Nếu không có kết quả -> ẩn
        if not filtered:
            if hasattr(self, "suggest_listbox"):
                self.suggest_listbox.place_forget()
            return

        # Tạo Listbox nếu chưa có
        if not hasattr(self, "suggest_listbox"):
            style = ttk.Style()
            entry_bg = style.lookup("TEntry", "fieldbackground", default="#2D2D30")
            entry_fg = style.lookup("TEntry", "foreground", default="#FFFFFF")
            select_bg = style.lookup("TCombobox", "selectbackground", default="#0078D4")
            select_fg = style.lookup("TCombobox", "selectforeground", default="#FFFFFF")

            self.suggest_listbox = tk.Listbox(
                self,
                height=8,
                activestyle="none",
                font=("Segoe UI", 10),
                bg=entry_bg,
                fg=entry_fg,
                highlightthickness=1,
                highlightbackground=entry_bg,
                relief="solid",
                borderwidth=1,
                selectbackground=select_bg,
                selectforeground=select_fg,
                cursor="hand2",
            )

            # --- Gắn sự kiện ---
            self.suggest_listbox.bind("<ButtonRelease-1>", self._select_suggestion)
            self.suggest_listbox.bind("<Escape>", lambda e: self.suggest_listbox.place_forget())
            self.suggest_listbox.bind("<Motion>", self._on_hover)
            self.suggest_listbox.bind("<Leave>", lambda e: self.suggest_listbox.selection_clear(0, tk.END))
            self.search_entry.bind("<Down>", self._focus_suggest_listbox)
            self.search_entry.bind("<Up>", self._focus_suggest_listbox)
            self.search_entry.bind("<Return>", self._enter_select)

        # Cập nhật danh sách
        self.suggest_listbox.delete(0, tk.END)
        for item in filtered[:100]:
            self.suggest_listbox.insert(tk.END, item)

        # Lấy vị trí Entry để popup
        x = self.search_entry.winfo_rootx() - self.winfo_rootx()
        y = self.search_entry.winfo_rooty() - self.winfo_rooty() + self.search_entry.winfo_height()
        w = self.search_entry.winfo_width()
        self.suggest_listbox.place(x=x, y=y, width=w)
        self.filtered_items = filtered  # Lưu lại danh sách hiển thị

    def _on_hover(self, event):
        """Highlight item khi rê chuột"""
        if not hasattr(self, "suggest_listbox"):
            return
        index = self.suggest_listbox.nearest(event.y)
        self.suggest_listbox.selection_clear(0, tk.END)
        self.suggest_listbox.selection_set(index)
        self.suggest_listbox.activate(index)

    def _focus_suggest_listbox(self, event):
        """Dùng phím ↑ ↓ để điều hướng"""
        if not hasattr(self, "suggest_listbox") or not self.suggest_listbox.winfo_ismapped():
            return "break"

        sel = self.suggest_listbox.curselection()
        if not sel:
            idx = 0 if event.keysym == "Down" else tk.END
        else:
            idx = sel[0] + (1 if event.keysym == "Down" else -1)
        idx = max(0, min(idx, self.suggest_listbox.size() - 1))
        self.suggest_listbox.selection_clear(0, tk.END)
        self.suggest_listbox.selection_set(idx)
        self.suggest_listbox.activate(idx)
        self.suggest_listbox.see(idx)
        return "break"

    def _enter_select(self, event):
        """Khi nhấn Enter trong ô tìm kiếm"""
        if hasattr(self, "suggest_listbox") and self.suggest_listbox.winfo_ismapped():
            sel = self.suggest_listbox.curselection()
            if sel:
                selection = self.suggest_listbox.get(sel[0])
                self._apply_selection(selection)
                self.suggest_listbox.place_forget()
                return "break"
        self._search_service()

    def _select_suggestion(self, event):
        """Chọn bằng chuột"""
        if not hasattr(self, "suggest_listbox"):
            return
        selection = self.suggest_listbox.get(tk.ACTIVE)
        self._apply_selection(selection)
        self.suggest_listbox.place_forget()

    def _apply_selection(self, selection):
        """Cập nhật khi chọn gợi ý"""
        if not selection:
            return
        self.cb_service.set(selection)
        self.search_var.set(selection)




    def _search_service(self):
        self._live_search_service()

    def _clear_search(self):
        self.search_var.set("")
        self._on_category_selected()

    # ===== BALANCE =====
    def auto_get_balance(self):
        threading.Thread(target=self._balance_thread, daemon=True).start()

    def _balance_thread(self):
        resp = api_request({"action": "balance"})
        if isinstance(resp, dict) and "error" in resp:
            self.balance_var.set("Error fetching balance")
        else:
            bal = resp.get("balance", "?")
            cur = resp.get("currency", "")
            self.balance_var.set(f"💰 Balance: {bal} {cur}")

    # ===== SERVICES =====
    def _load_services(self):
        resp = api_request({"action": "services"})
        if isinstance(resp, dict) and "error" in resp:
            self.services_by_category = {"Unknown": []}
            return
        data = resp if isinstance(resp, list) else resp.get("services", [])
        cats = {}
        for s in data:
            cats.setdefault(s.get("category", "Unknown"), []).append(s)
        self.services_by_category = cats
        self.cb_category["values"] = list(cats.keys())
        if cats:
            first = list(cats.keys())[0]
            self.category_var.set(first)
            self._on_category_selected()

    def _on_category_selected(self, *_):
        cat = self.category_var.get()
        services = self.services_by_category.get(cat, [])
        names = []
        self.service_id_map.clear()
        for s in services:
            name = f"{s['service']} - {s['name']}"
            names.append(name)
            self.service_id_map[name] = s["service"]
        self.cb_service["values"] = names
        if names:
            self.cb_service.set(names[0])

    # ===== SCHEDULE =====
    def add_schedule(self):
        if not self.cb_service.get():
            messagebox.showwarning("Missing", "Please select a service.")
            return
        d = self.date_entry.get_date()
        h, m = int(self.hour_var.get()), int(self.min_var.get())
        run_time = datetime.datetime(d.year, d.month, d.day, h, m)
        if run_time <= datetime.datetime.now():
            messagebox.showwarning("Invalid Time", "Run time must be in the future.")
            return
        service_id = self.service_id_map.get(self.cb_service.get())
        data = {
            "run_time": run_time.strftime("%Y-%m-%d %H:%M"),
            "service": service_id,
            "link": self.link_var.get(),
            "quantity": self.quantity_var.get(),
            "status": "In Queue"
        }
        self._append_to_csv(data)
        self._insert_tree(data)
        threading.Thread(target=self._wait_and_send, args=(data,), daemon=True).start()

    def send_now(self):
        if not self.cb_service.get():
            messagebox.showwarning("Missing", "Please select a service.")
            return
        service_id = self.service_id_map.get(self.cb_service.get())
        data = {
            "run_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "service": service_id,
            "link": self.link_var.get(),
            "quantity": self.quantity_var.get(),
            "status": "In Queue"
        }
        self._append_to_csv(data)
        self._insert_tree(data)
        threading.Thread(target=self._send_order, args=(data,), daemon=True).start()

    def _wait_and_send(self, data):
        run_time = datetime.datetime.strptime(data["run_time"], "%Y-%m-%d %H:%M")
        delta = (run_time - datetime.datetime.now()).total_seconds()
        if delta > 0:
            time.sleep(delta)
        self._send_order(data)

    def _send_order(self, data):
        resp = api_request({
            "action": "add",
            "service": data["service"],
            "link": data["link"],
            "quantity": data["quantity"],
        })
        status = "Done" if isinstance(resp, dict) and "error" not in resp else "Failed"
        self._update_status(data["run_time"], status)

    # ===== CSV =====
    def _append_to_csv(self, data):
        exists = os.path.exists(CSV_PATH)
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["run_time", "service", "link", "quantity", "status"])
            if not exists:
                writer.writeheader()
            writer.writerow(data)

    def _load_csv(self):
        if not os.path.exists(CSV_PATH):
            return
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self._insert_tree(row)
                if row["status"] == "In Queue":
                    threading.Thread(target=self._wait_and_send, args=(row,), daemon=True).start()

    def _update_status(self, run_time, new_status):
        rows = []
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        for r in rows:
            if r["run_time"] == run_time:
                r["status"] = new_status
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["run_time", "service", "link", "quantity", "status"])
            writer.writeheader()
            writer.writerows(rows)
        # Update UI
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, "values")
            if vals[0] == run_time:
                new_vals = (*vals[:4], new_status)
                self.tree.item(iid, values=new_vals)
                break

    def _insert_tree(self, data):
        self.tree.insert("", "end", values=(data["run_time"], data["service"], data["link"],
                                            data["quantity"], data["status"]))

    def _start_realtime_update(self):
        self.after(3000, self._start_realtime_update)
