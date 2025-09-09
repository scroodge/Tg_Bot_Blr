
"""
Telegram бот для перевода с русского на белорусский через Google Translate API
Совместим с python-telegram-bot==13.15
"""

import os
import sys
import threading
import time
import re
import sqlite3
import argparse
from datetime import datetime
from typing import Optional, Dict, List

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Updater, CommandHandler, MessageHandler, InlineQueryHandler, Filters, CallbackContext
from uuid import uuid4

# Google Translate API
try:
    from googletrans import Translator
    GOOGLE_LIBRARY_AVAILABLE = True
except ImportError:
    GOOGLE_LIBRARY_AVAILABLE = False
    print("❌ googletrans не установлен. Установите: pip install googletrans==4.0.0rc1")

# Gemini API
try:
    import google.generativeai as genai
    GEMINI_API_AVAILABLE = True
except ImportError:
    GEMINI_API_AVAILABLE = False
    print("❌ google-generativeai не установлен. Установите: pip install google-generativeai")

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

def load_gemini_api_key() -> Optional[str]:
    """Загружает Gemini API ключ из .env файла"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return api_key.strip()

    # Попытка прочитать из .env
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    if api_key:
                        os.environ["GEMINI_API_KEY"] = api_key
                        return api_key
    
    return None

def load_admins_from_env() -> List[int]:
    """Загружает список админов из .env файла"""
    admins = []
    
    # Сначала проверяем переменную окружения
    env_admins = os.environ.get("ADMIN_USER_IDS")
    if env_admins:
        try:
            admins = [int(admin_id.strip()) for admin_id in env_admins.split(",") if admin_id.strip()]
            print(f"📋 Загружены админы из переменной окружения: {admins}")
            return admins
        except ValueError as e:
            print(f"❌ Ошибка парсинга ADMIN_USER_IDS: {e}")
    
    # Затем проверяем .env файл
    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("ADMIN_USER_IDS="):
                        admin_ids_str = line.split("=", 1)[1].strip()
                        if admin_ids_str:
                            admins = [int(admin_id.strip()) for admin_id in admin_ids_str.split(",") if admin_id.strip()]
                            print(f"📋 Загружены админы из .env: {admins}")
                            return admins
        except ValueError as e:
            print(f"❌ Ошибка парсинга ADMIN_USER_IDS в .env: {e}")
        except Exception as e:
            print(f"❌ Ошибка чтения .env: {e}")
    
    print("📋 Админы не настроены. Добавьте ADMIN_USER_IDS в .env файл")
    return admins

# Переводчик через Google Translate Library (googletrans)
class GoogleLibraryTranslator:
    def __init__(self):
        if not GOOGLE_LIBRARY_AVAILABLE:
            raise ImportError("googletrans не установлен")
        
        self.translator = Translator()
        print("✅ Google Translate Library переводчик инициализирован")

    def translate_ru_to_be(self, text: str, max_len: int = 512) -> str:
        text = text.strip()
        if not text:
            return ""
        
        try:
            print(f"🔍 Перевожу через Google Library: '{text}'")
            
            # Google Translate Library
            result = self.translator.translate(text, src='ru', dest='be')
            
            if result and result.text:
                translation = result.text.strip()
                print(f"✅ Google Library перевод: '{text}' → '{translation}'")
                return translation
            else:
                print(f"❌ Google Library не вернул перевод для: '{text}'")
                return f"Пераклад не знойдзены для: {text}"
                
        except Exception as e:
            print(f"❌ Ошибка Google Library: {e}")
            return f"Памылка перакладу: {e}"

# Переводчик через Gemini API
class GeminiAPITranslator:
    def __init__(self, api_key: str):
        if not GEMINI_API_AVAILABLE:
            raise ImportError("google-generativeai не установлен")
        
        # Настраиваем Gemini API
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        print("✅ Gemini API переводчик инициализирован")

    def translate_ru_to_be(self, text: str, max_len: int = 512) -> str:
        text = text.strip()
        if not text:
            return ""
        
        try:
            print(f"🔍 Перевожу через Gemini API: '{text}'")
            
            # Формируем промпт для перевода
            prompt = f"""Переведи следующий текст с русского на белорусский язык. Отвечай только переводом, без дополнительных объяснений.

Русский текст: {text}

