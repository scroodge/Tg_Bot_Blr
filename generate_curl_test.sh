#!/bin/bash

# Генерирует curl команды для тестирования с реальным API ключом

echo "🔧 Генератор curl команд для тестирования Gemini API"
echo "=================================================="

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
echo ""

# Генерируем curl команды для разных моделей
MODELS=("gemini-2.0-flash" "gemini-1.5-flash" "gemini-1.5-pro" "gemini-pro")

for MODEL in "${MODELS[@]}"; do
    echo "📋 Команда для тестирования $MODEL:"
    echo "----------------------------------------"
    echo "curl \"https://generativelanguage.googleapis.com/v1beta/models/$MODEL:generateContent\" \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -H 'X-goog-api-key: $API_KEY' \\"
    echo "  -X POST \\"
    echo "  -d '{"
    echo "    \"contents\": ["
    echo "      {"
    echo "        \"parts\": ["
    echo "          {"
    echo "            \"text\": \"Переведи слово \\\"привет\\\" на белорусский язык. Отвечай только переводом.\""
    echo "          }"
    echo "        ]"
    echo "      }"
    echo "    ]"
    echo "  }'"
    echo ""
    echo "💡 Скопируйте и выполните эту команду для тестирования $MODEL"
    echo ""
done

echo "✅ Генерация команд завершена"
echo ""
echo "🚀 Для быстрого тестирования запустите:"
echo "python3 test_direct_api.py"
