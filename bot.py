import os
import sys
import threading
import requests
import json
from typing import Optional

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
            # Формируем промпт для Mistral - эта модель лучше понимает контекст
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
                        "temperature": 0.1,  # Немного увеличиваем температуру для Mistral
                        "top_p": 0.8,
                        "max_tokens": max_len
                    }
                },
                timeout=60  # Увеличиваем timeout до 60 секунд
            )
            
            if response.status_code == 200:
                result = response.json()
                translation = result.get('response', '').strip()
                
                # Специальная обработка для Mistral
                if self.model_name == "mistral:7b":
                    # Убираем возможные префиксы и суффиксы для нового формата
                    if translation.startswith("Переведи следующий текст с русского на белорусский язык:"):
                        translation = translation[67:].strip()
                    if translation.startswith("Русский:"):
                        translation = translation[8:].strip()
                    if translation.startswith("Белорусский:"):
                        translation = translation[12:].strip()
                    if translation.startswith(":"):
                        translation = translation[1:].strip()
                    
                    # Убираем возможные объяснения в скобках
                    if "(" in translation and ")" in translation:
                        # Оставляем только текст до первой скобки
                        translation = translation.split("(")[0].strip()
                
                # Общая очистка результата
                if translation.startswith("Белорусский перевод:"):
                    translation = translation[22:].strip()
                if translation.startswith("Белорусский:"):
                    translation = translation[12:].strip()
                if translation.startswith(":"):
                    translation = translation[1:].strip()
                
                # Валидация результата - проверяем, что перевод не слишком короткий
                if translation and len(translation.split()) < len(text.split()) * 0.6:
                    # Перевод слишком короткий, пробуем еще раз с более строгим промптом
                    print(f"Перевод слишком короткий: '{translation}' для текста '{text}', пробую еще раз...")
                    
                    strict_prompt = f"""Переведи ВСЕ слова с русского на белорусский. Не пропускай ничего:

Русский: {text}
Белорусский:"""
                    
                    retry_response = requests.post(
                        f"{self.base_url}/api/generate",
                        json={
                            "model": self.model_name,
                            "prompt": strict_prompt,
                            "stream": False,
                            "options": {
                                "temperature": 0.05,  # Низкая температура для точности
                                "top_p": 0.6,
                                "max_tokens": max_len
                            }
                        },
                        timeout=60
                    )
                    
                    if retry_response.status_code == 200:
                        retry_result = retry_response.json()
                        retry_translation = retry_result.get('response', '').strip()
                        
                        # Очищаем повторный результат
                        if retry_translation.startswith("Переведи ВСЕ слова с русского на белорусский. Не пропускай ничего:"):
                            retry_translation = retry_translation[67:].strip()
                        if retry_translation.startswith("Русский:"):
                            retry_translation = retry_translation[8:].strip()
                        if retry_translation.startswith("Белорусский:"):
                            retry_translation = retry_translation[12:].strip()
                        if retry_translation.startswith(":"):
                            retry_translation = retry_translation[1:].strip()
                        
                        # Используем лучший из двух вариантов
                        if len(retry_translation.split()) > len(translation.split()):
                            translation = retry_translation
                            print(f"Улучшенный перевод: '{translation}'")
                
                # Дополнительная проверка - если перевод все еще неполный, пробуем третий раз
                if translation and len(translation.split()) < len(text.split()) * 0.8:
                    print(f"Перевод все еще неполный: '{translation}' для текста '{text}', пробую третий раз...")
                    
                    final_prompt = f"""Переведи КАЖДОЕ слово с русского на белорусский язык:

Русский: {text}
Белорусский:"""
                    
                    final_response = requests.post(
                        f"{self.base_url}/api/generate",
                        json={
                            "model": self.model_name,
                            "prompt": final_prompt,
                            "stream": False,
                            "options": {
                                "temperature": 0.0,
                                "top_p": 0.4,
                                "max_tokens": max_len
                            }
                        },
                        timeout=60
                    )
                    
                    if final_response.status_code == 200:
                        final_result = final_response.json()
                        final_translation = final_result.get('response', '').strip()
                        
                        # Очищаем финальный результат
                        if final_translation.startswith("Переведи КАЖДОЕ слово с русского на белорусский язык:"):
                            final_translation = final_translation[67:].strip()
                        if final_translation.startswith("Русский:"):
                            final_translation = final_translation[8:].strip()
                        if final_translation.startswith("Белорусский:"):
                            final_translation = final_translation[12:].strip()
                        if final_translation.startswith(":"):
                            final_translation = final_translation[1:].strip()
                        
                        # Используем лучший из всех вариантов
                        if len(final_translation.split()) > len(translation.split()):
                            translation = final_translation
                            print(f"Финальный улучшенный перевод: '{translation}'")
                
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

