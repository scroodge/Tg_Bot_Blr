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
        
        return "Пераклад не знойдзены ў базе. Паспрабуйте іншы тэкст."

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

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    msg = (
        "Прывітанне! Я перакладаю з рускай на беларускую праз Skarnik 🎯\n\n"
        "📝 Спосабы выкарыстання:\n"
        "• Напішыце мне тэкст — я адкажу перакладам.\n"
        "• У любым чаце ўвядзіце: @"
        f"{bot_username} ваш рускі тэкст — і ўстаўце вынік.\n"
        f"• Для перакладу аднаго слова: Добрае @{bot_username} утро\n\n"
        "Крыніца: онлайн-слоўнік Skarnik (107,141 слова).\n"
        "У выпадку памылкі выкарыстоўваецца fallback перакладчык.\n\n"
        "Каманды:\n"
        "/start - пачатак\n"
        "/help - дапамога\n"
        "/status - статус перакладчыка\n"
        "/test - тэст перакладу"
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
        "Бот выкарыстоўвае онлайн-слоўнік Skarnik для перакладу.\n"
        "Каманды:\n"
        "/status - статус перакладчыка\n"
        "/test - тэст перакладу"
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

async def test_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестирование качества перевода"""
    if not context.args:
        await update.message.reply_text(
            "Выкарыстоўвайце: /test <рускі тэкст>\n\n"
            "Прыклад: /test как дела моя хорошая"
        )
        return
    
    test_text = " ".join(context.args)
    skarnik_tr, fallback_tr = await ensure_translator()
    
    if skarnik_tr:
        await update.message.reply_text(f"🎯 Тэст перакладу праз Skarnik:\n\nРускі: {test_text}\n\nПеракладаю...")
        
        try:
            be = skarnik_tr.translate_ru_to_be(test_text)
            await update.message.reply_text(f"Беларускі: {be}")
        except Exception as e:
            await update.message.reply_text(f"❌ Памылка: {e}")
    else:
        await update.message.reply_text("❌ Skarnik перакладчык не даступны")

# Перевод обычных сообщений
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    bot_username = (await context.bot.get_me()).username
    
    # Проверяем, есть ли упоминание бота в тексте
    mention_pattern = f"@{bot_username}\\s+(.+)"
    import re
    mention_match = re.search(mention_pattern, text, re.IGNORECASE)
    
    print(f"🔍 Проверяю текст: '{text}'")
    print(f"🔍 Паттерн: {mention_pattern}")
    print(f"🔍 Найдено совпадение: {mention_match is not None}")
    
    if mention_match:
        # Если есть упоминание, переводим только последнее слово из фразы
        phrase_after_mention = mention_match.group(1).strip()
        # Берем только последнее слово
        words = phrase_after_mention.split()
        word_to_translate = words[-1] if words else phrase_after_mention
        
        print(f"🔍 Обрабатываю упоминание: '{phrase_after_mention}' -> слово: '{word_to_translate}'")
        
        skarnik_tr, fallback_tr = await ensure_translator()
        
        try:
            # Отправляем сообщение о том, что перевод в процессе
            wait_message = await update.message.reply_text(f"🔍 Шукаю пераклад слова '{word_to_translate}' у Skarnik...")
            
            if skarnik_tr:
                # Пробуем Skarnik переводчик
                be = skarnik_tr.translate_ru_to_be(word_to_translate)
                if be and not be.startswith("Памылка") and not be.startswith("Пераклад не знойдзены"):
                    # Удаляем сообщение об ожидании и отправляем перевод
                    try:
                        await wait_message.delete()
                    except:
                        pass  # Игнорируем ошибки удаления сообщения
                    await update.message.reply_text(f"'{word_to_translate}' → '{be}'")
                    return
            
            # Если Skarnik не сработал, используем fallback
            be = fallback_tr.translate_ru_to_be(word_to_translate)
            if not be or be.startswith("Пераклад не знойдзены"):
                be = "пераклад не знойдзены"
            
            # Удаляем сообщение об ожидании и отправляем перевод
            try:
                await wait_message.delete()
            except:
                pass  # Игнорируем ошибки удаления сообщения
            await update.message.reply_text(f"'{word_to_translate}' → '{be}'")
            
        except Exception as e:
            print(f"❌ Ошибка при обработке упоминания: {e}")
            # Удаляем сообщение об ожидании и отправляем ошибку
            try:
                await wait_message.delete()
            except:
                pass  # Игнорируем ошибки удаления сообщения
            await update.message.reply_text(f"Памылка перакладу: {e}")
    else:
        # Если нет упоминания, переводим весь текст как обычно
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

# Инлайн-режим: @BotName <русский текст>
async def on_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = (update.inline_query.query or "").strip()
    if not query:
        # Покажем подсказку-пустышку, чтобы было что выбрать
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
                description="Праверце тэкст і паспрабуйте зноў"
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)

def main():
    token = load_or_ask_token()
    
    # Настройка с retry и обработкой ошибок
    app = Application.builder().token(token).build()
    
    # Добавляем обработчик ошибок
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Логирует ошибки, вызванные обновлениями."""
        print(f"Ошибка при обработке обновления: {context.error}")
        
        # Если это NetworkError, пробуем переподключиться
        if "NetworkError" in str(context.error) or "httpx.ReadError" in str(context.error):
            print("Обнаружена сетевая ошибка. Бот будет пытаться переподключиться...")
            # Здесь можно добавить логику переподключения

    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("test", test_cmd))
    app.add_handler(InlineQueryHandler(on_inline_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    print("🔍 Бот перакладу праз Skarnik запущен. Наберите Ctrl+C для остановки.")
    print("💡 Выкарыстоўваю онлайн-слоўнік Skarnik для перакладу...")
    
    # Запуск с retry логикой
    try:
        app.run_polling(
            close_loop=False,
            drop_pending_updates=True,  # Игнорируем старые обновления
            allowed_updates=["message", "inline_query"]  # Только нужные типы обновлений
        )
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        print("Попробуйте перезапустить бота или проверить интернет-соединение")

if __name__ == "__main__":
    main()
