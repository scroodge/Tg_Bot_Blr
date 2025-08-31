import os
import sys
import threading
from typing import Optional

import platform
import traceback
import transformers as _tf
import huggingface_hub as _hf

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from transformers.utils import logging as hf_logging
from tqdm import tqdm
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

# Локальный переводчик через transformers для абсолютной точности
class PreciseTranslator:
    def __init__(self):
        model_name = os.getenv("RU_BE_MODEL", "Helsinki-NLP/opus-mt-ru-be")
        cache_dir = os.getenv("HF_CACHE_DIR", os.path.expanduser("~/.cache/huggingface"))
        local_only = os.getenv("HF_LOCAL_ONLY", "0") == "1"
        print(f"🔄 Загружаю модель {model_name}... (local_only={local_only}, cache_dir={cache_dir})")

        is_local_path = os.path.isdir(model_name)
        print(f"🔎 is_local_path={is_local_path}")
        if is_local_path:
            print(f"📁 Содержимое локальной папки модели: {model_name}")
            try:
                print("   ", os.listdir(model_name)[:10])
            except Exception as ee:
                print("   (не удалось прочитать каталог)", ee)

        def _suggest_alternatives():
            try:
                from huggingface_hub import HfApi
                api = HfApi()
                # Ищем возможные варианты ru→be от Helsinki-NLP
                cands = api.list_models(search="ru-be", author="Helsinki-NLP")
                if not cands:
                    cands = api.list_models(search="opus-mt be", author="Helsinki-NLP")
                if cands:
                    print("🔎 Магчымая падмена ідэнтыфікатара. Праверце гэтыя мадэлі:")
                    for m in cands[:10]:
                        print("   •", m.modelId)
                else:
                    print("🔎 Альтэрнатывы не знойдзены праз API. Паспрабуйце пошук на huggingface.co па 'ru-be opus-mt'.")
            except Exception as ee:
                print(f"(debug) Не ўдалося атрымаць спіс мадэляў: {ee}")

        # Определяем устройство: сначала MPS (Apple Silicon), затем CUDA, затем CPU
        if torch.backends.mps.is_available():
            self.device = torch.device("mps")
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
        else:
            self.device = torch.device("cpu")

        try:
            # Включаем прогресс-бар загрузки
            try:
                import huggingface_hub
                huggingface_hub.utils._validators.disable_progress_bars = False
            except Exception:
                pass
            hf_logging.set_verbosity_info()
            if not local_only and not is_local_path:
                try:
                    print("🌐 Проверяю доступ к репозиторию на Hugging Face...")
                    info = _hf.HfApi().model_info(model_name)
                    print(f"   ✅ Найдена модель: {info.modelId} (sha: {getattr(info, 'sha', 'n/a')})")
                except Exception as ping_e:
                    print("   ❌ Не удалось получить метаданные модели через API:")
                    print("   ", ping_e)
            print("⏬ Загружаю токенизатор...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                local_files_only=local_only,
                cache_dir=cache_dir,
                use_auth_token=None
            )
            print("✅ Токенизатор загружен")
            try:
                print(f"   🔤 vocab_size={getattr(self.tokenizer, 'vocab_size', 'n/a')}")
                print(f"   BOS={self.tokenizer.bos_token} EOS={self.tokenizer.eos_token} PAD={self.tokenizer.pad_token}")
            except Exception:
                pass
            print("⏬ Загружаю модель (веса)... это может занять несколько минут при первом запуске")
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name,
                local_files_only=local_only,
                cache_dir=cache_dir,
                use_auth_token=None
            ).to(self.device)
            self.model.eval()
            print("✅ Веса модели загружены")
            print(f"✅ Модель успешно загружена! Устройство: {self.device}")
            try:
                params = sum(p.numel() for p in self.model.parameters())
                print(f"   🧮 Параметров модели: {params:,}")
            except Exception:
                pass
            try:
                if self.device.type == 'cuda':
                    print(f"   💠 CUDA: {torch.cuda.get_device_name(0)}")
                    print(f"     память: {torch.cuda.memory_reserved()/1e6:.1f}MB reserved/{torch.cuda.memory_allocated()/1e6:.1f}MB alloc")
                elif self.device.type == 'mps':
                    print("   💠 MPS активен")
            except Exception:
                pass
        except Exception as e:
            print(f"❌ Ошибка загрузки модели: {e}")
            print("💡 Попробуйте установить: pip install transformers torch")
            if not local_only:
                print("💡 Если интернет недоступен/блокируется: скачайте модель в ./models/opus-mt-ru-be и запустите с RU_BE_MODEL=./models/opus-mt-ru-be HF_LOCAL_ONLY=1")
                print("   Пример: huggingface-cli download Helsinki-NLP/opus-mt-ru-be --local-dir ./models/opus-mt-ru-be")
            _suggest_alternatives()
            print("💡 Можна ўсталяваць дакладны ід мадэлі праз RU_BE_MODEL=... і перазапусціць.")
            print("--- traceback ---")
            traceback.print_exc()
            print("------------------")
            raise

    def translate_ru_to_be(self, text: str, max_len: int = 512) -> str:
        text = text.strip()
        if not text:
            return ""
        try:
            # Ограничим количество генерируемых токенов отдельно (не равно входной длине)
            max_new = 256 if max_len > 256 else max_len

            inputs = self.tokenizer(
                [text],
                return_tensors="pt",
                truncation=True,
                max_length=max_len,
                padding=True,
            ).to(self.device)

            with torch.inference_mode():
                output_tokens = self.model.generate(
                    **inputs,
                    num_beams=4,
                    length_penalty=1.0,
                    max_new_tokens=max_new,
                    early_stopping=True,
                    do_sample=False,
                )

            result = self.tokenizer.batch_decode(
                output_tokens,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True,
            )[0]
            return result.strip()
        except Exception as e:
            print(f"Ошибка перевода: {e}")
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
            "как тебя зовут": "як цябе завуць",
            "меня зовут": "мяне завуць",
            "где ты живешь": "дзе ты жывеш",
            "сколько тебе лет": "колькі табе гадоў",
            "не надо": "не трэба",
            "в кровати": "у пасцелі",
            "так хорошо": "так добра",
            "моя хорошая": "мая дарагая",
            "люблю тебя": "кахаю цябе",
            "спокойной ночи": "спакойнай ночы"
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

