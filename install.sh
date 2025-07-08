#!/bin/bash

# Скрипт автоматической установки Telegram-бота для жалоб на водителей
# Автор: Manus AI
# Версия: 1.0

set -e

echo "🤖 Установка Telegram-бота для жалоб на водителей"
echo "=================================================="

# Проверка операционной системы
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "❌ Этот скрипт предназначен только для Linux"
    exit 1
fi

# Проверка прав root
if [[ $EUID -eq 0 ]]; then
    echo "⚠️  Не запускайте скрипт от имени root"
    echo "Используйте обычного пользователя с sudo правами"
    exit 1
fi

# Функция для вывода сообщений
log() {
    echo "📝 $1"
}

error() {
    echo "❌ $1"
    exit 1
}

success() {
    echo "✅ $1"
}

# Проверка наличия sudo
if ! command -v sudo &> /dev/null; then
    error "sudo не установлен. Установите sudo и добавьте пользователя в группу sudo"
fi

# Обновление системы
log "Обновление системы..."
sudo apt update && sudo apt upgrade -y

# Установка Python и зависимостей
log "Установка Python и зависимостей..."
sudo apt install -y python3 python3-pip python3-venv git curl wget

# Проверка версии Python
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    error "Требуется Python $REQUIRED_VERSION или выше. Установлена версия: $PYTHON_VERSION"
fi

success "Python $PYTHON_VERSION установлен"

# Создание директории проекта
PROJECT_DIR="$HOME/telegram_bot"
log "Создание директории проекта: $PROJECT_DIR"

if [ -d "$PROJECT_DIR" ]; then
    read -p "⚠️  Директория $PROJECT_DIR уже существует. Перезаписать? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        error "Установка отменена"
    fi
    rm -rf "$PROJECT_DIR"
fi

mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Создание виртуального окружения
log "Создание виртуального окружения..."
python3 -m venv venv
source venv/bin/activate

# Проверка наличия файлов бота
if [ ! -f "main.py" ] || [ ! -f "text_processor.py" ] || [ ! -f "requirements.txt" ]; then
    error "Файлы бота не найдены в текущей директории. Убедитесь, что файлы main.py, text_processor.py и requirements.txt находятся в $PROJECT_DIR"
fi

# Установка зависимостей Python
log "Установка зависимостей Python..."
pip install --upgrade pip
pip install -r requirements.txt

success "Зависимости установлены"

# Настройка конфигурации
log "Настройка конфигурации..."

echo
echo "🔧 НАСТРОЙКА БОТА"
echo "=================="

# Запрос токена бота
while true; do
    read -p "Введите токен бота (получите у @BotFather): " BOT_TOKEN
    if [[ $BOT_TOKEN =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]]; then
        break
    else
        echo "❌ Неверный формат токена. Попробуйте еще раз."
    fi
done

# Запрос ID канала
read -p "Введите ID канала (например: @mychannel или -1001234567890): " CHANNEL_ID

# Запрос username администратора
read -p "Введите username администратора (без @): " ADMIN_USERNAME

# Создание резервной копии оригинального файла
cp main.py main.py.backup

# Замена настроек в файле
sed -i "s/BOT_TOKEN = \".*\"/BOT_TOKEN = \"$BOT_TOKEN\"/" main.py
sed -i "s/CHANNEL_ID = \".*\"/CHANNEL_ID = \"$CHANNEL_ID\"/" main.py
sed -i "s/ADMIN_USERNAME = \".*\"/ADMIN_USERNAME = \"$ADMIN_USERNAME\"/" main.py

success "Конфигурация сохранена"

# Создание systemd сервиса
log "Создание systemd сервиса..."

SERVICE_FILE="/etc/systemd/system/telegram-bot.service"
USER=$(whoami)

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Telegram Bot for Driver Complaints
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Перезагрузка systemd и включение сервиса
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot

success "Systemd сервис создан"

# Тестовый запуск
log "Выполнение тестового запуска..."

echo "Тестируем подключение к Telegram API..."
timeout 10s python3 -c "
import asyncio
from aiogram import Bot

async def test_bot():
    bot = Bot(token='$BOT_TOKEN')
    try:
        me = await bot.get_me()
        print(f'✅ Бот подключен: @{me.username}')
        return True
    except Exception as e:
        print(f'❌ Ошибка подключения: {e}')
        return False
    finally:
        await bot.session.close()

result = asyncio.run(test_bot())
" || error "Не удалось подключиться к Telegram API. Проверьте токен."

success "Тестовое подключение успешно"

# Создание скриптов управления
log "Создание скриптов управления..."

# Скрипт запуска
cat > start_bot.sh << 'EOF'
#!/bin/bash
sudo systemctl start telegram-bot
echo "✅ Бот запущен"
sudo systemctl status telegram-bot --no-pager
EOF

# Скрипт остановки
cat > stop_bot.sh << 'EOF'
#!/bin/bash
sudo systemctl stop telegram-bot
echo "⏹️  Бот остановлен"
EOF

# Скрипт просмотра логов
cat > view_logs.sh << 'EOF'
#!/bin/bash
echo "📋 Логи бота (нажмите Ctrl+C для выхода):"
tail -f bot.log
EOF

# Скрипт статуса
cat > status.sh << 'EOF'
#!/bin/bash
echo "📊 Статус бота:"
sudo systemctl status telegram-bot --no-pager
echo
echo "📋 Последние 10 строк лога:"
tail -10 bot.log 2>/dev/null || echo "Лог-файл пока не создан"
EOF

chmod +x *.sh

success "Скрипты управления созданы"

# Финальные инструкции
echo
echo "🎉 УСТАНОВКА ЗАВЕРШЕНА!"
echo "======================="
echo
echo "📁 Директория проекта: $PROJECT_DIR"
echo "🤖 Токен бота: $BOT_TOKEN"
echo "📢 Канал: $CHANNEL_ID"
echo "👤 Администратор: @$ADMIN_USERNAME"
echo
echo "🚀 УПРАВЛЕНИЕ БОТОМ:"
echo "  Запуск:     ./start_bot.sh"
echo "  Остановка:  ./stop_bot.sh"
echo "  Статус:     ./status.sh"
echo "  Логи:       ./view_logs.sh"
echo
echo "📋 СИСТЕМНЫЕ КОМАНДЫ:"
echo "  sudo systemctl start telegram-bot    # Запуск"
echo "  sudo systemctl stop telegram-bot     # Остановка"
echo "  sudo systemctl restart telegram-bot  # Перезапуск"
echo "  sudo systemctl status telegram-bot   # Статус"
echo
echo "⚠️  ВАЖНО:"
echo "1. Убедитесь, что бот добавлен в канал как администратор"
echo "2. Дайте боту права на отправку сообщений и медиафайлов"
echo "3. Администратор должен начать диалог с ботом командой /start"
echo
echo "🔧 Для изменения настроек отредактируйте файл main.py"
echo "📖 Подробная документация в файле README.md"
echo

# Предложение запуска
read -p "🚀 Запустить бота сейчас? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    log "Запуск бота..."
    sudo systemctl start telegram-bot
    sleep 3
    
    if sudo systemctl is-active --quiet telegram-bot; then
        success "Бот успешно запущен!"
        echo "📊 Статус:"
        sudo systemctl status telegram-bot --no-pager
    else
        error "Не удалось запустить бота. Проверьте логи: sudo journalctl -u telegram-bot -f"
    fi
else
    echo "ℹ️  Для запуска бота используйте: ./start_bot.sh"
fi

echo
echo "✨ Установка завершена! Бот готов к работе."

