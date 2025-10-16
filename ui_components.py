import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox, Toplevel, Label, Entry, Button
from tkinter.font import Font
from PIL import Image, ImageTk
import subprocess  # Добавлен для управления процессами Chrome
import logging  # Добавлен для логирования
import time

import webbrowser  # Добавлен импорт для работы с браузером

# Настройка логирования
logger = logging.getLogger(__name__)

def resource_path(relative_path):
    """ Получить путь к ресурсу для PyInstaller """
    try:
        # PyInstaller создает временную папку и сохраняет путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


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
        
        paste_img = Image.open(resource_path("resource/paste.png"))
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
        self.image_label.bind("<Button-1>", lambda event: self.winfo_toplevel().on_cell_click(self.index))
        self.image_label.bind("<Double-Button-1>", lambda event: self.winfo_toplevel().open_modal(self.index))
        
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

# Функция для открытия карты в новом окне Google Chrome
def open_ufanet_map():
    try:
        chrome_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
        url = 'http://maps.ufanet.ru/orenburg#'
        if not os.path.exists(chrome_path):
            logger.error(f"[{time.strftime('%H:%M:%S')}] Chrome not found at {chrome_path}")
            messagebox.showerror("Ошибка", "Google Chrome не найден по пути: " + chrome_path)
            return
        subprocess.Popen([chrome_path, '--new-window', url])
        logger.info(f"[{time.strftime('%H:%M:%S')}] Opened new Chrome window with URL: {url}")
    except Exception as e:
        logger.error(f"[{time.strftime('%H:%M:%S')}] Failed to open map: {str(e)}")
        messagebox.showerror("Ошибка", f"Не удалось открыть карту: {str(e)}")