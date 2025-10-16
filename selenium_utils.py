import logging
import time
import tkinter as tk
from tkinter import Toplevel, Label
from PIL import Image, ImageTk
import io
import re
import numpy as np
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium import webdriver

logger = logging.getLogger(__name__)

class SeleniumUtils:
    def initialize_drivers(self):
        self.driver = webdriver.Chrome(service=Service(self.driver_path), options=self.options)
        self.driver.get('about:blank')
        self.main_handle = self.driver.current_window_handle
        current_group = next((g for g in self.groups if g.get("current", False)), None)
        if current_group:
            grid = current_group.get("grid", [None] * 9)
            for i in range(9):
                self.driver.execute_script("window.open('about:blank', '_blank');")
                self.handles[i] = self.driver.window_handles[-1]

    def start_load_group_to_drivers(self):
        current_group = next((g for g in self.groups if g.get("current", False)), None)
        if current_group:
            grid = current_group.get("grid", [None] * 9)
            for i in range(9):
                link = grid[i] if i < len(grid) else None
                if self.handles[i]:
                    self.driver.switch_to.window(self.handles[i])
                    if link:
                        self.driver.get('about:blank')
                        self.driver.get(link)
                        try:
                            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "ModalBodyPlayer")))
                        except Exception as e:
                            logger.error(f"[{time.strftime('%H:%M:%S')}] Error loading tab for cell {i}: {str(e)}")
                    else:
                        self.driver.get('about:blank')
        self.driver.switch_to.window(self.main_handle)

    def update_frames(self):
        if not self.driver:
            self.update_frames_id = self.after(self.period, self.update_frames)
            return
        for cell in self.cells:
            i = cell.index
            if not self.full_update and i != self.modal_cell_index:
                continue
            if not cell.cam or not self.handles[i]:
                cell.photo = self.nocam_photo if not cell.cam else self.noconnect_photo
                cell.image_label.config(image=cell.photo)
                continue
            retries = 2
            while retries > 0:
                try:
                    self.driver.switch_to.window(self.handles[i])
                    if self.driver.current_url == 'about:blank':
                        cell.photo = self.nocam_photo
                        cell.image_label.config(image=cell.photo)
                        break
                    element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.ID, "ModalBodyPlayer"))
                    )
                    screenshot_bytes = None
                    try:
                        iframe = element.find_element(By.TAG_NAME, "iframe")
                        self.driver.switch_to.frame(iframe)
                        body = self.driver.find_element(By.TAG_NAME, "body")
                        if body.size['height'] == 0:
                            self.driver.execute_script("document.body.style.height = '300px';")
                            self.driver.execute_script("document.body.style.display = 'block';")
                        screenshot_bytes = body.screenshot_as_png
                    except:
                        self.driver.switch_to.default_content()
                        style = element.get_attribute('style')
                        height_match = re.search(r'height:\s*(\d+)px', style, re.IGNORECASE)
                        height = int(height_match.group(1)) if height_match else 300
                        if element.size['height'] == 0:
                            self.driver.execute_script(f"arguments[0].style.height = '{height}px';", element)
                            self.driver.execute_script("arguments[0].style.display = 'block';", element)
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
                        self.original_pil_images[i] = cropped_image.copy()
                        resized_small = cropped_image.resize((self.cell_width, self.cell_height), Image.LANCZOS)
                        cell.photo = ImageTk.PhotoImage(resized_small)
                        cell.image_label.config(image=cell.photo)
                        if self.modal_cell_index == i and self.modal_image_label:
                            resized_modal = cropped_image.resize(self.modal_image_size, Image.LANCZOS)
                            self.modal_photo = ImageTk.PhotoImage(resized_modal)
                            self.modal_image_label.config(image=self.modal_photo)
                    self.driver.switch_to.default_content()
                    break
                except Exception as e:
                    retries -= 1
                    if retries == 0:
                        error_msg = f"[{time.strftime('%H:%M:%S')}] Error updating frame for cell {i}: {str(e)}"
                        logger.error(error_msg)
                        cell.photo = self.noconnect_photo
                        cell.image_label.config(image=cell.photo)
        self.driver.switch_to.window(self.main_handle)
        self.update_frames_id = self.after(self.period, self.update_frames)

    def set_frame_rate(self, period):
        self.period = period