import tkinter as tk
from tkinter import ttk
from imports import *
import threading
from gemini_helper import ask_gemini, get_gemini_model


class ChatPage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg='#f5f5f5', highlightthickness=0)
        self.scroll_y = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)

        self.chat_frame = ttk.Frame(self.canvas)
        

        # Output box
        self.chat_output = tk.Text(self, height=20, wrap=tk.WORD)
        self.chat_output.pack(fill="both", expand=True, padx=10, pady=10)

        # Input box
        self.chat_input = tk.Entry(self)
        self.chat_input.pack(fill="x", padx=10)
        self.chat_input.bind("<Return>", self._on_chat_send)

    # Gửi tin nhắn
    def _on_chat_send(self, event=None):
        msg = self.chat_input.get().strip()
        if not msg:
            return

        # Show user message immediately
        self.chat_output.insert(tk.END, f"\nYOU: {msg}\n")
        self.chat_output.see(tk.END)
        self.chat_input.delete(0, tk.END)

        # Run AI in background thread
        threading.Thread(target=self._reply_background, args=(msg,), daemon=True).start()

    def _reply_background(self, msg):
        try:
            model = get_gemini_model()
            if not model:
                reply = "(Gemini model not available)"
            else:
                reply = ask_gemini(msg)
        except Exception as e:
            reply = f"(Error: {e})"

        # Insert AI reply back into UI (must use .after)
        self.after(0, lambda: self._insert_ai_reply(reply))

    def _insert_ai_reply(self, reply):
        self.chat_output.insert(tk.END, f'AI: {reply}\n')
        self.chat_output.see(tk.END)
