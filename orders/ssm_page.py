import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkcalendar import DateEntry
import datetime, threading, time, requests, csv, os
import webbrowser
import os

API_URL = "https://smmstore.pro/api/v2"
CSV_PATH = "orders/orders.csv"
api_key_path = "orders/api_key.txt"
def get_api_key(interactive=True, force_edit=False, api_key_path = "orders/api_key.txt"):
    os.makedirs("orders", exist_ok=True)
    api_path = api_key_path
    if os.path.exists(api_path) and not force_edit: 
        with open(api_path, encoding="utf-8") as f:
            key = f.read().strip()
        if key:
            return key

    if not interactive:
        return ""

    root = tk.Toplevel()
    root.withdraw()

    old_key = ""
    if os.path.exists(api_path):
        with open(api_path, encoding="utf-8") as f:
            old_key = f.read().strip()

    key = simpledialog.askstring(
        "SMMStore API Key",
        "Enter your SMMStore API key:",
        show="*",
        initialvalue=old_key
    )
    if not key:
        messagebox.showwarning("Missing", "API key is required.")
        root.destroy()
        return ""

    with open(api_path, "w", encoding="utf-8") as f:
        f.write(key.strip())

    messagebox.showinfo("Saved", "API key saved successfully.")
    root.destroy()
    return key.strip()

def read_api_key(api_key_path = "orders/api_key.txt"):
    path = api_key_path
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip() #return api key
    return ""

