
import os, sys, threading, datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd

try:
    from .data_crawler_module import (
        crawl_data, clean_data, replace_link_with_channel,
        extract_phpsessid_dict, read_cookie_from_txt,
        COOKIE_TXT, CLEAN_CSV_PATH
    )
except Exception:
    from data_crawler_module import (
        crawl_data, clean_data, replace_link_with_channel,
        extract_phpsessid_dict, read_cookie_from_txt,
        COOKIE_TXT, CLEAN_CSV_PATH
    )


class TextRedirector:
    """
    Redirect print → 2 Text widget.
    ĐÃ LÀM THREAD-SAFE: mọi thao tác Tk đều chạy bằng .after(0, ...)
    """
    def __init__(self, process_widget: tk.Text, stat_widget: tk.Text):
        self.process_widget = process_widget
        self.stat_widget = stat_widget

        for widget in (self.process_widget, self.stat_widget):
            widget.tag_config("INFO", foreground="#00ff9f")
            widget.tag_config("ERROR", foreground="#ff5555")
            widget.tag_config("WARNING", foreground="#ffcc00")
            widget.tag_config("TITLE", foreground="#00bfff", font=("Consolas", 10, "bold"))

    def _append(self, widget: tk.Text, line: str, tag: str):
        def do():
            ts = datetime.datetime.now().strftime("[%H:%M:%S] ")
            widget.insert("end", ts, "INFO")
            widget.insert("end", line + "\n", tag)
            widget.see("end")
        widget.after(0, do)

    def write(self, message: str):
        tag = "INFO"
        if "[LỖI]" in message or "Error" in message:
            tag = "ERROR"
        elif "CẢNH BÁO" in message or "Warning" in message:
            tag = "WARNING"
        elif "===" in message:
            tag = "TITLE"

        target_widget = self.process_widget
        if any(kw in message for kw in ("Chi phí", "Charge", "Tổng", "Unidentified", "$ ")):
            target_widget = self.stat_widget

        for line in message.splitlines():
            if not line.strip():
                self._append(target_widget, "", "INFO")
            else:
                self._append(target_widget, line, tag)

    def flush(self):
        pass


