import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import pandas as pd
import os, sys
from data_crawler_module import *
import threading


# === Redirect print ra 2 Text widget riêng biệt ===
class TextRedirector:
    def __init__(self, process_widget, stat_widget):
        self.process_widget = process_widget
        self.stat_widget = stat_widget

        for widget in (self.process_widget, self.stat_widget):
            widget.tag_config("INFO", foreground="#00ff9f")
            widget.tag_config("ERROR", foreground="#ff5555")
            widget.tag_config("WARNING", foreground="#ffcc00")
            widget.tag_config("TITLE", foreground="#00bfff", font=("Consolas", 10, "bold"))

    def write(self, message):
        tag = "INFO"
        if "[LỖI]" in message or "Error" in message:
            tag = "ERROR"
        elif "CẢNH BÁO" in message or "Warning" in message:
            tag = "WARNING"
        elif "===" in message:
            tag = "TITLE"

        # Chọn log bên nào hiển thị
        target_widget = self.process_widget
        if any(kw in message for kw in ("Chi phí", "Charge", "Tổng", "Unidentified", "$ ")):
            target_widget = self.stat_widget

        # Ghi log có timestamp
        for line in message.splitlines():
            if not line.strip():
                target_widget.insert("end", "\n")
                continue
            timestamp = datetime.datetime.now().strftime("[%H:%M:%S] ")
            target_widget.insert("end", timestamp, "INFO")
            target_widget.insert("end", line + "\n", tag)
            target_widget.see("end")

    def flush(self):
        pass


def run_process():
    year = year_var.get()
    month = month_var.get()
    if not year or not month:
        messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn tháng và năm!")
        return

    month_str = f"{year}-{int(month):02d}"

    process_text.delete("1.0", "end")
    stat_text.delete("1.0", "end")
    root.after(100, lambda: process_text.yview_moveto(0))
    thread = threading.Thread(target=process_worker, args=(month_str,), daemon=True)
    thread.start()


def process_worker(month_str):
    """Chạy trong thread riêng, log realtime"""
    try:
        print(f"=== BẮT ĐẦU XỬ LÝ DỮ LIỆU CHO THÁNG {month_str} ===\n")

        crawl_data()
        clean_data()

        df = pd.read_csv("statistics/data/orders_clean.csv", encoding="utf-8")
        replace_link_with_channel(df, month_str)

        print(f"\nĐã xử lý dữ liệu cho tháng {month_str}")
        load_data(month_str)

        messagebox.showinfo("Hoàn tất", f"Đã xử lý dữ liệu cho tháng {month_str}")
    except Exception as e:
        messagebox.showerror("Lỗi", str(e))
        print(f"[LỖI] {e}")



def load_data(month_str=None):
    """Đọc CSV và hiển thị dữ liệu theo tháng đã chọn"""
    try:
        file_path = f"statistics/data/orders_with_channels_{month_str}.csv"
        if not os.path.exists(file_path):
            file_path = CLEAN_CSV_PATH

        df = pd.read_csv(file_path, encoding="utf-8-sig")
    except Exception as e:
        messagebox.showerror("Lỗi đọc file", str(e))
        print(f"[LỖI] Không đọc được file: {e}")
        return

    if "Date" not in df.columns:
        messagebox.showerror("Lỗi", "Không tìm thấy cột 'Date' trong file CSV.")
        return

    # Lọc theo tháng
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df[df["Date"].dt.strftime("%Y-%m") == month_str]

    # Xóa dữ liệu cũ
    for row in tree.get_children():
        tree.delete(row)
    
    #sort
    df = df.sort_values(by="Date", ascending=False)

    # Thêm dữ liệu mới
    for _, row in df.iterrows():
        tree.insert("", "end", values=list(row.values))

    count_label.config(text=f"Hiển thị {len(df)} dòng dữ liệu cho {month_str}")

    # === Thống kê tổng charge theo kênh ===
    try:
        df["Charge"] = pd.to_numeric(df["Charge"], errors="coerce").fillna(0)
        df["Link"] = df["Link"].fillna("").replace("", "Unidentified")
        total_by_channel = df.groupby("Link")["Charge"].sum().sort_values(ascending=False)
        total_sum = df["Charge"].sum()

        print("\n=== Thống kê tổng Chi phí theo kênh ===")
        for link, charge in total_by_channel.items():
            print(f"{link:50} : $ {charge:,.2f}")
        print(f"\nTổng toàn bộ Chi phí: $ {total_sum:,.2f}\n")

    except Exception as e:
        print(f"[CẢNH BÁO] Không tính được tổng chi phí: {e}")


def extract_cookie_action():#
    """Xử lý nút Extract PHPSESSID"""
    raw_cookie = cookie_entry.get("1.0", "end").strip()
    if not raw_cookie:
        messagebox.showwarning("Thiếu cookie", "Vui lòng nhập chuỗi cookie vào ô bên trên!")
        return

    try:
        cookies = extract_phpsessid_dict(raw_cookie)
        print(f"\nKết quả extract cookie:\n{cookies}\n")

        # === Lưu vào file cookie.txt ===
        save_path = os.path.join(os.getcwd(), COOKIE_TXT)
        with open(save_path, "w", encoding="utf-8") as f:
            for k, v in cookies.items():
                f.write(f"{k}={v}\n")

        messagebox.showinfo(
            "Kết quả",
            f"Đã lấy PHPSESSID:\n{cookies}\n\nĐã lưu tại:\n{save_path}"
        )
        update_cookie_label()

    except Exception as e:
        print(f"[LỖI] Khi extract cookie: {e}")
        messagebox.showerror("Lỗi", str(e))