translator: Optional[PreciseTranslator] = None
fallback_translator: Optional[FallbackTranslator] = None
translator_lock = threading.Lock()

async def ensure_translator():
    global translator, fallback_translator
    
    if translator is None:
        with translator_lock:
            if translator is None:
                try:
                    translator = PreciseTranslator()
                    fallback_translator = FallbackTranslator()
                except Exception as e:
                    print(f"Не удалось инициализировать точный переводчик: {e}")
                    print("Использую fallback переводчик...")
                    translator = None
                    fallback_translator = FallbackTranslator()
    
    return translator, fallback_translator

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "Прывітанне! Я перакладаю з рускай на беларускую з абсалютнай дакладнасцю 🎯\n\n"
        "• Напішыце мне тэкст — я адкажу перакладам.\n"
        "• У любым чаце ўвядзіце: @"
        f"{(await context.bot.get_me()).username} ваш рускі тэкст — і ўстаўце вынік.\n\n"
        "Крыніца: лакальная мадэль перакладу (канфігуруецца праз RU_BE_MODEL).\n"
        "У выпадку памылкі выкарыстоўваецца fallback перакладчык.\n\n"
        "Каманды:\n"
        "/start - пачатак\n"
        "/help - дапамога\n"
        "/status - статус мадэлі\n"
        "/test - тэст перакладу"
    )
    await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Проста дашліце рускі тэкст — я перакладу на беларускую.\n"
        "Інлайн: @ІмяБота ваш рускі тэкст.\n\n"
        "Бот выкарыстоўвае лакальную мадэль Helsinki-NLP/opus-mt-ru-be.\n"
        "Каманды:\n"
        "/status - статус мадэлі\n"
        "/test - тэст перакладу"
    )

