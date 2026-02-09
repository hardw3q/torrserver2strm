#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime


INVALID_CHARS_RE = re.compile(r'[<>:"/\\\\|?*]')
WHITESPACE_RE = re.compile(r"\s+")
# Символы вне ASCII (для режима --ascii-names)
NON_ASCII_RE = re.compile(r"[^\x00-\x7F]+")

# Флаг для включения подробного логирования
VERBOSE = False
# Использовать только ASCII в именах (для LANG=C и совместимости)
USE_ASCII_NAMES = False


def log(message, level="INFO"):
    """Логирование с временной меткой"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = f"[{timestamp}] [{level}]"
    print(f"{prefix} {message}", file=sys.stderr if level in ("ERROR", "WARN") else sys.stdout)


def log_verbose(message):
    """Подробное логирование (только при --verbose)"""
    if VERBOSE:
        log(message, "DEBUG")


def _use_ascii_names() -> bool:
    """Проверяет, нужно ли использовать только ASCII в именах (LANG=C и т.п.)."""
    if USE_ASCII_NAMES:
        return True
    lang = os.environ.get("LANG", "") or os.environ.get("LC_ALL", "")
    if not lang:
        return True
    lang_upper = lang.upper().split(".")[-1]
    return "UTF-8" not in lang_upper and "UTF8" not in lang_upper


def safe_name(value: str, fallback: str = "item") -> str:
    """Очистка имени файла/директории от недопустимых символов"""
    if not value:
        log_verbose(f"safe_name: пустое значение, используем fallback '{fallback}'")
        return fallback
    
    original = value
    log_verbose(f"safe_name: исходное значение: {repr(original)} (тип: {type(original)})")
    
    # Убеждаемся, что это строка
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
        log_verbose(f"safe_name: преобразовано из bytes: {repr(value)}")
    
    value = INVALID_CHARS_RE.sub("_", value)
    value = WHITESPACE_RE.sub(" ", value).strip()
    value = value.strip(". ")
    
    # В режиме LANG=C заменяем не-ASCII на подчёркивание, чтобы имена отображались в терминале
    if _use_ascii_names():
        value = NON_ASCII_RE.sub("_", value)
        value = re.sub(r"_+", "_", value).strip("_")
        log_verbose(f"safe_name: после ASCII-очистки: {repr(value)}")
    
    result = value or fallback
    
    log_verbose(f"safe_name: результат: {repr(result)}")
    return result


def safe_path(path_value: str) -> str:
    if not path_value:
        return safe_name(path_value)
    parts = re.split(r"[\\/]+", path_value)
    clean_parts = [safe_name(p, "item") for p in parts if p.strip()]
    return os.path.join(*clean_parts) if clean_parts else safe_name(path_value)


def category_folder(category: str) -> str:
    """Преобразование категории в имя папки"""
    original_cat = category
    cat = (category or "").strip().lower()
    log_verbose(f"category_folder: исходная категория: {repr(original_cat)} -> нормализована: {repr(cat)}")
    
    # При LANG=C или --ascii-names используем английские имена
    if _use_ascii_names():
        mapping = {
            "tv": "TV",
            "movie": "Movies",
            "music": "Music",
            "other": "Other",
        }
        default = "Other"
    else:
        mapping = {
            "tv": "Сериалы",
            "movie": "Фильмы",
            "music": "Музыка",
            "other": "Прочее",
        }
        default = "Прочее"
    
    if cat in mapping:
        result = mapping[cat]
        log_verbose(f"category_folder: найдено в маппинге '{cat}' -> '{result}'")
        return result
    if not cat:
        result = default
        log_verbose(f"category_folder: пустая категория -> '{result}'")
        return result
    result = safe_name(cat)
    log_verbose(f"category_folder: используем safe_name -> '{result}'")
    return result


def build_auth_header(username: str, password: str) -> str:
    if username is None and password is None:
        return ""
    user = username or ""
    pwd = password or ""
    token = base64.b64encode(f"{user}:{pwd}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def fetch_torrents(api_url: str, username: str, password: str, timeout: int):
    """Получение списка торрентов из TorrServer API"""
    url = api_url.rstrip("/") + "/torrents"
    log(f"Запрос к API: {url}")
    
    payload = json.dumps({"action": "list"}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    auth_header = build_auth_header(username, password)
    if auth_header:
        headers["Authorization"] = auth_header
        log_verbose("Используется HTTP Basic Auth")
    
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode("utf-8", errors="replace")
    
    result = json.loads(data) if data else []
    if not isinstance(result, list):
        log(f"Ожидался список, получен: {type(result)}", "WARN")
        return []
    
    log(f"Получено торрентов: {len(result)}")
    log_verbose(f"Данные API (первые 500 символов): {data[:500]}")
    return result


def build_strm_entries(torrents):
    """Построение структуры .strm файлов из списка торрентов"""
    entries = {}
    log(f"Обработка {len(torrents)} торрентов")
    
    for idx, tor in enumerate(torrents):
        if not isinstance(tor, dict):
            log(f"Торрент #{idx}: пропущен (не словарь)", "WARN")
            continue
        
        info_hash = tor.get("hash") or ""
        if not info_hash:
            log(f"Торрент #{idx}: пропущен (нет hash)", "WARN")
            continue
        
        category_raw = tor.get("category")
        category = category_folder(category_raw)
        log_verbose(f"Торрент #{idx} ({info_hash[:8]}...): категория '{category_raw}' -> '{category}'")
        
        title = tor.get("title") or tor.get("name") or info_hash
        log_verbose(f"Торрент #{idx}: title='{title}', name='{tor.get('name')}'")
        
        torrent_folder = safe_name(title, info_hash)
        log_verbose(f"Торрент #{idx}: папка торрента -> '{torrent_folder}'")
        
        file_stats = tor.get("file_stats") or []
        log_verbose(f"Торрент #{idx}: файлов в торренте: {len(file_stats)}")
        
        if file_stats:
            for file_idx, file_stat in enumerate(file_stats):
                if not isinstance(file_stat, dict):
                    log(f"Торрент #{idx}, файл #{file_idx}: пропущен (не словарь)", "WARN")
                    continue
                
                file_id = file_stat.get("id")
                if file_id is None:
                    log(f"Торрент #{idx}, файл #{file_idx}: пропущен (нет id)", "WARN")
                    continue
                
                file_path_raw = file_stat.get("path") or str(file_id)
                file_path = safe_path(file_path_raw)
                log_verbose(f"Торрент #{idx}, файл #{file_id}: путь '{file_path_raw}' -> '{file_path}'")
                
                base, _ext = os.path.splitext(file_path)
                rel_path = os.path.join(category, torrent_folder, base + ".strm")
                log_verbose(f"Торрент #{idx}, файл #{file_id}: относительный путь -> '{rel_path}'")
                
                entries[rel_path] = f"play/{info_hash}/{file_id}"
        else:
            rel_path = os.path.join(
                category, torrent_folder, safe_name(title, info_hash) + ".strm"
            )
            log_verbose(f"Торрент #{idx}: без file_stats, создаем '{rel_path}'")
            entries[rel_path] = f"play/{info_hash}/1"
    
    log(f"Создано записей для .strm файлов: {len(entries)}")
    return entries


def read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        return ""
    except OSError:
        return ""


def write_text_file(path: str, content: str):
    """Запись .strm файла с логированием"""
    dir_path = os.path.dirname(path)
    log_verbose(f"write_text_file: создание директории '{dir_path}'")
    
    try:
        os.makedirs(dir_path, exist_ok=True)
        log_verbose(f"write_text_file: директория создана/существует: '{dir_path}'")
    except OSError as e:
        log(f"Ошибка создания директории '{dir_path}': {e}", "ERROR")
        raise
    
    log_verbose(f"write_text_file: запись файла '{path}' с содержимым '{content}'")
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        log(f"Создан/обновлен: {path}")
    except OSError as e:
        log(f"Ошибка записи файла '{path}': {e}", "ERROR")
        raise


def sync_strm_files(entries, output_dir: str, cleanup: bool):
    """Синхронизация .strm файлов"""
    log(f"Синхронизация в директорию: {output_dir}")
    log(f"Всего записей для обработки: {len(entries)}")
    
    desired_paths = set()
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    for rel_path, content in sorted(entries.items()):
        abs_path = os.path.join(output_dir, rel_path)
        normalized_path = os.path.normpath(abs_path)
        desired_paths.add(normalized_path)
        
        log_verbose(f"Обработка: '{rel_path}' -> '{abs_path}'")
        log_verbose(f"  Нормализованный путь: '{normalized_path}'")
        log_verbose(f"  Содержимое: '{content}'")
        
        existing = read_text_file(abs_path)
        if existing != content:
            if existing:
                log_verbose(f"  Файл существует, содержимое отличается - обновление")
                updated_count += 1
            else:
                log_verbose(f"  Файл не существует - создание")
                created_count += 1
            write_text_file(abs_path, content)
        else:
            log_verbose(f"  Файл существует, содержимое совпадает - пропуск")
            skipped_count += 1
    
    log(f"Создано файлов: {created_count}, обновлено: {updated_count}, пропущено: {skipped_count}")
    
    if not cleanup:
        return
    
    log("Проверка на удаление устаревших файлов...")
    removed_count = 0
    for root, _dirs, files in os.walk(output_dir):
        for name in files:
            if not name.lower().endswith(".strm"):
                continue
            abs_path = os.path.normpath(os.path.join(root, name))
            if abs_path not in desired_paths:
                log_verbose(f"Удаление устаревшего файла: {abs_path}")
                try:
                    os.remove(abs_path)
                    removed_count += 1
                except OSError as e:
                    log(f"Ошибка удаления файла '{abs_path}': {e}", "WARN")
                    continue
    
    if removed_count > 0:
        log(f"Удалено устаревших файлов: {removed_count}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Sync TorrServer torrents into .strm files."
    )
    parser.add_argument(
        "--api-url",
        required=True,
        help="TorrServer base URL, e.g. http://127.0.0.1:8090",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to create STRM structure in.",
    )
    parser.add_argument("--username", default=None, help="HTTP basic auth username.")
    parser.add_argument("--password", default=None, help="HTTP basic auth password.")
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Polling interval in seconds (default: 2).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP timeout in seconds (default: 10).",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove .strm files that are no longer in TorrServer list.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run sync once and exit.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging.",
    )
    parser.add_argument(
        "--ascii-names",
        action="store_true",
        help="Use ASCII-only names for dirs/files (e.g. Movies, TV). Auto-enabled when LANG=C.",
    )
    return parser.parse_args()


def main():
    global VERBOSE, USE_ASCII_NAMES
    args = parse_args()
    VERBOSE = args.verbose
    USE_ASCII_NAMES = args.ascii_names
    
    log("=" * 60)
    log("TorrServer STRM Sync started")
    log(f"API URL: {args.api_url}")
    log(f"Output directory: {args.output_dir}")
    log(f"Interval: {args.interval}s")
    log(f"Verbose: {VERBOSE}")
    log(f"ASCII-only names (LANG=C or --ascii-names): {_use_ascii_names()}")
    log("=" * 60)
    
    output_dir = os.path.abspath(args.output_dir)
    log(f"Абсолютный путь output directory: {output_dir}")
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        log(f"Директория создана/существует: {output_dir}")
    except OSError as e:
        log(f"Ошибка создания директории '{output_dir}': {e}", "ERROR")
        sys.exit(1)

    sync_count = 0
    while True:
        sync_count += 1
        log(f"\n--- Синхронизация #{sync_count} ---")
        
        try:
            torrents = fetch_torrents(
                args.api_url, args.username, args.password, args.timeout
            )
            entries = build_strm_entries(torrents)
            sync_strm_files(entries, output_dir, args.cleanup)
            log(f"Синхронизация #{sync_count} завершена успешно")
        except urllib.error.HTTPError as exc:
            log(f"HTTP error: {exc.code} {exc.reason}", "ERROR")
        except urllib.error.URLError as exc:
            log(f"Connection error: {exc.reason}", "ERROR")
        except Exception as exc:
            log(f"Unexpected error: {exc}", "ERROR")
            import traceback
            log_verbose(traceback.format_exc())

        if args.once:
            log("Завершение работы (--once)")
            break
        
        log_verbose(f"Ожидание {args.interval} секунд до следующей синхронизации...")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