def api_request(params: dict):
    key = read_api_key()
    if not key:
        return {"error": "Missing API key. Please configure it from menu."}
    params["key"] = key
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
        ttk.Label(self, text="📦 SMMStore Auto Scheduler",font=("Segoe UI", 16, "bold")).pack(pady=(2, 0))

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
        
        # ===== DRIP-FEED TOGGLE =====
        self.drip_var = tk.BooleanVar(value=False)
        ttk.Label(form, text="Drip-Feed:").grid(row=5, column=0, sticky="e", padx=(0, 6))

        # frame gộp toggle + runs + interval
        self.drip_container = ttk.Frame(form)
        self.drip_container.grid(row=5, column=1, columnspan=5, sticky="w")

        # toggle switch
        self._drip_switch = tk.Canvas(self.drip_container, width=46, height=24,
                                    highlightthickness=0, bd=0, cursor="hand2")
        self._drip_switch.pack(side="left", padx=(0, 10))
        self._drip_switch.bind("<Button-1>", lambda e: self._toggle_drip_feed())
        self._render_drip_feed_toggle()
        self._drip_switch.bind("<Enter>", lambda e: self._show_tip("Enable Drip-Feed: split order into multiple runs"))
        self._drip_switch.bind("<Leave>", lambda e: self._hide_tip())


        # runs + interval (ẩn mặc định)
        self.runs_var = tk.StringVar(value='')
        self.interval_var = tk.StringVar(value='')

        self.lbl_runs = ttk.Label(self.drip_container, text='Runs:')
        self.entry_runs = ttk.Entry(self.drip_container, textvariable=self.runs_var,
                                    width=8, justify="center")
        self.lbl_interval = ttk.Label(self.drip_container, text="Interval (min):")
        self.entry_interval = ttk.Entry(self.drip_container, textvariable=self.interval_var,
                                        width=8, justify="center")


        
        btn_frame = ttk.Frame(form)
        btn_frame.grid(row=4, column=6, columnspan=2, sticky="e")
        ttk.Button(btn_frame, text="Submit", command=self.add_schedule).pack(side="left", padx=(0, 4))

        # ===== QUEUE =====
        ttk.Label(self, text="🧾 Request Queue", font=("Segoe UI", 12, "bold")).pack(pady=(0, 2))
        columns = ("run_time", 'order_id', "service", "link", "quantity", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=10)
        for col in columns:
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, width=180 if col == "link" else 100, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 2))
        self.tree.bind("<Button-1>", self._on_tree_click)

        self.tree.tag_configure('st_queue',      foreground="#FBFF00")  # In Queue
        self.tree.tag_configure('st_processing', foreground="#0066FF")  # Processing/Unknown
        self.tree.tag_configure('st_completed',  foreground="#1CFD08")  # Completed (xanh)
        self.tree.tag_configure('st_partial',    foreground='#8A6D00')  # Partial
        self.tree.tag_configure('st_failed',     foreground="#FF0000")  # Failed/Cancelled (đỏ)
        self.tree.tag_configure('st_unknown',    foreground='#333333')

        #DELETE
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Delete", command=self._delete_selected)
        self.tree.bind('<Button-3>', self._show_context_menu)
        self.tree.bind('<Delete>', lambda e: self._delete_selected())


        # ===== DATA =====
        self.services_by_category = {}
        self.service_id_map = {}

        self.after(200, self.auto_get_balance)
        threading.Thread(target=self._load_services, daemon=True).start()
        self._load_csv()
        self._start_realtime_update()

    HEADERS = ("run_time","order_id","service","link","quantity","status","charge","remains")
    
    def _on_tree_click(self, event):
        """Mở link khi click vào cột Link"""
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return  # bỏ qua click ngoài ô
        col = self.tree.identify_column(event.x)
        if col != "#4":  
            return

        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        values = self.tree.item(row_id, "values")
        if len(values) >= 4:
            link = values[3].strip()
            if link.startswith("http"):
                webbrowser.open(link)
            else:
                messagebox.showinfo("Invalid Link", f"URL is not valid:\n{link}")
                
    def _status_to_tag(self, status_text: str) -> str:
        s = (status_text or "").lower()
        if 'completed' in s:
            return 'st_completed'
        if 'partial' in s:
            return 'st_partial'
        if 'cancel' in s or 'failed' in s or 'error' in s:
            return 'st_failed'
        if 'queue' in s:
            return 'st_queue'
        return 'st_processing'
    def _apply_status_tag(self, iid, status_text: str):
        tag = self._status_to_tag(status_text)
        self.tree.item(iid, tags=(tag,))

    def _ensure_row_keys(self, row: dict):
        for k in self.HEADERS:
            row.setdefault(k, "")

    def _set_tree_cells(self, run_time: str, **cols):
        col_names = list(self.tree["columns"])
        for iid in self.tree.get_children():
            vals = list(self.tree.item(iid, "values"))
            if vals and vals[0] == run_time:
                for k, v in cols.items():
                    if k in col_names:
                        idx = col_names.index(k)
                        while len(vals) < len(col_names):
                            vals.append("")
                        vals[idx] = v
                self.tree.item(iid, values=tuple(vals))
                if 'status' in cols:
                    self._apply_status_tag(iid, cols['status'])
                break

    # ===== Delete =====
    def _show_context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.menu.post(event.x_root, event.y_root)
    def _delete_selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo('Info', 'No item selected!!')
            return

        confirm = messagebox.askyesno('Confirm delete?','Do you want to delete selected item(s)?')
        if not confirm:
            return
        
        run_times_to_delete = [self.tree.item(iid, "values")[0] for iid in selection]
        for iid in selection:
            self.tree.delete(iid)
        
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, newline='', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
            new_rows = [r for r in rows if r.get('run_time') not in run_times_to_delete]
            # Bù cột trước khi ghi
            for r in new_rows:
                self._ensure_row_keys(r)
            with open(CSV_PATH,'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.HEADERS)
                writer.writeheader()
                writer.writerows(new_rows)

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
        if not selection:
            return
        # Cập nhật hiển thị
        self.cb_service.set(selection)
        self.search_var.set(selection)
        self.service_var.set(selection)  

        # Nếu selection nằm trong map, giữ id lại để submit
        if selection in self.service_id_map:
            service_id = self.service_id_map[selection]
        else:
            try:
                service_id = selection.split(" - ")[0].strip()
                self.service_id_map[selection] = service_id
            except Exception:
                service_id = None
        print(f"[DEBUG] Selected service: {selection} -> ID: {service_id}")


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
            self.balance_var.set("Error loading balance")
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
            service_id = self.service_id_map.get(self.cb_service.get())
            data = {
                "run_time": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                "service": service_id,
                "link": self.link_var.get(),
                "quantity": self.quantity_var.get(),
                "status": "In Queue"
            }
            self._append_to_csv(data)
            self._insert_tree(data)
            threading.Thread(target=self._send_order, args=(data,), daemon=True).start()
            return
        service_id = self.service_id_map.get(self.cb_service.get())
        data = {
            "run_time": run_time.strftime("%d/%m/%Y %H:%M"),
            "service": service_id,
            "link": self.link_var.get(),
            "quantity": self.quantity_var.get(),
            "status": "In Queue"
        }
        self._append_to_csv(data)
        self._insert_tree(data)
        threading.Thread(target=self._wait_and_send, args=(data,), daemon=True).start()

    def _wait_and_send(self, data):
        run_time = datetime.datetime.strptime(data["run_time"], "%d/%m/%Y %H:%M")
        delta = (run_time - datetime.datetime.now()).total_seconds()
        if delta > 0:
            time.sleep(delta)
        self._send_order(data)

    def _send_order(self, data):
        params = {
            "action": "add",
            "service": data["service"],
            "link": data["link"],
            "quantity": data["quantity"],
        }

        # Nếu bật drip-feed, thêm 2 tham số
        if self.drip_var.get():
            params["runs"] = self.runs_var.get()
            params["interval"] = self.interval_var.get()

        resp = api_request(params)
        if not isinstance(resp, dict) or 'error' in resp:
            self._update_status(data['run_time'], 'Failed')
            return
        order_id = str(resp.get('order', "")).strip()
        if not order_id:
            self._update_status(data['run_time'], 'Failed')
            return
        self._set_tree_cells(data['run_time'], order_id=order_id)
        self._update_order_status_in_csv(data['run_time'], order_id, status="In Queue",
                                         charge="", remains="")
        threading.Thread(target=self._track_order_status, args=(data['run_time'], order_id), daemon=True).start()
    
    def _track_order_status(self, run_time, order_id):
        while True:
            time.sleep(15)
            resp = api_request({'action':'status', 'order':order_id})
            if not isinstance(resp, dict):
                continue
            status =  resp.get('status', 'Unknown')
            charge = resp.get('charge', '?')
            remains = resp.get('remains', resp.get('remain', '?'))

            # Cập nhật UI (chỉ cột status)
            if status.lower() in {"completed"}:
                display_status = status
            else:
                display_status = f"{status} (remains: {remains})"

            # Cập nhật UI (chỉ cột status)
            self._set_tree_cells(run_time, status=display_status)
            # Ghi CSV đầy đủ trường
            self._update_order_status_in_csv(run_time, order_id, status, charge, remains)

            if status and status.lower() in {'completed', 'partial', 'cancelled', 'canceled'}:
                break

    def _update_order_status_in_csv(self, run_time, order_id, status, charge, remains):
        rows = []
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, newline='', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))

        for r in rows:
            if r.get('run_time') == run_time:
                r['status'] = status
                r['order_id'] = order_id
                r['charge'] = charge
                r['remains'] = remains
            self._ensure_row_keys(r)

        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.HEADERS)
            writer.writeheader()
            writer.writerows(rows)

    # ===== CSV =====
    def _append_to_csv(self, data):
        self._ensure_row_keys(data)
        exists = os.path.exists(CSV_PATH)
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.HEADERS)
            if not exists:
                writer.writeheader()
            writer.writerow(data)


    def _load_csv(self):
        if not os.path.exists(CSV_PATH):
            return
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self._ensure_row_keys(row)
                self._insert_tree(row)
                status = row["status"].lower()
                order_id = row.get("order_id", "").strip()

                if not order_id and "queue" in status:
                    threading.Thread(target=self._wait_and_send, args=(row,), daemon=True).start()
                elif order_id and not any(s in status for s in ["completed", "partial", "cancel", "failed"]):
                    threading.Thread(target=self._track_order_status, args=(row["run_time"], order_id), daemon=True).start()


    def _update_status(self, run_time, new_status):
        rows = []
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

        for r in rows:
            if r.get("run_time") == run_time:
                r["status"] = new_status
            self._ensure_row_keys(r)

        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.HEADERS)
            writer.writeheader()
            writer.writerows(rows)

        # Update đúng cột 'status' trên UI
        self._set_tree_cells(run_time, status=new_status)


    def _insert_tree(self, data):
        self._ensure_row_keys(data)
        tag = self._status_to_tag(data.get("status",""))
        self.tree.insert(
            "", "end",
            values=(
                data.get("run_time",""),
                data.get("order_id",""),
                data.get("service",""),
                data.get("link",""),
                data.get("quantity",""),
                data.get("status","")
            ),
            tags=(tag,)
        )

    def _start_realtime_update(self):
        self.after(3000, self._start_realtime_update)

    def _render_drip_feed_toggle(self):
        """Vẽ công tắc Drip-Feed"""
        if not hasattr(self, "_drip_switch"):
            return
        cv = self._drip_switch
        cv.delete("all")

        on = bool(self.drip_var.get())
        track = "#4CAF50" if on else "#FF6B6B"
        knob_x = 26 if on else 2

        # Nền 'pill'
        cv.create_oval(1, 1, 23, 23, fill=track, outline=track)
        cv.create_oval(23, 1, 45, 23, fill=track, outline=track)
        cv.create_rectangle(12, 1, 34, 23, fill=track, outline=track)

        # Nút trắng
        cv.create_oval(knob_x, 3, knob_x + 18, 21, fill="#FFFFFF", outline="#DDDDDD")


    def _toggle_drip_feed(self):
        self.drip_var.set(not self.drip_var.get())
        self._render_drip_feed_toggle()

        if self.drip_var.get():
            self.lbl_runs.pack(side="left", padx=(10, 2))
            self.entry_runs.pack(side="left")
            self.lbl_interval.pack(side="left", padx=(10, 2))
            self.entry_interval.pack(side="left")
        else:
            for w in [self.lbl_runs, self.entry_runs, self.lbl_interval, self.entry_interval]:
                w.pack_forget()

    def _show_tip(self, text):
        x, y = self.winfo_pointerxy()
        self.tip = tk.Toplevel(self)
        self.tip.wm_overrideredirect(True)
        self.tip.geometry(f"+{x+10}+{y+10}")
        label = ttk.Label(self.tip, text=text, background="#6c696d", relief="solid", borderwidth=1)
        label.pack(ipadx=4, ipady=2)

    def _hide_tip(self):
        if hasattr(self, "tip"):
            self.tip.destroy()
            del self.tip

