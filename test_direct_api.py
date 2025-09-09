#!/usr/bin/env python3
"""
Прямое тестирование Gemini API через requests
"""

import os
import json
import requests
from typing import Optional

def load_gemini_api_key() -> Optional[str]:
    """Загружает Gemini API ключ из .env файла"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return api_key.strip()

    # Попытка прочитать из .env
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    if api_key:
                        return api_key
    return None

def test_gemini_model(api_key: str, model_name: str, text: str) -> bool:
    """Тестирует конкретную модель Gemini"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    
    headers = {
        'Content-Type': 'application/json',
        'X-goog-api-key': api_key
    }
    
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": text
                    }
                ]
            }
        ]
    }
    
    try:
        print(f"🔍 Тестирую {model_name}...")
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                content = result['candidates'][0]['content']['parts'][0]['text']
                print(f"✅ {model_name}: {content}")
                return True
            else:
                print(f"❌ {model_name}: Нет содержимого в ответе")
                return False
        else:
            print(f"❌ {model_name}: HTTP {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ {model_name}: Ошибка - {e}")
        return False

def main():
    print("🤖 Прямое тестирование Gemini API")
    print("=" * 40)
    
    # Загружаем API ключ
    api_key = load_gemini_api_key()
    if not api_key:
        print("❌ GEMINI_API_KEY не найден в .env файле")
        print("💡 Добавьте GEMINI_API_KEY=your_api_key в .env файл")
        return
    
    print(f"🔑 API ключ найден: {api_key[:10]}...")
    
    # Список моделей для тестирования
    models = [
        "gemini-2.0-flash",
        "gemini-1.5-flash", 
        "gemini-1.5-pro",
        "gemini-pro"
    ]
    
    # Тестовый текст для перевода
    test_text = "Переведи слово \"привет\" на белорусский язык. Отвечай только переводом."
    
    print(f"\n📝 Тестовый текст: {test_text}")
    print("\n" + "=" * 40)
    
    # Тестируем каждую модель
    working_model = None
    for model in models:
        if test_gemini_model(api_key, model, test_text):
            working_model = model
            break
        print()
    
    if working_model:
        print(f"\n🎉 Рабочая модель найдена: {working_model}")
        
        # Дополнительные тесты с рабочей моделью
        print(f"\n🔄 Дополнительные тесты с {working_model}:")
        test_texts = [
            "Как дела?",
            "Спасибо большое",
            "Доброе утро",
            "До свидания"
        ]
        
        for text in test_texts:
            prompt = f"Переведи \"{text}\" на белорусский язык. Отвечай только переводом."
            test_gemini_model(api_key, working_model, prompt)
    else:
        print("\n❌ Ни одна модель не работает")
        print("💡 Проверьте API ключ и доступность сервиса")

if __name__ == "__main__":
    main()
