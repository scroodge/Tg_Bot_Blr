# Ручное тестирование Gemini API

## 1. Проверка API ключа

Сначала убедитесь, что у вас есть API ключ в .env файле:

```bash
grep GEMINI_API_KEY .env
```

Если ключа нет, добавьте его в .env:
```env
GEMINI_API_KEY=your_actual_api_key_here
```

## 2. Тестирование через curl

### Тест модели gemini-2.0-flash:

```bash
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent" \
  -H 'Content-Type: application/json' \
  -H 'X-goog-api-key: YOUR_ACTUAL_API_KEY' \
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
  }'
```

### Тест модели gemini-1.5-flash:

```bash
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent" \
  -H 'Content-Type: application/json' \
  -H 'X-goog-api-key: YOUR_ACTUAL_API_KEY' \
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
  }'
```

## 3. Тестирование через Python

```bash
python3 test_direct_api.py
```

## 4. Тестирование бота

```bash
# С Gemini API
python3 bot_google.py -google

# С Google Library (бесплатно)
python3 bot_google.py
```

## Ожидаемые результаты

### Успешный ответ:
```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": "прывітанне"
          }
        ]
      }
    }
  ]
}
```

### Ошибка модели:
```json
{
  "error": {
    "code": 404,
    "message": "models/gemini-pro is not found for API version v1beta"
  }
}
```

## Решение проблем

1. **404 ошибка** - модель недоступна, попробуйте другую
2. **403 ошибка** - неверный API ключ
3. **429 ошибка** - превышен лимит запросов
4. **400 ошибка** - неверный формат запроса