class StatisticsPage(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)  # khối bảng + logs nở

        # Styles (nhẹ)
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=22, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))

        # ==== Thanh chọn tháng/năm ====
        top_frame = ttk.Frame(self, padding=10)
        top_frame.grid(row=0, column=0, sticky="ew")

        ttk.Label(top_frame, text="Month:", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=5)
        self.month_var = tk.StringVar(value=datetime.datetime.now().strftime("%m"))
        month_cb = ttk.Combobox(top_frame, textvariable=self.month_var, width=5, state="readonly",
                                values=[f"{i:02d}" for i in range(1, 13)])
        month_cb.grid(row=0, column=1, padx=5)

        ttk.Label(top_frame, text="Year:", font=("Segoe UI", 10)).grid(row=0, column=2, sticky="w", padx=5)
        current_year = datetime.datetime.now().year
        self.year_var = tk.StringVar(value=str(current_year))
        year_cb = ttk.Combobox(top_frame, textvariable=self.year_var, width=6, state="readonly",
                               values=[str(y) for y in range(current_year - 3, current_year + 2)])
        year_cb.grid(row=0, column=3, padx=5)

        ttk.Button(top_frame, text="Update data", command=self._run_process).grid(row=0, column=4, padx=15)

        month_cb.bind("<<ComboboxSelected>>", self._on_month_year_change)
        year_cb.bind("<<ComboboxSelected>>", self._on_month_year_change)

        # ==== Ô nhập cookie & nút extract ====
        cookie_frame = ttk.LabelFrame(self, text="Paste here to get cookies", padding=10)
        cookie_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.cookie_entry = tk.Text(cookie_frame, height=4, wrap="word", font=("Consolas", 9))
        self.cookie_entry.pack(side="left", expand=True, fill="x")

        extract_btn = ttk.Button(cookie_frame, text="Extract PHPSESSID", command=self._extract_cookie_action)
        extract_btn.pack(side="right", padx=10)

        self.cookie_status_label = ttk.Label(self, text="Cookies in use: (chưa có)", wraplength=1000)
        self.cookie_status_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self._update_cookie_label()

        # ==== Khu vực bảng ====
        frame_table = ttk.Frame(self, padding=(10, 5))
        frame_table.grid(row=3, column=0, sticky="nsew")
        frame_table.rowconfigure(0, weight=1)
        frame_table.columnconfigure(0, weight=1)

        columns = ["ID", "Date", "Link", "Charge", "Start count", "Quantity", "Service", "Status", "Remains"]
        self.tree = ttk.Treeview(frame_table, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120 if col != "Link" else 300, anchor="w")

        scroll_y = ttk.Scrollbar(frame_table, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(frame_table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        # ==== Hai vùng log song song ====
        log_frame = ttk.LabelFrame(self, text="Log", padding=5)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.columnconfigure(1, weight=1)
        log_frame.rowconfigure(1, weight=1)

        ttk.Label(log_frame, text="📜 Process log", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(log_frame, text="📊 Statistics", font=("Segoe UI", 10, "bold")).grid(row=0, column=1, sticky="w", padx=5)

        self.process_text = tk.Text(log_frame, height=14, wrap="word", font=("Consolas", 9),
                                    bg="#1e1e1e", fg="#dcdcdc", insertbackground="white")
        self.process_text.grid(row=1, column=0, sticky="nsew", padx=(0, 5))

        self.stat_text = tk.Text(log_frame, height=14, wrap="word", font=("Consolas", 9),
                                 bg="#1e1e1e", fg="#dcdcdc", insertbackground="white")
        self.stat_text.grid(row=1, column=1, sticky="nsew", padx=(5, 0))

        self.redirector = TextRedirector(self.process_text, self.stat_text)

        # Count label
        self.count_label = ttk.Label(self, text="Haven't loaded data yet", font=("Segoe UI", 9, "italic"), padding=5)
        self.count_label.grid(row=5, column=0, sticky="e")

        # Hiển thị tháng hiện tại
        self._on_month_year_change()

    # ---------- Helpers ----------
    def _month_str(self):
        y = self.year_var.get()
        m = self.month_var.get()
        return f"{y}-{int(m):02d}"

    def _info(self, title, msg):
        self.after(0, lambda: messagebox.showinfo(title, msg, parent=self))

    def _error(self, title, msg):
        self.after(0, lambda: messagebox.showerror(title, msg, parent=self))

    # ---------- Actions ----------
    def _run_process(self):
        year = self.year_var.get()
        month = self.month_var.get()
        if not year or not month:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn tháng và năm!", parent=self)
            return

        month_str = self._month_str()

        # clear logs
        self.process_text.delete("1.0", "end")
        self.stat_text.delete("1.0", "end")

        t = threading.Thread(target=self._process_worker, args=(month_str,), daemon=True)
        t.start()

    def _process_worker(self, month_str: str):
        """Chạy trong thread riêng, redirect stdout/stderr tạm thời."""
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = self.redirector
        sys.stderr = self.redirector
        try:
            print(f"=== BẮT ĐẦU XỬ LÝ DỮ LIỆU CHO THÁNG {month_str} ===\n")

            crawl_data()
            clean_data()

            df = pd.read_csv("thong_ke/data/orders_clean.csv", encoding="utf-8")
            replace_link_with_channel(df, month_str)

            print(f"\nĐã xử lý dữ liệu cho tháng {month_str}\n")
            self.after(0, lambda: self._load_data(month_str))
            self._info("Hoàn tất", f"Đã xử lý dữ liệu cho tháng {month_str}")
        except Exception as e:
            self._error("Lỗi", str(e))
            print(f"[LỖI] {e}")
        finally:
            sys.stdout = old_out
            sys.stderr = old_err

    def _load_data(self, month_str: str = None):
        """Đọc CSV và hiển thị dữ liệu theo tháng đã chọn."""
        if month_str is None:
            month_str = self._month_str()

        try:
            file_path = f"thong_ke/data/orders_with_channels_{month_str}.csv"
            if not os.path.exists(file_path):
                file_path = CLEAN_CSV_PATH
            df = pd.read_csv(file_path, encoding="utf-8-sig")
        except Exception as e:
            print("Lỗi đọc file", str(e))
            self.redirector.write(f"[LỖI] Không đọc được file: {e}\n")
            return

        if "Date" not in df.columns:
            self.redirector.write("Lỗi", "Không tìm thấy cột 'Date' trong file CSV.")
            return

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df[df["Date"].dt.strftime("%Y-%m") == month_str]

        # dọn bảng
        for row in self.tree.get_children():
            self.tree.delete(row)

        # sort & add
        df = df.sort_values(by="Date", ascending=False)
        for _, row in df.iterrows():
            self.tree.insert("", "end", values=list(row.values))

        self.count_label.config(text=f"{len(df)} lines")

        # === Thống kê tổng charge theo kênh ===
        try:
            df["Charge"] = pd.to_numeric(df["Charge"], errors="coerce").fillna(0)
            df["Link"] = df["Link"].fillna("").replace("", "Unidentified")
            total_by_channel = df.groupby("Link")["Charge"].sum().sort_values(ascending=False)
            total_sum = df["Charge"].sum()

            self.redirector.write("\n=== Thống kê tổng Chi phí theo kênh ===")
            for link, charge in total_by_channel.items():
                self.redirector.write(f"{link:50} : $ {charge:,.2f}")
            self.redirector.write(f"\nTổng toàn bộ Chi phí: $ {total_sum:,.2f}\n")
        except Exception as e:
            self.redirector.write(f"[CẢNH BÁO] Không tính được tổng chi phí: {e}")

    # ---------- Cookie ----------
    def _extract_cookie_action(self):
        raw_cookie = self.cookie_entry.get("1.0", "end").strip()
        if not raw_cookie:
            messagebox.showwarning("Thiếu cookie", "Vui lòng nhập chuỗi cookie vào ô bên trên!", parent=self)
            return

        try:
            cookies = extract_phpsessid_dict(raw_cookie)
            self.redirector.write(f"\nKết quả extract cookie:\n{cookies}\n")

            save_path = os.path.join(os.getcwd(), COOKIE_TXT)
            with open(save_path, "w", encoding="utf-8") as f:
                for k, v in cookies.items():
                    f.write(f"{k}={v}\n")

            self._info(
                "Kết quả",
                f"Đã lấy PHPSESSID:\n{cookies}\n\nĐã lưu tại:\n{save_path}"
            )
            self._update_cookie_label()
        except Exception as e:
            self.redirector.write(f"[LỖI] Khi extract cookie: {e}")
            self._error("Lỗi", str(e))

    def _update_cookie_label(self):
        try:
            cookies = read_cookie_from_txt()
            display = "; ".join([f"{k}={v}" for k, v in cookies.items()]) if cookies else "Chưa có cookies trong bộ nhớ"
        except FileNotFoundError:
            display = "⚠️ Chưa có file cookie.txt"
        except Exception as e:
            display = f"Lỗi khi đọc cookies: {e}"

        self.cookie_status_label.config(text=f"Cookies hiện tại: {display}")

    # ---------- Events ----------
    def _on_month_year_change(self, event=None):
        self._load_data(self._month_str())
