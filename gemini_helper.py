import google.generativeai as genai
import os

KEY_FILE = "gemini.key"

def load_api_key():
    """Đọc API key từ file gemini.key"""
    if not os.path.exists(KEY_FILE):
        raise FileNotFoundError("File gemini.key chưa tồn tại.")
    with open(KEY_FILE, "r", encoding="utf-8") as f:
        key = f.read().strip()
        if not key:
            raise ValueError("File gemini.key rỗng.")
        return key


def get_gemini_model():
    """Load API key + khởi tạo model Gemini"""
    key = load_api_key()
    genai.configure(api_key=key)
    return genai.GenerativeModel("gemini-2.5-pro")


def ask_gemini(prompt: str) -> str:
    """Gửi câu hỏi tới Gemini"""
    try:
        model = get_gemini_model()
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"[Gemini Error] {e}"
