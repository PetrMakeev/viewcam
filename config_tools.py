import logging
import json
import time
from tkinter import messagebox

# Настройка logging в файл
logging.basicConfig(filename='app.log', level=logging.ERROR, force=True)
logger = logging.getLogger(__name__)

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

def save_config(self):
    current_group = next((g for g in self.groups if g.get("current", False)), None)
    if current_group:
        current_grid = [cell.cam["link"] if cell.cam else None for cell in self.cells]
        current_group["grid"] = compact_grid(self, current_grid)
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