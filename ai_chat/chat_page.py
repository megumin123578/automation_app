import tkinter as tk
from tkinter import ttk
import json, os, datetime
import threading
from gemini_helper import ask_gemini, get_gemini_model

import re

def parse_markdown(text):

    tokens = []

    # Inline code: `code`
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)

    # Bold: **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # Italic: *text*
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)

    pattern = r"<b>.*?</b>|<i>.*?</i>|<code>.*?</code>|[^<]+"

    for part in re.findall(pattern, text):
        if part.startswith("<b>"):
            tokens.append(("bold", part[3:-4]))
        elif part.startswith("<i>"):
            tokens.append(("italic", part[3:-4]))
        elif part.startswith("<code>"):
            tokens.append(("code", part[6:-7]))
        else:
            tokens.append(("normal", part))

    return tokens



class ChatPage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        # ====== FOLDER LƯU CHAT ======
        self.log_dir = "ai_chat/chat_logs"
        os.makedirs(self.log_dir, exist_ok=True)

        today = datetime.date.today().strftime("%d%m%Y")
        self.log_path = os.path.join(self.log_dir, f"session_{today}.json")
        self.chat_history = self._load_history()

        # ====== DARK THEME ======
        style = ttk.Style()
        style.configure("Chat.TFrame", background="#1E1E1E")
        style.configure("Input.TEntry", fieldbackground="#2F2F2F", foreground="white")
        style.configure("Send.TButton", background="#4A90E2", foreground="white")

        # Frame gốc của page phải fill được
        self.configure(style="Chat.TFrame")
        self.rowconfigure(0, weight=1)   # hàng chat area
        self.rowconfigure(1, weight=0)   # hàng input
        self.columnconfigure(0, weight=1)

        chat_area = ttk.Frame(self, style="Chat.TFrame")
        chat_area.grid(row=0, column=0, sticky="nsew")  # fill toàn bộ

        chat_area.rowconfigure(0, weight=1)
        chat_area.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(chat_area, bg="#1E1E1E", highlightthickness=0)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)   
        self.scroll_y = ttk.Scrollbar(chat_area, orient="vertical",
                                      command=self.canvas.yview)

        self.chat_frame = ttk.Frame(self.canvas, style="Chat.TFrame")
        self.chat_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.chat_frame, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=self.scroll_y.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scroll_y.grid(row=0, column=1, sticky="ns")

        # Đảm bảo canvas resize theo chat_area
        def _on_resize(event):
            self.canvas.itemconfig(self.canvas_window, width=event.width)
        self.canvas.bind("<Configure>", _on_resize)

        input_wrapper = ttk.Frame(self, style="Chat.TFrame")
        input_wrapper.grid(row=1, column=0, sticky="ew", padx=12, pady=12)
        input_wrapper.columnconfigure(0, weight=1)

        # Canvas bo góc chứa ô nhập
        input_canvas = tk.Canvas(input_wrapper, bg="#1E1E1E",
                                highlightthickness=0, bd=0, height=48)
        input_canvas.grid(row=0, column=0, sticky="ew")
        input_canvas.update_idletasks()

        # Vẽ nền bo góc
        w = input_canvas.winfo_width()
        h = 48
        r = 16
        self._rounded_rect(input_canvas, 0, 0, w, h, r, fill="#2F2F2F")

        def _resize_input_bg(e):
            input_canvas.delete("all")
            self._rounded_rect(input_canvas, 0, 0, e.width, h, r, fill="#2F2F2F")
        input_canvas.bind("<Configure>", _resize_input_bg)

        # Ô nhập text nằm trên canvas
        self.chat_input = tk.Entry(input_canvas,
                                font=("Segoe UI", 11),
                                bg="#2F2F2F",
                                fg="white",
                                relief="flat",
                                insertbackground="white",
                                highlightthickness=0,
                                borderwidth=0)
        self.chat_input.place(x=14, y=10, relwidth=0.95)  # đặt vào giữa
        self.chat_input.bind("<Return>", self._on_send)

        for sender, text in self.chat_history:
            self._add_bubble(text, sender, save=False)

    def _load_history(self):
        if not os.path.exists(self.log_path):
            return []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_history(self):
        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump(self.chat_history, f, ensure_ascii=False, indent=2)

    def _add_bubble(self, text, sender="user", save=True):
        if save:
            self.chat_history.append((sender, text))
            self._save_history()

        canvas_w = self.canvas.winfo_width()
        if canvas_w < 200:
            canvas_w = 900
        wrap = int(canvas_w * 0.60)

        # ==== Tạo frame chứa bubble ====
        outer = tk.Frame(self.chat_frame, bg="#1E1E1E")
        outer.pack(anchor="e" if sender=="user" else "w",
                padx=(canvas_w*0.20,10) if sender=="user" else (10,canvas_w*0.20),
                pady=6)

        # ==== Tạo Canvas để vẽ bubble bo góc ====
        bubble_canvas = tk.Canvas(outer, bg="#1E1E1E", highlightthickness=0, bd=0)
        bubble_canvas.pack()

        # ==== Tạo text trước để đo kích thước ====
        temp = bubble_canvas.create_text(
            0, 0,
            text=text,
            font=("Segoe UI", 11),
            fill="white",
            width=wrap,
            anchor="nw"
        )
        bubble_canvas.update_idletasks()
        bbox = bubble_canvas.bbox(temp)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        padding = 14
        width = text_w + padding*2
        height = text_h + padding*2

        bubble_canvas.config(width=width, height=height)

        # ==== Reset để vẽ rounded rect trước ====
        bubble_canvas.delete(temp)

        # ==== Chọn màu theo sender ====
        color = "#4CAF50" if sender=="user" else "#3A3A3A"

        # ==== VẼ BUBBLE BO GÓC ====
        r = 16  # bán kính bo góc
        self._rounded_rect(bubble_canvas, 0, 0, width, height, r, fill=color)

        # ==== Thêm text ====
        bubble_canvas.create_text(
            padding, padding,
            text=text,
            font=("Segoe UI", 11),
            fill="white",
            width=text_w,
            anchor="nw"
        )

        # Auto scroll xuống cuối
        self.after(50, lambda: self.canvas.yview_moveto(1.0))
    
    def _rounded_rect(self, canvas, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1+r, y1,
            x2-r, y1,
            x2,   y1,
            x2,   y1+r,
            x2,   y2-r,
            x2,   y2,
            x2-r, y2,
            x1+r, y2,
            x1,   y2,
            x1,   y2-r,
            x1,   y1+r,
            x1,   y1
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _on_send(self, event=None):
        msg = self.chat_input.get().strip()
        if not msg:
            return

        self.chat_input.delete(0, tk.END)
        self._add_bubble(msg, sender="user")

        threading.Thread(target=self._handle_ai, args=(msg,), daemon=True).start()

    def _handle_ai(self, msg):
        # Tạo bubble AI trống để stream vào
        ai_bubble = self._add_bubble_stream("", sender="ai")

        try:
            from gemini_helper import ask_gemini_stream
            for chunk in ask_gemini_stream(msg):
                # append chunk vào bubble
                self.after(0, lambda c=chunk: ai_bubble["append"](c))
                # scroll xuống
                self.after(0, lambda: self.canvas.yview_moveto(1.0))

        except Exception as e:
            self.after(0, lambda: ai_bubble["append"]("[Error] " + str(e)))

    def _add_bubble_stream(self, text, sender="ai"):
        """Tạo bubble mà có thể append text vào (dùng cho streaming)."""

        canvas_w = self.canvas.winfo_width()
        wrap = int(canvas_w * 0.60)
        padding = 14

        outer = tk.Frame(self.chat_frame, bg="#1E1E1E")
        outer.pack(anchor="w" if sender=="ai" else "e", pady=6, padx=15)

        bubble_canvas = tk.Canvas(outer, bg="#1E1E1E",
                                  highlightthickness=0, bd=0)
        bubble_canvas.pack()

        color = "#3A3A3A" if sender=="ai" else "#4CAF50"

        # text item để update dần
        text_item = bubble_canvas.create_text(
            padding, padding,
            text="",
            font=("Segoe UI", 11),
            fill="white",
            width=wrap,
            anchor="nw"
        )

        # === HÀM NỘI BỘ append text ===
        buffer = []   # lưu phần text hiện tại

        def append_chunk(chunk):
            buffer.append(chunk)
            full_text = "".join(buffer)

            bubble_canvas.itemconfig(text_item, text=full_text)
            bubble_canvas.update_idletasks()

            bbox = bubble_canvas.bbox(text_item)
            w = (bbox[2] - bbox[0]) + padding * 2
            h = (bbox[3] - bbox[1]) + padding * 2

            bubble_canvas.config(width=w, height=h)

            # Vẽ lại background
            bubble_canvas.delete("bg")
            self._rounded_rect(bubble_canvas, 0, 0, w, h, 16, fill=color)

            # Đặt text lại phía trên
            bubble_canvas.lift(text_item)

        # Set initial text
        append_chunk(text)

        return {
            "append": append_chunk,
            "get_text": lambda: "".join(buffer),
        }

    def _on_mousewheel(self, event):
        # Windows
        if event.delta:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")
        # Linux (event.num 4 = scroll up, 5 = scroll down)
        elif event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
