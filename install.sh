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
    error "Пожалуйста, запустите скрипт с правами root (sudo)"
    exit 1
fi

# Определение пути к скрипту
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_FILE="$SCRIPT_DIR/torrserver_strm_sync.py"
SERVICE_FILE="$SCRIPT_DIR/torrserver-strm-sync.service"

# Проверка наличия файлов
if [ ! -f "$SCRIPT_FILE" ]; then
    error "Файл $SCRIPT_FILE не найден!"
    exit 1
fi

if [ ! -f "$SERVICE_FILE" ]; then
    error "Файл $SERVICE_FILE не найден!"
    exit 1
fi

info "Установка TorrServer STRM Sync сервиса"
echo ""

# Запрос параметров
read -p "Путь к директории скрипта [/opt/torrserver/scripts]: " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-/opt/torrserver/scripts}

read -p "URL TorrServer API [http://127.0.0.1:8090]: " API_URL
API_URL=${API_URL:-http://127.0.0.1:8090}

read -p "Директория для .strm файлов [/mnt/media/strm]: " OUTPUT_DIR
OUTPUT_DIR=${OUTPUT_DIR:-/mnt/media/strm}

read -p "Пользователь для запуска сервиса [torrserver]: " SERVICE_USER
SERVICE_USER=${SERVICE_USER:-torrserver}

# Проверка существования пользователя
if ! id "$SERVICE_USER" &>/dev/null; then
    warn "Пользователь $SERVICE_USER не существует. Создать? (y/n)"
    read -r CREATE_USER
    if [ "$CREATE_USER" = "y" ] || [ "$CREATE_USER" = "Y" ]; then
        useradd -r -s /bin/false "$SERVICE_USER" || {
            error "Не удалось создать пользователя $SERVICE_USER"
            exit 1
        }
        info "Пользователь $SERVICE_USER создан"
    else
        error "Установка отменена"
        exit 1
    fi
fi

# Запрос HTTP Basic Auth (опционально)
echo ""
read -p "Использовать HTTP Basic Auth? (y/n) [n]: " USE_AUTH
USE_AUTH=${USE_AUTH:-n}

AUTH_ARGS=""
if [ "$USE_AUTH" = "y" ] || [ "$USE_AUTH" = "Y" ]; then
    read -p "Имя пользователя: " AUTH_USER
    read -sp "Пароль: " AUTH_PASS
    echo ""
    if [ -n "$AUTH_USER" ] && [ -n "$AUTH_PASS" ]; then
        AUTH_ARGS="--username $AUTH_USER --password $AUTH_PASS"
    fi
fi

# Создание директории для скрипта
info "Создание директории $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Копирование скрипта
info "Копирование скрипта в $INSTALL_DIR"
cp "$SCRIPT_FILE" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/torrserver_strm_sync.py"
chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/torrserver_strm_sync.py"

# Создание директории для .strm файлов
info "Создание директории $OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$OUTPUT_DIR"

# Создание временного unit файла
TEMP_SERVICE="/tmp/torrserver-strm-sync.service"
cat > "$TEMP_SERVICE" <<EOF
[Unit]
Description=TorrServer STRM sync service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/torrserver_strm_sync.py --api-url $API_URL --output-dir $OUTPUT_DIR $AUTH_ARGS
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

# Копирование unit файла
info "Установка systemd unit файла"
cp "$TEMP_SERVICE" /etc/systemd/system/torrserver-strm-sync.service
rm "$TEMP_SERVICE"

# Перезагрузка systemd
info "Перезагрузка systemd daemon"
systemctl daemon-reload

# Включение и запуск сервиса
info "Включение и запуск сервиса"
systemctl enable torrserver-strm-sync.service

if systemctl start torrserver-strm-sync.service; then
    info "Сервис успешно запущен!"
else
    error "Не удалось запустить сервис. Проверьте логи: sudo journalctl -u torrserver-strm-sync"
    exit 1
fi

# Проверка статуса
echo ""
info "Статус сервиса:"
systemctl status torrserver-strm-sync.service --no-pager -l

echo ""
info "Установка завершена!"
echo ""
echo "Полезные команды:"
echo "  Просмотр логов: sudo journalctl -u torrserver-strm-sync -f"
echo "  Статус сервиса: sudo systemctl status torrserver-strm-sync"
echo "  Перезапуск:     sudo systemctl restart torrserver-strm-sync"
echo "  Остановка:      sudo systemctl stop torrserver-strm-sync"