Белорусский перевод:"""
            
            # Отправляем запрос к Gemini
            response = self.model.generate_content(prompt)
            
            if response and response.text:
                translation = response.text.strip()
                print(f"✅ Gemini API перевод: '{text}' → '{translation}'")
                return translation
            else:
                print(f"❌ Gemini API не вернул перевод для: '{text}'")
                return f"Пераклад не знойдзены для: {text}"
                
        except Exception as e:
            print(f"❌ Ошибка Gemini API: {e}")
            return f"Памылка перакладу: {e}"

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
            "утро": "раніца",
            "день": "дзень",
            "вечер": "вечар",
            "ночь": "ноч",
            "солнце": "сонца",
            "луна": "месяц",
            "звезда": "зорка",
            "небо": "неба",
            "земля": "зямля",
            "вода": "вада",
            "огонь": "агонь",
            "воздух": "паветра",
            "дерево": "дрэва",
            "цветок": "кветка",
            "трава": "трава",
            "лист": "ліст",
            "корень": "корань",
            "ветка": "галіна",
            "плод": "плод",
            "семя": "семя",
            "ствол": "ствол",
            "кора": "кара",
            "сок": "сок",
            "смола": "смола",
            "пыльца": "пылок",
            "нектар": "нектар",
            "мед": "мёд",
            "воск": "воск",
            "пчела": "пчала",
            "оса": "аса",
            "шмель": "шмель",
            "бабочка": "матылёк",
            "жук": "жук",
            "паук": "павук",
            "муравей": "мурашка",
            "кузнечик": "конік",
            "сверчок": "цвыркун",
            "цикада": "цыкада",
            "стрекоза": "стракоза",
            "комар": "камар",
            "муха": "муха",
            "дела": "справы",
            "работа": "праца",
            "дом": "дом",
            "семья": "сям'я",
            "друг": "сябар",
            "любовь": "каханне",
            "счастье": "шчасце",
            "грусть": "сум",
            "радость": "радасць",
            "смех": "смех",
            "плач": "плач",
            "сон": "сон",
            "мечта": "мара",
            "надежда": "надзея",
            "вера": "вера",
            "правда": "праўда",
            "ложь": "хлусня",
            "добро": "дабро",
            "зло": "зло",
            "красота": "прыгажосць",
            "уродство": "брыдота",
            "молодость": "маладосць",
            "старость": "старасць",
            "жизнь": "жыццё",
            "смерть": "смерць",
            "рождение": "нараджэнне",
            "взросление": "узросценне",
            "детство": "дзяцінства",
            "юность": "юнацтва",
            "зрелость": "сталасць"
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

# Глобальные переменные для переводчиков
translator = None
fallback_translator: Optional[FallbackTranslator] = None
translator_lock = threading.Lock()
use_gemini_api = False  # Флаг для выбора между API и библиотекой

# Таймеры для задержки перевода
translation_timers: Dict[int, threading.Timer] = {}
translation_lock = threading.Lock()

# Таймеры для инлайн-режима
inline_timers: Dict[str, threading.Timer] = {}
inline_lock = threading.Lock()

# Система базы данных SQLite
DB_FILE = "bot_stats.db"
db_lock = threading.Lock()

def init_database():
    """Инициализирует базу данных"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    total_requests INTEGER DEFAULT 0,
                    inline_requests INTEGER DEFAULT 0,
                    message_requests INTEGER DEFAULT 0,
                    mention_requests INTEGER DEFAULT 0,
                    first_seen TEXT,
                    last_activity TEXT
                )
            ''')
            
            # Таблица запросов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    request_type TEXT,
                    text TEXT,
                    text_length INTEGER,
                    timestamp TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица админов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    added_date TEXT
                )
            ''')
            
            conn.commit()
            print("✅ База данных инициализирована")
            
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")

