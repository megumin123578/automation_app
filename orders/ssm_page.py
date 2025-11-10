import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
import datetime, threading, time, requests, csv, os

API_URL = "https://smmstore.pro/api/v2"
API_KEY = "0f06dab474e72deb25b69026871433af"
CSV_PATH = "orders/orders.csv"


def api_request(params: dict):
    """Gửi request POST đến SMMStore API."""
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

        ttk.Label(self, text="📦 SMMStore Auto Scheduler", font=("Segoe UI", 16, "bold")).pack(pady=8)

        # ========== BALANCE ==========
        self.balance_var = tk.StringVar(value="Fetching balance...")
        ttk.Label(self, textvariable=self.balance_var, font=("Segoe UI", 12, "bold"), foreground="#0078D4").pack(pady=(0, 10))

        # ========== INPUT AREA ==========
        form = ttk.LabelFrame(self, text="Order Information", padding=12)
        form.pack(fill="x", padx=10)

        # --- Category + Date + Time ---
        ttk.Label(form, text="Category:").grid(row=0, column=0, sticky="w", pady=3)
        self.category_var = tk.StringVar()
        self.cb_category = ttk.Combobox(form, textvariable=self.category_var, width=120, state="readonly")
        self.cb_category.grid(row=0, column=1, sticky="w")
        self.cb_category.bind("<<ComboboxSelected>>", self._on_category_selected)

        ttk.Label(form, text="Run Date:").grid(row=0, column=2, sticky="e", padx=5)
        self.date_entry = DateEntry(form, width=12, date_pattern="mm/dd/yyyy", state="readonly")
        self.date_entry.set_date(datetime.date.today())
        self.date_entry.grid(row=0, column=3, sticky="w")

        ttk.Label(form, text="Time:").grid(row=0, column=4, sticky="e", padx=5)
        self.hour_var = tk.StringVar(value=f"{datetime.datetime.now().hour:02d}")
        self.min_var = tk.StringVar(value=f"{datetime.datetime.now().minute:02d}")
        ttk.Combobox(form, values=[f"{i:02d}" for i in range(24)], width=3, textvariable=self.hour_var,
                    state="readonly").grid(row=0, column=5, sticky="w")
        ttk.Label(form, text=":").grid(row=0, column=6)
        ttk.Combobox(form, values=[f"{i:02d}" for i in range(0, 60, 5)], width=3, textvariable=self.min_var,
                    state="readonly").grid(row=0, column=7, sticky="w")

        # --- Service ---
        ttk.Label(form, text="Service:").grid(row=1, column=0, sticky="w", pady=3)
        self.service_var = tk.StringVar()
        self.cb_service = ttk.Combobox(form, textvariable=self.service_var, width=120, state="readonly")
        self.cb_service.grid(row=1, column=1, sticky="w", columnspan=6)

        # --- Link ---
        ttk.Label(form, text="Link:").grid(row=2, column=0, sticky="w", pady=3)
        self.link_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.link_var, width=120).grid(row=2, column=1, columnspan=6, pady=3, sticky="w")

        # --- Quantity ---
        ttk.Label(form, text="Quantity:").grid(row=3, column=0, sticky="w", pady=3)
        self.quantity_var = tk.StringVar(value="1000")
        ttk.Entry(form, textvariable=self.quantity_var, width=15).grid(row=3, column=1, sticky="w")



        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="➕ Add Schedule", command=self.add_schedule).grid(row=0, column=0, padx=8)
        ttk.Button(btn_frame, text="🚀 Send Now", command=self.send_now).grid(row=0, column=1, padx=8)

        # ========== TABLE ==========
        ttk.Label(self, text="🧾 Request Queue", font=("Segoe UI", 12, "bold")).pack(pady=(5, 0))
        columns = ("run_time", "service", "link", "quantity", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=10)
        for col in columns:
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, width=180 if col == "link" else 100, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # ========== DATA ==========
        self.services_by_category = {}
        self.service_id_map = {}

        self.after(200, self.auto_get_balance)
        threading.Thread(target=self._load_services, daemon=True).start()
        self._load_csv()
        self._start_realtime_update()

    # ========== API BALANCE ==========
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

    # ========== LOAD SERVICES ==========
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

    # ========== SCHEDULES ==========
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

    # ========== CSV HANDLERS ==========
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
        # Update CSV
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
        """Tự động cập nhật trạng thái Done/Failed trong bảng mỗi 3 giây."""
        self.after(3000, self._start_realtime_update)
