#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request


INVALID_CHARS_RE = re.compile(r'[<>:"/\\\\|?*]')
WHITESPACE_RE = re.compile(r"\s+")


def safe_name(value: str, fallback: str = "item") -> str:
    if not value:
        return fallback
    value = INVALID_CHARS_RE.sub("_", value)
    value = WHITESPACE_RE.sub(" ", value).strip()
    value = value.strip(". ")
    return value or fallback


def safe_path(path_value: str) -> str:
    if not path_value:
        return safe_name(path_value)
    parts = re.split(r"[\\/]+", path_value)
    clean_parts = [safe_name(p, "item") for p in parts if p.strip()]
    return os.path.join(*clean_parts) if clean_parts else safe_name(path_value)


def category_folder(category: str) -> str:
    cat = (category or "").strip().lower()
    mapping = {
        "tv": "Сериалы",
        "movie": "Фильмы",
        "music": "Музыка",
        "other": "Прочее",
    }
    if cat in mapping:
        return mapping[cat]
    if not cat:
        return "Прочее"
    return safe_name(cat)


def build_auth_header(username: str, password: str) -> str:
    if username is None and password is None:
        return ""
    user = username or ""
    pwd = password or ""
    token = base64.b64encode(f"{user}:{pwd}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def fetch_torrents(api_url: str, username: str, password: str, timeout: int):
    url = api_url.rstrip("/") + "/torrents"
    payload = json.dumps({"action": "list"}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    auth_header = build_auth_header(username, password)
    if auth_header:
        headers["Authorization"] = auth_header
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode("utf-8", errors="replace")
    result = json.loads(data) if data else []
    return result if isinstance(result, list) else []


def build_strm_entries(torrents):
    entries = {}
    for tor in torrents:
        if not isinstance(tor, dict):
            continue
        info_hash = tor.get("hash") or ""
        if not info_hash:
            continue
        category = category_folder(tor.get("category"))
        title = tor.get("title") or tor.get("name") or info_hash
        torrent_folder = safe_name(title, info_hash)
        file_stats = tor.get("file_stats") or []
        if file_stats:
            for file_stat in file_stats:
                if not isinstance(file_stat, dict):
                    continue
                file_id = file_stat.get("id")
                if file_id is None:
                    continue
                file_path = safe_path(file_stat.get("path") or str(file_id))
                base, _ext = os.path.splitext(file_path)
                rel_path = os.path.join(category, torrent_folder, base + ".strm")
                entries[rel_path] = f"play/{info_hash}/{file_id}"
        else:
            rel_path = os.path.join(
                category, torrent_folder, safe_name(title, info_hash) + ".strm"
            )
            entries[rel_path] = f"play/{info_hash}/1"
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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def sync_strm_files(entries, output_dir: str, cleanup: bool):
    desired_paths = set()
    for rel_path, content in sorted(entries.items()):
        abs_path = os.path.join(output_dir, rel_path)
        desired_paths.add(os.path.normpath(abs_path))
        existing = read_text_file(abs_path)
        if existing != content:
            write_text_file(abs_path, content)

    if not cleanup:
        return

    for root, _dirs, files in os.walk(output_dir):
        for name in files:
            if not name.lower().endswith(".strm"):
                continue
            abs_path = os.path.normpath(os.path.join(root, name))
            if abs_path not in desired_paths:
                try:
                    os.remove(abs_path)
                except OSError:
                    continue


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
    return parser.parse_args()


def main():
    args = parse_args()
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    while True:
        try:
            torrents = fetch_torrents(
                args.api_url, args.username, args.password, args.timeout
            )
            entries = build_strm_entries(torrents)
            sync_strm_files(entries, output_dir, args.cleanup)
        except urllib.error.HTTPError as exc:
            print(f"[sync] HTTP error: {exc.code} {exc.reason}", file=sys.stderr)
        except urllib.error.URLError as exc:
            print(f"[sync] Connection error: {exc.reason}", file=sys.stderr)
        except Exception as exc:
            print(f"[sync] Unexpected error: {exc}", file=sys.stderr)

        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
