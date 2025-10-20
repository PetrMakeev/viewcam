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
import base64

# from main_app import MainApp

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

def encrypt(text, key='orenburg_secret'):
    """Простое шифрование XOR + base64"""
    key = key * (len(text) // len(key) + 1)
    encrypted = ''.join(chr(ord(c) ^ ord(k)) for c, k in zip(text, key))
    return base64.b64encode(encrypted.encode('utf-8')).decode('utf-8')

def decrypt(encrypted, key='orenburg_secret'):
    """Дешифровка XOR + base64"""
    encrypted = base64.b64decode(encrypted).decode('utf-8')
    key = key * (len(encrypted) // len(key) + 1)
    return ''.join(chr(ord(c) ^ ord(k)) for c, k in zip(encrypted, key))

class ChangePasswordWindow(tk.Toplevel):
    def __init__(self, parent, require_change=False):
        super().__init__(parent)
        print(f"ChangePasswordWindow initialized with parent={parent}, require_change={require_change}")
        logger.info(f"[{time.strftime('%H:%M:%S')}] ChangePasswordWindow initialized with parent={parent}, require_change={require_change}")
        self.title("Смена паролей")
        self.transient(parent)
        self.grab_set()
        self.require_change = require_change  # Новый параметр
        self.success = False  # Новый флаг: True, если пароли успешно изменены

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

        # Флаги для отслеживания изменений
        self.admin_modified = False
        self.user_modified = False

        # Основной фрейм
        main_frame = tk.Frame(self)
        main_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # Поля для ввода нового пароля администратора
        Label(main_frame, text="Новый пароль администратора (8-12):", font=self.font).pack(anchor="w", padx=5, pady=3)
        self.admin_password_entry = Entry(main_frame, font=self.font, show="*")
        self.admin_password_entry.pack(fill=tk.X, padx=5, pady=3)
        Label(main_frame, text="Повторите пароль администратора:", font=self.font).pack(anchor="w", padx=5, pady=3)
        self.admin_password_confirm_entry = Entry(main_frame, font=self.font, show="*")
        self.admin_password_confirm_entry.pack(fill=tk.X, padx=5, pady=3)

        # Поля для ввода нового пароля пользователя
        Label(main_frame, text="Новый пароль пользователя (3-8):", font=self.font).pack(anchor="w", padx=5, pady=3)
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
            self.user_password_entry.insert(0, "********")
            self.user_password_confirm_entry.insert(0, "********")

        # Привязка события ввода текста для динамической проверки и установки флагов модификации
        self.admin_password_entry.bind("<KeyRelease>", lambda e: [self.set_modified('admin'), self.check_passwords(e)])
        self.admin_password_confirm_entry.bind("<KeyRelease>", lambda e: [self.set_modified('admin'), self.check_passwords(e)])
        self.user_password_entry.bind("<KeyRelease>", lambda e: [self.set_modified('user'), self.check_passwords(e)])
        self.user_password_confirm_entry.bind("<KeyRelease>", lambda e: [self.set_modified('user'), self.check_passwords(e)])

        # Кнопки
        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=15)
        Button(button_frame, text="Сохранить", font=self.font, command=self.save_passwords, width=10).pack(side=tk.LEFT, padx=5)
        Button(button_frame, text="Отмена", font=self.font, command=self.on_cancel, width=10).pack(side=tk.LEFT, padx=5)
        
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)  # Изменено: вызов on_cancel (но on_cancel теперь не закрывает всё) 
        
        self.admin_password_entry.focus_set()

    def set_modified(self, password_type):
        """Установка флага модификации для админа или пользователя"""
        if password_type == 'admin':
            self.admin_modified = True
        elif password_type == 'user':
            self.user_modified = True

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

    # В классе ChangePasswordWindow: Изменить save_passwords
    def save_passwords(self):
        
        import logging
        logger = logging.getLogger(__name__)
        print(f"save_passwords called with parent={self.parent}, has_config={hasattr(self.parent, 'config')}")
        logger.info(f"[{time.strftime('%H:%M:%S')}] save_passwords called with parent={self.parent}, has_config={hasattr(self.parent, 'config')}")
        
        current_admin_hash = self.parent.config.get("admin_password") if hasattr(self.parent, 'config') else self.parent.intro_window.config.get("admin_password")
        current_user_hash = self.parent.config.get("user_password") if hasattr(self.parent, 'config') else self.parent.intro_window.config.get("user_password")
        changes_made = False

        # Обработка пароля администратора (только если изменён или None)
        if self.admin_modified or current_admin_hash is None:
            admin_password = self.admin_password_entry.get()
            admin_password_confirm = self.admin_password_confirm_entry.get()

            # Проверка совпадения
            if admin_password != admin_password_confirm:
                messagebox.showerror("Ошибка", "Пароли администратора не совпадают.")
                return

            # Проверка длины
            if not (8 <= len(admin_password) <= 12):
                messagebox.showerror("Ошибка", "Пароль администратора должен быть длиной от 8 до 12 символов.")
                return

            admin_password_hash = hashlib.sha256(admin_password.encode('utf-8')).hexdigest()
            if admin_password_hash != current_admin_hash:
                if hasattr(self.parent, 'config'):
                    self.parent.config["admin_password"] = admin_password_hash
                else:
                    self.parent.intro_window.config["admin_password"] = admin_password_hash
                changes_made = True
                logger.info(f"[{time.strftime('%H:%M:%S')}] Admin password changed.")

        # Обработка пароля пользователя (только если изменён или None)
        if self.user_modified or current_user_hash is None:
            user_password = self.user_password_entry.get()
            user_password_confirm = self.user_password_confirm_entry.get()

            # Проверка совпадения
            if user_password != user_password_confirm:
                messagebox.showerror("Ошибка", "Пароли пользователя не совпадают.")
                return

            # Проверка длины
            if not (3 <= len(user_password) <= 8):
                messagebox.showerror("Ошибка", "Пароль пользователя должен быть длиной от 3 до 8 символов.")
                return

            user_password_hash = hashlib.sha256(user_password.encode('utf-8')).hexdigest()
            if user_password_hash != current_user_hash:
                if hasattr(self.parent, 'config'):
                    self.parent.config["user_password"] = user_password_hash
                    # Обновляем timestamp для user_password, если он изменён
                    timestamp_str = datetime.now().isoformat()
                    self.parent.config["user_password_timestamp"] = encrypt(timestamp_str)
                else:
                    self.parent.intro_window.config["user_password"] = user_password_hash
                    # Обновляем timestamp для user_password, если он изменён
                    timestamp_str = datetime.now().isoformat()
                    self.parent.intro_window.config["user_password_timestamp"] = encrypt(timestamp_str)
                changes_made = True
                logger.info(f"[{time.strftime('%H:%M:%S')}] User password changed, timestamp updated.")

        if not changes_made:
            messagebox.showinfo("Информация", "Пароли не изменены.")
            self.destroy()
            return

        # Сохраняем конфигурацию
        if hasattr(self.parent, 'config'):
            self.parent.save_config()
        else:
            self.parent.intro_window.save_config()
        messagebox.showinfo("Успех", "Пароли успешно сохранены.")
        self.success = True
        self.destroy()

    def on_cancel(self):
        """Завершение только окна смены пароля"""
        self.destroy()  # Изменено: только destroy этого окна, без закрытия parent и sys.exit()

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
        Button(self.button_frame, text="Отмена", font=self.font, command=self.on_cancel).pack(side=tk.LEFT, padx=5)
    
        # Иконка окна
        try:
            self.iconbitmap(resource_path("resource/eye.ico"))
        except:
            pass  # Если иконка не найдена, игнорируем
        
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)        

        self.config = self.load_config()
        self.parent.config = self.config  # Передаём конфигурацию в MainApp
        
        self.focus_set()
        self.password_entry.focus_set()

    def load_config(self):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.info(f"[{time.strftime('%H:%M:%S')}] config.json not found or corrupted: {str(e)}. Creating default config.")
            config = {"cams": [], "groups": [], "period": 1, "admin_password": None, "user_password": None, "login_attempts": [], "user_password_timestamp": None}
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
        import logging
        logger = logging.getLogger(__name__)  # Добавлено для явного логирования
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
                self.on_cancel()
                return

            if self.hash_password(password) == user_password_hash:
                # Проверка на просрочку пароля
                current_time = datetime.now()
                if current_time.hour >= 12:
                    try:
                        timestamp_enc = self.config.get("user_password_timestamp")
                        if not timestamp_enc:
                            raise ValueError("No timestamp")
                        timestamp_str = decrypt(timestamp_enc)
                        last_change = datetime.fromisoformat(timestamp_str)
                        if last_change.date() < current_time.date() or (last_change.date() == current_time.date() and last_change.hour < 12):
                            raise ValueError("Expired")
                    except Exception as e:
                        logger.warning(f"[{time.strftime('%H:%M:%S')}] User password expired or invalid timestamp: {str(e)}")
                        messagebox.showerror("Ошибка", "Пароль пользователя просрочен, обратитесь к администратору.")
                        if self.login_attempts_count >= 3:
                            self.config.setdefault("login_attempts", []).append({"user": login, "timestamp": now, "success": False})
                            self.save_config()
                        return

                logger.info(f"[{time.strftime('%H:%M:%S')}] Successful user login")
                # Добавлено для ролей: установка роли в MainApp
                self.parent.user_role = "Пользователь"  # Добавлено для ролей
                # Показать сообщение "Вход выполнен. Подключение ..."
                success_label = Label(self.main_frame, text="Вход выполнен. Подключение ...", font=("Arial", 12, "bold"), fg="green")
                success_label.pack(before=self.button_frame, pady=5)
                self.update()  # Обновить интерфейс для отображения надписи
                # Прячем окно авторизации, показываем основное окно
                self.withdraw()  # Скрываем IntroWindow
                self.grab_release()  # Освобождаем фокус
                self.parent.deiconify()  # Показываем MainApp
                self.login_combobox.config(state=tk.DISABLED)
                self.password_entry.config(state=tk.DISABLED)
                self.parent.setup_app()  # Запускаем настройку приложения
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
                
                # Добавлено для ролей: установка роли в MainApp
                self.parent.user_role = "Администратор"  # Добавлено для ролей
                
                # Показываем основное окно и скрываем окно авторизации
                self.withdraw()  # Скрываем IntroWindow
                self.parent.deiconify()  # Показываем MainApp
                self.deiconify()
                self.grab_release()  # Освобождаем фокус
                
                
                # Если пароль по умолчанию, требуем смену
                if admin_password_hash is None and password == default_password:
                    logger.info(f"[{time.strftime('%H:%M:%S')}] Default admin password detected, opening ChangePasswordWindow")
                    messagebox.showinfo("Требуется смена пароля", "Вы используете пароль по умолчанию. Пожалуйста, смените пароли.")
                    change_window = ChangePasswordWindow(self, require_change=True)  # Создаём окно смены паролей
                    change_window.deiconify()  # Явно показываем окно
                    change_window.focus_set()  # Устанавливаем фокус
                    change_window.grab_set()  # Захватываем фокус
                    logger.info(f"[{time.strftime('%H:%M:%S')}] ChangePasswordWindow created and displayed")
                    self.wait_window(change_window)  # Ждём закрытия окна смены
                    
                    if change_window.success:
                        logger.info(f"[{time.strftime('%H:%M:%S')}] Passwords changed successfully, proceeding to setup_app")
                        self.parent.setup_app()  # После успешной смены запускаем setup_app
                    else:
                        logger.info(f"[{time.strftime('%H:%M:%S')}] Password change cancelled, closing application")
                        self.parent.destroy()  # Если отмена, закрываем приложение
                        sys.exit(0)
                else:
                    logger.info(f"[{time.strftime('%H:%M:%S')}] Non-default admin password, proceeding to setup_app")
                    self.parent.setup_app()  # Для не-дефолтного сразу setup_app
            else:
                messagebox.showerror("Ошибка", f"Неверный пароль. Осталось попыток: {3 - self.login_attempts_count}")
                if self.login_attempts_count >= 3:
                    self.config.setdefault("login_attempts", []).append({"user": login, "timestamp": now, "success": False})
                    self.save_config()
                    self.destroy()

    def on_cancel(self):
        """Завершение приложения при нажатии на Отмена"""
        super().destroy()  # Вызываем стандартное закрытие Toplevel
        self.parent.destroy()  # Закрываем основное окно
        sys.exit(0)  # Гарантируем завершение
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
        Button(self.button_frame, text="Отмена", font=self.font, command=self.on_cancel).pack(side=tk.LEFT, padx=5)
    
        # Иконка окна
        try:
            self.iconbitmap(resource_path("resource/eye.ico"))
        except:
            pass  # Если иконка не найдена, игнорируем
        
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)        

        self.config = self.load_config()
        self.parent.config = self.config  # Передаём конфигурацию в MainApp
        
        self.focus_set()
        self.password_entry.focus_set()

    def load_config(self):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.info(f"[{time.strftime('%H:%M:%S')}] config.json not found or corrupted: {str(e)}. Creating default config.")
            config = {"cams": [], "groups": [], "period": 1, "admin_password": None, "user_password": None, "login_attempts": [], "user_password_timestamp": None}
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
        import logging
        logger = logging.getLogger(__name__)  # Добавлено для явного логирования
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
                self.on_cancel()
                return

            if self.hash_password(password) == user_password_hash:
                # Проверка на просрочку пароля
                current_time = datetime.now()
                if current_time.hour >= 12:
                    try:
                        timestamp_enc = self.config.get("user_password_timestamp")
                        if not timestamp_enc:
                            raise ValueError("No timestamp")
                        timestamp_str = decrypt(timestamp_enc)
                        last_change = datetime.fromisoformat(timestamp_str)
                        if last_change.date() < current_time.date() or (last_change.date() == current_time.date() and last_change.hour < 12):
                            raise ValueError("Expired")
                    except Exception as e:
                        logger.warning(f"[{time.strftime('%H:%M:%S')}] User password expired or invalid timestamp: {str(e)}")
                        messagebox.showerror("Ошибка", "Пароль пользователя просрочен, обратитесь к администратору.")
                        if self.login_attempts_count >= 3:
                            self.config.setdefault("login_attempts", []).append({"user": login, "timestamp": now, "success": False})
                            self.save_config()
                        return

                logger.info(f"[{time.strftime('%H:%M:%S')}] Successful user login")
                # Добавлено для ролей: установка роли в MainApp
                self.parent.user_role = "Пользователь"  # Добавлено для ролей
                # Показать сообщение "Вход выполнен. Подключение ..."
                success_label = Label(self.main_frame, text="Вход выполнен. Подключение ...", font=("Arial", 12, "bold"), fg="green")
                success_label.pack(before=self.button_frame, pady=5)
                self.update()  # Обновить интерфейс для отображения надписи
                # Прячем окно авторизации, показываем основное окно
                self.withdraw()  # Скрываем IntroWindow
                self.grab_release()  # Освобождаем фокус
                self.parent.deiconify()  # Показываем MainApp
                self.login_combobox.config(state=tk.DISABLED)
                self.password_entry.config(state=tk.DISABLED)
                self.parent.setup_app()  # Запускаем настройку приложения
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
                
                # Добавлено для ролей: установка роли в MainApp
                self.parent.user_role = "Администратор"  # Добавлено для ролей
                
                # Показываем основное окно и скрываем окно авторизации
                self.withdraw()  # Скрываем IntroWindow
                self.parent.deiconify()  # Показываем MainApp
                self.deiconify()
                self.grab_release()  # Освобождаем фокус
                
                
                # Если пароль по умолчанию, требуем смену
                if admin_password_hash is None and password == default_password:
                    logger.info(f"[{time.strftime('%H:%M:%S')}] Default admin password detected, opening ChangePasswordWindow")
                    messagebox.showinfo("Требуется смена пароля", "Вы используете пароль по умолчанию. Пожалуйста, смените пароли.")
                    change_window = ChangePasswordWindow(self, require_change=True)  # Создаём окно смены паролей
                    change_window.deiconify()  # Явно показываем окно
                    change_window.focus_set()  # Устанавливаем фокус
                    change_window.grab_set()  # Захватываем фокус
                    logger.info(f"[{time.strftime('%H:%M:%S')}] ChangePasswordWindow created and displayed")
                    self.wait_window(change_window)  # Ждём закрытия окна смены
                    
                    if change_window.success:
                        logger.info(f"[{time.strftime('%H:%M:%S')}] Passwords changed successfully, proceeding to setup_app")
                        self.parent.setup_app()  # После успешной смены запускаем setup_app
                    else:
                        logger.info(f"[{time.strftime('%H:%M:%S')}] Password change cancelled, closing application")
                        self.parent.destroy()  # Если отмена, закрываем приложение
                        sys.exit(0)
                else:
                    logger.info(f"[{time.strftime('%H:%M:%S')}] Non-default admin password, proceeding to setup_app")
                    self.parent.setup_app()  # Для не-дефолтного сразу setup_app
            else:
                messagebox.showerror("Ошибка", f"Неверный пароль. Осталось попыток: {3 - self.login_attempts_count}")
                if self.login_attempts_count >= 3:
                    self.config.setdefault("login_attempts", []).append({"user": login, "timestamp": now, "success": False})
                    self.save_config()
                    self.destroy()

    def on_cancel(self):
        """Завершение приложения при нажатии на Отмена"""
        super().destroy()  # Вызываем стандартное закрытие Toplevel
        self.parent.destroy()  # Закрываем основное окно
        sys.exit(0)  # Гарантируем завершение