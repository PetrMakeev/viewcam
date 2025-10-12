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
    def __init__(self, parent=None, street="", link="", title="Добавить камеру"):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x150")
        self.font = Font(family="Arial", size=11)
        
        self.street_label = Label(self, text="Название:", font=self.font)
        self.street_label.grid(row=0, column=0, padx=10, pady=10)
        self.street_entry = Entry(self, font=self.font, width=50)
        self.street_entry.insert(0, street)
        self.street_entry.grid(row=0, column=1, padx=10, pady=10)
        
        self.link_label = Label(self, text="Ссылка:", font=self.font)
        self.link_label.grid(row=1, column=0, padx=10, pady=10)
        self.link_entry = Entry(self, font=self.font, width=50)
        self.link_entry.insert(0, link)
        self.link_entry.grid(row=1, column=1, padx=10, pady=10)
        
        self.ok_button = Button(self, text="OK", font=self.font, command=self.accept)
        self.ok_button.grid(row=2, column=0, columnspan=2, pady=10)
        
        self.cancel_button = Button(self, text="Отмена", font=self.font, command=self.destroy)
        self.cancel_button.grid(row=2, column=1, columnspan=2, pady=10)
        
        self.result = None
        self.protocol("WM_DELETE_WINDOW", self.destroy)

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
            img = Image.open("resource/nocam.png")
            self.photo = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.photo)
        else:
            self.name_label.config(text=self.cam["street"])
            img = Image.open("resource/noconnect.png")
            self.photo = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.photo)

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Видеонаблюдение")
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight() - 50
        self.geometry(f"{screen_width}x{screen_height}+0+0")
        
        # Загрузка конфигурации
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {"cams": [], "groups": [], "period": 1}
        self.period = self.config.get("period", 1) * 1000
        self.groups = self.config.get("groups", [])
        self.cams = self.config.get("cams", [])
        self.selected_camera = None
        self.drivers = []  # Список из 9 фиксированных драйверов
        
        # Левая панель
        left_frame = tk.Frame(self, width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        self.add_camera_button = Button(left_frame, text="Добавить камеру", font=Font(family="Arial", size=11), command=self.add_camera)
        self.add_camera_button.pack(fill=tk.X)
        
        self.reload_button = Button(left_frame, text="Reload", font=Font(family="Arial", size=11), command=self.reload_drivers)
        self.reload_button.pack(fill=tk.X)
        
        self.tree = ttk.Treeview(left_frame, show="tree")
        self.tree.pack(expand=True, fill=tk.BOTH)
        self.update_camera_list()
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        # Правая панель: сетка 3x3
        right_frame = tk.Frame(self)
        right_frame.pack(expand=True, fill=tk.BOTH)
        
        cell_width = (screen_width - 300) // 3
        cell_height = screen_height // 3
        self.cells = []
        for i in range(3):
            for j in range(3):
                cell = CellFrame(right_frame, i * 3 + j)
                cell.grid(row=i, column=j, sticky="nsew")
                cell.config(width=cell_width, height=cell_height)
                self.cells.append(cell)
                right_frame.rowconfigure(i, weight=1)
                right_frame.columnconfigure(j, weight=1)
        
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
        self.after(self.period, self.update_frames)
        
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

    def update_camera_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        used_links = set()
        for group in self.groups:
            if group.get("name") != "Другие камеры":
                for link in group.get("grid", []):
                    if link:
                        used_links.add(link)

        other_cams = [cam for cam in self.cams if cam["link"] not in used_links]

        for group in self.groups:
            group_name = group.get("name", "Группа")
            group_iid = self.tree.insert("", "end", text=group_name + (" [X]" if group.get("current", False) else ""))
            if group_name == "Другие камеры":
                group_cams = other_cams
            else:
                group_cams = []
                for link in group.get("grid", []):
                    if link:
                        cam = next((c for c in self.cams if c["link"] == link), None)
                        if cam:
                            group_cams.append(cam)
            for cam in group_cams:
                self.tree.insert(group_iid, "end", text=cam["street"])

    def on_tree_select(self, event):
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            parent = self.tree.parent(item)
            if parent == "":  # Это группа
                group_name = self.tree.item(item)["text"].split(" [")[0]
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
                        self.cells[i].update_display()
                    self.save_config()
                    self.update_camera_list()
                    self.start_load_group_to_drivers()

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
            self.cams.append({"street": street, "link": link})
            self.save_config()
            self.update_camera_list()
            # Если влияет на текущую группу
            current_group = next((g for g in self.groups if g.get("current", False)), None)
            current_grid = current_group.get("grid", [None] * 9) if current_group else []
            if link in current_grid:
                self.start_load_group_to_drivers()

    def reload_drivers(self):
        self.start_load_group_to_drivers()

    def update_frames(self):
        for cell in self.cells:
            if not cell.cam or not self.drivers[cell.index]:
                img = Image.open("resource/noconnect.png")
                cell.photo = ImageTk.PhotoImage(img)
                cell.image_label.config(image=cell.photo)
                continue
            driver = self.drivers[cell.index]
            try:
                if driver.current_url == 'about:blank':
                    continue
            except Exception as e:
                logger.error(f"[{time.strftime('%H:%M:%S')}] Error checking url for cell {cell.index}: {str(e)}")
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
                    cell.photo = ImageTk.PhotoImage(cropped_image)
                    cell.image_label.config(image=cell.photo)
                driver.switch_to.default_content()
            except Exception as e:
                error_msg = f"[{time.strftime('%H:%M:%S')}] Error updating frame for cell {cell.index}: {str(e)}"
                logger.error(error_msg)
                img = Image.open("resource/noconnect.png")
                cell.photo = ImageTk.PhotoImage(img)
                cell.image_label.config(image=cell.photo)
        self.after(self.period, self.update_frames)

    def save_config(self):
        current_group = next((g for g in self.groups if g.get("current", False)), None)
        if current_group:
            current_group["grid"] = [cell.cam["link"] if cell.cam else None for cell in self.cells]
        self.config["groups"] = self.groups
        self.config["cams"] = self.cams
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def on_close(self):
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

