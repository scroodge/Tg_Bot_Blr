#!/bin/bash

# Скрипт для исправления зависимостей

echo "🔧 Исправление зависимостей..."

# Обновляем pip
echo "📦 Обновляю pip..."
pip install --upgrade pip

# Устанавливаем совместимые версии
echo "📦 Устанавливаю совместимые версии..."
pip install httpx==0.24.1
pip install python-telegram-bot==20.7
pip install googletrans==4.0.0rc1

# Проверяем установку
echo "🔍 Проверяю установку..."
python3 -c "import telegram; print('✅ python-telegram-bot:', telegram.__version__)"
python3 -c "import httpx; print('✅ httpx:', httpx.__version__)"
python3 -c "from googletrans import Translator; print('✅ googletrans установлен')"

echo "✅ Зависимости исправлены!"
echo "🚀 Теперь можно запустить: python3 bot_google.py"
