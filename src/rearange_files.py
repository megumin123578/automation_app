import os
import shutil

cur = str(os.getcwd())
parent_folder = cur[:-4]
src_folder = os.path.join(parent_folder, 'src')

def check_current_folder():
    return str(os.getcwd())[-3:] == 'src'

def move_out_and_delete_src():
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

    
    try:
        os.rmdir(cur)
        print(f'Deleted src folder')
    except Exception as e:
        print(f'Error deleting src folder: {e}')

if __name__ == "__main__":
    move_out_and_delete_src()
