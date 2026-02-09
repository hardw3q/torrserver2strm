# TorrServer STRM Sync

Python скрипт для автоматической синхронизации торрентов из TorrServer в структуру `.strm` файлов для медиа-серверов (Kodi, Jellyfin, Plex и т.д.).

## Описание

Скрипт периодически опрашивает API TorrServer, получает список активных торрентов и создает структуру `.strm` файлов, организованную по категориям и названиям торрентов. Каждый `.strm` файл содержит ссылку на потоковое воспроизведение через TorrServer.

### Структура файлов

Скрипт создает следующую структуру:

```
output_dir/
├── Сериалы/
│   └── Название сериала/
│       ├── Серия 01.strm
│       └── Серия 02.strm
├── Фильмы/
│   └── Название фильма/
│       └── Название фильма.strm
├── Музыка/
│   └── Альбом/
│       └── Трек.strm
└── Прочее/
    └── Торрент/
        └── Файл.strm
```

### Маппинг категорий

- `tv` → `Сериалы`
- `movie` → `Фильмы`
- `music` → `Музыка`
- `other` или пусто → `Прочее`
- Другие категории → используются как есть (с очисткой имени)

## Требования

- Python 3.6+
- Доступ к TorrServer API
- Права на запись в директорию вывода

## Установка

### Ручная установка

1. Скопируйте скрипт в нужную директорию:
```bash
sudo mkdir -p /opt/torrserver/scripts
sudo cp torrserver_strm_sync.py /opt/torrserver/scripts/
sudo chmod +x /opt/torrserver/scripts/torrserver_strm_sync.py
```

2. Установите как systemd сервис (см. раздел "Установка как сервис")

### Автоматическая установка

Используйте скрипт `install.sh`:

```bash
sudo ./install.sh
```

**Для LXC контейнеров или если файл не имеет прав на выполнение:**

```bash
# Если вы уже root (в LXC контейнере)
bash install.sh

# Или дайте права на выполнение
chmod +x install.sh
./install.sh
```

Скрипт автоматически определит свою текущую директорию и запросит:
- Путь для установки скрипта (по умолчанию: `/opt/torrserver/scripts`) - скрипт будет скопирован из текущей директории
- URL TorrServer API (по умолчанию: `http://127.0.0.1:8090`)
- Директорию для `.strm` файлов (по умолчанию: `/mnt/media/strm`)
- Имя пользователя для systemd (по умолчанию: `torrserver`)
- Опционально: логин и пароль для HTTP Basic Auth

**Примечание для LXC контейнеров:**
- Если вы уже работаете от root, используйте `bash install.sh` вместо `sudo ./install.sh`
- Скрипт автоматически определит, что вы root, и пропустит проверку sudo

## Использование

### Базовое использование

```bash
python3 torrserver_strm_sync.py \
    --api-url http://127.0.0.1:8090 \
    --output-dir /path/to/strm
```

### С HTTP Basic Auth

```bash
python3 torrserver_strm_sync.py \
    --api-url http://127.0.0.1:8090 \
    --output-dir /path/to/strm \
    --username user \
    --password pass
```

### Однократная синхронизация

```bash
python3 torrserver_strm_sync.py \
    --api-url http://127.0.0.1:8090 \
    --output-dir /path/to/strm \
    --once
```

### С очисткой удаленных торрентов

```bash
python3 torrserver_strm_sync.py \
    --api-url http://127.0.0.1:8090 \
    --output-dir /path/to/strm \
    --cleanup
```

### Параметры командной строки

| Параметр | Обязательный | Описание | По умолчанию |
|----------|--------------|----------|--------------|
| `--api-url` | Да | Базовый URL TorrServer API | - |
| `--output-dir` | Да | Директория для создания `.strm` файлов | - |
| `--username` | Нет | Имя пользователя для HTTP Basic Auth | - |
| `--password` | Нет | Пароль для HTTP Basic Auth | - |
| `--interval` | Нет | Интервал опроса API в секундах | `2.0` |
| `--timeout` | Нет | Таймаут HTTP запросов в секундах | `10` |
| `--cleanup` | Нет | Удалять `.strm` файлы удаленных торрентов | `False` |
| `--once` | Нет | Выполнить синхронизацию один раз и выйти | `False` |

