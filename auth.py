import sys
import os
import logging
import json
import time
import tkinter as tk
from tkinter import ttk, messagebox, Toplevel, Label, Entry, Button
from tkinter.font import Font
import hashlib
from datetime import datetime, timedelta

from main_app import MainApp

# Настройка логирования
logging.basicConfig(filename='app.log', level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

def resource_path(relative_path):
    """ Получить путь к ресурсу для PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class ChangePasswordWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Смена паролей")
        self.transient(parent)
        self.grab_set()

        # Размер окна
        window_width = 400
        window_height = 300  # Уменьшено с 400 до 300
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self.font = Font(family="Arial", size=11)
        self.parent = parent

        # Основной фрейм
        main_frame = tk.Frame(self)
        main_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # Поля для ввода нового пароля администратора
        Label(main_frame, text="Новый пароль администратора:", font=self.font).pack(anchor="w", padx=5, pady=3)
        self.admin_password_entry = Entry(main_frame, font=self.font, show="*")
        self.admin_password_entry.pack(fill=tk.X, padx=5, pady=3)
        Label(main_frame, text="Повторите пароль администратора:", font=self.font).pack(anchor="w", padx=5, pady=3)
        self.admin_password_confirm_entry = Entry(main_frame, font=self.font, show="*")
        self.admin_password_confirm_entry.pack(fill=tk.X, padx=5, pady=3)

        # Поля для ввода нового пароля пользователя
        Label(main_frame, text="Новый пароль пользователя:", font=self.font).pack(anchor="w", padx=5, pady=3)
        self.user_password_entry = Entry(main_frame, font=self.font, show="*")
        self.user_password_entry.pack(fill=tk.X, padx=5, pady=3)
        Label(main_frame, text="Повторите пароль пользователя:", font=self.font).pack(anchor="w", padx=5, pady=3)
        self.user_password_confirm_entry = Entry(main_frame, font=self.font, show="*")
        self.user_password_confirm_entry.pack(fill=tk.X, padx=5, pady=3)

        # Заполнение полей звёздочками, если пароли уже есть
        if self.parent.config.get("admin_password") is not None:
            self.admin_password_entry.insert(0, "************")
            self.admin_password_confirm_entry.insert(0, "************")
        if self.parent.config.get("user_password") is not None:
            self.user_password_entry.insert(0, "************")
            self.user_password_confirm_entry.insert(0, "************")

        # Привязка события ввода текста для динамической проверки
        self.admin_password_entry.bind("<KeyRelease>", self.check_passwords)
        self.admin_password_confirm_entry.bind("<KeyRelease>", self.check_passwords)
        self.user_password_entry.bind("<KeyRelease>", self.check_passwords)
        self.user_password_confirm_entry.bind("<KeyRelease>", self.check_passwords)

        # Кнопки
        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=15)
        Button(button_frame, text="Сохранить", font=self.font, command=self.save_passwords, width=10).pack(side=tk.LEFT, padx=5)
        Button(button_frame, text="Отмена", font=self.font, command=self.destroy, width=10).pack(side=tk.LEFT, padx=5)

    def check_passwords(self, event=None):
        """Проверка совпадения паролей в реальном времени"""
        admin_password = self.admin_password_entry.get()
        admin_password_confirm = self.admin_password_confirm_entry.get()
        user_password = self.user_password_entry.get()
        user_password_confirm = self.user_password_confirm_entry.get()

        # Проверка паролей администратора
        if admin_password and admin_password_confirm and admin_password != admin_password_confirm:
            self.admin_password_entry.config(bg="#FF0000")
            self.admin_password_confirm_entry.config(bg="#FF0000")
        else:
            self.admin_password_entry.config(bg="#FFFFFF")
            self.admin_password_confirm_entry.config(bg="#FFFFFF")

        # Проверка паролей пользователя
        if user_password and user_password_confirm and user_password != user_password_confirm:
            self.user_password_entry.config(bg="#FF0000")
            self.user_password_confirm_entry.config(bg="#FF0000")
        else:
            self.user_password_entry.config(bg="#FFFFFF")
            self.user_password_confirm_entry.config(bg="#FFFFFF")

        self.update_idletasks()  # Обновить интерфейс для немедленного отображения

    def save_passwords(self):
        admin_password = self.admin_password_entry.get()
        admin_password_confirm = self.admin_password_confirm_entry.get()
        user_password = self.user_password_entry.get()
        user_password_confirm = self.user_password_confirm_entry.get()

        # Проверка длины паролей
        if not (8 <= len(admin_password) <= 12) or not (8 <= len(user_password) <= 12):
            messagebox.showerror("Ошибка", "Пароли должны быть длиной от 8 до 12 символов.")
            return

        # Проверка совпадения паролей
        if admin_password != admin_password_confirm:
            messagebox.showerror("Ошибка", "Пароли администратора не совпадают.")
            return
        if user_password != user_password_confirm:
            messagebox.showerror("Ошибка", "Пароли пользователя не совпадают.")
            return

        # Проверка изменения паролей
        admin_password_hash = hashlib.sha256(admin_password.encode('utf-8')).hexdigest()
        user_password_hash = hashlib.sha256(user_password.encode('utf-8')).hexdigest()
        current_admin_hash = self.parent.config.get("admin_password")
        current_user_hash = self.parent.config.get("user_password")

        if admin_password_hash == current_admin_hash and user_password_hash == current_user_hash:
            messagebox.showinfo("Информация", "Пароли не изменены.")
            self.destroy()
            return

        # Сохранение паролей, если они изменились
        self.parent.config["admin_password"] = admin_password_hash
        self.parent.config["user_password"] = user_password_hash
        self.parent.save_config()
        messagebox.showinfo("Успех", "Пароли успешно сохранены. Пожалуйста, войдите заново.")
        self.destroy()

    def destroy(self):
        """Завершение приложения при закрытии окна"""
        super().destroy()
        self.parent.destroy()  # Закрываем главное окно приложения

class IntroWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Вход в приложение")
        
        # Размер окна
        window_width = 300
        window_height = 200
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        self.font = Font(family="Arial", size=11)
        self.login_attempts_count = 0  # Счётчик попыток входа
        self.parent = parent  # Сохраняем ссылку на родительское окно (MainApp)
        
        # Основной фрейм
        self.main_frame = tk.Frame(self)
        self.main_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        # Поле логина (Combobox)
        Label(self.main_frame, text="Логин:", font=self.font).pack(anchor="w", padx=5, pady=5)
        self.login_combobox = ttk.Combobox(self.main_frame, values=["Администратор", "Пользователь"], font=self.font, state="readonly")
        self.login_combobox.set("Пользователь")
        self.login_combobox.pack(fill=tk.X, padx=5, pady=5)
        
        # Поле пароля
        Label(self.main_frame, text="Пароль:", font=self.font).pack(anchor="w", padx=5, pady=5)
        self.password_entry = Entry(self.main_frame, font=self.font, show="*")
        self.password_entry.pack(fill=tk.X, padx=5, pady=5)
        self.password_entry.bind("<Return>", lambda event: self.on_ok())  # Привязка Enter
        
        # Кнопки
        self.button_frame = tk.Frame(self.main_frame)
        self.button_frame.pack(pady=10)
        Button(self.button_frame, text="Вход", font=self.font, command=self.on_ok).pack(side=tk.LEFT, padx=5)
        Button(self.button_frame, text="Отмена", font=self.font, command=self.destroy).pack(side=tk.LEFT, padx=5)
        
        # Иконка окна
        try:
            self.iconbitmap(resource_path("resource/eye.ico"))
        except:
            pass  # Если иконка не найдена, игнорируем

        self.config = self.load_config()

    def load_config(self):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.info(f"[{time.strftime('%H:%M:%S')}] config.json not found or corrupted: {str(e)}. Creating default config.")
            config = {"cams": [], "groups": [], "period": 1, "admin_password": None, "user_password": None, "login_attempts": []}
        return config

    def save_config(self):
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info(f"[{time.strftime('%H:%M:%S')}] Config saved to config.json.")
        except Exception as e:
            logger.error(f"[{time.strftime('%H:%M:%S')}] Error saving config: {str(e)}")
            messagebox.showerror("Ошибка", "Не удалось сохранить конфигурацию")

    def clean_login_attempts(self):
        """Удаление записей о попытках входа старше 7 дней"""
        cutoff = datetime.now() - timedelta(days=7)
        initial_count = len(self.config.get("login_attempts", []))
        self.config["login_attempts"] = [
            attempt for attempt in self.config.get("login_attempts", [])
            if datetime.fromisoformat(attempt["timestamp"]) > cutoff
        ]
        if len(self.config["login_attempts"]) < initial_count:
            logger.info(f"[{time.strftime('%H:%M:%S')}] Removed {initial_count - len(self.config['login_attempts'])} old login attempts.")
        self.save_config()

    def hash_password(self, password):
        """Хеширование пароля с использованием SHA-256"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def get_default_admin_password(self):
        """Генерация пароля администратора по умолчанию"""
        now = datetime.now()
        day = now.day
        year = now.year
        month = now.month
        return f"{day}%{year}@Admin#{month}"

    def on_ok(self):
        if self.login_attempts_count >= 3:
            messagebox.showerror("Ошибка", "Превышено количество попыток входа (3).")
            self.config.setdefault("login_attempts", []).append({
                "user": self.login_combobox.get(),
                "timestamp": datetime.now().isoformat(),
                "success": False
            })
            self.save_config()
            self.destroy()
            return

        login = self.login_combobox.get()
        password = self.password_entry.get()
        now = datetime.now().isoformat()
        self.clean_login_attempts()
        self.login_attempts_count += 1

        # Проверка пароля
        if login == "Пользователь":
            user_password_hash = self.config.get("user_password")
            if user_password_hash is None:
                messagebox.showerror("Ошибка", "Пароль пользователя не установлен. Обратитесь к администратору.")
                if self.login_attempts_count >= 3:
                    self.config.setdefault("login_attempts", []).append({"user": login, "timestamp": now, "success": False})
                    self.save_config()
                self.destroy()
                return

            if self.hash_password(password) == user_password_hash:
                logger.info(f"[{time.strftime('%H:%M:%S')}] Successful user login")
                # Показать сообщение "Вход выполнен. Подключение ..."
                success_label = Label(self.main_frame, text="Вход выполнен. Подключение ...", font=("Arial", 12, "bold"), fg="green")
                success_label.pack(before=self.button_frame, pady=5)
                self.update()  # Обновить интерфейс для отображения надписи
                # Показать основное приложение
                self.parent.deiconify()  # Показываем MainApp
            else:
                messagebox.showerror("Ошибка", f"Неверный пароль. Осталось попыток: {3 - self.login_attempts_count}")
                if self.login_attempts_count >= 3:
                    self.config.setdefault("login_attempts", []).append({"user": login, "timestamp": now, "success": False})
                    self.save_config()
                    self.destroy()

        elif login == "Администратор":
            admin_password_hash = self.config.get("admin_password")
            default_password = self.get_default_admin_password()
            default_password_hash = self.hash_password(default_password)

            if self.hash_password(password) == admin_password_hash or (admin_password_hash is None and self.hash_password(password) == default_password_hash):
                logger.info(f"[{time.strftime('%H:%M:%S')}] Successful admin login")
                # Если пароль по умолчанию, требуем смену
                if admin_password_hash is None and password == default_password:
                    messagebox.showinfo("Требуется смена пароля", "Вы используете пароль по умолчанию. Пожалуйста, смените пароли.")
                ChangePasswordWindow(self)
            else:
                messagebox.showerror("Ошибка", f"Неверный пароль. Осталось попыток: {3 - self.login_attempts_count}")
                if self.login_attempts_count >= 3:
                    self.config.setdefault("login_attempts", []).append({"user": login, "timestamp": now, "success": False})
                    self.save_config()
                    self.destroy()

    def on_cancel(self):
        """Завершение приложения при нажатии на Отмена"""
        self.destroy()