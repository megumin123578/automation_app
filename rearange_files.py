import os
import shutil

cur = str(os.getcwd())
parent_folder = os.path.dirname(cur)
src_folder = os.path.join(parent_folder, 'src')

def check_current_folder():
    return str(os.getcwd())[-3:] == 'src'

def move_out_and_delete_src():
    # delete tree.py in parent folder if exists
    tree_py_path = os.path.join(parent_folder, 'tree.py')
    if os.path.exists(tree_py_path):
        try:
            os.remove(tree_py_path)
            print('Deleted existing tree.py in parent folder')
        except Exception as e:
            print(f'Error when deleting tree.py: {e}')

    # nếu không đang ở thư mục src thì bỏ qua
    if not check_current_folder():
        print('Not in src folder, skip moving')
        return

    print(f'Moving files from: {cur}')
    for root, dirs, files in os.walk(cur):
        for file in files:
            src_path = os.path.join(root, file)
            # Tạo đường dẫn tương đối so với src/
            rel_path = os.path.relpath(src_path, cur)
            dst_path = os.path.join(parent_folder, rel_path)

            os.makedirs(os.path.dirname(dst_path), exist_ok=True)

            try:
                if os.path.exists(dst_path):
                    print(f'Skipping {rel_path} (already exists)')
                    continue
                shutil.move(src_path, dst_path)
                print(f'Moved {rel_path}')
            except Exception as e:
                print(f'Error moving {rel_path}: {e}')


def rearrange_and_delete_junk_files(): #main function to be called
    move_out_and_delete_src()
    if not check_current_folder(): #if not in src folder
        print('Attempting to delete src folder...')
        try:
            shutil.rmtree((os.path.join(cur, 'src')))
            print(f'Deleted src folder')
        except Exception as e:
            print(f'Error deleting src folder: {e}')