#!/usr/bin/env python3
"""
Версия бота с поддержкой прокси для обхода блокировок
"""

import os
import sys
import threading
import requests
import json
from typing import Optional

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, InlineQueryHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from uuid import uuid4
import httpx

ENV_PATH = ".env"

def load_or_ask_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token.strip()

    # Попытка прочитать из .env
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                    if token:
                        os.environ["TELEGRAM_BOT_TOKEN"] = token
                        return token

    # Если токена нет — запросим у пользователя 1 раз и сохраним
    print("Вставьте токен бота от @BotFather и нажмите Enter:")
    token = input().strip()
    if not token:
        print("Токен пуст. Выход.")
        sys.exit(1)

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(f"TELEGRAM_BOT_TOKEN={token}\n")
    os.environ["TELEGRAM_BOT_TOKEN"] = token
    return token

def get_proxy_config():
    """Получает настройки прокси из переменных окружения"""
    proxy_url = os.environ.get("PROXY_URL")
    if proxy_url:
        print(f"🔧 Используется прокси: {proxy_url}")
        return {
            "proxy_url": proxy_url,
            "proxy_auth": None
        }
    
    # Проверяем .env файл
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("PROXY_URL="):
                    proxy_url = line.split("=", 1)[1].strip()
                    if proxy_url:
                        print(f"🔧 Используется прокси из .env: {proxy_url}")
                        return {
                            "proxy_url": proxy_url,
                            "proxy_auth": None
                        }
    
    return None

# Локальный переводчик через Ollama
class OllamaTranslator:
    def __init__(self, model_name: str = "mistral:7b"):
        self.model_name = model_name
        self.base_url = "http://localhost:11434"
        self.test_connection()
    
    def test_connection(self):
        """Проверяет подключение к Ollama"""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                print(f"✅ Подключение к Ollama успешно. Доступные модели: {model_names}")
                
                # Проверяем, доступна ли текущая модель
                if self.model_name not in model_names:
                    print(f"⚠️ Модель {self.model_name} недоступна. Доступные: {model_names}")
                    if model_names:
                        self.model_name = model_names[0]
                        print(f"Автоматически выбрана модель: {self.model_name}")
            else:
                print(f"⚠️ Ollama ответил с кодом {response.status_code}")
        except requests.exceptions.ConnectionError:
            print("❌ Не удается подключиться к Ollama. Убедитесь, что Ollama запущена на localhost:11434")
            print("💡 Запустите: ollama serve")
        except Exception as e:
            print(f"❌ Ошибка подключения к Ollama: {e}")
    
    def change_model(self, new_model: str):
        """Смена модели"""
        self.model_name = new_model
        print(f"Модель изменена на: {new_model}")

    def translate_ru_to_be(self, text: str, max_len: int = 512) -> str:
        text = text.strip()
        if not text:
            return ""
        
        try:
            # Формируем промпт для Mistral
            prompt = f"""Переведи следующий текст с русского на белорусский язык:

Русский: {text}
Белорусский:"""
            
            # Отправляем запрос к Ollama
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.8,
                        "max_tokens": max_len
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                translation = result.get('response', '').strip()
                
                # Очистка результата
                if translation.startswith("Переведи следующий текст с русского на белорусский язык:"):
                    translation = translation[67:].strip()
                if translation.startswith("Русский:"):
                    translation = translation[8:].strip()
                if translation.startswith("Белорусский:"):
                    translation = translation[12:].strip()
                if translation.startswith(":"):
                    translation = translation[1:].strip()
                
                return translation if translation else "Пераклад не атрымаўся"
            else:
                print(f"Ошибка Ollama API: {response.status_code} - {response.text}")
                return f"Памылка API: {response.status_code}"
                
        except requests.exceptions.Timeout:
            return "Памылка: пераўзыход часу чакання (60 сек)"
        except requests.exceptions.ConnectionError:
            return "Памылка: няма злучэння з Ollama"
        except Exception as e:
            print(f"Ошибка перевода: {e}")
            return f"Памылка перакладу: {e}"

# Fallback переводчик
class FallbackTranslator:
    def __init__(self):
        self.translations = {
            "привет": "прывітанне",
            "здравствуйте": "дабрыдзень",
            "спасибо": "дзякуй",
            "пожалуйста": "калі ласка",
            "да": "так",
            "нет": "не",
            "хорошо": "добра",
            "плохо": "дрэнна",
            "как дела": "як справы",
            "до свидания": "да пабачэння"
        }
    
    def translate_ru_to_be(self, text: str, max_len: int = 512) -> str:
        text = text.strip().lower()
        if not text:
            return ""
        
        if text in self.translations:
            return self.translations[text]
        
        for ru, be in self.translations.items():
            if ru in text:
                return f"Частковы пераклад: {be} (для '{ru}')"
        
        return "Пераклад не знойдзены ў базе. Паспрабуйце іншы тэкст."

translator: Optional[OllamaTranslator] = None
fallback_translator: Optional[FallbackTranslator] = None
translator_lock = threading.Lock()

async def ensure_translator():
    global translator, fallback_translator
    
    if translator is None:
        with translator_lock:
            if translator is None:
                try:
                    translator = OllamaTranslator()
                    fallback_translator = FallbackTranslator()
                except Exception as e:
                    print(f"Не удалось инициализировать Ollama: {e}")
                    translator = None
                    fallback_translator = FallbackTranslator()
    
    return translator, fallback_translator

