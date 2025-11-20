import tkinter as tk
from tkinter import ttk
import json, os, datetime
import threading
from gemini_helper import ask_gemini, get_gemini_model


class ChatPage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        # Folder lưu chat
        self.log_dir = "ai_chat\chat_logs"
        os.makedirs(self.log_dir, exist_ok=True)

        # Tạo file session
        today = datetime.date.today().strftime("%Y%m%d")
        self.log_path = os.path.join(self.log_dir, f"session_{today}.json")

        # Load lịch sử chat cũ
        self.chat_history = self._load_history()

        # ====== DARK THEME ======
        style = ttk.Style()
        style.configure("Chat.TFrame", background="#1E1E1E")
        style.configure("Input.TEntry", fieldbackground="#2F2F2F", foreground="white")
        style.configure("Send.TButton", background="#4A90E2", foreground="white")

        self.configure(style="Chat.TFrame")

        main = ttk.Frame(self, style="Chat.TFrame")
        main.pack(fill="both", expand=True)

        # ==== CHAT AREA (phải expand) ====
        chat_area = ttk.Frame(main, style="Chat.TFrame")
        chat_area.pack(fill="both", expand=True)   # <- QUAN TRỌNG

        self.canvas = tk.Canvas(chat_area, bg="#1E1E1E", highlightthickness=0)
        self.scroll_y = ttk.Scrollbar(chat_area, orient="vertical", command=self.canvas.yview)

        self.chat_frame = ttk.Frame(self.canvas, style="Chat.TFrame")
        self.chat_frame.bind("<Configure>",
                            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.chat_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll_y.set)

        self.canvas.pack(side="left", fill="both", expand=True)  # <- CHO CANVAS EXPAND
        self.scroll_y.pack(side="right", fill="y")

        # ==== INPUT FIELD (không expand) ====
        input_frame = ttk.Frame(main, style="Chat.TFrame")
        input_frame.pack(side="bottom", fill="x", padx=10, pady=10)

        self.chat_input = ttk.Entry(input_frame, font=("Segoe UI", 11), style="Input.TEntry")
        self.chat_input.pack(side="left", fill="x", expand=True)
        self.chat_input.bind("<Return>", self._on_send)


        # Render chat cũ
        for sender, text in self.chat_history:
            self._add_bubble(text, sender, save=False)


    # ===============================================
    #                  HISTORY
    # ===============================================
    def _load_history(self):
        if not os.path.exists(self.log_path):
            return []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    def _save_history(self):
        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump(self.chat_history, f, ensure_ascii=False, indent=2)


    # ===============================================
    #                ADD BUBBLE UI
    # ===============================================
    def _add_bubble(self, text, sender="user", save=True):

        # Lưu lịch sử
        if save:
            self.chat_history.append((sender, text))
            self._save_history()

        canvas_w = self.canvas.winfo_width()
        if canvas_w < 200:
            canvas_w = 900  # fallback

        wrap = int(canvas_w * 0.60)

        if sender == "user":
            bg = "#4CAF50"
            anchor = "e"
            padx = (canvas_w * 0.20, 10)
        else:
            bg = "#3A3A3A"
            anchor = "w"
            padx = (10, canvas_w * 0.20)

        outer = tk.Frame(self.chat_frame, bg="#1E1E1E")
        outer.pack(anchor=anchor, padx=padx, pady=6)

        bubble = tk.Label(
            outer,
            text=text,
            bg=bg,
            fg="white",
            padx=12,
            pady=8,
            font=("Segoe UI", 11),
            wraplength=wrap,
            justify="left"
        )
        bubble.pack()

        self.after(100, lambda: self.canvas.yview_moveto(1.0))


    # ===============================================
    #                 HANDLE SEND
    # ===============================================
    def _on_send(self, event=None):
        msg = self.chat_input.get().strip()
        if not msg:
            return

        self.chat_input.delete(0, tk.END)

        # Hiển thị message user
        self._add_bubble(msg, sender="user")

        # Xử lý AI ở thread riêng
        threading.Thread(target=self._handle_ai, args=(msg,), daemon=True).start()


    # ===============================================
    #                HANDLE AI RESPONSE
    # ===============================================
    def _handle_ai(self, msg):
        try:
            model = get_gemini_model()
            reply = ask_gemini(msg) if model else "(Gemini model unavailable)"
        except Exception as e:
            reply = f"(Error: {e})"

        self.after(0, lambda: self._add_bubble(reply, sender="ai"))
