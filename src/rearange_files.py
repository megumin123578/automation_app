import os
import shutil

cur = str(os.getcwd())
parent_folder = os.path.dirname(cur)
src_folder = os.path.join(parent_folder, 'src')

def check_current_folder():
    return str(os.getcwd())[-3:] == 'src'

def move_out_and_delete_src():
    #delete tree.py in parent folder if exists
    tree_py_path = os.path.join(parent_folder, 'tree.py')
    if os.path.exists(tree_py_path):
        try:
            os.remove(tree_py_path)
            print(f'Deleted existing tree.py in parent folder')
        except Exception as e:
            print(f'Error when deleting tree.py: {e}')

    if not check_current_folder():
        print(f'not in src folder, run main program')
        return  
    for item in os.listdir(cur):
        src = os.path.join(cur, item)
        dst = os.path.join(parent_folder, item)
        try:
            if os.path.exists(dst):
                print(f'skipping {item}, already exists in parent folder')
                continue
            shutil.move(src, dst)
            print(f'Moved {item} to parent folder')

        except Exception as e:
            print(f'Error moving {item}: {e}')

def rearrange_and_delete_junk_files(): #main function to be called
    move_out_and_delete_src()
    if not check_current_folder(): #if not in src folder
        print('Attempting to delete src folder...')
        try:
            shutil.rmtree((src_folder))
            print(f'Deleted src folder')
        except Exception as e:
            print(f'Error deleting src folder: {e}')
        
        try:
            shutil.rmtree((os.path.join(cur, 'src')))
            print(f'Deleted src folder')
        except Exception as e:
            print(f'Error deleting src folder: {e}')