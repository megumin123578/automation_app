import os

# Dùng thư mục hiện tại (nơi file .py này được chạy)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Thư mục cần bỏ qua
IGNORE_DIRS = {'.git', '.venv', 'node_modules', '__pycache__', 'dist', 'build', '.mypy_cache', '.pytest_cache'}

def print_tree(root_dir, indent=""):
    """In ra cây thư mục tại thư mục hiện tại, bỏ qua các thư mục build hoặc ẩn"""
    if not os.path.exists(root_dir):
        print(f"Không tồn tại: {root_dir}")
        return

    items = sorted(os.listdir(root_dir))
    for i, name in enumerate(items):
        # Bỏ qua thư mục hoặc file ẩn
        if name.startswith('.') or name in IGNORE_DIRS:
            continue

        path = os.path.join(root_dir, name)
        connector = "└── " if i == len(items) - 1 else "├── "

        if os.path.isfile(path) and name.endswith(('.py', '.txt', '.csv', '.json')):
            print(indent + connector + name)
        elif os.path.isdir(path):
            # Bỏ qua toàn bộ thư mục nằm trong IGNORE_DIRS
            if any(ignored in os.path.normpath(path).split(os.sep) for ignored in IGNORE_DIRS):
                continue
            print(indent + connector + name)
            new_indent = indent + ("    " if i == len(items) - 1 else "│   ")
            print_tree(path, new_indent)

# In cây thư mục hiện tại
print_tree(BASE_DIR)
