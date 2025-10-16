import logging
import time
import json
import re
import tkinter as tk
from tkinter import messagebox, Toplevel, Label
from tkinter.font import Font
from tkinter import ttk
from PIL import Image, ImageTk
import io
import numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os

from ui_components import CameraDialog
from selenium_utils import SeleniumUtils

logger = logging.getLogger(__name__)

class MainAppMethods(SeleniumUtils):
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
                if added:
                    logger.info(f"[{time.strftime('%H:%M:%S')}] Lost camera '{cam['street']}' added to '{added_group_name}'")

        config["groups"] = groups
        return config

    def update_camera_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        current_group = next((g for g in self.groups if g.get("current", False)), None)
        for group in self.groups:
            group_iid = self.tree.insert("", "end", text=group["name"])
            if group == current_group:
                self.tree.item(group_iid, image=self.checked_photo)
            else:
                self.tree.item(group_iid, image=self.unchecked_photo)
            grid = group.get("grid", [None] * 9)
            for link in [l for l in grid if l is not None]:
                cam = next((c for c in self.cams if c["link"] == link), None)
                if cam:
                    self.tree.insert(group_iid, "end", text=cam["street"])

    def move_top(self):
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        parent = self.tree.parent(item)
        if parent == "":  # Группа
            group_name = self.tree.item(item)["text"]
            group_index = next((i for i, g in enumerate(self.groups) if g.get("name") == group_name), -1)
            if group_index > 0:
                self.groups.insert(0, self.groups.pop(group_index))
                logger.info(f"[{time.strftime('%H:%M:%S')}] Moved group '{group_name}' to top")
                self.save_config()
                self.update_camera_list()
                new_item = self.tree.get_children()[0]
                self.tree.selection_set(new_item)
                self.tree.focus(new_item)
        else:  # Камера
            group_iid = parent
            group_name = self.tree.item(group_iid)["text"]
            group = next((g for g in self.groups if g.get("name") == group_name), None)
            if not group:
                logger.error(f"[{time.strftime('%H:%M:%S')}] Group '{group_name}' not found in move_top")
                return
            children = self.tree.get_children(group_iid)
            cam_index = children.index(item)
            if cam_index == 0:
                return
            grid = group.get("grid", [None] * 9)
            non_none = [x for x in grid if x is not None]
            link = non_none.pop(cam_index)
            non_none.insert(0, link)
            group["grid"] = non_none + [None] * (9 - len(non_none))
            logger.info(f"[{time.strftime('%H:%M:%S')}] Moved camera to top in group '{group_name}'")
            is_current = group.get("current", False)
            if is_current:
                self.load_current_group_to_cells()
            self.save_config()
            self.update_camera_list()
            new_group_iid = next((iid for iid in self.tree.get_children() if self.tree.item(iid)["text"] == group_name), None)
            if new_group_iid:
                new_children = self.tree.get_children(new_group_iid)
                if new_children:
                    new_item = new_children[0]
                    self.tree.selection_set(new_item)
                    self.tree.focus(new_item)

    def move_up(self):
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        parent = self.tree.parent(item)
        if parent == "":  # Группа
            group_name = self.tree.item(item)["text"]
            group_index = next((i for i, g in enumerate(self.groups) if g.get("name") == group_name), -1)
            if group_index > 0:
                self.groups[group_index - 1], self.groups[group_index] = self.groups[group_index], self.groups[group_index - 1]
                logger.info(f"[{time.strftime('%H:%M:%S')}] Moved group '{group_name}' up")
                self.save_config()
                self.update_camera_list()
                new_items = self.tree.get_children()
                new_item = new_items[group_index - 1]
                self.tree.selection_set(new_item)
                self.tree.focus(new_item)
        else:  # Камера
            group_iid = parent
            group_name = self.tree.item(group_iid)["text"]
            group = next((g for g in self.groups if g.get("name") == group_name), None)
            if not group:
                logger.error(f"[{time.strftime('%H:%M:%S')}] Group '{group_name}' not found in move_up")
                return
            children = self.tree.get_children(group_iid)
            cam_index = children.index(item)
            if cam_index == 0:
                return
            grid = group.get("grid", [None] * 9)
            non_none = [x for x in grid if x is not None]
            non_none[cam_index - 1], non_none[cam_index] = non_none[cam_index], non_none[cam_index - 1]
            group["grid"] = non_none + [None] * (9 - len(non_none))
            logger.info(f"[{time.strftime('%H:%M:%S')}] Moved camera up in group '{group_name}'")
            is_current = group.get("current", False)
            if is_current:
                self.load_current_group_to_cells()
            self.save_config()
            self.update_camera_list()
            new_group_iid = next((iid for iid in self.tree.get_children() if self.tree.item(iid)["text"] == group_name), None)
            if new_group_iid:
                new_children = self.tree.get_children(new_group_iid)
                if cam_index - 1 < len(new_children):
                    new_item = new_children[cam_index - 1]
                    self.tree.selection_set(new_item)
                    self.tree.focus(new_item)

    def move_bottom(self):
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        parent = self.tree.parent(item)
        if parent == "":  # Группа
            group_name = self.tree.item(item)["text"]
            group_index = next((i for i, g in enumerate(self.groups) if g.get("name") == group_name), -1)
            if group_index < len(self.groups) - 1:
                self.groups.append(self.groups.pop(group_index))
                logger.info(f"[{time.strftime('%H:%M:%S')}] Moved group '{group_name}' to bottom")
                self.save_config()
                self.update_camera_list()
                new_item = self.tree.get_children()[-1]
                self.tree.selection_set(new_item)
                self.tree.focus(new_item)
        else:  # Камера
            group_iid = parent
            group_name = self.tree.item(group_iid)["text"]
            group = next((g for g in self.groups if g.get("name") == group_name), None)
            if not group:
                logger.error(f"[{time.strftime('%H:%M:%S')}] Group '{group_name}' not found in move_bottom")
                return
            children = self.tree.get_children(group_iid)
            cam_index = children.index(item)
            grid = group.get("grid", [None] * 9)
            non_none = [x for x in grid if x is not None]
            if cam_index >= len(non_none) - 1:
                return
            link = non_none.pop(cam_index)
            non_none.append(link)
            group["grid"] = non_none + [None] * (9 - len(non_none))
            logger.info(f"[{time.strftime('%H:%M:%S')}] Moved camera to bottom in group '{group_name}'")
            is_current = group.get("current", False)
            if is_current:
                self.load_current_group_to_cells()
            self.save_config()
            self.update_camera_list()
            new_group_iid = next((iid for iid in self.tree.get_children() if self.tree.item(iid)["text"] == group_name), None)
            if new_group_iid:
                new_children = self.tree.get_children(new_group_iid)
                if new_children:
                    new_item = new_children[-1]
                    self.tree.selection_set(new_item)
                    self.tree.focus(new_item)

    def move_down(self):
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        parent = self.tree.parent(item)
        if parent == "":  # Группа
            group_name = self.tree.item(item)["text"]
            group_index = next((i for i, g in enumerate(self.groups) if g.get("name") == group_name), -1)
            if group_index < len(self.groups) - 1:
                self.groups[group_index], self.groups[group_index + 1] = self.groups[group_index + 1], self.groups[group_index]
                logger.info(f"[{time.strftime('%H:%M:%S')}] Moved group '{group_name}' down")
                self.save_config()
                self.update_camera_list()
                new_items = self.tree.get_children()
                new_item = new_items[group_index + 1]
                self.tree.selection_set(new_item)
                self.tree.focus(new_item)
        else:  # Камера
            group_iid = parent
            group_name = self.tree.item(group_iid)["text"]
            group = next((g for g in self.groups if g.get("name") == group_name), None)
            if not group:
                logger.error(f"[{time.strftime('%H:%M:%S')}] Group '{group_name}' not found in move_down")
                return
            children = self.tree.get_children(group_iid)
            cam_index = children.index(item)
            grid = group.get("grid", [None] * 9)
            non_none = [x for x in grid if x is not None]
            if cam_index >= len(non_none) - 1:
                return  # Не двигаем на пустые ячейки или если последняя
            # Swap в grid
            non_none[cam_index], non_none[cam_index + 1] = non_none[cam_index + 1], non_none[cam_index]
            group["grid"] = non_none + [None] * (9 - len(non_none))
            logger.info(f"[{time.strftime('%H:%M:%S')}] After move_down swap in group '{group_name}': {non_none}")
            is_current = group.get("current", False)
            if is_current:
                self.load_current_group_to_cells()  # Обновляем cells и drivers по новому grid перед сохранением
            self.save_config()  # Теперь сохраняем — grid не перезапишется старым
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
                    self.save_config()
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
                self.save_config()
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
                self.start_load_group_to_drivers()  # Обновляем вкладки после добавления
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
                        if self.handles[i]:
                            self.driver.switch_to.window(self.handles[i])
                            self.driver.get(new_link)
                            self.driver.refresh()
                            try:
                                WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "ModalBodyPlayer")))
                            except Exception as e:
                                logger.error(f"[{time.strftime('%H:%M:%S')}] Error reloading tab for cell {i}: {str(e)}")
            self.driver.switch_to.window(self.main_handle)

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
            group["grid"] = self.compact_grid(new_grid)
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
        self.save_config()
        self.update_camera_list()
        self.start_load_group_to_drivers()  # Обновляем вкладки после удаления

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
            self.save_config()
            self.update_camera_list()

    def reload_drivers(self):
        if self.driver:
            # Закрываем все вкладки кроме основной
            for handle in self.handles:
                if handle:
                    try:
                        self.driver.switch_to.window(handle)
                        self.driver.close()
                    except:
                        pass
            self.handles = [None] * 9
            self.driver.switch_to.window(self.main_handle)
        self.start_load_group_to_drivers()

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
            self.start_load_group_to_drivers()  # Обновляем вкладки

    def on_close(self):
        self.close_modal()
        if self.update_frames_id:
            self.after_cancel(self.update_frames_id)
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                error_msg = f"[{time.strftime('%H:%M:%S')}] Error quitting driver: {str(e)}"
                logger.error(error_msg)
        self.destroy()

    def compact_grid(self, grid):
        return [x for x in grid if x is not None] + [None] * (9 - len([x for x in grid if x is not None]))