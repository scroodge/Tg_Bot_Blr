#!/bin/bash

# Тестовый скрипт для проверки Gemini API через curl

echo "🤖 Тестирование Gemini API через curl"
echo "======================================"

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден"
    echo "💡 Создайте .env файл с GEMINI_API_KEY"
    exit 1
fi

# Загружаем API ключ из .env
API_KEY=$(grep "GEMINI_API_KEY=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'")

if [ -z "$API_KEY" ]; then
    echo "❌ GEMINI_API_KEY не найден в .env файле"
    echo "💡 Добавьте GEMINI_API_KEY=your_api_key в .env файл"
    exit 1
fi

echo "🔑 API ключ найден: ${API_KEY:0:10}..."

# Тестируем разные модели
MODELS=("gemini-2.0-flash" "gemini-1.5-flash" "gemini-1.5-pro" "gemini-pro")

for MODEL in "${MODELS[@]}"; do
    echo ""
    echo "🔍 Тестирую модель: $MODEL"
    echo "------------------------"
    
    # Тестовый запрос
    curl -s "https://generativelanguage.googleapis.com/v1beta/models/$MODEL:generateContent" \
        -H 'Content-Type: application/json' \
        -H "X-goog-api-key: $API_KEY" \
        -X POST \
        -d '{
            "contents": [
                {
                    "parts": [
                        {
                            "text": "Переведи слово \"привет\" на белорусский язык. Отвечай только переводом."
                        }
                    ]
                }
            ]
        }' | jq -r '.candidates[0].content.parts[0].text' 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo "✅ Модель $MODEL работает!"
        break
    else
        echo "❌ Модель $MODEL недоступна"
    fi
done

echo ""
echo "✅ Тестирование завершено"
