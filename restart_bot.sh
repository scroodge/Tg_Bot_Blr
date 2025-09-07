#!/bin/bash

# Скрипт для автоматического перезапуска бота при ошибках

BOT_SCRIPT="bot.py"
LOG_FILE="bot.log"
MAX_RESTARTS=10
RESTART_DELAY=5

echo "🚀 Запуск бота с автоматическим перезапуском"
echo "Логи сохраняются в: $LOG_FILE"
echo "Максимум перезапусков: $MAX_RESTARTS"
echo "Задержка между перезапусками: ${RESTART_DELAY}с"
echo "=========================================="

restart_count=0

while [ $restart_count -lt $MAX_RESTARTS ]; do
    echo "$(date): Запуск бота (попытка $((restart_count + 1))/$MAX_RESTARTS)" | tee -a $LOG_FILE
    
    # Запускаем бота
    python3 $BOT_SCRIPT 2>&1 | tee -a $LOG_FILE
    
    exit_code=$?
    echo "$(date): Бот завершился с кодом $exit_code" | tee -a $LOG_FILE
    
    # Если бот завершился нормально (Ctrl+C), не перезапускаем
    if [ $exit_code -eq 0 ]; then
        echo "$(date): Бот завершен пользователем" | tee -a $LOG_FILE
        break
    fi
    
    restart_count=$((restart_count + 1))
    
    if [ $restart_count -lt $MAX_RESTARTS ]; then
        echo "$(date): Перезапуск через $RESTART_DELAY секунд..." | tee -a $LOG_FILE
        sleep $RESTART_DELAY
    else
        echo "$(date): Достигнуто максимальное количество перезапусков" | tee -a $LOG_FILE
    fi
done

echo "$(date): Скрипт завершен" | tee -a $LOG_FILE
