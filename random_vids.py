import os
import random

def get_random_unused_mp4(folder_path: str, used_paths: set) -> str:
    if not os.path.isdir(folder_path):
        return ""

    all_mp4s = [
        os.path.abspath(os.path.join(folder_path, f))
        for f in os.listdir(folder_path)
        if f.lower().endswith(".mp4")
    ]

    unused = [f for f in all_mp4s if f not in used_paths]
    if not unused:
        return ""
    return random.choice(unused)

