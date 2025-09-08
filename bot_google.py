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
            translation_timers[chat_id].cancel()
        
        # Создаем новый таймер
        timer = threading.Timer(2.0, delayed_translation, args=(update, context, text, is_mention, word_to_translate))
        translation_timers[chat_id] = timer
        timer.start()
        
        print(f"⏰ Запланирован перевод через 2 секунды для чата {chat_id}")

def delayed_inline_translation(update: Update, context: CallbackContext, query: str):
    """Выполняет инлайн-перевод с задержкой"""
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
            inline_timers[user_id].cancel()
        
        # Создаем новый таймер
        timer = threading.Timer(1.0, delayed_inline_translation, args=(update, context, query))
        inline_timers[user_id] = timer
        timer.start()
        
        print(f"⏰ Запланирован инлайн-перевод через 1 секунду для пользователя {user_id}")

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
        "/status - статус перакладчыка"
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
        "/status - статус перакладчыка"
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

# Перевод обычных сообщений
def on_text(update: Update, context: CallbackContext):
    text = update.message.text
    bot_username = context.bot.username
    
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
        
        # Планируем перевод с задержкой
        schedule_translation(update, context, text, is_mention=True, word_to_translate=word_to_translate)
    else:
        # Если нет упоминания, переводим весь текст с задержкой
        print(f"🔍 Планирую перевод текста: '{text}' через 2 секунды")
        
        # Планируем перевод с задержкой
        schedule_translation(update, context, text, is_mention=False)

# Инлайн-режим
def on_inline_query(update: Update, context: CallbackContext):
    query = (update.inline_query.query or "").strip()
    print(f"🔍 ИНЛАЙН ЗАПРОС: '{query}'")
    
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
    
    # Добавляем обработчики
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_cmd))
    dispatcher.add_handler(CommandHandler("status", status_cmd))
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
    except Exception as e:
        print(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    main()
