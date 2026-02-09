#!/bin/bash

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    error "Пожалуйста, запустите скрипт с правами root (sudo или от root)"
    exit 1
fi

# Информация для пользователя
info "Запуск от пользователя: $(whoami)"

info "Удаление TorrServer STRM Sync сервиса"
echo ""

# Проверка существования сервиса
if ! systemctl list-unit-files | grep -q "torrserver-strm-sync.service"; then
    warn "Сервис torrserver-strm-sync не найден в systemd"
    exit 0
fi

# Остановка и отключение сервиса
if systemctl is-active --quiet torrserver-strm-sync.service; then
    info "Остановка сервиса..."
    systemctl stop torrserver-strm-sync.service
fi

if systemctl is-enabled --quiet torrserver-strm-sync.service; then
    info "Отключение автозапуска сервиса..."
    systemctl disable torrserver-strm-sync.service
fi

# Удаление unit файла
SERVICE_FILE="/etc/systemd/system/torrserver-strm-sync.service"
if [ -f "$SERVICE_FILE" ]; then
    info "Удаление unit файла..."
    rm -f "$SERVICE_FILE"
    systemctl daemon-reload
    info "Unit файл удален"
else
    warn "Unit файл не найден: $SERVICE_FILE"
fi

# Опциональное удаление скрипта
echo ""
read -p "Удалить скрипт и директорию установки? (y/n) [n]: " REMOVE_SCRIPT
REMOVE_SCRIPT=${REMOVE_SCRIPT:-n}

if [ "$REMOVE_SCRIPT" = "y" ] || [ "$REMOVE_SCRIPT" = "Y" ]; then
    # Определение пути к скрипту из unit файла
    INSTALL_DIR=""
    SCRIPT_PATH=""
    
    # Пытаемся прочитать из сохраненного unit файла перед удалением
    if [ -f "$SERVICE_FILE" ]; then
        # Извлекаем путь к скрипту из ExecStart
        EXEC_LINE=$(grep "^ExecStart=" "$SERVICE_FILE" | cut -d'=' -f2-)
        # Ищем путь к python скрипту (после python3)
        SCRIPT_PATH=$(echo "$EXEC_LINE" | grep -oP '(?<=python3\s)[^\s]+' | head -1)
        if [ -n "$SCRIPT_PATH" ] && [ -f "$SCRIPT_PATH" ]; then
            INSTALL_DIR=$(dirname "$SCRIPT_PATH")
            info "Найден путь к скрипту: $SCRIPT_PATH"
        fi
    fi
    
    # Если не удалось определить автоматически, запрашиваем у пользователя
    if [ -z "$INSTALL_DIR" ] || [ ! -d "$INSTALL_DIR" ]; then
        read -p "Введите путь к директории со скриптом [/opt/torrserver/scripts]: " INSTALL_DIR
        INSTALL_DIR=${INSTALL_DIR:-/opt/torrserver/scripts}
        SCRIPT_PATH="$INSTALL_DIR/torrserver_strm_sync.py"
    fi
    
    if [ -d "$INSTALL_DIR" ]; then
        read -p "Удалить директорию $INSTALL_DIR? (y/n) [n]: " REMOVE_DIR
        REMOVE_DIR=${REMOVE_DIR:-n}
        
        if [ "$REMOVE_DIR" = "y" ] || [ "$REMOVE_DIR" = "Y" ]; then
            info "Удаление директории $INSTALL_DIR..."
            rm -rf "$INSTALL_DIR"
            info "Директория удалена"
        else
            info "Удаление только скрипта..."
            if [ -f "$SCRIPT_PATH" ]; then
                rm -f "$SCRIPT_PATH"
                info "Скрипт удален"
            else
                warn "Скрипт не найден: $SCRIPT_PATH"
            fi
        fi
    else
        warn "Директория $INSTALL_DIR не найдена"
    fi
else
    info "Скрипт оставлен на месте"
fi

# Опциональное удаление директории с .strm файлами
echo ""
read -p "Удалить директорию с .strm файлами? (y/n) [n]: " REMOVE_STRM_DIR
REMOVE_STRM_DIR=${REMOVE_STRM_DIR:-n}

if [ "$REMOVE_STRM_DIR" = "y" ] || [ "$REMOVE_STRM_DIR" = "Y" ]; then
    # Попытка определить путь из unit файла (если он еще существует)
    OUTPUT_DIR=""
    if [ -f "$SERVICE_FILE" ]; then
        EXEC_LINE=$(grep "^ExecStart=" "$SERVICE_FILE" | cut -d'=' -f2-)
        # Ищем --output-dir и следующий за ним путь
        OUTPUT_DIR=$(echo "$EXEC_LINE" | grep -oP '(?<=--output-dir\s)[^\s]+' | head -1)
    fi
    
    if [ -z "$OUTPUT_DIR" ]; then
        read -p "Введите путь к директории с .strm файлами: " OUTPUT_DIR
    fi
    
    if [ -n "$OUTPUT_DIR" ] && [ -d "$OUTPUT_DIR" ]; then
        warn "ВНИМАНИЕ: Будут удалены все файлы в $OUTPUT_DIR!"
        read -p "Продолжить? (yes/no): " CONFIRM
        if [ "$CONFIRM" = "yes" ]; then
            info "Удаление директории $OUTPUT_DIR..."
            rm -rf "$OUTPUT_DIR"
            info "Директория удалена"
        else
            info "Удаление отменено"
        fi
    else
        warn "Директория $OUTPUT_DIR не найдена"
    fi
else
    info "Директория с .strm файлами оставлена"
fi

echo ""
info "Удаление завершено!"
