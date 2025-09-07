#!/usr/bin/env python3
"""
Скрипт для проверки подключения к Telegram API и диагностики проблем
"""

import requests
import time
import sys
from urllib.parse import urlparse

def check_telegram_api():
    """Проверяет доступность Telegram API"""
    print("🔍 Проверяем подключение к Telegram API...")
    
    urls_to_check = [
        "https://api.telegram.org",
        "https://api.telegram.org/bot/getMe",  # Этот URL вернет 404, но покажет доступность API
    ]
    
    for url in urls_to_check:
        try:
            print(f"  Проверяем: {url}")
            response = requests.get(url, timeout=10)
            print(f"  ✅ Статус: {response.status_code}")
            if response.status_code == 404:
                print("  ℹ️  API доступен (404 ожидаем для /getMe без токена)")
            break
        except requests.exceptions.Timeout:
            print(f"  ❌ Таймаут при подключении к {url}")
        except requests.exceptions.ConnectionError as e:
            print(f"  ❌ Ошибка подключения: {e}")
        except Exception as e:
            print(f"  ❌ Неожиданная ошибка: {e}")
    
    return True

def check_internet():
    """Проверяет общее интернет-соединение"""
    print("\n🌐 Проверяем общее интернет-соединение...")
    
    test_urls = [
        "https://google.com",
        "https://yandex.ru",
        "https://github.com"
    ]
    
    for url in test_urls:
        try:
            print(f"  Проверяем: {url}")
            response = requests.get(url, timeout=5)
            print(f"  ✅ Статус: {response.status_code}")
            return True
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
    
    return False

def check_dns():
    """Проверяет DNS резолюцию"""
    print("\n🔍 Проверяем DNS резолюцию...")
    
    import socket
    
    domains = ["api.telegram.org", "google.com", "github.com"]
    
    for domain in domains:
        try:
            ip = socket.gethostbyname(domain)
            print(f"  ✅ {domain} -> {ip}")
        except socket.gaierror as e:
            print(f"  ❌ {domain}: {e}")

def suggest_solutions():
    """Предлагает решения проблем"""
    print("\n💡 Возможные решения:")
    print("1. Проверьте интернет-соединение")
    print("2. Если Telegram заблокирован в вашей стране/сети:")
    print("   - Используйте VPN")
    print("   - Настройте прокси в боте")
    print("3. Попробуйте перезапустить бота")
    print("4. Проверьте, не блокирует ли файрвол подключения")
    print("5. Если проблема постоянная, попробуйте другой сервер")

def main():
    print("🚀 Диагностика подключения Telegram бота\n")
    
    # Проверяем интернет
    internet_ok = check_internet()
    
    # Проверяем DNS
    check_dns()
    
    # Проверяем Telegram API
    telegram_ok = check_telegram_api()
    
    print("\n" + "="*50)
    print("📊 РЕЗУЛЬТАТЫ ДИАГНОСТИКИ:")
    print(f"Интернет: {'✅ OK' if internet_ok else '❌ ПРОБЛЕМЫ'}")
    print(f"Telegram API: {'✅ OK' if telegram_ok else '❌ ПРОБЛЕМЫ'}")
    
    if not internet_ok:
        print("\n❌ Проблемы с интернет-соединением")
        suggest_solutions()
    elif not telegram_ok:
        print("\n❌ Telegram API недоступен")
        print("Возможно, Telegram заблокирован в вашей сети")
        suggest_solutions()
    else:
        print("\n✅ Все проверки пройдены успешно!")
        print("Проблема может быть временной. Попробуйте перезапустить бота.")

if __name__ == "__main__":
    main()
