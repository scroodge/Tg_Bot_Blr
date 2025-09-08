#!/usr/bin/env python3
"""
Telegram бот для перевода с русского на белорусский через Google Translate API
Совместим с python-telegram-bot==13.15
"""

import os
import sys
import threading
import time
import re
import json
from datetime import datetime
from typing import Optional, Dict

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Updater, CommandHandler, MessageHandler, InlineQueryHandler, Filters, CallbackContext
from uuid import uuid4

# Google Translate API
try:
    from googletrans import Translator
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    print("❌ googletrans не установлен. Установите: pip install googletrans==4.0.0rc1")

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

# Переводчик через Google Translate API
class GoogleTranslator:
    def __init__(self):
        if not GOOGLE_AVAILABLE:
            raise ImportError("googletrans не установлен")
        
        self.translator = Translator()
        print("✅ Google Translate переводчик инициализирован")

    def translate_ru_to_be(self, text: str, max_len: int = 512) -> str:
        text = text.strip()
        if not text:
            return ""
        
        try:
            print(f"🔍 Перевожу через Google: '{text}'")
            
            # Google Translate API
            result = self.translator.translate(text, src='ru', dest='be')
            
            if result and result.text:
                translation = result.text.strip()
                print(f"✅ Google перевод: '{text}' → '{translation}'")
                return translation
            else:
                print(f"❌ Google не вернул перевод для: '{text}'")
                return f"Пераклад не знойдзены для: {text}"
                
        except Exception as e:
            print(f"❌ Ошибка Google Translate: {e}")
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

translator: Optional[GoogleTranslator] = None
fallback_translator: Optional[FallbackTranslator] = None
translator_lock = threading.Lock()

# Таймеры для задержки перевода
translation_timers: Dict[int, threading.Timer] = {}
translation_lock = threading.Lock()

# Таймеры для инлайн-режима
inline_timers: Dict[str, threading.Timer] = {}
inline_lock = threading.Lock()

# Система логирования пользователей
user_stats: Dict[int, Dict] = {}
stats_lock = threading.Lock()
STATS_FILE = "user_stats.json"

def load_user_stats():
    """Загружает статистику пользователей из файла"""
    global user_stats
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                user_stats = json.load(f)
            print(f"📊 Загружена статистика для {len(user_stats)} пользователей")
        else:
            user_stats = {}
            print("📊 Статистика пользователей инициализирована")
    except Exception as e:
        print(f"❌ Ошибка загрузки статистики: {e}")
        user_stats = {}

def save_user_stats():
    """Сохраняет статистику пользователей в файл"""
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Ошибка сохранения статистики: {e}")

def log_user_request(user_id: int, username: str, first_name: str, last_name: str, request_type: str, text: str = ""):
    """Логирует запрос пользователя"""
    with stats_lock:
        if user_id not in user_stats:
            user_stats[user_id] = {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "total_requests": 0,
                "inline_requests": 0,
                "message_requests": 0,
                "mention_requests": 0,
                "last_activity": "",
                "first_seen": datetime.now().isoformat(),
                "requests_history": []
            }
        
        # Обновляем информацию о пользователе
        user_stats[user_id]["username"] = username or user_stats[user_id]["username"]
        user_stats[user_id]["first_name"] = first_name or user_stats[user_id]["first_name"]
        user_stats[user_id]["last_name"] = last_name or user_stats[user_id]["last_name"]
        user_stats[user_id]["total_requests"] += 1
        user_stats[user_id]["last_activity"] = datetime.now().isoformat()
        
        # Увеличиваем счетчик по типу запроса
        if request_type == "inline":
            user_stats[user_id]["inline_requests"] += 1
        elif request_type == "message":
            user_stats[user_id]["message_requests"] += 1
        elif request_type == "mention":
            user_stats[user_id]["mention_requests"] += 1
        
        # Добавляем в историю (последние 50 запросов)
        request_record = {
            "timestamp": datetime.now().isoformat(),
            "type": request_type,
            "text": text[:100] if text else "",  # Ограничиваем длину
            "length": len(text) if text else 0
        }
        user_stats[user_id]["requests_history"].append(request_record)
        
        # Ограничиваем историю последними 50 запросами
        if len(user_stats[user_id]["requests_history"]) > 50:
            user_stats[user_id]["requests_history"] = user_stats[user_id]["requests_history"][-50:]
        
        # Сохраняем статистику каждые 10 запросов
        if user_stats[user_id]["total_requests"] % 10 == 0:
            save_user_stats()
        
        # Логируем в консоль
        print(f"📊 Пользователь {user_id} ({username or first_name}): {request_type} запрос #{user_stats[user_id]['total_requests']}")

