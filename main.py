import sys
import os
import logging
import time
import json
import re
import tkinter as tk
from tkinter import ttk, messagebox, Toplevel, Label, Entry, Button
from tkinter.font import Font
from PIL import Image, ImageTk
import io
import numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Настройка logging в файл
logging.basicConfig(filename='app.log', level=logging.ERROR, force=True)
logger = logging.getLogger(__name__)

class CameraDialog(Toplevel):
    def __init__(self, parent=None, street="", link="", title="Добавить камеру", is_group=False):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()
        
        window_width = 600
        window_height = 160 if not is_group else 120
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        self.font = Font(family="Arial", size=11)
        
        paste_img = Image.open("resource/paste.png")
        paste_img = paste_img.resize((24, 24), Image.LANCZOS)
        self.paste_photo = ImageTk.PhotoImage(paste_img)
        
        self.main_frame = tk.Frame(self)
        self.main_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        self.street_label = Label(self.main_frame, text="Название:", font=self.font)
        self.street_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.street_entry = Entry(self.main_frame, font=self.font)
        self.street_entry.insert(0, street)
        self.street_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.street_paste_button = Button(
            self.main_frame,
            image=self.paste_photo,
            command=lambda: self.paste_text(self.street_entry)
        )
        self.street_paste_button.grid(row=0, column=2, padx=5, pady=5)
        if is_group:
            self.street_paste_button.grid_remove()
        
        self.link_label = Label(self.main_frame, text="Ссылка:", font=self.font)
        self.link_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.link_entry = Entry(self.main_frame, font=self.font)
        self.link_entry.insert(0, link)
        self.link_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        self.link_paste_button = Button(
            self.main_frame,
            image=self.paste_photo,
            command=lambda: self.paste_text(self.link_entry)
        )
        self.link_paste_button.grid(row=1, column=2, padx=5, pady=5)
        
        if is_group:
            self.link_label.grid_remove()
            self.link_entry.grid_remove()
            self.link_paste_button.grid_remove()
        
        self.main_frame.columnconfigure(1, weight=1)
        
        self.button_frame = tk.Frame(self.main_frame)
        self.button_frame.grid(row=2 if not is_group else 1, column=0, columnspan=3, pady=15)
        
        self.save_button = Button(
            self.button_frame,
            text="Сохранить",
            font=self.font,
            command=self.accept,
            width=10
        )
        self.save_button.pack(side=tk.LEFT, padx=(0, 15))
        
        self.cancel_button = Button(
            self.button_frame,
            text="Отмена",
            font=self.font,
            command=self.destroy,
            width=10
        )
        self.cancel_button.pack(side=tk.LEFT)
        
        self.result = None
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def paste_text(self, entry):
        try:
            text = self.clipboard_get()
            entry.delete(0, tk.END)
            entry.insert(0, text)
        except Exception as e:
            messagebox.showwarning("Ошибка", f"Не удалось вставить текст: {str(e)}")

    def accept(self):
        self.result = (self.street_entry.get(), self.link_entry.get())
        self.destroy()

class CellFrame(tk.Frame):
    def __init__(self, parent, index):
        super().__init__(parent)
        self.index = index
        self.cam = None
        
        self.name_label = Label(self, text="", font=Font(family="Arial", size=11), height=1)
        self.name_label.pack(fill=tk.X)
        
        self.image_label = Label(self)
        self.image_label.pack(expand=True, fill=tk.BOTH)
        
        self.update_display()

    def update_display(self):
        if not self.cam:
            self.name_label.config(text="")
            self.photo = self.winfo_toplevel().nocam_photo
            self.image_label.config(image=self.photo)
        else:
            self.name_label.config(text=self.cam["street"])
            self.photo = self.winfo_toplevel().noconnect_photo
            self.image_label.config(image=self.photo)

