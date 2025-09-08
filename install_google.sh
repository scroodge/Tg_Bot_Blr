#!/bin/bash

# Скрипт для установки Google Translate бота

echo "🌐 Установка Google Translate бота..."

# Установка googletrans
echo "📦 Устанавливаю googletrans..."
pip install googletrans==4.0.0rc1

# Проверка установки
echo "🔍 Проверяю установку..."
python3 -c "from googletrans import Translator; print('✅ googletrans установлен успешно')"

echo "✅ Установка завершена!"
echo "🚀 Для запуска бота: python3 bot_google.py"