## Установка как systemd сервис

### Использование install.sh

```bash
sudo ./install.sh
```

### Ручная установка

1. Отредактируйте файл `torrserver-strm-sync.service`:
   - Измените `User` на нужного пользователя
   - Измените `WorkingDirectory` на путь к скрипту
   - Измените `ExecStart` с нужными параметрами

2. Скопируйте unit файл:
```bash
sudo cp torrserver-strm-sync.service /etc/systemd/system/
```

3. Перезагрузите systemd и включите сервис:
```bash
sudo systemctl daemon-reload
sudo systemctl enable torrserver-strm-sync
sudo systemctl start torrserver-strm-sync
```

### Управление сервисом

```bash
# Проверить статус
sudo systemctl status torrserver-strm-sync

# Просмотр логов
sudo journalctl -u torrserver-strm-sync -f

# Остановить сервис
sudo systemctl stop torrserver-strm-sync

# Запустить сервис
sudo systemctl start torrserver-strm-sync

# Перезапустить сервис
sudo systemctl restart torrserver-strm-sync
```

## Удаление сервиса

### Использование uninstall.sh

```bash
sudo ./uninstall.sh
```

### Ручное удаление

```bash
sudo systemctl stop torrserver-strm-sync
sudo systemctl disable torrserver-strm-sync
sudo rm /etc/systemd/system/torrserver-strm-sync.service
sudo systemctl daemon-reload
```

## Формат .strm файлов

Каждый `.strm` файл содержит одну строку с относительным URL для воспроизведения:

```
play/{hash}/{id}
```

Где:
- `{hash}` - хеш торрента (infohash)
- `{id}` - индекс файла в торренте (начинается с 1)

Пример:
```
play/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0/1
```

Для использования в медиа-серверах, URL должен быть полным:
```
http://127.0.0.1:8090/play/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0/1
```

## Особенности работы

1. **Идемпотентность**: Скрипт перезаписывает `.strm` файлы только если их содержимое изменилось, что предотвращает ненужные операции записи.

2. **Безопасные имена**: Все имена файлов и директорий очищаются от недопустимых символов (`<>:"/\|?*`), что обеспечивает совместимость с различными файловыми системами.

3. **Обработка ошибок**: Скрипт продолжает работу при временных ошибках сети или API, выводя сообщения в stderr.

4. **Множественные файлы**: Если в торренте несколько файлов, для каждого создается отдельный `.strm` файл с соответствующим индексом.

5. **Пути файлов**: Структура путей внутри торрента сохраняется в именах `.strm` файлов (без расширения исходного файла).

## Устранение неполадок

### Permission denied при запуске install.sh

Если вы получаете ошибку "Permission denied" при запуске скрипта:

```bash
# В LXC контейнере или если вы уже root
bash install.sh

# Или дайте права на выполнение
chmod +x install.sh
./install.sh
```

### Сервис не запускается

1. Проверьте логи:
```bash
# Если вы root (LXC контейнер)
journalctl -u torrserver-strm-sync -n 50

# Или с sudo
sudo journalctl -u torrserver-strm-sync -n 50
```

2. Проверьте права доступа к директории вывода:
```bash
# Если вы root
chown -R torrserver:torrserver /mnt/media/strm

# Или с sudo
sudo chown -R torrserver:torrserver /mnt/media/strm
```

3. Проверьте доступность TorrServer API:
```bash
curl -X POST http://127.0.0.1:8090/torrents \
    -H "Content-Type: application/json" \
    -d '{"action":"list"}'
```

### Файлы не создаются

1. Убедитесь, что в TorrServer есть активные торренты
2. Проверьте права на запись в директорию вывода
3. Проверьте логи скрипта на наличие ошибок

### Неправильные пути в .strm файлах

Скрипт использует относительные пути (`play/{hash}/{id}`). Для медиа-серверов может потребоваться настройка базового URL TorrServer в конфигурации медиа-сервера.

## Лицензия

Скрипт распространяется под той же лицензией, что и TorrServer (GPL 3.0).

## Автор

Скрипт создан для автоматизации синхронизации торрентов TorrServer в структуру `.strm` файлов.
