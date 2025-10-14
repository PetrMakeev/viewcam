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
        # Устанавливаем модальность
        self.transient(parent)
        self.grab_set()
        
        # Центрируем окно на экране
        window_width = 600
        window_height = 160 if not is_group else 120  # Меньше высота для группы
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        self.font = Font(family="Arial", size=11)
        
        # Загружаем и масштабируем изображение для кнопок вставки
        paste_img = Image.open("resource/paste.png")
        paste_img = paste_img.resize((24, 24), Image.LANCZOS)
        self.paste_photo = ImageTk.PhotoImage(paste_img)
        
        # Контейнер для элементов
        self.main_frame = tk.Frame(self)
        self.main_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        # Название
        self.street_label = Label(self.main_frame, text="Название:", font=self.font)
        self.street_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.street_entry = Entry(self.main_frame, font=self.font)
        self.street_entry.insert(0, street)
        self.street_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Кнопка вставки для названия (скрывается для группы)
        self.street_paste_button = Button(
            self.main_frame,
            image=self.paste_photo,
            command=lambda: self.paste_text(self.street_entry)
        )
        self.street_paste_button.grid(row=0, column=2, padx=5, pady=5)
        if is_group:
            self.street_paste_button.grid_remove()
        
        # Ссылка (скрывается для группы)
        self.link_label = Label(self.main_frame, text="Ссылка:", font=self.font)
        self.link_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.link_entry = Entry(self.main_frame, font=self.font)
        self.link_entry.insert(0, link)
        self.link_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        # Кнопка вставки для ссылки
        self.link_paste_button = Button(
            self.main_frame,
            image=self.paste_photo,
            command=lambda: self.paste_text(self.link_entry)
        )
        self.link_paste_button.grid(row=1, column=2, padx=5, pady=5)
        
        # Скрываем элементы ссылки, если редактируем группу
        if is_group:
            self.link_label.grid_remove()
            self.link_entry.grid_remove()
            self.link_paste_button.grid_remove()
        
        # Настройка растяжки столбцов
        self.main_frame.columnconfigure(1, weight=1)
        
        # Фрейм для кнопок Сохранить/Отмена
        self.button_frame = tk.Frame(self.main_frame)
        self.button_frame.grid(row=2 if not is_group else 1, column=0, columnspan=3, pady=15)
        
        # Кнопка Сохранить
        self.save_button = Button(
            self.button_frame,
            text="Сохранить",
            font=self.font,
            command=self.accept,
            width=10
        )
        self.save_button.pack(side=tk.LEFT, padx=(0, 15))
        
        # Кнопка Отмена
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
        
        # Сохраняем размеры ячеек
        self.cell_width = (screen_width - 10 - 300) // 3
        self.cell_height = (screen_height - 15) // 3
        
        # Кэширование масштабированных изображений для ячеек
        nocam_img = Image.open("resource/nocam.png")
        nocam_img = nocam_img.resize((self.cell_width, self.cell_height), Image.LANCZOS)
        self.nocam_photo = ImageTk.PhotoImage(nocam_img)
        
        noconnect_img = Image.open("resource/noconnect.png")
        noconnect_img = noconnect_img.resize((self.cell_width, self.cell_height), Image.LANCZOS)
        self.noconnect_photo = ImageTk.PhotoImage(noconnect_img)
        
        # Кэширование изображений для дерева
        checked_img = Image.open("resource/ui-check-box.png")
        checked_img = checked_img.resize((24, 24), Image.LANCZOS)
        self.checked_photo = ImageTk.PhotoImage(checked_img)
        
        unchecked_img = Image.open("resource/ui-check-box-uncheck.png")
        unchecked_img = unchecked_img.resize((24, 24), Image.LANCZOS)
        self.unchecked_photo = ImageTk.PhotoImage(unchecked_img)
        
        # Загрузка конфигурации
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {"cams": [], "groups": [], "period": 1}
        self.period = self.config.get("period", 1) * 1000
        self.original_period = self.period  # Сохраняем исходный период
        self.groups = self.config.get("groups", [])
        self.cams = self.config.get("cams", [])
        self.selected_camera = None
        self.drivers = []  # Список из 9 фиксированных драйверов
        self.update_frames_id = None  # Для хранения ID таймера
        
        # Настройка стиля для комбобоксов
        style = ttk.Style()
        style.configure("Custom.TCombobox", padding=(5, 2, 5, 2))
        
        # Левая панель
        left_frame = tk.Frame(self, width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        self.tree = ttk.Treeview(left_frame, show="tree")
        self.tree.pack(expand=True, fill=tk.BOTH, padx=3, pady=3)
        self.update_camera_list()
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        # Правая часть: верхний фрейм с элементами управления и сетка камер
        right_frame = tk.Frame(self)
        right_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        
        # Верхний фрейм для кнопок и комбобоксов
        top_frame = tk.Frame(right_frame, relief="sunken", borderwidth=2)
        top_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        # Внутренний фрейм для центрирования элементов
        controls_frame = tk.Frame(top_frame)
        controls_frame.pack(anchor="center")
        
        # Кнопка "Добавить камеру"
        self.add_camera_button = Button(
            controls_frame,
            text="Добавить камеру",
            font=Font(family="Arial", size=11),
            command=self.add_camera,
            width=20
        )
        self.add_camera_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        # Кнопка "Изменить камеру"
        self.edit_camera_button = Button(
            controls_frame,
            text="Изменить камеру",
            font=Font(family="Arial", size=11),
            command=self.edit_camera,
            width=20,
            state=tk.DISABLED
        )
        self.edit_camera_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        # Кнопка "Изменить группу"
        self.edit_group_button = Button(
            controls_frame,
            text="Изменить группу",
            font=Font(family="Arial", size=11),
            command=self.edit_group,
            width=20
        )
        self.edit_group_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        # Кнопка "Reload"
        self.reload_button = Button(
            controls_frame,
            text="Перезагрузить камеры",
            font=Font(family="Arial", size=11),
            command=self.reload_drivers,
            width=20
        )
        self.reload_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        # Комбобокс для выбора сетки
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
        
        # Комбобокс для выбора интервала кадров
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
        
        # Кнопка "Открыть карту"
        self.open_map_button = Button(
            controls_frame,
            text="Открыть карту",
            font=Font(family="Arial", size=11),
            command=lambda: None,
            width=25
        )
        self.open_map_button.pack(side=tk.LEFT, padx=5, pady=3)
        
        # Сетка камер
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
        
        # Настройка опций для драйверов
        self.driver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chromedriver.exe")
        self.options = Options()
        self.options.add_argument('--headless=new')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--window-size=1920,1080')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        
        # Инициализация фиксированных драйверов
        self.initialize_drivers()
        
        # Начальная загрузка группы
        self.start_load_group_to_drivers()
        
        # Таймер для обновления
        self.update_frames()
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)

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
        """Устанавливает частоту обновления кадров и перезапускает таймер."""
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
                url = current_grid[i] if i < len(current_grid) else None
                driver = self.drivers[i]
                if driver:
                    if url:
                        driver.get(url)
                        driver.refresh()
                        # Ждем загрузки элемента
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

    def on_tree_select(self, event):
        selection = self.tree.selection()
        self.selected_camera = None
        self.edit_camera_button.config(state=tk.DISABLED)
        if selection:
            item = selection[0]
            parent = self.tree.parent(item)
            if parent == "":  # Это группа
                group_name = self.tree.item(item)["text"]
                current_group = next((g for g in self.groups if g.get("current", False)), None)
                if current_group and current_group.get("name") == group_name:
                    return  # Не делаем ничего, если выбрана текущая группа
                if messagebox.askyesno("Подтверждение", f"Хотите переключить вывод на '{group_name}'?"):
                    for group in self.groups:
                        if group.get("name") == group_name:
                            group["current"] = True
                        else:
                            group["current"] = False
                    for cell in self.cells:
                        cell.cam = None
                        cell.update_display()
                    current_group = next((g for g in self.groups if g.get("current", False)), None)
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
                    self.save_config()
                    self.update_camera_list()
                    self.start_load_group_to_drivers()
            else:  # Это камера
                cam_text = self.tree.item(item)["text"]
                self.selected_camera = next((c for c in self.cams if c["street"] == cam_text), None)
                if self.selected_camera:
                    self.edit_camera_button.config(state=tk.NORMAL)

    def add_camera(self):
        dialog = CameraDialog(self)
        dialog.wait_window()
        if dialog.result:
            street, link = dialog.result
            if not street or not link:
                messagebox.showwarning("Ошибка", "Название и ссылка не могут быть пустыми")
                return
            if any(cam["link"] == link for cam in self.cams):
                messagebox.showwarning("Ошибка", "Камера с такой ссылкой уже существует")
                return
            # Добавляем камеру в список cams
            new_cam = {"street": street, "link": link}
            self.cams.append(new_cam)

            # Находим текущую группу
            current_group = next((g for g in self.groups if g.get("current", False)), None)
            added = False
            added_group_name = None
            is_current = False

            if not self.groups:
                # Если групп нет, создаем первую как текущую
                new_group = {
                    "name": "Группа 1",
                    "grid": [link] + [None] * 8,
                    "current": True
                }
                self.groups.append(new_group)
                added = True
                added_group_name = new_group["name"]
                is_current = True
                logger.info(f"[{time.strftime('%H:%M:%S')}] Created first group and added camera")
            else:
                # Проверяем текущую группу
                if current_group:
                    grid = current_group.get("grid", [None] * 9)
                    if len(grid) < 9:
                        grid += [None] * (9 - len(grid))
                    try:
                        free_index = grid.index(None)
                        grid[free_index] = link
                        current_group["grid"] = grid
                        added = True
                        added_group_name = current_group["name"]
                        is_current = True
                    except ValueError:
                        pass  # Нет свободных

                # Если не добавили в текущую, проверяем другие группы
                if not added:
                    for group in self.groups:
                        if group == current_group:
                            continue
                        grid = group.get("grid", [None] * 9)
                        if len(grid) < 9:
                            grid += [None] * (9 - len(grid))
                        try:
                            free_index = grid.index(None)
                            grid[free_index] = link
                            group["grid"] = grid
                            added = True
                            added_group_name = group["name"]
                            break
                        except ValueError:
                            pass

                # Если нигде нет места, создаем новую группу
                if not added:
                    new_group = {
                        "name": f"Группа {len(self.groups) + 1}",
                        "grid": [link] + [None] * 8,
                        "current": False
                    }
                    self.groups.append(new_group)
                    added = True
                    added_group_name = new_group["name"]

            if added:
                # Обновляем ячейки, если добавили в текущую группу
                if is_current:
                    current_grid = current_group.get("grid", [None] * 9)
                    for i in range(9):
                        link_in_grid = current_grid[i] if i < len(current_grid) else None
                        if link_in_grid == link:
                            self.cells[i].cam = new_cam
                            self.cells[i].update_display()
                            break
                    self.start_load_group_to_drivers()

                # Сохраняем и обновляем дерево
                self.save_config()
                self.update_camera_list()

                # Сообщаем пользователю, если не в текущую
                if not is_current:
                    messagebox.showinfo("Информация", f"Камера добавлена в группу '{added_group_name}'")
            else:
                logger.error(f"[{time.strftime('%H:%M:%S')}] Failed to add camera: no space found")
                messagebox.showerror("Ошибка", "Не удалось добавить камеру: нет свободных мест")

    def edit_camera(self):
        if not self.selected_camera:
            return
        self.original_period = self.period
        self.set_frame_rate(5000)  # Устанавливаем 5 секунд на время диалога
        dialog = CameraDialog(self, street=self.selected_camera["street"], link=self.selected_camera["link"], title="Изменить камеру")
        dialog.wait_window()
        # Восстанавливаем частоту из комбобокса
        selected_rate = self.frame_rate_combobox.get()
        period_map = {"Кадр в 1 сек": 1000, "Кадр в 2 сек": 2000, "Кадр в 4 сек": 4000}
        self.set_frame_rate(period_map.get(selected_rate, 1000))
        if dialog.result:
            new_street, new_link = dialog.result
            if new_street == self.selected_camera["street"] and new_link == self.selected_camera["link"]:
                return  # Ничего не делаем, если данные не изменились
            if not new_street or not new_link:
                messagebox.showwarning("Ошибка", "Название и ссылка не могут быть пустыми")
                return
            if any(cam["link"] == new_link and cam != self.selected_camera for cam in self.cams):
                messagebox.showwarning("Ошибка", "Камера с такой ссылкой уже существует")
                return
            old_link = self.selected_camera["link"]
            self.selected_camera["street"] = new_street
            self.selected_camera["link"] = new_link
            # Обновляем ссылки во всех группах
            for group in self.groups:
                grid = group.get("grid", [])
                for i in range(len(grid)):
                    if grid[i] == old_link:
                        grid[i] = new_link
            # Сохраняем конфиг
            self.save_config()
            # Обновляем дерево
            self.update_camera_list()
            # Если в текущей группе, обновляем ячейку
            current_group = next((g for g in self.groups if g.get("current", False)), None)
            if current_group:
                current_grid = current_group.get("grid", [None] * 9)
                for i in range(9):
                    if i < len(current_grid) and current_grid[i] == new_link:
                        self.cells[i].cam = self.selected_camera
                        self.cells[i].update_display()
                        # Перезагружаем драйвер для этой ячейки
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
        self.original_period = self.period
        self.set_frame_rate(5000)  # Устанавливаем 5 секунд на время диалога
        dialog = CameraDialog(self, street=current_group["name"], title="Изменить группу", is_group=True)
        dialog.wait_window()
        # Восстанавливаем частоту из комбобокса
        selected_rate = self.frame_rate_combobox.get()
        period_map = {"Кадр в 1 сек": 1000, "Кадр в 2 сек": 2000, "Кадр в 4 сек": 4000}
        self.set_frame_rate(period_map.get(selected_rate, 1000))
        if dialog.result:
            new_name, _ = dialog.result  # Игнорируем ссылку, так как она не используется
            if new_name == current_group["name"]:
                return  # Ничего не делаем, если имя не изменилось
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
            current_group["grid"] = [cell.cam["link"] if cell.cam else None for cell in self.cells]
        self.config["groups"] = self.groups
        self.config["cams"] = self.cams
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

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

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()