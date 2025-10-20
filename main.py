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

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
    
    
# 20%2025@Admin#10