def log_user_request(user_id: int, username: str, first_name: str, last_name: str, request_type: str, text: str = ""):
    """Логирует запрос пользователя в БД"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            # Проверяем, есть ли пользователь
            cursor.execute("SELECT total_requests FROM users WHERE user_id = ?", (user_id,))
            user_exists = cursor.fetchone()
            
            if user_exists:
                # Обновляем существующего пользователя
                cursor.execute('''
                    UPDATE users SET 
                        username = COALESCE(?, username),
                        first_name = COALESCE(?, first_name),
                        last_name = COALESCE(?, last_name),
                        total_requests = total_requests + 1,
                        last_activity = ?,
                        inline_requests = inline_requests + ?,
                        message_requests = message_requests + ?,
                        mention_requests = mention_requests + ?
                    WHERE user_id = ?
                ''', (
                    username, first_name, last_name, now,
                    1 if request_type == "inline" else 0,
                    1 if request_type == "message" else 0,
                    1 if request_type == "mention" else 0,
                    user_id
                ))
            else:
                # Создаем нового пользователя
                cursor.execute('''
                    INSERT INTO users (user_id, username, first_name, last_name, total_requests, 
                                    inline_requests, message_requests, mention_requests, first_seen, last_activity)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                ''', (
                    user_id, username, first_name, last_name,
                    1 if request_type == "inline" else 0,
                    1 if request_type == "message" else 0,
                    1 if request_type == "mention" else 0,
                    now, now
                ))
            
            # Добавляем запрос в историю
            cursor.execute('''
                INSERT INTO requests (user_id, request_type, text, text_length, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, request_type, text[:500], len(text), now))
            
            conn.commit()
            
            # Получаем общее количество запросов пользователя
            cursor.execute("SELECT total_requests FROM users WHERE user_id = ?", (user_id,))
            total_requests = cursor.fetchone()[0]
            
            print(f"📊 Пользователь {user_id} ({username or first_name}): {request_type} запрос #{total_requests}")
            
    except Exception as e:
        print(f"❌ Ошибка записи в БД: {e}")

def get_user_stats_summary():
    """Возвращает сводку статистики пользователей"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Общая статистика
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(total_requests) FROM users")
            total_requests = cursor.fetchone()[0] or 0
            
            # Топ-5 пользователей
            cursor.execute('''
                SELECT user_id, username, first_name, total_requests 
                FROM users 
                ORDER BY total_requests DESC 
                LIMIT 5
            ''')
            top_users = cursor.fetchall()
            
            summary = f"📊 **Статистика пользователей**\n\n"
            summary += f"👥 Всего пользователей: {total_users}\n"
            summary += f"📝 Всего запросов: {total_requests}\n\n"
            summary += f"🏆 **Топ-5 пользователей:**\n"
            
            for i, (user_id, username, first_name, requests) in enumerate(top_users, 1):
                name = username or first_name or f"ID:{user_id}"
                summary += f"{i}. {name}: {requests} запросов\n"
            
            return summary
            
    except Exception as e:
        return f"❌ Ошибка получения статистики: {e}"

