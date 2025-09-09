# Использование бота перевода

## Запуск бота

### 1. С Google Translate Library (бесплатно)
```bash
python3 bot_google.py
```

### 2. С Gemini API (платно, но дешевле Google Translate)
```bash
python3 bot_google.py -google
```

## Настройка

### 1. Создайте .env файл
Скопируйте `env_example.txt` в `.env` и заполните:

```env
# Telegram Bot Token
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Admin User IDs (через запятую)
ADMIN_USER_IDS=123456789,987654321,555666777

# Gemini API Key (для использования с параметром -google)
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Установите зависимости
```bash
pip3 install -r requirements.txt
```

## Получение API ключей

### Telegram Bot Token
1. Напишите @BotFather в Telegram
2. Создайте нового бота командой `/newbot`
3. Скопируйте полученный токен

### Gemini API Key
1. Перейдите в [Google AI Studio](https://aistudio.google.com/)
2. Войдите в аккаунт Google
3. Создайте новый API ключ
4. Скопируйте ключ в .env файл

## Режимы работы

### Google Translate Library (по умолчанию)
- ✅ Бесплатно
- ✅ Не требует API ключа
- ⚠️ Может быть заблокирован Google
- 📚 Использует библиотеку googletrans

### Gemini API (с параметром -google)
- 💰 Платно (но дешевле Google Translate)
- 🔑 Требует API ключ
- ✅ Более стабильный
- 🤖 Использует Google Gemini AI

## Команды бота

- `/start` - начать работу
- `/help` - помощь
- `/status` - статус переводчика
- `/stats` - статистика пользователей
- `/mystats` - ваша статистика

## Админ команды

- `/adminstats` - детальная статистика
- `/addadmin <id>` - добавить админа
- `/listadmins` - список админов
- `/export` - экспорт в CSV
