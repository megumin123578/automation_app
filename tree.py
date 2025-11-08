import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_DIR = f"{BASE_DIR}/data/cleaned html"
def print_tree(root_dir, indent=""):
    """In ra cấu trúc cây thư mục (giống lệnh tree)"""
    if not os.path.exists(root_dir):
        print(f"Không tồn tại: {root_dir}")
        return

    items = sorted(os.listdir(root_dir))
    for i, name in enumerate(items):
        path = os.path.join(root_dir, name)
        connector = "└── " if i == len(items) - 1 else "├── "
        if name.endswith('.py') or name.endswith('.txt') or name.endswith('.csv') or name.endswith('.json'):
            print(indent + connector + name)
        if os.path.isdir(path):
            new_indent = indent + ("    " if i == len(items) - 1 else "│   ")
            print_tree(path, new_indent)
print_tree(BASE_DIR)