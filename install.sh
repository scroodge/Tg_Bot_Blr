#!/bin/bash

echo "🔧 Установка совместимых версий..."

# Удаляем конфликтующие пакеты
pip uninstall -y python-telegram-bot httpx googletrans httpcore h11

# Устанавливаем совместимые версии
pip install -r requirements.txt

echo "✅ Установка завершена!"
echo "🚀 Для запуска бота: python3 bot_google.py"
