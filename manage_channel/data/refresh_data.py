
from data_helper import *
if __name__ == "__main__":
    html_paths = list_html_paths(FOLDER)
    total_files= len(html_paths)
    print(f"Found {total_files} file HTML.")

    if total_files > 0: #check total files
        for path in html_paths:
            print("•", path)
        list_html_after_delete = delete_unwanted_files(html_paths)
    else:
        list_html_after_delete = []
    #move to html folder
    total_files = len(list_html_after_delete)
    if total_files > 0:
        html_new_dirs = move_file_to_html_folder(list_html_after_delete)
    else:
        print("No files to process")

    #get list of file in html folder
    html_ls = list_html_paths(OUTPUT_HTML_DIR)
    if len(html_ls) > 0:
        remove_abundant_value(html_ls)

    
    