def get_user_personal_stats(user_id: int):
    """Возвращает личную статистику пользователя"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT username, first_name, last_name, total_requests, 
                       inline_requests, message_requests, mention_requests, 
                       first_seen, last_activity
                FROM users WHERE user_id = ?
            ''', (user_id,))
            
            user_data = cursor.fetchone()
            if not user_data:
                return None
                
            username, first_name, last_name, total_requests, inline_requests, message_requests, mention_requests, first_seen, last_activity = user_data
            
            # Последние 5 запросов
            cursor.execute('''
                SELECT request_type, text, timestamp 
                FROM requests 
                WHERE user_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 5
            ''', (user_id,))
            recent_requests = cursor.fetchall()
            
            return {
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'total_requests': total_requests,
                'inline_requests': inline_requests,
                'message_requests': message_requests,
                'mention_requests': mention_requests,
                'first_seen': first_seen,
                'last_activity': last_activity,
                'recent_requests': recent_requests
            }
            
    except Exception as e:
        print(f"❌ Ошибка получения личной статистики: {e}")
        return None

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь админом"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None
    except Exception as e:
        print(f"❌ Ошибка проверки админа: {e}")
        return False

def add_admin(user_id: int, username: str = None):
    """Добавляет админа"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO admins (user_id, username, added_date)
                VALUES (?, ?, ?)
            ''', (user_id, username, datetime.now().isoformat()))
            conn.commit()
            return True
    except Exception as e:
        print(f"❌ Ошибка добавления админа: {e}")
        return False

def get_detailed_stats():
    """Возвращает детальную статистику для админов"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Общая статистика
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(total_requests) FROM users")
            total_requests = cursor.fetchone()[0] or 0
            
            # Статистика по типам запросов
            cursor.execute("SELECT SUM(inline_requests) FROM users")
            total_inline = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT SUM(message_requests) FROM users")
            total_messages = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT SUM(mention_requests) FROM users")
            total_mentions = cursor.fetchone()[0] or 0
            
            # Активность за последние 24 часа
            yesterday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            cursor.execute("SELECT COUNT(*) FROM requests WHERE timestamp > ?", (yesterday,))
            requests_today = cursor.fetchone()[0]
            
            # Топ-10 пользователей
            cursor.execute('''
                SELECT user_id, username, first_name, total_requests, last_activity
                FROM users 
                ORDER BY total_requests DESC 
                LIMIT 10
            ''')
            top_users = cursor.fetchall()
            
            return {
                'total_users': total_users,
                'total_requests': total_requests,
                'total_inline': total_inline,
                'total_messages': total_messages,
                'total_mentions': total_mentions,
                'requests_today': requests_today,
                'top_users': top_users
            }
            
    except Exception as e:
        print(f"❌ Ошибка получения детальной статистики: {e}")
        return None

def ensure_translator():
    global translator, fallback_translator, use_gemini_api
    
    if translator is None:
        with translator_lock:
            if translator is None:
                try:
                    if use_gemini_api:
                        # Используем Gemini API
                        api_key = load_gemini_api_key()
                        if not api_key:
                            print("❌ Gemini API ключ не найден в .env файле")
                            print("💡 Добавьте GEMINI_API_KEY=your_api_key в .env файл")
                            raise ValueError("Gemini API ключ не найден")
                        
                        if not GEMINI_API_AVAILABLE:
                            print("❌ Gemini API не установлен")
                            print("💡 Установите: pip install google-generativeai")
                            raise ImportError("google-generativeai не установлен")
                        
                        translator = GeminiAPITranslator(api_key)
                        print("🤖 Использую Gemini API")
                    else:
                        # Используем Google Translate Library
                        if not GOOGLE_LIBRARY_AVAILABLE:
                            print("❌ Google Translate Library не установлен")
                            print("💡 Установите: pip install googletrans==4.0.0rc1")
                            raise ImportError("googletrans не установлен")
                        
                        translator = GoogleLibraryTranslator()
                        print("📚 Использую Google Translate Library")
                    
                    fallback_translator = FallbackTranslator()
                except Exception as e:
                    print(f"Не удалось инициализировать переводчик: {e}")
                    print("Использую fallback переводчик...")
                    translator = None
                    fallback_translator = FallbackTranslator()
    
    return translator, fallback_translator

def delayed_translation(update: Update, context: CallbackContext, text: str, is_mention: bool = False, word_to_translate: str = ""):
    """Выполняет перевод с задержкой"""
    chat_id = update.message.chat_id
    
    # Очищаем таймер после выполнения
    with translation_lock:
        if chat_id in translation_timers:
            del translation_timers[chat_id]
    
    try:
        google_tr, fallback_tr = ensure_translator()
        
        if is_mention and word_to_translate:
            # Перевод одного слова при упоминании
            print(f"🔍 Обрабатываю упоминание: '{word_to_translate}'")
            
            if google_tr:
                be = google_tr.translate_ru_to_be(word_to_translate)
                if be and not be.startswith("Памылка") and not be.startswith("Пераклад не знойдзены"):
                    update.message.reply_text(f"'{word_to_translate}' → '{be}'")
                    return
            
            # Если Google не сработал, используем fallback
            be = fallback_tr.translate_ru_to_be(word_to_translate)
            if not be or be.startswith("Пераклад не знойдзены"):
                be = "пераклад не знойдзены"
            
            update.message.reply_text(f"'{word_to_translate}' → '{be}'")
        else:
            # Перевод всего текста
            print(f"🔍 Перевожу текст: '{text}'")
            
            if google_tr:
                be = google_tr.translate_ru_to_be(text)
                if be and not be.startswith("Памылка") and not be.startswith("Пераклад не знойдзены"):
                    update.message.reply_text(be)
                    return
            
            # Если Google не сработал, используем fallback
            be = fallback_tr.translate_ru_to_be(text)
            if not be or be.startswith("Пераклад не знойдзены"):
                be = "Пераклад не атрымаўся. Паспрабуйце іншы тэкст."
            
            update.message.reply_text(be)
            
    except Exception as e:
        print(f"❌ Ошибка при переводе: {e}")
        update.message.reply_text(f"Памылка перакладу: {e}")

def schedule_translation(update: Update, context: CallbackContext, text: str, is_mention: bool = False, word_to_translate: str = ""):
    """Планирует перевод с задержкой 2 секунды"""
    chat_id = update.message.chat_id
    
    with translation_lock:
        # Отменяем предыдущий таймер для этого чата
        if chat_id in translation_timers:
            print(f"🔄 Отменяю предыдущий таймер для чата {chat_id}")
            translation_timers[chat_id].cancel()
            del translation_timers[chat_id]
        
        # Создаем новый таймер
        timer = threading.Timer(2.0, delayed_translation, args=(update, context, text, is_mention, word_to_translate))
        translation_timers[chat_id] = timer
        timer.start()
        
        print(f"⏰ Запланирован перевод через 2 секунды для чата {chat_id}: '{text[:50]}...'")

def delayed_inline_translation(update: Update, context: CallbackContext, query: str):
    """Выполняет инлайн-перевод с задержкой"""
    user_id = update.inline_query.from_user.id
    
    # Очищаем таймер после выполнения
    with inline_lock:
        if user_id in inline_timers:
            del inline_timers[user_id]
    
    try:
        google_tr, fallback_tr = ensure_translator()
        
        if google_tr:
            # Пробуем Google Translate
            be = google_tr.translate_ru_to_be(query)
            if be and not be.startswith("Памылка") and not be.startswith("Пераклад не знойдзены"):
                results = [
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title="Пераклад на беларускую (Google)",
                        input_message_content=InputTextMessageContent(be),
                        description=be[:120]
                    )
                ]
                update.inline_query.answer(results, cache_time=0, is_personal=True)
                return
        
        # Если Google не сработал, используем fallback
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
        update.inline_query.answer(results, cache_time=0, is_personal=True)
        
    except Exception as e:
        print(f"❌ Ошибка в инлайн-переводе: {e}")
        results = [
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Памылка перакладу",
                input_message_content=InputTextMessageContent(f"Памылка: {e}"),
                description="Праверце тэкст і паспрабуйце зноў"
            )
        ]
        update.inline_query.answer(results, cache_time=0, is_personal=True)

def schedule_inline_translation(update: Update, context: CallbackContext, query: str):
    """Планирует инлайн-перевод с задержкой 1 секунда"""
    user_id = update.inline_query.from_user.id
    
    with inline_lock:
        # Отменяем предыдущий таймер для этого пользователя
        if user_id in inline_timers:
            print(f"🔄 Отменяю предыдущий таймер для пользователя {user_id}")
            inline_timers[user_id].cancel()
            del inline_timers[user_id]
        
        # Создаем новый таймер
        timer = threading.Timer(1.0, delayed_inline_translation, args=(update, context, query))
        inline_timers[user_id] = timer
        timer.start()
        
        print(f"⏰ Запланирован инлайн-перевод через 1 секунду для пользователя {user_id}: '{query}'")

# Команды
def start(update: Update, context: CallbackContext):
    bot_username = context.bot.username
    msg = (
        "Прывітанне! Я перакладаю з рускай на беларускую праз Google Translate 🌐\n\n"
        "📝 Спосабы выкарыстання:\n"
        "• Напішыце мне тэкст — я адкажу перакладам праз 2 секунды.\n"
        "• У любым чаце ўвядзіце: @"
        f"{bot_username} ваш рускі тэкст — і ўстаўце вынік.\n"
        f"• Для перакладу аднаго слова: Добрае @{bot_username} утро\n\n"
        "⏰ Пераклад адбываецца праз 2 секунды пасля апошняга ўводу.\n"
        "Крыніца: Google Translate API.\n"
        "У выпадку памылкі выкарыстоўваецца fallback перакладчык.\n\n"
        "Каманды:\n"
        "/start - пачатак\n"
        "/help - дапамога\n"
        "/status - статус перакладчыка\n"
        "/stats - статистика всех пользователей\n"
        "/mystats - ваша статистика\n\n"
        "Админ-команды:\n"
        "/adminstats - детальная статистика\n"
        "/addadmin <id> - добавить админа\n"
        "/listadmins - список админов\n"
        "/export - экспорт в CSV"
    )
    update.message.reply_text(msg)

def help_cmd(update: Update, context: CallbackContext):
    bot_username = context.bot.username
    update.message.reply_text(
        "📝 Спосабы выкарыстання:\n\n"
        "1️⃣ Пераклад поўнага тэксту:\n"
        "Напішыце мне рускі тэкст — я адкажу перакладам праз 2 секунды.\n\n"
        "2️⃣ Інлайн-рэжым:\n"
        f"@{bot_username} ваш рускі тэкст\n\n"
        f"3️⃣ Пераклад аднаго слова:\n"
        f"Добрае @{bot_username} утро\n"
        f"Спасибо @{bot_username} большое\n\n"
        "⏰ Пераклад адбываецца праз 2 секунды пасля апошняга ўводу.\n"
        "Бот выкарыстоўвае Google Translate API для перакладу.\n"
        "Каманды:\n"
        "/status - статус перакладчыка\n"
        "/stats - статистика всех пользователей\n"
        "/mystats - ваша статистика\n\n"
        "Админ-команды:\n"
        "/adminstats - детальная статистика\n"
        "/addadmin <id> - добавить админа\n"
        "/listadmins - список админов\n"
        "/export - экспорт в CSV"
    )

def status_cmd(update: Update, context: CallbackContext):
    """Проверяет статус переводчика"""
    global translator, use_gemini_api
    
    if translator:
        if use_gemini_api:
            msg = "✅ Gemini API перакладчык працуе\n\n"
            msg += "🤖 Крыніца: Google Gemini API\n"
            msg += "⚡ Хуткасць: онлайн пераклад\n"
            msg += "🎯 Точнасць: высокая\n"
            msg += "💰 Кошт: платны API (але танней за Google Translate)"
        else:
            msg = "✅ Google Translate Library перакладчык працуе\n\n"
            msg += "📚 Крыніца: Google Translate Library (googletrans)\n"
            msg += "⚡ Хуткасць: онлайн пераклад\n"
            msg += "🎯 Точнасць: высокая\n"
            msg += "💰 Кошт: бясплатны"
    else:
        msg = "❌ Google Translate перакладчык не даступны\n💡 Выкарыстоўваецца fallback перакладчык"
    
    update.message.reply_text(msg)

def stats_cmd(update: Update, context: CallbackContext):
    """Показывает статистику пользователей"""
    summary = get_user_stats_summary()
    update.message.reply_text(summary, parse_mode='Markdown')

def my_stats_cmd(update: Update, context: CallbackContext):
    """Показывает статистику текущего пользователя"""
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    first_name = update.message.from_user.first_name
    last_name = update.message.from_user.last_name
    
    stats = get_user_personal_stats(user_id)
    if not stats:
        update.message.reply_text("📊 У вас пока нет статистики. Сделайте несколько запросов!")
        return
    
    msg = f"📊 **Ваша статистика**\n\n"
    msg += f"👤 Имя: {first_name} {last_name or ''}\n"
    msg += f"🆔 Username: @{username or 'не указан'}\n"
    msg += f"📝 Всего запросов: {stats['total_requests']}\n"
    msg += f"  • Обычные сообщения: {stats['message_requests']}\n"
    msg += f"  • Инлайн-запросы: {stats['inline_requests']}\n"
    msg += f"  • Упоминания: {stats['mention_requests']}\n"
    msg += f"🕐 Первое использование: {stats['first_seen'][:19]}\n"
    msg += f"🕐 Последняя активность: {stats['last_activity'][:19]}\n"
    
    # Последние 5 запросов
    if stats['recent_requests']:
        msg += f"\n📋 **Последние запросы:**\n"
        for req_type, req_text, req_time in stats['recent_requests']:
            msg += f"• {req_type}: {req_text[:30]}{'...' if len(req_text) > 30 else ''}\n"
    
    update.message.reply_text(msg, parse_mode='Markdown')

def admin_stats_cmd(update: Update, context: CallbackContext):
    """Детальная статистика для админов"""
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        update.message.reply_text("❌ У вас нет прав администратора")
        return
    
    stats = get_detailed_stats()
    if not stats:
        update.message.reply_text("❌ Ошибка получения статистики")
        return
    
    msg = f"📊 **Детальная статистика (Админ)**\n\n"
    msg += f"👥 Всего пользователей: {stats['total_users']}\n"
    msg += f"📝 Всего запросов: {stats['total_requests']}\n"
    msg += f"📅 Запросов сегодня: {stats['requests_today']}\n\n"
    msg += f"📈 **По типам запросов:**\n"
    msg += f"• Обычные сообщения: {stats['total_messages']}\n"
    msg += f"• Инлайн-запросы: {stats['total_inline']}\n"
    msg += f"• Упоминания: {stats['total_mentions']}\n\n"
    msg += f"🏆 **Топ-10 пользователей:**\n"
    
    for i, (uid, username, first_name, requests, last_activity) in enumerate(stats['top_users'], 1):
        name = username or first_name or f"ID:{uid}"
        last_seen = last_activity[:16] if last_activity else "неизвестно"
        msg += f"{i}. {name}: {requests} запросов (последняя активность: {last_seen})\n"
    
    update.message.reply_text(msg, parse_mode='Markdown')

def add_admin_cmd(update: Update, context: CallbackContext):
    """Добавляет админа"""
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        update.message.reply_text("❌ У вас нет прав администратора")
        return
    
    if not context.args:
        update.message.reply_text("❌ Укажите ID пользователя: /addadmin <user_id>")
        return
    
    try:
        new_admin_id = int(context.args[0])
        username = update.message.from_user.username
        
        if add_admin(new_admin_id, username):
            update.message.reply_text(f"✅ Пользователь {new_admin_id} добавлен в админы")
        else:
            update.message.reply_text("❌ Ошибка добавления админа")
    except ValueError:
        update.message.reply_text("❌ Неверный формат ID пользователя")

def export_stats_cmd(update: Update, context: CallbackContext):
    """Экспортирует статистику в CSV"""
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        update.message.reply_text("❌ У вас нет прав администратора")
        return
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Экспорт пользователей
            cursor.execute('''
                SELECT user_id, username, first_name, last_name, total_requests, 
                       inline_requests, message_requests, mention_requests, 
                       first_seen, last_activity
                FROM users ORDER BY total_requests DESC
            ''')
            users_data = cursor.fetchall()
            
            csv_content = "user_id,username,first_name,last_name,total_requests,inline_requests,message_requests,mention_requests,first_seen,last_activity\n"
            for row in users_data:
                csv_content += ",".join(str(x) if x is not None else "" for x in row) + "\n"
            
            # Сохраняем в файл
            with open("users_export.csv", "w", encoding="utf-8") as f:
                f.write(csv_content)
            
            update.message.reply_text("✅ Статистика экспортирована в users_export.csv")
            
    except Exception as e:
        update.message.reply_text(f"❌ Ошибка экспорта: {e}")

def list_admins_cmd(update: Update, context: CallbackContext):
    """Показывает список админов"""
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        update.message.reply_text("❌ У вас нет прав администратора")
        return
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT user_id, username, added_date
                FROM admins ORDER BY added_date
            ''')
            admins_data = cursor.fetchall()
            
            if not admins_data:
                update.message.reply_text("📋 Список админов пуст")
                return
            
            msg = "📋 **Список администраторов:**\n\n"
            for i, (admin_id, username, added_date) in enumerate(admins_data, 1):
                added = added_date[:16] if added_date else "неизвестно"
                msg += f"{i}. ID: `{admin_id}`\n"
                msg += f"   Username: @{username or 'не указан'}\n"
                msg += f"   Добавлен: {added}\n\n"
            
            update.message.reply_text(msg, parse_mode='Markdown')
            
    except Exception as e:
        update.message.reply_text(f"❌ Ошибка получения списка админов: {e}")

