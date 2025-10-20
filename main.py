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

from main_app import MainApp

# Добавлено для проверки мьютекса (запрет запуска второй копии)
import ctypes
from ctypes import wintypes

# Настройка логирования (используем существующий logger)
logging.basicConfig(filename='app.log', level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

# Функции для Windows API
kernel32 = ctypes.windll.kernel32
CreateMutex = kernel32.CreateMutexW
CreateMutex.argtypes = [wintypes.LPCVOID, wintypes.BOOL, wintypes.LPCWSTR]
CreateMutex.restype = wintypes.HANDLE

GetLastError = kernel32.GetLastError
GetLastError.argtypes = []
GetLastError.restype = wintypes.DWORD

ERROR_ALREADY_EXISTS = 183

if __name__ == "__main__":
    # Проверка на запуск второй копии
    mutex_name = "OrenburgCameraViewerMutex"  # Уникальное имя мьютекса
    handle = CreateMutex(None, False, mutex_name)
    if GetLastError() == ERROR_ALREADY_EXISTS:
        logger.info(f"[{time.strftime('%H:%M:%S')}] Attempt to launch second instance detected. Exiting.")
        print("Application is already running.")
        sys.exit(0)
    else:
        logger.info(f"[{time.strftime('%H:%M:%S')}] Mutex created successfully. Launching application.")

    app = MainApp()
    app.mainloop()