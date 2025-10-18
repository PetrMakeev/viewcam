import sys
import os
import logging
import time
import json
import numpy as np
import re
import io
import tkinter as tk
from tkinter import ttk, Button
from tkinter.font import Font
from tkinter import ttk, messagebox, Toplevel, Label, Entry, Button
from PIL import Image, ImageTk
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from ui_components import CellFrame, CameraDialog, clean_config_data, open_ufanet_map, compact_grid, save_config
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def resource_path(relative_path):
    """ Получить путь к ресурсу для PyInstaller """
    try:
        # PyInstaller создает временную папку и сохраняет путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Настройка logging в файл
logging.basicConfig(filename='app.log', level=logging.ERROR, force=True)
logger = logging.getLogger(__name__)

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Видеонаблюдение")
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight() - 50
        self.geometry(f"{screen_width - 10}x{screen_height - 15}+0+0")
        
        self.cell_width = (screen_width - 10 - 300) // 3
        self.cell_height = (screen_height - 15) // 3
        
        nocam_img = Image.open(resource_path("resource/nocam.png"))
        nocam_img = nocam_img.resize((self.cell_width, self.cell_height), Image.LANCZOS)
        self.nocam_photo = ImageTk.PhotoImage(nocam_img)
        
        noconnect_img = Image.open(resource_path("resource/noconnect.png"))
        noconnect_img = nocam_img.resize((self.cell_width, self.cell_height), Image.LANCZOS)
        self.noconnect_photo = ImageTk.PhotoImage(noconnect_img)
        
        checked_img = Image.open(resource_path("resource/ui-check-box.png"))
        checked_img = checked_img.resize((24, 24), Image.LANCZOS)
        self.checked_photo = ImageTk.PhotoImage(checked_img)
        
        unchecked_img = Image.open(resource_path("resource/ui-check-box-uncheck.png"))
        unchecked_img = unchecked_img.resize((24, 24), Image.LANCZOS)
        self.unchecked_photo = ImageTk.PhotoImage(unchecked_img)
        
        arrow_up_img = Image.open(resource_path("resource/arrow-up.png"))
        arrow_up_img = arrow_up_img.resize((24, 24), Image.LANCZOS)
        self.arrow_up_photo = ImageTk.PhotoImage(arrow_up_img)
        
        arrow_down_img = Image.open(resource_path("resource/arrow-down.png"))
        arrow_down_img = arrow_down_img.resize((24, 24), Image.LANCZOS)
        self.arrow_down_photo = ImageTk.PhotoImage(arrow_down_img)
        
        arrow_top_img = Image.open(resource_path("resource/arrow-top.png"))
        arrow_top_img = arrow_top_img.resize((24, 24), Image.LANCZOS)
        self.arrow_top_photo = ImageTk.PhotoImage(arrow_top_img)
        
        arrow_bottom_img = Image.open(resource_path("resource/arrow-bottom.png"))
        arrow_bottom_img = arrow_bottom_img.resize((24, 24), Image.LANCZOS)
        self.arrow_bottom_photo = ImageTk.PhotoImage(arrow_bottom_img)
        
        # Загрузка и очистка конфигурации
        self.config = clean_config_data(self)
        self.cams = self.config.get("cams", [])
        self.groups = self.config.get("groups", [])
        self.period = self.config.get("period", 1) * 1000
        if self.period not in [1000, 2000, 4000]:
            logger.warning(f"[{time.strftime('%H:%M:%S')}] Invalid period {self.period // 1000} sec in config. Setting to 1 sec.")
            self.period = 1000
        self.original_period = self.period
        self.selected_camera = None
        self.drivers = []
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
            width=14
        )
        self.add_camera_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        self.edit_camera_button = Button(
            controls_frame,
            text="Изменить камеру",
            font=Font(family="Arial", size=11),
            command=self.edit_camera,
            width=14,
            state=tk.DISABLED
        )
        self.edit_camera_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        self.delete_camera_button = Button(
            controls_frame,
            text="Удалить камеру",
            font=Font(family="Arial", size=11),
            command=self.delete_camera,
            width=14,
            state=tk.DISABLED
        )
        self.delete_camera_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        self.edit_group_button = Button(
            controls_frame,
            text="Изменить группу",
            font=Font(family="Arial", size=11),
            command=self.edit_group,
            width=14
        )
        self.edit_group_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        self.reload_button = Button(
            controls_frame,
            text="Перезагрузить",
            font=Font(family="Arial", size=11),
            command=self.reload_drivers,
            width=14
        )
        self.reload_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        
        self.open_map_button = Button(
            controls_frame,
            text="Карта",
            font=Font(family="Arial", size=11),
            command=open_ufanet_map,
            width=8
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
        
        self.initialize_drivers()
        
        self.start_load_group_to_drivers()
        
        self.update_frames()
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Установка иконки окна
        self.iconbitmap(resource_path("resource/eye.ico"))
        
    def on_resize(self, event):
            # Debounce: отменяем предыдущий вызов и планируем новый
            if self.resize_id:
                self.after_cancel(self.resize_id)
            self.resize_id = self.after(200, lambda: self._delayed_on_resize(event))
            
    def _delayed_on_resize(self, event):
        self.resize_id = None
        screen_width = self.winfo_width()
        screen_height = self.winfo_height()
        new_cell_width = (screen_width - 10 - 300) // 3
        new_cell_height = (screen_height - 15) // 3
        if new_cell_width != self.prev_cell_width or new_cell_height != self.prev_cell_height:
            self.cell_width = new_cell_width
            self.cell_height = new_cell_height
            self.prev_cell_width = new_cell_width
            self.prev_cell_height = new_cell_height
            # Обновляем конфигурацию ячеек
            for cell in self.cells:
                cell.config(width=self.cell_width, height=self.cell_height)
            # Отменяем текущий update и планируем новый
            if self.update_frames_id:
                self.after_cancel(self.update_frames_id)
            self.update_frames()

    def show_tooltip(self, event, button_key):
        if self.tooltip_texts[button_key] == '':
            return
        self.hide_tooltip()  # Уничтожаем старую подсказку, если есть
        widget = event.widget
        x = widget.winfo_rootx() + widget.winfo_width() // 2
        y = widget.winfo_rooty() + 30  # Смещение вниз для видимости
        self.tooltip = Toplevel(self)
        self.tooltip.wm_overrideredirect(True)  # Убираем рамку окна
        self.tooltip.wm_geometry(f"+{x}+{y}")
        label = Label(
            self.tooltip,
            text=self.tooltip_texts[button_key],
            font=("Arial", 10),
            background="white",
            foreground="black",
            borderwidth=1,
            relief="solid",
            padx=5,
            pady=2
        )
        label.pack()
        logger.info(f"[{time.strftime('%H:%M:%S')}] Showing tooltip for {button_key}: {self.tooltip_texts[button_key]}")

    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
            logger.info(f"[{time.strftime('%H:%M:%S')}] Tooltip hidden")

    def open_modal(self, cell_index):
        if self.cells[cell_index].cam is None:
            logger.info(f"[{time.strftime('%H:%M:%S')}] Double-click on empty cell {cell_index}")
            return
        if self.modal_window:
            self.close_modal()
        cam = self.cells[cell_index].cam
        logger.info(f"[{time.strftime('%H:%M:%S')}] Opening modal for camera '{cam['street']}' in cell {cell_index}")
        self.modal_cell_index = cell_index
        self.full_update = False
        modal = Toplevel(self)
        modal.title(cam["street"])
        modal.geometry(self.geometry())
        modal.transient(self)
        modal.grab_set()
        modal.bind("<Escape>", self.close_modal)
        modal_frame = tk.Frame(modal)
        modal_frame.pack(expand=True, fill=tk.BOTH)
        self.modal_name_label = Label(modal_frame, text=cam["street"], font=Font(family="Arial", size=11), height=1)
        self.modal_name_label.pack(fill=tk.X)
        self.modal_image_label = Label(modal_frame)
        self.modal_image_label.pack(expand=True, fill=tk.BOTH)
        self.modal_image_label.bind("<Double-Button-1>", self.close_modal)
        modal.protocol("WM_DELETE_WINDOW", self.close_modal)
        self.modal_window = modal
        modal.update()
        modal_width = modal.winfo_width()
        modal_height = modal.winfo_height() - self.modal_name_label.winfo_reqheight()
        self.modal_image_size = (modal_width, modal_height)
        # Initial image
        if self.original_pil_images[cell_index]:
            resized_modal = self.original_pil_images[cell_index].resize(self.modal_image_size, Image.LANCZOS)
            self.modal_photo = ImageTk.PhotoImage(resized_modal)
            self.modal_image_label.config(image=self.modal_photo)
        # Cancel current update and schedule new
        if self.update_frames_id:
            self.after_cancel(self.update_frames_id)
        self.update_frames_id = self.after(self.period, self.update_frames)

    def close_modal(self, event=None):
        if self.modal_window:
            logger.info(f"[{time.strftime('%H:%M:%S')}] Closing modal window")
            self.modal_window.destroy()
            self.modal_window = None
            self.modal_name_label = None
            self.modal_image_label = None
            self.modal_photo = None
            self.modal_image_size = None
            self.modal_cell_index = None
            self.full_update = True
            if self.update_frames_id:
                self.after_cancel(self.update_frames_id)
            self.update_frames_id = self.after(self.period, self.update_frames)

    def on_cell_click(self, cell_index):
        if not self.cells[cell_index].cam:
            logger.info(f"[{time.strftime('%H:%M:%S')}] Clicked on empty cell {cell_index}")
            return
        cam = self.cells[cell_index].cam
        cam_street = cam["street"]
        logger.info(f"[{time.strftime('%H:%M:%S')}] Clicked on cell {cell_index}: selecting camera '{cam_street}'")
        current_group = next((g for g in self.groups if g.get("current", False)), None)
        if not current_group:
            logger.warning(f"[{time.strftime('%H:%M:%S')}] No current group found for cell click")
            messagebox.showwarning("Ошибка", "Нет текущей группы для выбора камеры")
            return
        group_name = current_group.get("name", "Группа")
        # Найти группу в дереве
        group_iid = None
        for iid in self.tree.get_children():
            if self.tree.item(iid)["text"] == group_name:
                group_iid = iid
                break
        if not group_iid:
            logger.warning(f"[{time.strftime('%H:%M:%S')}] Group '{group_name}' not found in tree")
            messagebox.showwarning("Ошибка", f"Группа '{group_name}' не найдена в дереве")
            return
        # Найти камеру в группе
        for child_iid in self.tree.get_children(group_iid):
            if self.tree.item(child_iid)["text"] == cam_street:
                self.tree.selection_set(child_iid)
                self.tree.focus(child_iid)
                self.on_tree_select(None)  # Обновить состояние кнопок и selected_camera
                return
        logger.warning(f"[{time.strftime('%H:%M:%S')}] Camera '{cam_street}' not found in group '{group_name}'")
        messagebox.showwarning("Ошибка", f"Камера '{cam_street}' не найдена в группе '{group_name}'")

    def initialize_drivers(self):
        self.drivers = []
        for _ in range(9):
            try:
                service = Service(self.driver_path)
                driver = webdriver.Chrome(service=service, options=self.options)
                driver.implicitly_wait(5)
                self.drivers.append(driver)
            except Exception as e:
                error_msg = f"[{time.strftime('%H:%M:%S')}] Error creating driver: {str(e)}"
                logger.error(error_msg)
                self.drivers.append(None)

    def set_frame_rate(self, period_ms):
        if self.update_frames_id:
            self.after_cancel(self.update_frames_id)
        self.period = period_ms
        self.update_frames_id = self.after(self.period, self.update_frames)

    def start_load_group_to_drivers(self):
        current_group = next((g for g in self.groups if g.get("current", False)), None)
        if not current_group:
            return
        current_grid = current_group.get("grid", [None] * 9)
        for i in range(9):
            try:
                if not self.drivers or len(self.drivers) <= i or not self.drivers[i]:
                    logger.warning(f"[{time.strftime('%H:%M:%S')}] Skipping load for cell {i}: driver not initialized")
                    continue
                url = current_grid[i] if i < len(current_grid) else None
                driver = self.drivers[i]
                if url:
                    driver.get(url)
                    driver.refresh()
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "ModalBodyPlayer")))
                else:
                    driver.get('about:blank')
            except Exception as e:
                error_msg = f"[{time.strftime('%H:%M:%S')}] Error loading for cell {i}: {str(e)}"
                logger.error(error_msg)
                messagebox.showerror("Ошибка загрузки", error_msg)

    def expand_tree(self):
        for item in self.tree.get_children():
            self.tree.item(item, open=True)

    def update_camera_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for group in self.groups:
            group_name = group.get("name", "Группа")
            group_iid = self.tree.insert(
                "", 
                "end", 
                text=group_name, 
                image=self.checked_photo if group.get("current", False) else self.unchecked_photo
            )
            for link in group.get("grid", []):
                if link:
                    cam = next((c for c in self.cams if c["link"] == link), None)
                    if cam:
                        self.tree.insert(group_iid, "end", text=cam["street"])
        self.expand_tree()
        # Устанавливаем фокус на текущую группу
        current_group = next((g for g in self.groups if g.get("current", False)), None)
        if current_group:
            for iid in self.tree.get_children():
                if self.tree.item(iid)["text"] == current_group["name"]:
                    self.tree.selection_set(iid)
                    self.tree.focus(iid)
                    break

    def move_top(self):
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        parent = self.tree.parent(item)
        if parent == "":  # Группа
            group_name = self.tree.item(item)["text"]
            group_index = next((i for i, g in enumerate(self.groups) if g.get("name") == group_name), -1)
            if group_index == -1 or group_index == 0:
                return
            logger.info(f"[{time.strftime('%H:%M:%S')}] Moving group '{group_name}' to top")
            group = self.groups.pop(group_index)
            self.groups.insert(0, group)
            save_config(self)
            self.update_camera_list()
            new_iid = next((iid for iid in self.tree.get_children() if self.tree.item(iid)["text"] == group_name), None)
            if new_iid:
                self.tree.selection_set(new_iid)
                self.tree.focus(new_iid)
        else:  # Камера
            group_iid = parent
            group_name = self.tree.item(group_iid)["text"]
            group = next((g for g in self.groups if g.get("name") == group_name), None)
            if not group:
                logger.error(f"[{time.strftime('%H:%M:%S')}] Group '{group_name}' not found in move_top")
                return
            if not self.tree.exists(group_iid):
                logger.error(f"[{time.strftime('%H:%M:%S')}] Group IID '{group_iid}' not found in tree")
                return
            children = self.tree.get_children(group_iid)
            cam_index = children.index(item)
            cam_name = self.tree.item(item)["text"]
            if cam_index == 0:
                return
            grid = group["grid"]
            non_none = [x for x in grid if x is not None]
            if cam_index >= len(non_none):
                return
            link = non_none[cam_index]
            non_none.pop(cam_index)
            non_none.insert(0, link)
            group["grid"] = non_none + [None] * (9 - len(non_none))
            logger.info(f"[{time.strftime('%H:%M:%S')}] Moving camera '{cam_name}' to top in group '{group_name}': {non_none}")
            is_current = group.get("current", False)
            if is_current:
                self.load_current_group_to_cells()
            save_config(self)
            self.update_camera_list()
            new_group_iid = next((iid for iid in self.tree.get_children() if self.tree.item(iid)["text"] == group_name), None)
            if new_group_iid and self.tree.exists(new_group_iid):
                new_children = self.tree.get_children(new_group_iid)
                if new_children:
                    new_item = new_children[0]  # Первая камера после перемещения
                    self.tree.selection_set(new_item)
                    self.tree.focus(new_item)
            else:
                logger.warning(f"[{time.strftime('%H:%M:%S')}] Group '{group_name}' not found after update in move_top")

    def move_bottom(self):
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        parent = self.tree.parent(item)
        if parent == "":  # Группа
            group_name = self.tree.item(item)["text"]
            group_index = next((i for i, g in enumerate(self.groups) if g.get("name") == group_name), -1)
            if group_index == -1 or group_index == len(self.groups) - 1:
                return
            logger.info(f"[{time.strftime('%H:%M:%S')}] Moving group '{group_name}' to bottom")
            group = self.groups.pop(group_index)
            self.groups.append(group)
            save_config(self)
            self.update_camera_list()
            new_iid = next((iid for iid in self.tree.get_children() if self.tree.item(iid)["text"] == group_name), None)
            if new_iid:
                self.tree.selection_set(new_iid)
                self.tree.focus(new_iid)
        else:  # Камера
            group_iid = parent
            group_name = self.tree.item(group_iid)["text"]
            group = next((g for g in self.groups if g.get("name") == group_name), None)
            if not group:
                logger.error(f"[{time.strftime('%H:%M:%S')}] Group '{group_name}' not found in move_bottom")
                return
            if not self.tree.exists(group_iid):
                logger.error(f"[{time.strftime('%H:%M:%S')}] Group IID '{group_iid}' not found in tree")
                return
            children = self.tree.get_children(group_iid)
            cam_index = children.index(item)
            cam_name = self.tree.item(item)["text"]
            non_none = [x for x in group["grid"] if x is not None]
            if cam_index >= len(non_none) - 1:
                return
            link = non_none[cam_index]
            non_none.pop(cam_index)
            non_none.append(link)
            group["grid"] = non_none + [None] * (9 - len(non_none))
            logger.info(f"[{time.strftime('%H:%M:%S')}] Moving camera '{cam_name}' to bottom in group '{group_name}': {non_none}")
            is_current = group.get("current", False)
            if is_current:
                self.load_current_group_to_cells()
            save_config(self)
            self.update_camera_list()
            new_group_iid = next((iid for iid in self.tree.get_children() if self.tree.item(iid)["text"] == group_name), None)
            if new_group_iid and self.tree.exists(new_group_iid):
                new_children = self.tree.get_children(new_group_iid)
                if new_children:
                    new_item = new_children[len(non_none) - 1]  # Последняя камера после перемещения
                    self.tree.selection_set(new_item)
                    self.tree.focus(new_item)
            else:
                logger.warning(f"[{time.strftime('%H:%M:%S')}] Group '{group_name}' not found after update in move_bottom")

    def move_up(self):
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        parent = self.tree.parent(item)
        if parent == "":  # Группа
            group_name = self.tree.item(item)["text"]
            group_index = next((i for i, g in enumerate(self.groups) if g.get("name") == group_name), -1)
            if group_index <= 0:
                return
            self.groups[group_index], self.groups[group_index - 1] = self.groups[group_index - 1], self.groups[group_index]
            save_config(self)
            self.update_camera_list()
            new_iid = next((iid for iid in self.tree.get_children() if self.tree.item(iid)["text"] == group_name), None)
            if new_iid:
                self.tree.selection_set(new_iid)
                self.tree.focus(new_iid)
        else:  # Камера
            group_iid = parent
            group_name = self.tree.item(group_iid)["text"]
            group = next((g for g in self.groups if g.get("name") == group_name), None)
            if not group:
                logger.error(f"[{time.strftime('%H:%M:%S')}] Group '{group_name}' not found in move_up")
                return
            # Проверяем, что group_iid существует
            if not self.tree.exists(group_iid):
                logger.error(f"[{time.strftime('%H:%M:%S')}] Group IID '{group_iid}' not found in tree")
                return
            children = self.tree.get_children(group_iid)
            cam_index = children.index(item)
            if cam_index <= 0:
                return
            # Swap в grid
            grid = group["grid"]
            non_none = [x for x in grid if x is not None]
            if cam_index >= len(non_none):
                return  # Не двигаем на пустые ячейки
            non_none[cam_index], non_none[cam_index - 1] = non_none[cam_index - 1], non_none[cam_index]
            group["grid"] = non_none + [None] * (9 - len(non_none))
            logger.info(f"[{time.strftime('%H:%M:%S')}] After move_up swap in group '{group_name}': {non_none}")
            is_current = group.get("current", False)
            if is_current:
                self.load_current_group_to_cells()  # Обновляем cells и drivers по новому grid перед сохранением
            save_config(self)  # Теперь сохраняем — grid не перезапишется старым
            self.update_camera_list()
            # Проверяем, что группа всё ещё существует
            new_group_iid = next((iid for iid in self.tree.get_children() if self.tree.item(iid)["text"] == group_name), None)
            if new_group_iid and self.tree.exists(new_group_iid):
                new_children = self.tree.get_children(new_group_iid)
                if cam_index - 1 < len(new_children):
                    new_item = new_children[cam_index - 1]
                    self.tree.selection_set(new_item)
                    self.tree.focus(new_item)
            else:
                logger.warning(f"[{time.strftime('%H:%M:%S')}] Group '{group_name}' not found after update in move_up")

    def move_down(self):
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        parent = self.tree.parent(item)
        if parent == "":  # Группа
            group_name = self.tree.item(item)["text"]
            group_index = next((i for i, g in enumerate(self.groups) if g.get("name") == group_name), -1)
            if group_index == -1 or group_index >= len(self.groups) - 1:
                return
            self.groups[group_index], self.groups[group_index + 1] = self.groups[group_index + 1], self.groups[group_index]
            save_config(self)
            self.update_camera_list()
            new_iid = next((iid for iid in self.tree.get_children() if self.tree.item(iid)["text"] == group_name), None)
            if new_iid:
                self.tree.selection_set(new_iid)
                self.tree.focus(new_iid)
        else:  # Камера
            group_iid = parent
            group_name = self.tree.item(group_iid)["text"]
            group = next((g for g in self.groups if g.get("name") == group_name), None)
            if not group:
                logger.error(f"[{time.strftime('%H:%M:%S')}] Group '{group_name}' not found in move_down")
                return
            # Проверяем, что group_iid существует
            if not self.tree.exists(group_iid):
                logger.error(f"[{time.strftime('%H:%M:%S')}] Group IID '{group_iid}' not found in tree")
                return
            children = self.tree.get_children(group_iid)
            cam_index = children.index(item)
            non_none = [x for x in group["grid"] if x is not None]
            if cam_index >= len(non_none) - 1:
                return  # Не двигаем на пустые ячейки или если последняя
            # Swap в grid
            non_none[cam_index], non_none[cam_index + 1] = non_none[cam_index + 1], non_none[cam_index]
            group["grid"] = non_none + [None] * (9 - len(non_none))
            logger.info(f"[{time.strftime('%H:%M:%S')}] After move_down swap in group '{group_name}': {non_none}")
            is_current = group.get("current", False)
            if is_current:
                self.load_current_group_to_cells()  # Обновляем cells и drivers по новому grid перед сохранением
            save_config(self)  # Теперь сохраняем — grid не перезапишется старым
            self.update_camera_list()
            # Проверяем, что группа всё ещё существует
            new_group_iid = next((iid for iid in self.tree.get_children() if self.tree.item(iid)["text"] == group_name), None)
            if new_group_iid and self.tree.exists(new_group_iid):
                new_children = self.tree.get_children(new_group_iid)
                if cam_index + 1 < len(new_children):
                    new_item = new_children[cam_index + 1]
                    self.tree.selection_set(new_item)
                    self.tree.focus(new_item)
            else:
                logger.warning(f"[{time.strftime('%H:%M:%S')}] Group '{group_name}' not found after update in move_down")

    def on_tree_select(self, event):
        selection = self.tree.selection()
        self.selected_camera = None
        self.edit_camera_button.config(state=tk.DISABLED)
        self.delete_camera_button.config(state=tk.DISABLED)
        if self.is_editing_structure:
            if not selection:
                self.move_top_button.config(state=tk.DISABLED)
                self.arrow_up_button.config(state=tk.DISABLED)
                self.arrow_down_button.config(state=tk.DISABLED)
                self.move_bottom_button.config(state=tk.DISABLED)
                self.tooltip_texts.update({
                    'move_top': '',
                    'move_up': '',
                    'move_down': '',
                    'move_bottom': ''
                })
                return
            item = selection[0]
            parent = self.tree.parent(item)
            if parent == "":  # Группа
                group_name = self.tree.item(item)["text"]
                group_index = next((i for i, g in enumerate(self.groups) if g.get("name") == group_name), -1)
                top_state = tk.NORMAL if group_index > 0 else tk.DISABLED
                up_state = tk.NORMAL if group_index > 0 else tk.DISABLED
                down_state = tk.NORMAL if group_index < len(self.groups) - 1 else tk.DISABLED
                bottom_state = tk.NORMAL if group_index < len(self.groups) - 1 else tk.DISABLED
                self.tooltip_texts.update({
                    'move_top': 'Переместить группу в начало списка',
                    'move_up': 'Переместить группу на позицию выше',
                    'move_down': 'Переместить группу на позицию ниже',
                    'move_bottom': 'Переместить группу в конец списка'
                })
            else:  # Камера
                group_iid = parent
                if not self.tree.exists(group_iid):
                    logger.error(f"[{time.strftime('%H:%M:%S')}] Group IID '{group_iid}' not found in on_tree_select")
                    self.move_top_button.config(state=tk.DISABLED)
                    self.arrow_up_button.config(state=tk.DISABLED)
                    self.arrow_down_button.config(state=tk.DISABLED)
                    self.move_bottom_button.config(state=tk.DISABLED)
                    self.tooltip_texts.update({
                        'move_top': '',
                        'move_up': '',
                        'move_down': '',
                        'move_bottom': ''
                    })
                    return
                children = self.tree.get_children(group_iid)
                cam_index = children.index(item)
                group_name = self.tree.item(group_iid)["text"]
                group = next((g for g in self.groups if g.get("name") == group_name), None)
                if not group:
                    logger.error(f"[{time.strftime('%H:%M:%S')}] Group '{group_name}' not found in on_tree_select")
                    self.move_top_button.config(state=tk.DISABLED)
                    self.arrow_up_button.config(state=tk.DISABLED)
                    self.arrow_down_button.config(state=tk.DISABLED)
                    self.move_bottom_button.config(state=tk.DISABLED)
                    self.tooltip_texts.update({
                        'move_top': '',
                        'move_up': '',
                        'move_down': '',
                        'move_bottom': ''
                    })
                    return
                non_none = [x for x in group["grid"] if x is not None]
                top_state = tk.NORMAL if cam_index > 0 else tk.DISABLED
                up_state = tk.NORMAL if cam_index > 0 else tk.DISABLED
                down_state = tk.NORMAL if cam_index < len(non_none) - 1 else tk.DISABLED
                bottom_state = tk.NORMAL if cam_index < len(non_none) - 1 else tk.DISABLED
                self.tooltip_texts.update({
                    'move_top': 'Переместить камеру в начало группы',
                    'move_up': 'Переместить камеру на позицию выше',
                    'move_down': 'Переместить камеру на позицию ниже',
                    'move_bottom': 'Переместить камеру в конец группы'
                })
            self.move_top_button.config(state=top_state)
            self.arrow_up_button.config(state=up_state)
            self.arrow_down_button.config(state=down_state)
            self.move_bottom_button.config(state=bottom_state)
            return
        if not self.groups:
            messagebox.showwarning("Ошибка", "Нет доступных групп для переключения")
            return
        if selection:
            item = selection[0]
            parent = self.tree.parent(item)
            if parent == "":
                group_name = self.tree.item(item)["text"]
                current_group = next((g for g in self.groups if g.get("current", False)), None)
                if current_group and current_group.get("name") == group_name:
                    return
                if messagebox.askyesno("Подтверждение", f"Хотите переключить вывод на '{group_name}'?"):
                    for group in self.groups:
                        group["current"] = (group["name"] == group_name)
                    self.load_current_group_to_cells()
                    save_config(self)
                    self.update_camera_list()
            else:
                cam_text = self.tree.item(item)["text"]
                self.selected_camera = next((c for c in self.cams if c["street"] == cam_text), None)
                if self.selected_camera:
                    self.edit_camera_button.config(state=tk.NORMAL)
                    self.delete_camera_button.config(state=tk.NORMAL)

    def toggle_structure_edit(self):
        if not self.is_editing_structure:
            self.is_editing_structure = True
            self.edit_structure_button.config(text="Сохранить\nизменения")
            for widget in self.top_frame.winfo_children():
                for child in widget.winfo_children():
                    child.configure(state='disabled')
            if self.update_frames_id:
                self.after_cancel(self.update_frames_id)
            self.set_frame_rate(3000)  # 1 кадр в 3 секунды в режиме редактирования
            self.tree_buttons_frame.pack(fill=tk.X, padx=3, pady=3, before=self.edit_structure_button)
            if self.tree.selection():
                self.on_tree_select(None)  # Обновить состояние кнопок
            else:
                self.move_top_button.config(state=tk.DISABLED)
                self.arrow_up_button.config(state=tk.DISABLED)
                self.arrow_down_button.config(state=tk.DISABLED)
                self.move_bottom_button.config(state=tk.DISABLED)
                self.tooltip_texts.update({
                    'move_top': '',
                    'move_up': '',
                    'move_down': '',
                    'move_bottom': ''
                })
        else:
            self.is_editing_structure = False
            self.edit_structure_button.config(text="Изменить\nструктуру")
            for widget in self.top_frame.winfo_children():
                for child in widget.winfo_children():
                    child.configure(state='normal')
            self.tree_buttons_frame.pack_forget()
            self.move_top_button.config(state=tk.DISABLED)
            self.arrow_up_button.config(state=tk.DISABLED)
            self.arrow_down_button.config(state=tk.DISABLED)
            self.move_bottom_button.config(state=tk.DISABLED)
            self.hide_tooltip()  # Скрываем подсказку при выходе из режима редактирования
            selected_rate = self.frame_rate_combobox.get()
            period_map = {"Кадр в 1 сек": 1000, "Кадр в 2 сек": 2000, "Кадр в 4 сек": 4000}
            new_period = period_map.get(selected_rate, 1000)
            if new_period != self.period:
                self.period = new_period
                self.config["period"] = self.period // 1000
                save_config(self)
            if self.update_frames_id:
                self.after_cancel(self.update_frames_id)
            self.update_frames_id = self.after(self.period, self.update_frames)

    def add_camera(self):
        if self.update_frames_id:
            self.after_cancel(self.update_frames_id)
        self.set_frame_rate(5000)
        dialog = CameraDialog(self)
        dialog.wait_window()
        self.set_frame_rate(self.original_period)  # Восстанавливаем исходный period
        if self.update_frames_id is None:
            self.update_frames_id = self.after(self.period, self.update_frames)
        if dialog.result:
            street, link = dialog.result
            if not link.startswith("http://maps.ufanet.ru/"):
                messagebox.showwarning("Ошибка", "Ссылка должна начинаться с 'http://maps.ufanet.ru/'")
                return
            if not street or not link:
                messagebox.showwarning("Ошибка", "Название и ссылка не могут быть пустыми")
                return
            if any(cam["link"] == link for cam in self.cams):
                messagebox.showwarning("Ошибка", "Камера с такой ссылкой уже существует")
                return
            # Проверка, не используется ли link в группах
            for group in self.groups:
                if link in group.get("grid", []):
                    messagebox.showwarning("Ошибка", f"Ссылка '{link}' уже используется в группе '{group['name']}'")
                    return
            new_cam = {"street": street, "link": link}
            self.cams.append(new_cam)
            added = False
            added_group_name = None
            is_current = False
            current_group = next((g for g in self.groups if g.get("current", False)), None)
            if not self.groups:
                new_group_name = f"Новая группа {time.strftime('%Y-%m-%d')}"
                new_group = {
                    "name": new_group_name,
                    "grid": [link] + [None] * 8,
                    "current": True
                }
                self.groups.append(new_group)
                added = True
                added_group_name = new_group_name
                is_current = True
                logger.info(f"[{time.strftime('%H:%M:%S')}] Created first group '{new_group_name}' and added camera")
            else:
                if current_group:
                    grid = current_group.get("grid", [None] * 9)
                    if None in grid:
                        free_index = grid.index(None)
                        grid[free_index] = link
                        current_group["grid"] = compact_grid(self, grid)
                        added = True
                        added_group_name = current_group["name"]
                        is_current = True
                if not added:
                    for group in self.groups:
                        if group == current_group:
                            continue
                        grid = group.get("grid", [None] * 9)
                        if None in grid:
                            free_index = grid.index(None)
                            grid[free_index] = link
                            group["grid"] = self.compact_grid(grid)
                            added = True
                            added_group_name = group["name"]
                            break
                if not added:
                    new_group_name = f"Новая группа {time.strftime('%Y-%m-%d')}"
                    new_group = {
                        "name": new_group_name,
                        "grid": [link] + [None] * 8,
                        "current": False
                    }
                    self.groups.append(new_group)
                    added = True
                    added_group_name = new_group_name
            if added:
                if is_current:
                    current_grid = current_group.get("grid", [None] * 9)
                    for i in range(9):
                        link_in_grid = current_grid[i] if i < len(current_grid) else None
                        if link_in_grid == link:
                            self.cells[i].cam = new_cam
                            self.cells[i].update_display()
                            break
                    self.start_load_group_to_drivers()
                else:
                    if messagebox.askyesno("Информация", f"Камера добавлена в группу '{added_group_name}'. Хотите переключиться на эту группу?"):
                        for group in self.groups:
                            group["current"] = (group["name"] == added_group_name)
                        self.load_current_group_to_cells()
                        save_config(self)
                        self.update_camera_list()
                save_config(self)
                self.update_camera_list()
                if not is_current:
                    messagebox.showinfo("Информация", f"Камера добавлена в группу '{added_group_name}'")
            else:
                logger.error(f"[{time.strftime('%H:%M:%S')}] Failed to add camera: no space found")
                messagebox.showerror("Ошибка", "Не удалось добавить камеру: нет свободных мест в группах. Создайте новую группу.")

    def edit_camera(self):
        if self.update_frames_id:
            self.after_cancel(self.update_frames_id)
        self.set_frame_rate(5000)
        dialog = CameraDialog(self, street=self.selected_camera["street"], link=self.selected_camera["link"], title="Изменить камеру")
        dialog.wait_window()
        self.set_frame_rate(self.original_period)  # Восстанавливаем исходный period
        if self.update_frames_id is None:
            self.update_frames_id = self.after(self.period, self.update_frames)
        if dialog.result:
            new_street, new_link = dialog.result
            if not new_street or not new_link:
                messagebox.showwarning("Ошибка", "Название и ссылка не могут быть пустыми")
                return
            if any(cam["link"] == new_link and cam != self.selected_camera for cam in self.cams):
                messagebox.showwarning("Ошибка", "Камера с такой ссылкой уже существует")
                return
            # Проверка, не используется ли новый link в группах
            for group in self.groups:
                if new_link in group.get("grid", []) and new_link != self.selected_camera["link"]:
                    messagebox.showwarning("Ошибка", f"Ссылка '{new_link}' уже используется в группе '{group['name']}'")
                    return
            old_link = self.selected_camera["link"]
            self.selected_camera["street"] = new_street
            self.selected_camera["link"] = new_link
            for group in self.groups:
                grid = group.get("grid", [])
                for i in range(len(grid)):
                    if grid[i] == old_link:
                        grid[i] = new_link
                group["grid"] = compact_grid(self, grid)
            save_config(self)
            self.update_camera_list()
            current_group = next((g for g in self.groups if g.get("current", False)), None)
            if current_group:
                current_grid = current_group.get("grid", [None] * 9)
                for i in range(9):
                    if i < len(current_grid) and current_grid[i] == new_link:
                        self.cells[i].cam = self.selected_camera
                        self.cells[i].update_display()
                        driver = self.drivers[i]
                        if driver:
                            driver.get(new_link)
                            driver.refresh()
                            try:
                                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "ModalBodyPlayer")))
                            except Exception as e:
                                logger.error(f"[{time.strftime('%H:%M:%S')}] Error reloading driver for cell {i}: {str(e)}")

    def delete_camera(self):
        if not self.selected_camera:
            return
        cam_name = self.selected_camera["street"]
        link = self.selected_camera["link"]
        if not messagebox.askyesno("Подтверждение", f"Удалить камеру '{cam_name}'?"):
            return
        logger.info(f"[{time.strftime('%H:%M:%S')}] Deleting camera '{cam_name}' with link '{link}'")
        # Удаляем из cams
        self.cams = [cam for cam in self.cams if cam["link"] != link]
        # Удаляем из групп и проверяем на пустоту
        groups_to_remove = []
        for group in self.groups:
            grid = group.get("grid", [])
            new_grid = [l for l in grid if l != link]
            group["grid"] = compact_grid(self, new_grid)
            # Не удаляем последнюю группу, даже если она пуста
            if all(g is None for g in group["grid"]) and len(self.groups) > 1:
                groups_to_remove.append(group)
        if groups_to_remove:
            self.groups = [g for g in self.groups if g not in groups_to_remove]
            logger.info(f"[{time.strftime('%H:%M:%S')}] Removed {len(groups_to_remove)} empty groups after camera deletion")
        elif len(self.groups) == 1 and all(g is None for g in self.groups[0]["grid"]):
            logger.info(f"[{time.strftime('%H:%M:%S')}] Last group '{self.groups[0]['name']}' kept empty after camera deletion")
        self.selected_camera = None
        self.edit_camera_button.config(state=tk.DISABLED)
        self.delete_camera_button.config(state=tk.DISABLED)
        self.load_current_group_to_cells()  # Синхронизируем ячейки с новым grid
        save_config(self)
        self.update_camera_list()
        self.start_load_group_to_drivers()

    def edit_group(self):
        if self.update_frames_id:
            self.after_cancel(self.update_frames_id)
        self.set_frame_rate(5000)
        dialog = CameraDialog(self, street=next((g for g in self.groups if g.get("current", False)), {}).get("name", ""), title="Изменить группу", is_group=True)
        dialog.wait_window()
        self.set_frame_rate(self.original_period)  # Восстанавливаем исходный period
        if self.update_frames_id is None:
            self.update_frames_id = self.after(self.period, self.update_frames)
        if dialog.result:
            new_name, _ = dialog.result
            current_group = next((g for g in self.groups if g.get("current", False)), None)
            if not current_group:
                messagebox.showwarning("Ошибка", "Нет текущей группы для редактирования")
                return
            if new_name == current_group["name"]:
                return
            if not new_name:
                messagebox.showwarning("Ошибка", "Название группы не может быть пустым")
                return
            if any(group["name"] == new_name for group in self.groups if group != current_group):
                messagebox.showwarning("Ошибка", "Группа с таким названием уже существует")
                return
            current_group["name"] = new_name
            save_config(self)
            self.update_camera_list()

    def reload_drivers(self):
        self.start_load_group_to_drivers()

    def update_frames(self):
        logger = logging.getLogger(__name__)
        for cell in self.cells:
            if not self.full_update and cell.index != self.modal_cell_index:
                continue
            if not cell.cam or not self.drivers[cell.index]:
                cell.photo = self.nocam_photo if not cell.cam else self.noconnect_photo
                cell.image_label.config(image=cell.photo)
                continue
            driver = self.drivers[cell.index]
            try:
                if driver.current_url == 'about:blank':
                    cell.photo = self.nocam_photo
                    cell.image_label.config(image=cell.photo)
                    continue
            except Exception as e:
                logger.error(f"[{time.strftime('%H:%M:%S')}] Error checking url for cell {cell.index}: {str(e)}")
                cell.photo = self.noconnect_photo
                cell.image_label.config(image=cell.photo)
                continue
            try:
                element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "ModalBodyPlayer"))
                )
                screenshot_bytes = None
                try:
                    iframe = element.find_element(By.TAG_NAME, "iframe")
                    driver.switch_to.frame(iframe)
                    body = driver.find_element(By.TAG_NAME, "body")
                    screenshot_bytes = body.screenshot_as_png
                except:
                    driver.switch_to.default_content()
                    screenshot_bytes = element.screenshot_as_png
                
                if screenshot_bytes:
                    pil_image = Image.open(io.BytesIO(screenshot_bytes))
                    img_array = np.array(pil_image)
                    height, width, _ = img_array.shape
                    
                    # Обрезка слева и справа
                    crop_fraction = 17 / 235
                    left_crop = int(width * crop_fraction)
                    right_crop = int(width * crop_fraction)
                    cropped_image = pil_image.crop((left_crop, 0, width - right_crop, height))
                    
                    # Получаем реальные размеры ячейки
                    target_width = cell.image_label.winfo_width()
                    target_height = cell.image_label.winfo_height()
                    if target_width <= 1 or target_height <= 1:
                        target_width = self.cell_width
                        target_height = self.cell_height - 30  # Вычет на name_label
                    
                    # Растяжение до размера ячейки с искажением
                    resized_small = cropped_image.resize((target_width, target_height), Image.LANCZOS)
                    cell.photo = ImageTk.PhotoImage(resized_small)
                    cell.image_label.config(image=cell.photo)
                    
                    self.original_pil_images[cell.index] = cropped_image.copy()
                    
                    if self.modal_cell_index == cell.index and self.modal_image_label:
                        modal_width = self.modal_image_size[0] if isinstance(self.modal_image_size, tuple) else self.modal_image_size
                        modal_height = self.modal_image_size[1] if isinstance(self.modal_image_size, tuple) else self.modal_image_size
                        resized_modal = cropped_image.resize((modal_width, modal_height), Image.LANCZOS)
                        self.modal_photo = ImageTk.PhotoImage(resized_modal)
                        self.modal_image_label.config(image=self.modal_photo)
                else:
                    logger.warning(f"[{time.strftime('%H:%M:%S')}] Cell {cell.index}: No screenshot bytes")
                driver.switch_to.default_content()
            except Exception as e:
                logger.error(f"[{time.strftime('%H:%M:%S')}] Error updating frame for cell {cell.index}: {str(e)}")
                cell.photo = self.noconnect_photo
                cell.image_label.config(image=cell.photo)
        self.update_frames_id = self.after(self.period, self.update_frames)

    def _update_label_size(self, cell):
        import logging
        logger = logging.getLogger(__name__)
        label_width = cell.image_label.winfo_width()
        label_height = cell.image_label.winfo_height()
        logger.info(f"[{time.strftime('%H:%M:%S')}] Cell {cell.index}: Label size after update {label_width}x{label_height}")
        if label_width > 1 and label_height > 1 and cell.photo and cell.index < len(self.original_pil_images) and self.original_pil_images[cell.index] is not None:
            # Используем сохранённое обрезанное изображение для пересчёта
            pil_image = self.original_pil_images[cell.index]
            resized = pil_image.resize((label_width, label_height), Image.LANCZOS)
            cell.photo = ImageTk.PhotoImage(resized)
            cell.image_label.config(image=cell.photo)
            logger.info(f"[{time.strftime('%H:%M:%S')}] Cell {cell.index}: Resized to match label {label_width}x{label_height}")


    def load_current_group_to_cells(self):
        current_group = next((g for g in self.groups if g.get("current", False)), None)
        if current_group:
            current_grid = current_group.get("grid", [None] * 9)
            for i in range(9):
                self.cells[i].cam = None  # Очищаем ячейку
                self.original_pil_images[i] = None
                link = current_grid[i] if i < len(current_grid) else None
                if link:
                    for cam in self.cams:
                        if cam["link"] == link:
                            self.cells[i].cam = cam
                            break
                self.cells[i].update_display()
            self.start_load_group_to_drivers()

    def on_close(self):
        self.close_modal()
        if self.update_frames_id:
            self.after_cancel(self.update_frames_id)
        for driver in self.drivers:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    error_msg = f"[{time.strftime('%H:%M:%S')}] Error quitting driver: {str(e)}"
                    logger.error(error_msg)
        self.destroy()      

     

