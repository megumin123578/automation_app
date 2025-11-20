from random_vids import get_random_unused_mp4
from ui_theme import setup_theme
from excel_helper import save_assignments_to_excel, combine_excels
from update_manager import check_update_only, check_and_update_safe
from module import *
from hyperparameter import *
from ghep_music.concat_page import ConcatPage
from thong_ke.stats_page import StatisticsPage
from orders.ssm_page import OrdersPage
import time
from rearange_files import rearrange_and_delete_junk_files 
from orders.ssm_page import get_api_key
from gemini_helper import ask_gemini, get_gemini_model