# Команды (упрощенные версии)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "Прывітанне! Я перакладаю з рускай на беларускую 🪄\n\n"
        "• Напішыце мне тэкст — я адкажу перакладам.\n"
        "• У любым чаце ўвядзіце: @"
        f"{(await context.bot.get_me()).username} ваш рускі тэкст — і ўстаўце вынік.\n\n"
        "Каманды:\n"
        "/start - пачатак\n"
        "/help - дапамога\n"
        "/status - статус Ollama"
    )
    await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Проста дашліце рускі тэкст — я перакладу на беларускую.\n"
        "Інлайн: @ІмяБота ваш рускі тэкст.\n\n"
        "Каманды:\n"
        "/status - статус Ollama"
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=10)
        if response.status_code == 200:
            models = response.json().get('models', [])
            if models:
                model_list = "\n".join([f"• {m['name']}" for m in models])
                msg = f"✅ Ollama працуе\n\nДоступныя мадэлі:\n{model_list}"
            else:
                msg = "✅ Ollama працуе, але мадэлі не знойдзены"
        else:
            msg = f"⚠️ Ollama адказаў з кодам {response.status_code}"
    except requests.exceptions.ConnectionError:
        msg = "❌ Не ўдаецца злучыцца з Ollama\n💡 Запусціце: ollama serve"
    except Exception as e:
        msg = f"❌ Памылка: {e}"
    
    await update.message.reply_text(msg)

# Перевод обычных сообщений
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    ollama_tr, fallback_tr = await ensure_translator()
    
    wait_message = await update.message.reply_text("⏳ Ожидайте перевод...")
    
    try:
        if ollama_tr:
            be = ollama_tr.translate_ru_to_be(text)
            if be and not be.startswith("Памылка"):
                await wait_message.delete()
                await update.message.reply_text(be)
                return
        
        be = fallback_tr.translate_ru_to_be(text)
        if not be or be.startswith("Пераклад не знойдзены"):
            be = "Пераклад не атрымаўся. Паспрабуйце іншы тэкст."
        
        await wait_message.delete()
        await update.message.reply_text(be)
        
    except Exception as e:
        await wait_message.delete()
        await update.message.reply_text(f"Памылка перакладу: {e}")

# Инлайн-режим
async def on_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = (update.inline_query.query or "").strip()
    if not query:
        results = [
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Увядзіце рускі тэкст",
                input_message_content=InputTextMessageContent("Увядзіце рускі тэкст для перакладу."),
                description="Я перакладу на беларускую"
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    ollama_tr, fallback_tr = await ensure_translator()
    
    try:
        if ollama_tr:
            be = ollama_tr.translate_ru_to_be(query)
            if be and not be.startswith("Памылка"):
                results = [
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title="Пераклад на беларускую",
                        input_message_content=InputTextMessageContent(be),
                        description=be[:120]
                    )
                ]
                await update.inline_query.answer(results, cache_time=0, is_personal=True)
                return
        
        be = fallback_tr.translate_ru_to_be(query)
        if not be or be.startswith("Пераклад не знойдзены"):
            be = "Пераклад не атрымаўся"
        
        results = [
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Пераклад на беларускую (Fallback)",
                input_message_content=InputTextMessageContent(be),
                description=be[:120]
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        
    except Exception as e:
        results = [
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Памылка перакладу",
                input_message_content=InputTextMessageContent(f"Памылка: {e}"),
                description="Праверце тэкст і паспрабуйце зноў"
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)

def main():
    token = load_or_ask_token()
    
    # Настройка прокси
    proxy_config = get_proxy_config()
    
    if proxy_config:
        # Создаем HTTPXRequest с прокси
        request = HTTPXRequest(
            proxy_url=proxy_config["proxy_url"],
            proxy_auth=proxy_config["proxy_auth"]
        )
        app = Application.builder().token(token).request(request).build()
        print("🔧 Бот запущен с прокси")
    else:
        app = Application.builder().token(token).build()
        print("🌐 Бот запущен без прокси")
    
    # Обработчик ошибок
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        print(f"Ошибка при обработке обновления: {context.error}")
        
        if "NetworkError" in str(context.error) or "httpx.ReadError" in str(context.error):
            print("Обнаружена сетевая ошибка. Проверьте подключение или настройте прокси.")

    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(InlineQueryHandler(on_inline_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    print("Бот запущен. Наберите Ctrl+C для остановки.")
    print("Убедитесь, что Ollama запущена: ollama serve")
    
    if not proxy_config:
        print("\n💡 Если Telegram заблокирован, добавьте в .env файл:")
        print("PROXY_URL=http://your-proxy:port")
        print("или")
        print("PROXY_URL=socks5://your-proxy:port")
    
    try:
        app.run_polling(
            close_loop=False,
            drop_pending_updates=True,
            allowed_updates=["message", "inline_query"]
        )
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        print("Попробуйте:")
        print("1. Проверить интернет-соединение")
        print("2. Настроить прокси")
        print("3. Перезапустить бота")

if __name__ == "__main__":
    main()