# Перевод обычных сообщений
def on_text(update: Update, context: CallbackContext):
    text = update.message.text
    bot_username = context.bot.username
    
    # Логируем пользователя
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    first_name = update.message.from_user.first_name
    last_name = update.message.from_user.last_name
    
    print(f"📨 ПОЛУЧЕНО СООБЩЕНИЕ: '{text}'")
    
    # Проверяем, есть ли упоминание бота через entities (для групп)
    is_mentioned = False
    phrase_after_mention = ""
    
    if update.message.entities:
        for entity in update.message.entities:
            if entity.type == "mention":
                # Извлекаем текст упоминания
                mention_text = text[entity.offset:entity.offset + entity.length]
                print(f"🔍 Найдено упоминание: '{mention_text}'")
                
                if f"@{bot_username}" in mention_text.lower():
                    # Находим текст после упоминания
                    text_after_mention = text[entity.offset + entity.length:].strip()
                    if text_after_mention:
                        phrase_after_mention = text_after_mention
                        is_mentioned = True
                        print(f"🔍 Текст после упоминания: '{phrase_after_mention}'")
                        break
    
    # Если не нашли через entities, проверяем через регулярные выражения
    if not is_mentioned:
        # Проверяем, есть ли упоминание бота в тексте
        mention_pattern = f"@{bot_username}\\s+(.+)"
        mention_match = re.search(mention_pattern, text, re.IGNORECASE)
        
        # Также проверяем, есть ли упоминание без @ (для личных чатов)
        simple_mention_pattern = f"{bot_username}\\s+(.+)"
        simple_mention_match = re.search(simple_mention_pattern, text, re.IGNORECASE)
        
        if mention_match:
            phrase_after_mention = mention_match.group(1).strip()
            is_mentioned = True
        elif simple_mention_match:
            phrase_after_mention = simple_mention_match.group(1).strip()
            is_mentioned = True
    
    if is_mentioned:
        # Если есть упоминание, переводим только последнее слово из фразы
        words = phrase_after_mention.split()
        word_to_translate = words[-1] if words else phrase_after_mention
        
        print(f"🔍 Планирую перевод слова: '{word_to_translate}' через 2 секунды")
        
        # Логируем упоминание
        log_user_request(user_id, username, first_name, last_name, "mention", word_to_translate)
        
        # Планируем перевод с задержкой
        schedule_translation(update, context, text, is_mention=True, word_to_translate=word_to_translate)
    else:
        # Если нет упоминания, переводим весь текст с задержкой
        print(f"🔍 Планирую перевод текста: '{text}' через 2 секунды")
        
        # Логируем обычное сообщение
        log_user_request(user_id, username, first_name, last_name, "message", text)
        
        # Планируем перевод с задержкой
        schedule_translation(update, context, text, is_mention=False)

