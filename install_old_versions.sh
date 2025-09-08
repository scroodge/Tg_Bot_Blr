#!/bin/bash

# Скрипт для установки старых совместимых версий

echo "🔧 Установка старых совместимых версий..."

# Удаляем текущие версии
echo "🗑️ Удаляю текущие версии..."
pip uninstall -y python-telegram-bot httpx googletrans

# Устанавливаем старые версии
echo "📦 Устанавливаю старые версии..."
pip install python-telegram-bot==13.15
pip install googletrans==4.0.0rc1

# Проверяем установку
echo "🔍 Проверяю установку..."
python3 -c "import telegram; print('✅ python-telegram-bot:', telegram.__version__)"
python3 -c "from googletrans import Translator; print('✅ googletrans установлен')"

echo "✅ Установка завершена!"
echo "🚀 Для запуска бота: python3 bot_google_simple.py"