# Fallback переводчик с базовым словарем
class FallbackTranslator:
    def __init__(self):
        # Простой словарь для базовых переводов
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
            "сколько тебе лет": "колькі табе гадоў"
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

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "Прывітанне! Я перакладаю з рускай на беларускую 🪄\n\n"
        "• Напішыце мне тэкст — я адкажу перакладам.\n"
        "• У любым чаце ўвядзіце: @"
        f"{(await context.bot.get_me()).username} ваш рускі тэкст — і ўстаўце вынік.\n\n"
        "Крыніца: мадэль Mistral 7B для перакладу.\n"
        "У выпадку памылкі выкарыстоўваецца fallback перакладчык.\n\n"
        "Каманды:\n"
        "/start - пачатак\n"
        "/help - дапамога\n"
        "/status - статус Ollama\n"
        "/model - змена мадэлі\n"
        "/test - тэст перакладу"
    )
    await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Проста дашліце рускі тэкст — я перакладу на беларускую.\n"
        "Інлайн: @ІмяБота ваш рускі тэкст.\n\n"
        "Бот выкарыстоўвае мадэль Mistral 7B для перакладу.\n"
        "Каманды:\n"
        "/status - статус Ollama\n"
        "/model - змена мадэлі\n"
        "/test - тэст перакладу"
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет статус Ollama и показывает доступные модели"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=10)
        if response.status_code == 200:
            models = response.json().get('models', [])
            if models:
                model_list = "\n".join([f"• {m['name']} ({m.get('details', {}).get('parameter_size', 'N/A')})" for m in models])
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

async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Смена модели для перевода"""
    global translator
    
    if not context.args:
        # Показываем текущую модель
        if translator:
            msg = f"Поточная мадэль: {translator.model_name}\n\nДля змены мадэлі выкарыстоўвайце:\n/model <назва_мадэлі>"
        else:
            msg = "Перакладчык не ініцыялізаваны"
        await update.message.reply_text(msg)
        return
    
    new_model = context.args[0]
    
    if translator:
        try:
            # Проверяем, доступна ли новая модель
            response = requests.get("http://localhost:11434/api/tags", timeout=10)
            if response.status_code == 200:
                models = [m['name'] for m in response.json().get('models', [])]
                if new_model in models:
                    translator.change_model(new_model)
                    msg = f"✅ Мадэль зменена на: {new_model}"
                else:
                    msg = f"❌ Мадэль {new_model} не знойдзена\n\nДоступныя мадэлі:\n" + "\n".join([f"• {m}" for m in models])
            else:
                msg = "❌ Не ўдаецца праверыць мадэлі"
        except Exception as e:
            msg = f"❌ Памылка: {e}"
    else:
        msg = "❌ Перакладчык не ініцыялізаваны"
    
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
    ollama_tr, fallback_tr = await ensure_translator()
    
    if ollama_tr:
        await update.message.reply_text(f"🧪 Тэст перакладу:\n\nРускі: {test_text}\n\nПеракладаю...")
        
        try:
            be = ollama_tr.translate_ru_to_be(test_text)
            await update.message.reply_text(f"Беларускі: {be}")
        except Exception as e:
            await update.message.reply_text(f"❌ Памылка: {e}")
    else:
        await update.message.reply_text("❌ Перакладчык Ollama не даступны")

# Перевод обычных сообщений
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    ollama_tr, fallback_tr = await ensure_translator()
    
    # Отправляем сообщение о том, что перевод в процессе
    wait_message = await update.message.reply_text("⏳ Ожидайте перевод...")
    
    try:
        if ollama_tr:
            # Пробуем Ollama
            be = ollama_tr.translate_ru_to_be(text)
            if be and not be.startswith("Памылка"):
                # Удаляем сообщение об ожидании и отправляем перевод
                await wait_message.delete()
                await update.message.reply_text(be)
                return
        
        # Если Ollama не сработала, используем fallback
        be = fallback_tr.translate_ru_to_be(text)
        if not be or be.startswith("Пераклад не знойдзены"):
            be = "Пераклад не атрымаўся. Паспрабуйте іншы тэкст."
        
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
                description="Я перакладу на беларускую"
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    ollama_tr, fallback_tr = await ensure_translator()
    
    try:
        if ollama_tr:
            # Пробуем Ollama
            be = ollama_tr.translate_ru_to_be(query)
            if be and not be.startswith("Памылка"):
                results = [
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title="Пераклад на беларускую (Ollama)",
                        input_message_content=InputTextMessageContent(be),
                        description=be[:120]
                    )
                ]
                await update.inline_query.answer(results, cache_time=0, is_personal=True)
                return
        
        # Если Ollama не сработала, используем fallback
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
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(CommandHandler("test", test_cmd))
    app.add_handler(InlineQueryHandler(on_inline_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    print("Бот запущен. Наберите Ctrl+C для остановки.")
    print("Убедитесь, что Ollama запущена: ollama serve")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()