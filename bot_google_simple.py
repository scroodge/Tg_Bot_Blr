#!/usr/bin/env python3
"""
Упрощенная версия Telegram бота для перевода с русского на белорусский через Google Translate API
Использует старые версии библиотек для совместимости
"""

import os
import sys
import threading
import time
from typing import Optional

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, InlineQueryHandler, filters, ContextTypes
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

async def ensure_translator():
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

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    msg = (
        "Прывітанне! Я перакладаю з рускай на беларускую праз Google Translate 🌐\n\n"
        "📝 Спосабы выкарыстання:\n"
        "• Напішыце мне тэкст — я адкажу перакладам.\n"
        "• У любым чаце ўвядзіце: @"
        f"{bot_username} ваш рускі тэкст — і ўстаўце вынік.\n"
        f"• Для перакладу аднаго слова: Добрае @{bot_username} утро\n\n"
        "Крыніца: Google Translate API.\n"
        "У выпадку памылкі выкарыстоўваецца fallback перакладчык.\n\n"
        "Каманды:\n"
        "/start - пачатак\n"
        "/help - дапамога\n"
        "/status - статус перакладчыка"
    )
    await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    await update.message.reply_text(
        "📝 Спосабы выкарыстання:\n\n"
        "1️⃣ Пераклад поўнага тэксту:\n"
        "Напішыце мне рускі тэкст — я адкажу перакладам.\n\n"
        "2️⃣ Інлайн-рэжым:\n"
        f"@{bot_username} ваш рускі тэкст\n\n"
        f"3️⃣ Пераклад аднаго слова:\n"
        f"Добрае @{bot_username} утро\n"
        f"Спасибо @{bot_username} большое\n\n"
        "Бот выкарыстоўвае Google Translate API для перакладу.\n"
        "Каманды:\n"
        "/status - статус перакладчыка"
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет статус переводчика"""
    global translator
    
    if translator:
        msg = "✅ Google Translate перакладчык працуе\n\n"
        msg += "🌐 Крыніца: Google Translate API\n"
        msg += "⚡ Хуткасць: онлайн пераклад\n"
        msg += "🎯 Точнасць: высокая"
    else:
        msg = "❌ Google Translate перакладчык не даступны\n💡 Выкарыстоўваецца fallback перакладчык"
    
    await update.message.reply_text(msg)

# Перевод обычных сообщений
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    bot_username = (await context.bot.get_me()).username
    
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
        import re
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
        
        print(f"🔍 Обрабатываю упоминание: '{phrase_after_mention}' -> слово: '{word_to_translate}'")
        
        google_tr, fallback_tr = await ensure_translator()
        
        try:
            # Отправляем сообщение о том, что перевод в процессе
            wait_message = await update.message.reply_text(f"🌐 Шукаю пераклад слова '{word_to_translate}' у Google...")
            
            if google_tr:
                # Пробуем Google Translate
                be = google_tr.translate_ru_to_be(word_to_translate)
                if be and not be.startswith("Памылка") and not be.startswith("Пераклад не знойдзены"):
                    # Удаляем сообщение об ожидании и отправляем перевод
                    try:
                        await wait_message.delete()
                    except:
                        pass
                    await update.message.reply_text(f"'{word_to_translate}' → '{be}'")
                    return
            
            # Если Google не сработал, используем fallback
            be = fallback_tr.translate_ru_to_be(word_to_translate)
            if not be or be.startswith("Пераклад не знойдзены"):
                be = "пераклад не знойдзены"
            
            # Удаляем сообщение об ожидании и отправляем перевод
            try:
                await wait_message.delete()
            except:
                pass
            await update.message.reply_text(f"'{word_to_translate}' → '{be}'")
            
        except Exception as e:
            print(f"❌ Ошибка при обработке упоминания: {e}")
            try:
                await wait_message.delete()
            except:
                pass
            await update.message.reply_text(f"Памылка перакладу: {e}")
    else:
        # Если нет упоминания, переводим весь текст как обычно
        google_tr, fallback_tr = await ensure_translator()
        
        # Отправляем сообщение о том, что перевод в процессе
        wait_message = await update.message.reply_text("🌐 Шукаю пераклад у Google...")
        
        try:
            if google_tr:
                # Пробуем Google Translate
                be = google_tr.translate_ru_to_be(text)
                if be and not be.startswith("Памылка") and not be.startswith("Пераклад не знойдзены"):
                    # Удаляем сообщение об ожидании и отправляем перевод
                    try:
                        await wait_message.delete()
                    except:
                        pass
                    await update.message.reply_text(be)
                    return
            
            # Если Google не сработал, используем fallback
            be = fallback_tr.translate_ru_to_be(text)
            if not be or be.startswith("Пераклад не знойдзены"):
                be = "Пераклад не атрымаўся. Паспрабуйце іншы тэкст."
            
            # Удаляем сообщение об ожидании и отправляем перевод
            try:
                await wait_message.delete()
            except:
                pass
            await update.message.reply_text(be)
            
        except Exception as e:
            # Удаляем сообщение об ожидании и отправляем ошибку
            try:
                await wait_message.delete()
            except:
                pass
            await update.message.reply_text(f"Памылка перакладу: {e}")

# Инлайн-режим
async def on_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    google_tr, fallback_tr = await ensure_translator()
    
    try:
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
                await update.inline_query.answer(results, cache_time=0, is_personal=True)
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
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        
    except Exception as e:
        print(f"❌ Ошибка в инлайн-режиме: {e}")
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
    if not GOOGLE_AVAILABLE:
        print("❌ Google Translate не доступен. Установите: pip install googletrans==4.0.0rc1")
        sys.exit(1)
    
    token = load_or_ask_token()
    
    # Упрощенная настройка без HTTPXRequest
    try:
        app = Application.builder().token(token).build()
        print(f"🔧 Токен: {token[:10]}...")
        print(f"🔧 Приложение создано")
    except Exception as e:
        print(f"❌ Ошибка создания приложения: {e}")
        print("💡 Попробуйте установить старые версии:")
        print("pip install python-telegram-bot==13.15")
        print("pip install googletrans==4.0.0rc1")
        sys.exit(1)
    
    # Добавляем обработчик ошибок
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        print(f"Ошибка при обработке обновления: {context.error}")

    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(InlineQueryHandler(on_inline_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    print("🌐 Бот перакладу праз Google Translate запущен. Наберите Ctrl+C для остановки.")
    print("💡 Выкарыстоўваю Google Translate API для перакладу...")
    
    # Упрощенный запуск
    try:
        app.run_polling()
    except Exception as e:
        print(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    main()