def get_user_stats_summary():
    """Возвращает сводку статистики пользователей"""
    with stats_lock:
        if not user_stats:
            return "📊 Статистика пуста"
        
        total_users = len(user_stats)
        total_requests = sum(stats["total_requests"] for stats in user_stats.values())
        
        # Топ-5 пользователей по количеству запросов
        top_users = sorted(user_stats.items(), key=lambda x: x[1]["total_requests"], reverse=True)[:5]
        
        summary = f"📊 **Статистика пользователей**\n\n"
        summary += f"👥 Всего пользователей: {total_users}\n"
        summary += f"📝 Всего запросов: {total_requests}\n\n"
        summary += f"🏆 **Топ-5 пользователей:**\n"
        
        for i, (user_id, stats) in enumerate(top_users, 1):
            name = stats["username"] or stats["first_name"] or f"ID:{user_id}"
            summary += f"{i}. {name}: {stats['total_requests']} запросов\n"
        
        return summary

def ensure_translator():
    global translator, fallback_translator
    
    if translator is None:
        with translator_lock:
            if translator is None:
                try:
                    translator = GoogleTranslator()
                    fallback_translator = FallbackTranslator()
                except Exception as e:
                    print(f"Не удалось инициализировать Google Translate: {e}")
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
        "/mystats - ваша статистика"
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
        "/mystats - ваша статистика"
    )

def status_cmd(update: Update, context: CallbackContext):
    """Проверяет статус переводчика"""
    global translator
    
    if translator:
        msg = "✅ Google Translate перакладчык працуе\n\n"
        msg += "🌐 Крыніца: Google Translate API\n"
        msg += "⚡ Хуткасць: онлайн пераклад\n"
        msg += "🎯 Точнасць: высокая"
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
    
    with stats_lock:
        if user_id not in user_stats:
            update.message.reply_text("📊 У вас пока нет статистики. Сделайте несколько запросов!")
            return
        
        stats = user_stats[user_id]
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
        if stats['requests_history']:
            msg += f"\n📋 **Последние запросы:**\n"
            for req in stats['requests_history'][-5:]:
                msg += f"• {req['type']}: {req['text'][:30]}{'...' if len(req['text']) > 30 else ''}\n"
    
    update.message.reply_text(msg, parse_mode='Markdown')

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
    if not GOOGLE_AVAILABLE:
        print("❌ Google Translate не доступен. Установите: pip install googletrans==4.0.0rc1")
        sys.exit(1)
    
    token = load_or_ask_token()
    
    # Создаем Updater для старой версии API
    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher
    
    print(f"🔧 Токен: {token[:10]}...")
    print(f"🔧 Updater создан")
    
    # Загружаем статистику пользователей
    load_user_stats()
    
    # Добавляем обработчики
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_cmd))
    dispatcher.add_handler(CommandHandler("status", status_cmd))
    dispatcher.add_handler(CommandHandler("stats", stats_cmd))
    dispatcher.add_handler(CommandHandler("mystats", my_stats_cmd))
    dispatcher.add_handler(InlineQueryHandler(on_inline_query))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, on_text))
    
    # Добавляем обработчик ошибок
    dispatcher.add_error_handler(error_handler)

    print("🌐 Бот перакладу праз Google Translate запущен. Наберите Ctrl+C для остановки.")
    print("💡 Выкарыстоўваю Google Translate API для перакладу...")
    
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
