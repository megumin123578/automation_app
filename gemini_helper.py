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

def generate_titles_and_descs(topic: str) -> tuple:
    # PROMPT TITLES
    prompt_titles = (
        f"Write 10 catchy YouTube Shorts titles about: {topic}.\n"
        f"STRICT RULES:\n"
        f"No more than 100 characters.\n"
        f"- Output MUST be 10 lines ONLY.\n"
        f"- NO numbering.\n"
        f"- NO bullets.\n"
        f"- NO intro sentences.\n"
        f"- NO explanations.\n"
        f"- Only titles, one per line."
    )

    raw_titles = ask_gemini(prompt_titles)

    # CLEAN TITLES
    titles_clean = []
    for line in raw_titles.splitlines():
        l = line.strip()
        if not l:
            continue
        if l.lower().startswith(("of course", "here are", "sure", "okay", "here you go")):
            continue
        l = l.lstrip("0123456789.:- ").strip()
        titles_clean.append(l)

    titles_text = "\n".join(titles_clean[:10])

    # PROMPT DESCRIPTIONS
    prompt_descs = (
        f"Write 10 short, SEO-optimized YouTube Shorts descriptions about: {topic}.\n"
        f"STRICT RULES:\n"
        f"- Include hashtags.\n"
        f"- No intro text.\n"
        f"- No numbering.\n"
        f"- Output exactly 10 lines, each line is one description."
    )

    raw_descs = ask_gemini(prompt_descs)

    # CLEAN DESCS
    descs_clean = []
    for line in raw_descs.splitlines():
        l = line.strip()
        if not l:
            continue
        if l.lower().startswith(("of course", "here are", "sure", "okay", "here you go")):
            continue
        l = l.lstrip("0123456789.:- ").strip()
        descs_clean.append(l)

    descs_text = "\n".join(descs_clean[:10])

    return titles_text, descs_text