# Инлайн-режим
def on_inline_query(update: Update, context: CallbackContext):
    query = (update.inline_query.query or "").strip()
    print(f"🔍 ИНЛАЙН ЗАПРОС: '{query}'")
    
    # Логируем пользователя для инлайн-запросов
    user_id = update.inline_query.from_user.id
    username = update.inline_query.from_user.username
    first_name = update.inline_query.from_user.first_name
    last_name = update.inline_query.from_user.last_name
    
    if not query:
        results = [
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Увядзіце рускі тэкст",
                input_message_content=InputTextMessageContent("Увядзіце рускі тэкст для перакладу."),
                description="Я перакладу на беларускую праз Google Translate"
            )
        ]
        update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    # Логируем инлайн-запрос
    log_user_request(user_id, username, first_name, last_name, "inline", query)

    # Планируем инлайн-перевод с задержкой 1 секунда
    print(f"🔍 Планирую инлайн-перевод: '{query}' через 1 секунду")
    schedule_inline_translation(update, context, query)

def error_handler(update: Update, context: CallbackContext):
    """Обработчик ошибок"""
    print(f"Ошибка при обработке обновления: {context.error}")

def main():
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Telegram бот для перевода с русского на белорусский')
    parser.add_argument('-google', '--google-api', action='store_true', 
                       help='Использовать Gemini API вместо библиотеки googletrans')
    args = parser.parse_args()
    
    # Устанавливаем глобальный флаг
    global use_gemini_api
    use_gemini_api = args.google_api
    
    # Проверяем доступность нужных библиотек
    if use_gemini_api:
        if not GEMINI_API_AVAILABLE:
            print("❌ Gemini API не доступен. Установите: pip install google-generativeai")
            sys.exit(1)
    else:
        if not GOOGLE_LIBRARY_AVAILABLE:
            print("❌ Google Translate Library не доступен. Установите: pip install googletrans==4.0.0rc1")
            sys.exit(1)
    
    token = load_or_ask_token()
    
    # Создаем Updater для старой версии API
    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher
    
    print(f"🔧 Токен: {token[:10]}...")
    print(f"🔧 Updater создан")
    
    # Инициализируем базу данных
    init_database()
    
    # Загружаем админов из .env файла
    admin_ids = load_admins_from_env()
    for admin_id in admin_ids:
        add_admin(admin_id, f"admin_{admin_id}")
        print(f"✅ Добавлен админ: {admin_id}")
    
    # Добавляем обработчики
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_cmd))
    dispatcher.add_handler(CommandHandler("status", status_cmd))
    dispatcher.add_handler(CommandHandler("stats", stats_cmd))
    dispatcher.add_handler(CommandHandler("mystats", my_stats_cmd))
    dispatcher.add_handler(CommandHandler("adminstats", admin_stats_cmd))
    dispatcher.add_handler(CommandHandler("addadmin", add_admin_cmd))
    dispatcher.add_handler(CommandHandler("listadmins", list_admins_cmd))
    dispatcher.add_handler(CommandHandler("export", export_stats_cmd))
    dispatcher.add_handler(InlineQueryHandler(on_inline_query))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, on_text))
    
    # Добавляем обработчик ошибок
    dispatcher.add_error_handler(error_handler)

    # Показываем информацию о режиме работы
    if use_gemini_api:
        print("🤖 Бот перакладу праз Gemini API запущен. Наберите Ctrl+C для остановки.")
        print("💡 Выкарыстоўваю Gemini API для перакладу...")
    else:
        print("📚 Бот перакладу праз Google Translate Library запущен. Наберите Ctrl+C для остановки.")
        print("💡 Выкарыстоўваю Google Translate Library для перакладу...")
    
    # Запускаем бота
    try:
        updater.start_polling()
        updater.idle()
    except KeyboardInterrupt:
        print("\n🛑 Остановка бота...")
        save_user_stats()
        print("📊 Статистика сохранена")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        save_user_stats()

if __name__ == "__main__":
    main()
