#!/usr/bin/env python3
"""
Версия bot_skarnik.py с поддержкой прокси для обхода блокировок
"""

import os
import sys
import threading
import requests
import re
import time
from typing import Optional
from urllib.parse import quote

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, InlineQueryHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from uuid import uuid4

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

# Переводчик через онлайн-словарь Skarnik
class SkarnikTranslator:
    def __init__(self):
        self.base_url = "https://www.skarnik.by/search"
        self.session = requests.Session()
        # Устанавливаем заголовки для имитации браузера
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        print("✅ Skarnik переводчик инициализирован")

    def translate_ru_to_be(self, text: str, max_len: int = 512) -> str:
        text = text.strip()
        if not text:
            return ""
        
        # Retry логика для сетевых запросов
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                # Кодируем текст для URL
                encoded_text = quote(text)
                
                # Формируем URL для поиска
                search_url = f"{self.base_url}?term={encoded_text}&lang=rus"
                
                if attempt == 0:  # Логируем только первую попытку
                    print(f"🔍 Ищу перевод для: {text}")
                    print(f"📡 URL: {search_url}")
                
                # Отправляем запрос с увеличенным timeout
                response = self.session.get(
                    search_url, 
                    timeout=15,  # Увеличиваем timeout
                    allow_redirects=True
                )
                response.raise_for_status()
                
                # Парсим ответ
                translation = self._parse_skarnik_response(response.text, text)
                
                if translation:
                    return translation
                else:
                    return f"Пераклад не знойдзены для: {text}"
                    
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"⏰ Таймаут, повторная попытка {attempt + 2}/{max_retries}...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Экспоненциальная задержка
                    continue
                return "Памылка: пераўзыход часу чакання"
                
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    print(f"🌐 Ошибка подключения, повторная попытка {attempt + 2}/{max_retries}...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return "Памылка: няма злучэння з Skarnik"
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Too Many Requests
                    if attempt < max_retries - 1:
                        print(f"🚫 Слишком много запросов, ждем {retry_delay}с...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    return "Памылка: занадта шмат запытаў"
                else:
                    return f"Памылка HTTP: {e.response.status_code}"
                    
            except Exception as e:
                print(f"Ошибка перевода: {e}")
                return f"Памылка перакладу: {e}"
        
        return "Памылка: не ўдалося атрымаць пераклад"

    def _parse_skarnik_response(self, html_content: str, original_text: str) -> str:
        """Парсит HTML ответ от Skarnik и извлекает перевод"""
        try:
            # Ищем перевод в HTML
            # Основной перевод находится в элементе с id="trn"
            
            # Вариант 1: Ищем основной перевод в элементе trn
            trn_pattern = r'<p id="trn">(.*?)</p>'
            match = re.search(trn_pattern, html_content, re.DOTALL)
            if match:
                trn_content = match.group(1)
                # Извлекаем основной перевод (первое слово после "перевод на белорусский язык:")
                main_translation = re.search(r'<font size="\+2" color="831b03">([^<]+)</font>', trn_content)
                if main_translation:
                    return main_translation.group(1).strip()
                
                # Альтернативно: ищем первое белорусское слово
                belarusian_word = re.search(r'<font color="5f5f5f"><strong>[^<]+</strong> — ([^<]+)</font>', trn_content)
                if belarusian_word:
                    return belarusian_word.group(1).strip()
            
            # Вариант 2: Ищем перевод в заголовке h1
            h1_pattern = r'<h1><span id="src">[^<]+</span></h1>\s*<p>перевод на белорусский язык:</p>\s*<p id="trn">(.*?)</p>'
            match = re.search(h1_pattern, html_content, re.DOTALL)
            if match:
                trn_content = match.group(1)
                # Ищем основной перевод
                main_translation = re.search(r'<font size="\+2" color="831b03">([^<]+)</font>', trn_content)
                if main_translation:
                    return main_translation.group(1).strip()
            
            # Вариант 3: Ищем перевод в таблице результатов
            table_pattern = r'<td[^>]*>([^<]+)</td>'
            matches = re.findall(table_pattern, html_content)
            
            # Ищем белорусский перевод (обычно второй столбец)
            if len(matches) >= 2:
                for i in range(1, len(matches), 2):  # Пропускаем русский, берем белорусский
                    if matches[i].strip() and matches[i].strip() != original_text:
                        return matches[i].strip()
            
            # Вариант 4: Ищем текст в определенных div'ах
            div_pattern = r'<div[^>]*class="[^"]*translation[^"]*"[^>]*>([^<]+)</div>'
            match = re.search(div_pattern, html_content)
            if match:
                return match.group(1).strip()
            
            # Вариант 5: Ищем текст между определенными маркерами
            marker_pattern = r'Перевод[^:]*:\s*([^<\n]+)'
            match = re.search(marker_pattern, html_content)
            if match:
                return match.group(1).strip()
            
            # Если ничего не найдено, возвращаем None
            print(f"❌ Не удалось распарсить ответ для: {original_text}")
            print(f"📄 HTML фрагмент: {html_content[:1000]}...")
            return None
            
        except Exception as e:
            print(f"Ошибка парсинга HTML: {e}")
            return None

# Fallback переводчик с базовым словарем
class FallbackTranslator:
    def __init__(self):
        # Расширенный словарь для базовых переводов
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
            "до свидания": "да пабачэння",
            "как тебя зовут": "як цябе завуць",
            "меня зовут": "мяне завуць",
            "где ты живешь": "дзе ты жывеш",
            "сколько тебе лет": "колькі табе гадоў",
            "не надо": "не трэба",
            "в кровати": "у пасцелі",
            "так хорошо": "так добра",
            "моя хорошая": "мая дарагая",
            "люблю тебя": "кахаю цябе",
            "спокойной ночи": "спакойнай ночы",
            "как дела": "як справы",
            "что делаешь": "што робіш",
            "где ты": "дзе ты",
            "когда придешь": "калі прыйдзеш"
        }
    
    def translate_ru_to_be(self, text: str, max_len: int = 512) -> str:
        text = text.strip().lower()
        if not text:
            return ""
        
        # Ищем точные совпадения
        if text in self.translations:
            return self.translations[text]
        
        # Ищем частичные совпадения
        for ru, be in self.translations.items():
            if ru in text:
                return f"Частковы пераклад: {be} (для '{ru}')"
        
        return "Пераклад не знойдзены ў базе. Паспрабуйце іншы тэкст."

translator: Optional[SkarnikTranslator] = None
fallback_translator: Optional[FallbackTranslator] = None
translator_lock = threading.Lock()

async def ensure_translator():
    global translator, fallback_translator
    
    if translator is None:
        with translator_lock:
            if translator is None:
                try:
                    translator = SkarnikTranslator()
                    fallback_translator = FallbackTranslator()
                except Exception as e:
                    print(f"Не удалось инициализировать Skarnik переводчик: {e}")
                    print("Использую fallback переводчик...")
                    translator = None
                    fallback_translator = FallbackTranslator()
    
    return translator, fallback_translator

# Команды (упрощенные версии)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "Прывітанне! Я перакладаю з рускай на беларускую праз Skarnik 🎯\n\n"
        "• Напішыце мне тэкст — я адкажу перакладам.\n"
        "• У любым чаце ўвядзіце: @"
        f"{(await context.bot.get_me()).username} ваш рускі тэкст — і ўстаўце вынік.\n\n"
        "Крыніца: онлайн-слоўнік Skarnik (107,141 слова).\n"
        "У выпадку памылкі выкарыстоўваецца fallback перакладчык.\n\n"
        "Каманды:\n"
        "/start - пачатак\n"
        "/help - дапамога\n"
        "/status - статус перакладчыка"
    )
    await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Проста дашліце рускі тэкст — я перакладу на беларускую.\n"
        "Інлайн: @ІмяБота ваш рускі тэкст.\n\n"
        "Бот выкарыстоўвае онлайн-слоўнік Skarnik для перакладу.\n"
        "Каманды:\n"
        "/status - статус перакладчыка"
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет статус переводчика"""
    global translator
    
    if translator:
        msg = "✅ Skarnik перакладчык працуе\n\n"
        msg += "📚 База: 107,141 слова\n"
        msg += "🌐 Крыніца: https://www.skarnik.by/\n"
        msg += "⚡ Хуткасць: онлайн пераклад"
    else:
        msg = "❌ Skarnik перакладчык не даступны\n💡 Выкарыстоўваецца fallback перакладчык"
    
    await update.message.reply_text(msg)

# Перевод обычных сообщений
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    skarnik_tr, fallback_tr = await ensure_translator()
    
    # Отправляем сообщение о том, что перевод в процессе
    wait_message = await update.message.reply_text("🔍 Шукаю пераклад у Skarnik...")
    
    try:
        if skarnik_tr:
            # Пробуем Skarnik переводчик
            be = skarnik_tr.translate_ru_to_be(text)
            if be and not be.startswith("Памылка") and not be.startswith("Пераклад не знойдзены"):
                # Удаляем сообщение об ожидании и отправляем перевод
                await wait_message.delete()
                await update.message.reply_text(be)
                return
        
        # Если Skarnik не сработал, используем fallback
        be = fallback_tr.translate_ru_to_be(text)
        if not be or be.startswith("Пераклад не знойдзены"):
            be = "Пераклад не атрымаўся. Паспрабуйце іншы тэкст."
        
        # Удаляем сообщение об ожидании и отправляем перевод
        await wait_message.delete()
        await update.message.reply_text(be)
        
    except Exception as e:
        # Удаляем сообщение об ожидании и отправляем ошибку
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
                description="Я перакладу на беларускую праз Skarnik"
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    skarnik_tr, fallback_tr = await ensure_translator()
    
    try:
        if skarnik_tr:
            # Пробуем Skarnik переводчик
            be = skarnik_tr.translate_ru_to_be(query)
            if be and not be.startswith("Памылка") and not be.startswith("Пераклад не знойдзены"):
                results = [
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title="Пераклад на беларускую (Skarnik)",
                        input_message_content=InputTextMessageContent(be),
                        description=be[:120]
                    )
                ]
                await update.inline_query.answer(results, cache_time=0, is_personal=True)
                return
        
        # Если Skarnik не сработал, используем fallback
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

    print("🔍 Бот перакладу праз Skarnik запущен. Наберите Ctrl+C для остановки.")
    print("💡 Выкарыстоўваю онлайн-слоўнік Skarnik для перакладу...")
    
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