def update_cookie_label():
    """Hiển thị cookie hiện tại trong file"""
    try:
        cookies = read_cookie_from_txt()
        if cookies:
            display = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        else:
            display = "Chưa có cookies trong bộ nhớ"
    except FileNotFoundError:
        display = "⚠️ Chưa có file cookie.txt"
    except Exception as e:
        display = f"Lỗi khi đọc cookies: {e}"

    cookie_status_label.config(text=f"Cookies hiện tại: {display}")


def on_month_year_change(event=None):
    year = year_var.get()
    month = month_var.get()
    if not year or not month:
        return
    month_str = f"{year}-{int(month):02d}"
    load_data(month_str)


# === Giao diện chính ===
root = tk.Tk()
root.title("Crawl & Xem dữ liệu theo tháng")
root.state("zoomed")
root.minsize(850, 500)

style = ttk.Style()
style.theme_use("clam")
style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
style.configure("Treeview", rowheight=22, font=("Segoe UI", 10))
style.configure("TButton", font=("Segoe UI", 10))

# ==== Thanh chọn tháng/năm ====
top_frame = ttk.Frame(root, padding=10)
top_frame.pack(fill="x")

ttk.Label(top_frame, text="Chọn tháng:", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=5)
month_var = tk.StringVar(value=datetime.datetime.now().strftime("%m"))
month_cb = ttk.Combobox(top_frame, textvariable=month_var, width=5, state="readonly",
                        values=[f"{i:02d}" for i in range(1, 13)])
month_cb.grid(row=0, column=1, padx=5)

ttk.Label(top_frame, text="Chọn năm:", font=("Segoe UI", 10)).grid(row=0, column=2, sticky="w", padx=5)
year_var = tk.StringVar(value=str(datetime.datetime.now().year))
current_year = datetime.datetime.now().year
year_cb = ttk.Combobox(top_frame, textvariable=year_var, width=6, state="readonly",
                       values=[str(y) for y in range(current_year - 3, current_year + 2)])
year_cb.grid(row=0, column=3, padx=5)

ttk.Button(top_frame, text="Update dữ liệu", command=run_process).grid(row=0, column=4, padx=15)

month_cb.bind("<<ComboboxSelected>>", on_month_year_change)
year_cb.bind("<<ComboboxSelected>>", on_month_year_change)

# ==== Ô nhập cookie & nút extract ====
cookie_frame = ttk.LabelFrame(root, text="Nhập chuỗi Cookie để lấy PHPSESSID", padding=10)
cookie_frame.pack(fill="x", padx=10, pady=(0, 10))

cookie_entry = tk.Text(cookie_frame, height=4, wrap="word", font=("Consolas", 9))
cookie_entry.pack(side="left", expand=True, fill="x")

extract_btn = ttk.Button(cookie_frame, text="Extract PHPSESSID", command=extract_cookie_action)
extract_btn.pack(side="right", padx=10)

cookie_status_label = ttk.Label(root, text="Cookies hiện tại: (chưa có)", wraplength=1000)
cookie_status_label.pack(fill="x", padx=10, pady=(0, 10))

update_cookie_label()

# ==== Khu vực bảng ====
frame_table = ttk.Frame(root, padding=(10, 5))
frame_table.pack(expand=True, fill="both")

columns = ["ID", "Date", "Link", "Charge", "Start count", "Quantity", "Service", "Status", "Remains"]
tree = ttk.Treeview(frame_table, columns=columns, show="headings")
for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=100, anchor="w")

scroll_y = ttk.Scrollbar(frame_table, orient="vertical", command=tree.yview)
scroll_x = ttk.Scrollbar(frame_table, orient="horizontal", command=tree.xview)
tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
scroll_y.pack(side="right", fill="y")
scroll_x.pack(side="bottom", fill="x")
tree.pack(expand=True, fill="both")

# ==== Hai vùng log song song ====
log_frame = ttk.LabelFrame(root, text="Log tiến trình & Thống kê chi phí", padding=5)
log_frame.pack(fill="both", expand=True, padx=10, pady=5)
log_frame.columnconfigure(0, weight=1)
log_frame.columnconfigure(1, weight=1)

# Bên trái
process_frame = ttk.Frame(log_frame)
process_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
ttk.Label(process_frame, text="📜 Tiến trình xử lý", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=5)

process_text = tk.Text(process_frame, height=20, wrap="word", font=("Consolas", 9),
                       bg="#1e1e1e", fg="#dcdcdc", insertbackground="white")
process_text.pack(expand=True, fill="both")

# Bên phải
stat_frame = ttk.Frame(log_frame)
stat_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
ttk.Label(stat_frame, text="📊 Thống kê chi phí", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=5)

stat_text = tk.Text(stat_frame, height=20, wrap="word", font=("Consolas", 9),
                    bg="#1e1e1e", fg="#dcdcdc", insertbackground="white")
stat_text.pack(expand=True, fill="both")

# Gắn redirect stdout/stderr
sys.stdout = TextRedirector(process_text, stat_text)
sys.stderr = TextRedirector(process_text, stat_text)

count_label = ttk.Label(root, text="Chưa tải dữ liệu", font=("Segoe UI", 9, "italic"), padding=5)
count_label.pack(anchor="e")

# Hiển thị dữ liệu mặc định tháng hiện tại
on_month_year_change()
root.mainloop()