async def debug_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from huggingface_hub import HfFolder
    hf_token = HfFolder.get_token()
    cache_dir = os.getenv("HF_CACHE_DIR", os.path.expanduser("~/.cache/huggingface"))
    env_summary = (
        f"HF_ENDPOINT={os.getenv('HF_ENDPOINT','')}\n"
        f"HF_LOCAL_ONLY={os.getenv('HF_LOCAL_ONLY','0')}\n"
        f"RU_BE_MODEL={os.getenv('RU_BE_MODEL','')}\n"
        f"HF_CACHE_DIR={cache_dir}\n"
        f"HF_TOKEN={'set' if hf_token else 'not set'}\n"
    )
    await update.message.reply_text("Debug env:\n" + env_summary)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет статус модели"""
    global translator
    
    if translator:
        try:
            params = sum(p.numel() for p in translator.model.parameters())
        except Exception:
            params = None
        device = getattr(translator, "device", "cpu")
        msg = (
            "✅ Мадэль Helsinki-NLP/opus-mt-ru-be загружана і працуе\n\n"
            f"Токенізатар: {type(translator.tokenizer).__name__}\n"
            f"Мадэль: {type(translator.model).__name__}\n"
            f"Прылада: {device}\n"
        )
        if params is not None:
            msg += f"Параметраў: {params:,}"
        msg += f"Кэш: {os.getenv('HF_CACHE_DIR', os.path.expanduser('~/.cache/huggingface'))}\n"
    else:
        msg = f"❌ Мадэль не загружена\n💡 Выкарыстоўваецца fallback перакладчык (канфігуруецца праз RU_BE_MODEL, па змаўчанні Helsinki-NLP/opus-mt-ru-be)"
    
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
    precise_tr, fallback_tr = await ensure_translator()
    
    if precise_tr:
        await update.message.reply_text(f"🎯 Тэст дакладнага перакладу:\n\nРускі: {test_text}\n\nПеракладаю...")
        
        try:
            be = precise_tr.translate_ru_to_be(test_text)
            await update.message.reply_text(f"Беларускі: {be}")
        except Exception as e:
            await update.message.reply_text(f"❌ Памылка: {e}")
    else:
        await update.message.reply_text("❌ Дакладны перакладчык не даступны")

# Перевод обычных сообщений
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    precise_tr, fallback_tr = await ensure_translator()
    
    # Отправляем сообщение о том, что перевод в процессе
    wait_message = await update.message.reply_text("🎯 Перакладаю з дакладнасцю...")
    
    try:
        if precise_tr:
            # Пробуем точный переводчик
            be = precise_tr.translate_ru_to_be(text)
            if be and not be.startswith("Памылка"):
                # Удаляем сообщение об ожидании и отправляем перевод
                await wait_message.delete()
                await update.message.reply_text(be)
                return
        
        # Если точный переводчик не сработал, используем fallback
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
                description="Я перакладу на беларускую з дакладнасцю"
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    precise_tr, fallback_tr = await ensure_translator()
    
    try:
        if precise_tr:
            # Пробуем точный переводчик
            be = precise_tr.translate_ru_to_be(query)
            if be and not be.startswith("Памылка"):
                results = [
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title="Пераклад на беларускую (Дакладна)",
                        input_message_content=InputTextMessageContent(be),
                        description=be[:120]
                    )
                ]
                await update.inline_query.answer(results, cache_time=0, is_personal=True)
                return
        
        # Если точный переводчик не сработал, используем fallback
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
    print("🔧 Debug info:")
    print(f"  Python: {platform.python_version()} ({platform.system()} {platform.machine()})")
    print(f"  Torch: {torch.__version__}")
    print(f"  Transformers: {_tf.__version__}")
    print(f"  HF Hub: {_hf.__version__}")
    print(f"  HF_ENDPOINT={os.getenv('HF_ENDPOINT','')}")
    print(f"  HF_LOCAL_ONLY={os.getenv('HF_LOCAL_ONLY','0')}")
    print(f"  RU_BE_MODEL={os.getenv('RU_BE_MODEL','Helsinki-NLP/opus-mt-ru-be')}")
    print(f"  HF_CACHE_DIR={os.getenv('HF_CACHE_DIR', os.path.expanduser('~/.cache/huggingface'))}")
    print(f"  HTTPS_PROXY={os.getenv('HTTPS_PROXY','')}")
    print(f"  HTTP_PROXY={os.getenv('HTTP_PROXY','')}")
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("debug", debug_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("test", test_cmd))
    app.add_handler(InlineQueryHandler(on_inline_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    print("🎯 Бот дакладнага перакладу запущен. Наберите Ctrl+C для остановки.")
    print(f"💡 Загружаю модель: {os.getenv('RU_BE_MODEL', 'Helsinki-NLP/opus-mt-ru-be')}")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
