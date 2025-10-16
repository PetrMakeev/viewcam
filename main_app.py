import sys
import os
import logging
import time
import json
import tkinter as tk
from tkinter import ttk, Button
from tkinter.font import Font
from PIL import Image, ImageTk
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from ui_components import CellFrame
from main_app_methods import MainAppMethods
from selenium_utils import SeleniumUtils

# Настройка logging в файл
logging.basicConfig(filename='app.log', level=logging.ERROR, force=True)
logger = logging.getLogger(__name__)

class MainApp(tk.Tk, MainAppMethods, SeleniumUtils):
    def __init__(self):
        super().__init__()
        self.title("Видеонаблюдение")
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight() - 50
        self.geometry(f"{screen_width - 10}x{screen_height - 15}+0+0")
        
        self.cell_width = (screen_width - 10 - 300) // 3
        self.cell_height = (screen_height - 15) // 3
        
        nocam_img = Image.open("resource/nocam.png")
        nocam_img = nocam_img.resize((self.cell_width, self.cell_height), Image.LANCZOS)
        self.nocam_photo = ImageTk.PhotoImage(nocam_img)
        
        noconnect_img = Image.open("resource/noconnect.png")
        noconnect_img = noconnect_img.resize((self.cell_width, self.cell_height), Image.LANCZOS)
        self.noconnect_photo = ImageTk.PhotoImage(noconnect_img)
        
        checked_img = Image.open("resource/ui-check-box.png")
        checked_img = checked_img.resize((24, 24), Image.LANCZOS)
        self.checked_photo = ImageTk.PhotoImage(checked_img)
        
        unchecked_img = Image.open("resource/ui-check-box-uncheck.png")
        unchecked_img = unchecked_img.resize((24, 24), Image.LANCZOS)
        self.unchecked_photo = ImageTk.PhotoImage(unchecked_img)
        
        arrow_up_img = Image.open("resource/arrow-up.png")
        arrow_up_img = arrow_up_img.resize((24, 24), Image.LANCZOS)
        self.arrow_up_photo = ImageTk.PhotoImage(arrow_up_img)
        
        arrow_down_img = Image.open("resource/arrow-down.png")
        arrow_down_img = arrow_down_img.resize((24, 24), Image.LANCZOS)
        self.arrow_down_photo = ImageTk.PhotoImage(arrow_down_img)
        
        arrow_top_img = Image.open("resource/arrow-top.png")
        arrow_top_img = arrow_top_img.resize((24, 24), Image.LANCZOS)
        self.arrow_top_photo = ImageTk.PhotoImage(arrow_top_img)
        
        arrow_bottom_img = Image.open("resource/arrow-bottom.png")
        arrow_bottom_img = arrow_bottom_img.resize((24, 24), Image.LANCZOS)
        self.arrow_bottom_photo = ImageTk.PhotoImage(arrow_bottom_img)
        
        # Загрузка и очистка конфигурации
        self.config = self.clean_config_data()
        self.cams = self.config.get("cams", [])
        self.groups = self.config.get("groups", [])
        self.period = self.config.get("period", 1) * 1000
        if self.period not in [1000, 2000, 4000]:
            logger.warning(f"[{time.strftime('%H:%M:%S')}] Invalid period {self.period // 1000} sec in config. Setting to 1 sec.")
            self.period = 1000
        self.original_period = self.period
        self.selected_camera = None
        self.driver = None  # Один драйвер
        self.handles = [None] * 9  # Хэндлы вкладок для 9 ячеек
        self.main_handle = None  # Основная вкладка
        self.update_frames_id = None
        self.is_editing_structure = False
        self.tooltip = None
        self.tooltip_texts = {
            'move_top': '',
            'move_up': '',
            'move_down': '',
            'move_bottom': ''
        }
        self.full_update = True
        self.modal_window = None
        self.modal_name_label = None
        self.modal_image_label = None
        self.modal_photo = None
        self.modal_image_size = None
        self.modal_cell_index = None
        self.original_pil_images = [None] * 9
        
        style = ttk.Style()
        style.configure("Custom.TCombobox", padding=(5, 2, 5, 2))
        
        left_frame = tk.Frame(self, width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        self.tree = ttk.Treeview(left_frame, show="tree")
        self.tree.pack(expand=True, fill=tk.BOTH, padx=3, pady=3)
        self.update_camera_list()
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        self.tree_buttons_frame = tk.Frame(left_frame)
        self.tree_buttons_frame.pack(fill=tk.X, padx=3, pady=3)
        self.tree_buttons_frame.pack_forget()
        
        self.move_top_button = Button(
            self.tree_buttons_frame,
            image=self.arrow_top_photo,
            command=self.move_top,
            state=tk.DISABLED
        )
        self.move_top_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        self.move_top_button.bind("<Enter>", lambda event: self.show_tooltip(event, 'move_top'))
        self.move_top_button.bind("<Leave>", self.hide_tooltip)
        
        self.arrow_up_button = Button(
            self.tree_buttons_frame,
            image=self.arrow_up_photo,
            command=self.move_up,
            state=tk.DISABLED
        )
        self.arrow_up_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 5))
        self.arrow_up_button.bind("<Enter>", lambda event: self.show_tooltip(event, 'move_up'))
        self.arrow_up_button.bind("<Leave>", self.hide_tooltip)
        
        self.arrow_down_button = Button(
            self.tree_buttons_frame,
            image=self.arrow_down_photo,
            command=self.move_down,
            state=tk.DISABLED
        )
        self.arrow_down_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 5))
        self.arrow_down_button.bind("<Enter>", lambda event: self.show_tooltip(event, 'move_down'))
        self.arrow_down_button.bind("<Leave>", self.hide_tooltip)
        
        self.move_bottom_button = Button(
            self.tree_buttons_frame,
            image=self.arrow_bottom_photo,
            command=self.move_bottom,
            state=tk.DISABLED
        )
        self.move_bottom_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))
        self.move_bottom_button.bind("<Enter>", lambda event: self.show_tooltip(event, 'move_bottom'))
        self.move_bottom_button.bind("<Leave>", self.hide_tooltip)
        
        self.edit_structure_button = Button(
            left_frame,
            text="Изменить\nструктуру",
            font=Font(family="Arial", size=11),
            command=self.toggle_structure_edit,
            width=20
        )
        self.edit_structure_button.pack(fill=tk.X, padx=3, pady=3)
        
        right_frame = tk.Frame(self)
        right_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        
        self.top_frame = tk.Frame(right_frame, relief="sunken", borderwidth=2)
        self.top_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        controls_frame = tk.Frame(self.top_frame)
        controls_frame.pack(anchor="center")
        
        self.add_camera_button = Button(
            controls_frame,
            text="Добавить камеру",
            font=Font(family="Arial", size=11),
            command=self.add_camera,
            width=20
        )
        self.add_camera_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        self.edit_camera_button = Button(
            controls_frame,
            text="Изменить камеру",
            font=Font(family="Arial", size=11),
            command=self.edit_camera,
            width=20,
            state=tk.DISABLED
        )
        self.edit_camera_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        self.delete_camera_button = Button(
            controls_frame,
            text="Удалить камеру",
            font=Font(family="Arial", size=11),
            command=self.delete_camera,
            width=20,
            state=tk.DISABLED
        )
        self.delete_camera_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        self.edit_group_button = Button(
            controls_frame,
            text="Изменить группу",
            font=Font(family="Arial", size=11),
            command=self.edit_group,
            width=20
        )
        self.edit_group_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        self.reload_button = Button(
            controls_frame,
            text="Перезагрузить",
            font=Font(family="Arial", size=11),
            command=self.reload_drivers,
            width=20
        )
        self.reload_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        self.grid_combobox = ttk.Combobox(
            controls_frame,
            values=["Сетка 2х2", "Сетка 3х3"],
            font=Font(family="Arial", size=11),
            style="Custom.TCombobox",
            state="readonly",
            width=15
        )
        self.grid_combobox.set("Сетка 3х3")
        self.grid_combobox.pack(side=tk.LEFT, padx=5, pady=3)
        
        self.frame_rate_combobox = ttk.Combobox(
            controls_frame,
            values=["Кадр в 1 сек", "Кадр в 2 сек", "Кадр в 4 сек"],
            font=Font(family="Arial", size=11),
            style="Custom.TCombobox",
            state="readonly",
            width=15
        )
        self.frame_rate_combobox.set(f"Кадр в {self.period // 1000} сек")
        self.frame_rate_combobox.pack(side=tk.LEFT, padx=5, pady=3)
        
        self.open_map_button = Button(
            controls_frame,
            text="Открыть карту",
            font=Font(family="Arial", size=11),
            command=lambda: None,
            width=25
        )
        self.open_map_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        camera_frame = tk.Frame(right_frame, relief="sunken", borderwidth=2)
        camera_frame.pack(expand=True, fill=tk.BOTH)
        
        self.cells = []
        for i in range(3):
            for j in range(3):
                cell = CellFrame(camera_frame, i * 3 + j)
                cell.grid(row=i, column=j, sticky="nsew")
                cell.config(width=self.cell_width, height=self.cell_height)
                self.cells.append(cell)
                camera_frame.rowconfigure(i, weight=1)
                camera_frame.columnconfigure(j, weight=1)
        
        # Инициализация ячеек
        current_group = next((g for g in self.groups if g.get("current", False)), self.groups[0] if self.groups else {})
        current_grid = current_group.get("grid", [None] * 9)
        for i in range(9):
            link = current_grid[i] if i < len(current_grid) else None
            if link:
                for cam in self.cams:
                    if cam["link"] == link:
                        self.cells[i].cam = cam
                        break
            else:
                self.cells[i].cam = None
            self.cells[i].update_display()
        
        self.driver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chromedriver.exe")
        self.options = Options()
        self.options.add_argument('--headless=new')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--window-size=1920,1080')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-background-throttling')  # Оптимизация для фона
        
        self.initialize_drivers()
        
        self.start_load_group_to_drivers()
        
        self.update_frames()
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)