class MainApp(tk.Tk):
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
        self.drivers = []
        self.update_frames_id = None
        self.is_editing_structure = False
        
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
        
        self.arrow_up_button = Button(
            self.tree_buttons_frame,
            image=self.arrow_up_photo,
            command=self.move_group_up,
            state=tk.DISABLED
        )
        self.arrow_up_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        
        self.arrow_down_button = Button(
            self.tree_buttons_frame,
            image=self.arrow_down_photo,
            command=self.move_group_down,
            state=tk.DISABLED
        )
        self.arrow_down_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))
        
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
        
        self.initialize_drivers()
        
        self.start_load_group_to_drivers()
        
        self.update_frames()
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def clean_config_data(self):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.info(f"[{time.strftime('%H:%M:%S')}] config.json not found or corrupted: {str(e)}. Creating default config.")
            config = {"cams": [], "groups": [], "period": 1}
        
        # 1. Удаление дубликатов камер по ссылке
        cams = config.get("cams", [])
        seen_links = set()
        unique_cams = []
        for cam in cams:
            link = cam.get("link")
            if link and link not in seen_links:
                seen_links.add(link)
                unique_cams.append(cam)
            else:
                logger.info(f"[{time.strftime('%H:%M:%S')}] Removed duplicate camera with link: {link}")
        config["cams"] = unique_cams
        if len(unique_cams) < len(cams):
            logger.info(f"[{time.strftime('%H:%M:%S')}] Duplicates removed from cams list. Remaining: {len(unique_cams)}")

        # 2. Очистка групп от недействительных ссылок
        existing_links = {cam["link"] for cam in config["cams"]}
        groups = config.get("groups", [])
        invalid_links_found = False
        for group in groups:
            grid = group.get("grid", [None] * 9)
            new_grid = [link if link in existing_links or link is None else None for link in grid]
            if new_grid != grid:
                invalid_links_found = True
                logger.info(f"[{time.strftime('%H:%M:%S')}] Removed invalid links from group '{group.get('name', 'Группа')}'")
            group["grid"] = [x for x in new_grid if x is not None] + [None] * (9 - len([x for x in new_grid if x is not None]))
        if invalid_links_found:
            logger.info(f"[{time.strftime('%H:%M:%S')}] Invalid links removed from groups.")

        # 3. Удаление дубликатов ссылок по всем группам (глобально)
        seen_links = set()
        duplicates_found = False
        for group in groups:
            grid = group.get("grid", [None] * 9)
            new_grid = []
            for link in grid:
                if link is None:
                    new_grid.append(None)
                elif link not in seen_links:
                    seen_links.add(link)
                    new_grid.append(link)
                else:
                    new_grid.append(None)
                    duplicates_found = True
                    logger.info(f"[{time.strftime('%H:%M:%S')}] Removed duplicate link '{link}' from group '{group.get('name', 'Группа')}'")
            group["grid"] = [x for x in new_grid if x is not None] + [None] * (9 - len([x for x in new_grid if x is not None]))
        if duplicates_found:
            logger.info(f"[{time.strftime('%H:%M:%S')}] Global duplicates removed from groups.")

        # 4. Удаление пустых групп
        initial_group_count = len(groups)
        groups = [g for g in groups if any(link is not None for link in g["grid"])]
        if len(groups) < initial_group_count:
            logger.info(f"[{time.strftime('%H:%M:%S')}] Removed {initial_group_count - len(groups)} empty groups.")
            if not groups:
                groups.append({"name": f"Новая группа {time.strftime('%Y-%m-%d')}", "grid": [None] * 9, "current": True})
                logger.info(f"[{time.strftime('%H:%M:%S')}] Created new empty group as no groups remain.")
            else:
                current_group = next((g for g in groups if g.get("current", False)), None)
                if not current_group:
                    groups[0]["current"] = True
                    logger.info(f"[{time.strftime('%H:%M:%S')}] Set first group as current after empty group removal.")

        # 5. Добавление потерянных камер в группы
        all_used_links = set()
        for group in groups:
            for link in group.get("grid", []):
                if link:
                    all_used_links.add(link)
        
        lost_cams = [cam for cam in config["cams"] if cam["link"] not in all_used_links]
        if lost_cams:
            logger.info(f"[{time.strftime('%H:%M:%S')}] Found {len(lost_cams)} lost cameras. Adding to groups.")
            for cam in lost_cams:
                link = cam["link"]
                added = False
                added_group_name = None
                current_group = next((g for g in groups if g.get("current", False)), None)
                
                if not groups:
                    new_group_name = f"Новая группа {time.strftime('%Y-%m-%d')}"
                    new_group = {
                        "name": new_group_name,
                        "grid": [link] + [None] * 8,
                        "current": True
                    }
                    groups.append(new_group)
                    added = True
                    added_group_name = new_group_name
                    logger.info(f"[{time.strftime('%H:%M:%S')}] Created first group '{new_group_name}' for lost camera: {cam['street']}")
                else:
                    if current_group:
                        grid = current_group.get("grid", [None] * 9)
                        if None in grid:
                            free_index = grid.index(None)
                            grid[free_index] = link
                            current_group["grid"] = [x for x in grid if x is not None] + [None] * (9 - len([x for x in grid if x is not None]))
                            added = True
                            added_group_name = current_group["name"]
                            logger.info(f"[{time.strftime('%H:%M:%S')}] Added lost camera '{cam['street']}' to current group '{added_group_name}'")
                    
                    if not added:
                        for group in groups:
                            if group == current_group:
                                continue
                            grid = group.get("grid", [None] * 9)
                            if None in grid:
                                free_index = grid.index(None)
                                grid[free_index] = link
                                group["grid"] = [x for x in grid if x is not None] + [None] * (9 - len([x for x in grid if x is not None]))
                                added = True
                                added_group_name = group["name"]
                                logger.info(f"[{time.strftime('%H:%M:%S')}] Added lost camera '{cam['street']}' to group '{added_group_name}'")
                                break
                    
                    if not added:
                        new_group_name = f"Новая группа {time.strftime('%Y-%m-%d')}"
                        new_group = {
                            "name": new_group_name,
                            "grid": [link] + [None] * 8,
                            "current": False
                        }
                        groups.append(new_group)
                        added = True
                        added_group_name = new_group_name
                        logger.info(f"[{time.strftime('%H:%M:%S')}] Created new group '{new_group_name}' for lost camera: {cam['street']}")
        
        config["groups"] = groups
        # Сохранение очищенной конфигурации
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info(f"[{time.strftime('%H:%M:%S')}] Cleaned config saved to config.json.")
        except Exception as e:
            logger.error(f"[{time.strftime('%H:%M:%S')}] Error saving cleaned config: {str(e)}")
        
        return config

    def compact_grid(self, grid):
        non_none = [x for x in grid if x is not None]
        return non_none + [None] * (9 - len(non_none))

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

    def move_group_up(self):
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        parent = self.tree.parent(item)
        if parent != "":
            return
        group_name = self.tree.item(item)["text"]
        group_index = next((i for i, g in enumerate(self.groups) if g.get("name") == group_name), -1)
        if group_index <= 0:
            return
        self.groups[group_index], self.groups[group_index - 1] = self.groups[group_index - 1], self.groups[group_index]
        self.save_config()
        self.update_camera_list()
        new_iid = next(iid for iid in self.tree.get_children() if self.tree.item(iid)["text"] == group_name)
        self.tree.selection_set(new_iid)
        self.tree.focus(new_iid)

    def move_group_down(self):
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        parent = self.tree.parent(item)
        if parent != "":
            return
        group_name = self.tree.item(item)["text"]
        group_index = next((i for i, g in enumerate(self.groups) if g.get("name") == group_name), -1)
        if group_index == -1 or group_index >= len(self.groups) - 1:
            return
        self.groups[group_index], self.groups[group_index + 1] = self.groups[group_index + 1], self.groups[group_index]
        self.save_config()
        self.update_camera_list()
        new_iid = next(iid for iid in self.tree.get_children() if self.tree.item(iid)["text"] == group_name)
        self.tree.selection_set(new_iid)
        self.tree.focus(new_iid)

    def on_tree_select(self, event):
        selection = self.tree.selection()
        self.selected_camera = None
        self.edit_camera_button.config(state=tk.DISABLED)
        if self.is_editing_structure:
            if selection:
                self.arrow_up_button.config(state=tk.NORMAL)
                self.arrow_down_button.config(state=tk.NORMAL)
            else:
                self.arrow_up_button.config(state=tk.DISABLED)
                self.arrow_down_button.config(state=tk.DISABLED)
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
                    self.save_config()
                    self.update_camera_list()
            else:
                cam_text = self.tree.item(item)["text"]
                self.selected_camera = next((c for c in self.cams if c["street"] == cam_text), None)
                if self.selected_camera:
                    self.edit_camera_button.config(state=tk.NORMAL)

    def toggle_structure_edit(self):
        if not self.is_editing_structure:
            self.is_editing_structure = True
            self.edit_structure_button.config(text="Сохранить\nизменения")
            for widget in self.top_frame.winfo_children():
                for child in widget.winfo_children():
                    child.configure(state='disabled')
            if self.update_frames_id:
                self.after_cancel(self.update_frames_id)
                self.update_frames_id = None
            self.tree_buttons_frame.pack(fill=tk.X, padx=3, pady=3, before=self.edit_structure_button)
            if self.tree.selection():
                self.arrow_up_button.config(state=tk.NORMAL)
                self.arrow_down_button.config(state=tk.NORMAL)
            else:
                self.arrow_up_button.config(state=tk.DISABLED)
                self.arrow_down_button.config(state=tk.DISABLED)
        else:
            self.is_editing_structure = False
            self.edit_structure_button.config(text="Изменить\nструктуру")
            for widget in self.top_frame.winfo_children():
                for child in widget.winfo_children():
                    child.configure(state='normal')
            self.tree_buttons_frame.pack_forget()
            self.arrow_up_button.config(state=tk.DISABLED)
            self.arrow_down_button.config(state=tk.DISABLED)
            selected_rate = self.frame_rate_combobox.get()
            period_map = {"Кадр в 1 сек": 1000, "Кадр в 2 сек": 2000, "Кадр в 4 сек": 4000}
            self.set_frame_rate(period_map.get(selected_rate, 1000))

    def add_camera(self):
        self.set_frame_rate(5000)
        dialog = CameraDialog(self)
        dialog.wait_window()
        selected_rate = self.frame_rate_combobox.get()
        period_map = {"Кадр в 1 сек": 1000, "Кадр в 2 сек": 2000, "Кадр в 4 сек": 4000}
        self.set_frame_rate(period_map.get(selected_rate, 1000))
        if dialog.result:
            street, link = dialog.result
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
                        current_group["grid"] = self.compact_grid(grid)
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
                        self.save_config()
                        self.update_camera_list()
                self.save_config()
                self.update_camera_list()
                if not is_current and not messagebox.askyesno("Информация", "Хотите добавить ещё одну камеру?"):
                    messagebox.showinfo("Информация", f"Камера добавлена в группу '{added_group_name}'")
            else:
                logger.error(f"[{time.strftime('%H:%M:%S')}] Failed to add camera: no space found")
                messagebox.showerror("Ошибка", "Не удалось добавить камеру: нет свободных мест в группах. Создайте новую группу.")

    def edit_camera(self):
        if not self.selected_camera:
            return
        self.set_frame_rate(5000)
        dialog = CameraDialog(self, street=self.selected_camera["street"], link=self.selected_camera["link"], title="Изменить камеру")
        dialog.wait_window()
        selected_rate = self.frame_rate_combobox.get()
        period_map = {"Кадр в 1 сек": 1000, "Кадр в 2 сек": 2000, "Кадр в 4 сек": 4000}
        self.set_frame_rate(period_map.get(selected_rate, 1000))
        if dialog.result:
            new_street, new_link = dialog.result
            if new_street == self.selected_camera["street"] and new_link == self.selected_camera["link"]:
                return
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
                group["grid"] = self.compact_grid(grid)
            self.save_config()
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

    def edit_group(self):
        current_group = next((g for g in self.groups if g.get("current", False)), None)
        if not current_group:
            messagebox.showwarning("Ошибка", "Нет текущей группы для редактирования")
            return
        self.set_frame_rate(5000)
        dialog = CameraDialog(self, street=current_group["name"], title="Изменить группу", is_group=True)
        dialog.wait_window()
        selected_rate = self.frame_rate_combobox.get()
        period_map = {"Кадр в 1 сек": 1000, "Кадр в 2 сек": 2000, "Кадр в 4 сек": 4000}
        self.set_frame_rate(period_map.get(selected_rate, 1000))
        if dialog.result:
            new_name, _ = dialog.result
            if new_name == current_group["name"]:
                return
            if not new_name:
                messagebox.showwarning("Ошибка", "Название группы не может быть пустым")
                return
            if any(group["name"] == new_name for group in self.groups if group != current_group):
                messagebox.showwarning("Ошибка", "Группа с таким названием уже существует")
                return
            current_group["name"] = new_name
            self.save_config()
            self.update_camera_list()

    def reload_drivers(self):
        self.start_load_group_to_drivers()

    def update_frames(self):
        for cell in self.cells:
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
                    if body.size['height'] == 0:
                        driver.execute_script("document.body.style.height = '300px';")
                        driver.execute_script("document.body.style.display = 'block';")
                    screenshot_bytes = body.screenshot_as_png
                except:
                    driver.switch_to.default_content()
                    style = element.get_attribute('style')
                    height_match = re.search(r'height:\s*(\d+)px', style, re.IGNORECASE)
                    height = int(height_match.group(1)) if height_match else 300
                    if element.size['height'] == 0:
                        driver.execute_script(f"arguments[0].style.height = '{height}px';", element)
                        driver.execute_script("arguments[0].style.display = 'block';", element)
                    screenshot_bytes = element.screenshot_as_png
                
                if screenshot_bytes:
                    pil_image = Image.open(io.BytesIO(screenshot_bytes))
                    img_array = np.array(pil_image)
                    height, width, _ = img_array.shape
                    left = 0
                    for x in range(width):
                        if np.any(img_array[:, x] != [0, 0, 0]):
                            left = x
                            break
                    right = width
                    for x in range(width - 1, -1, -1):
                        if np.any(img_array[:, x] != [0, 0, 0]):
                            right = x + 1
                            break
                    cropped_image = pil_image.crop((left, 0, right, height))
                    cropped_image = cropped_image.resize((self.cell_width, self.cell_height), Image.LANCZOS)
                    cell.photo = ImageTk.PhotoImage(cropped_image)
                    cell.image_label.config(image=cell.photo)
                driver.switch_to.default_content()
            except Exception as e:
                error_msg = f"[{time.strftime('%H:%M:%S')}] Error updating frame for cell {cell.index}: {str(e)}"
                logger.error(error_msg)
                cell.photo = self.noconnect_photo
                cell.image_label.config(image=cell.photo)
        self.update_frames_id = self.after(self.period, self.update_frames)

    def save_config(self):
        current_group = next((g for g in self.groups if g.get("current", False)), None)
        if current_group:
            current_grid = [cell.cam["link"] if cell.cam else None for cell in self.cells]
            current_group["grid"] = self.compact_grid(current_grid)
        self.config["groups"] = self.groups
        self.config["cams"] = self.cams
        self.config["period"] = self.period // 1000
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info(f"[{time.strftime('%H:%M:%S')}] Config saved to config.json.")
        except Exception as e:
            logger.error(f"[{time.strftime('%H:%M:%S')}] Error saving config: {str(e)}")
            messagebox.showerror("Ошибка", "Не удалось сохранить конфигурацию")
        
        if current_group:
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
            self.start_load_group_to_drivers()

    def on_close(self):
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

    def load_current_group_to_cells(self):
        current_group = next((g for g in self.groups if g.get("current", False)), None)
        if current_group:
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
            self.start_load_group_to_drivers()

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()