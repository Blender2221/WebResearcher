import requests
from bs4 import BeautifulSoup
import time
import datetime
import os
import smtplib
from email.mime.text import MIMEText
from urllib.parse import urljoin # Добавлен импорт для корректной обработки ссылок

# --- КОНФИГУРАЦИЯ ---
# ВАЖНО: Веб-сайты часто меняют свою HTML-структуру. Если скрипт перестает
# работать (например, выдает "N/A" или "Не найдено контейнеров статей"),
# вам нужно будет обновить CSS-селекторы для этого сайта.
# Инструкции по поиску селекторов см. ниже.
NEWS_SOURCES = {
    "StopGame": {
        "url": "https://stopgame.ru/news",
        "selectors": {
            # ЭТИ СЕЛЕКТОРЫ МОГУТ ПОТРЕБОВАТЬ РУЧНОЙ ПРОВЕРКИ И ОБНОВЛЕНИЯ!
            # ИСПОЛЬЗУЙТЕ ИНСТРУМЕНТЫ РАЗРАБОТЧИКА В БРАУЗЕРЕ (F12).
            # Пример:
            "article": 'div._card_18o0g_1', # Общий контейнер для одной новости
            "title": 'a._title_18o0g_60',             # Заголовок новости (ссылка внутри h3)
            "link": 'a._title_18o0g_60',              # Сама ссылка новости
            "summary": "div._tags_18o0g_89"                 # Краткое описание
        }
    },
    # GameSpot был временно удален из-за ошибки 403 (блокировка).
    # Для скрапинга таких сайтов требуются более сложные методы (прокси, Selenium и т.д.),
    # которые выходят за рамки текущего простого скрипта.
    # Если хотите добавить GameSpot или похожий сайт, будьте готовы к
    # необходимости реализации этих сложных методов.
}

HEADERS = {
    # Обновленный и более реалистичный User-Agent
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7", # Добавлен заголовок языка
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Connection": "keep-alive"
}

OUTPUT_HTML_FILE = "gaming_news_aggregator.html"

# --- НАСТРОЙКИ ЭЛЕКТРОННОЙ ПОЧТЫ (ОБЯЗАТЕЛЬНО К НАСТРОЙКЕ ДЛЯ РАБОТЫ) ---
EMAIL_CONFIG = {
    "ENABLED": False, # Установите True для включения отправки отчетов по почте
    "SENDER_EMAIL": "", # <--- ЗАМЕНИТЕ НА ВАШ EMAIL
    # ВАЖНО: Для Gmail и некоторых других провайдеров используйте ПАРОЛЬ ПРИЛОЖЕНИЯ (App Password)!
    # Ваш обычный пароль аккаунта работать НЕ БУДЕТ.
    # Инструкции для Gmail:
    # 1. Зайдите в Google Account (myaccount.google.com).
    # 2. Перейдите в раздел "Безопасность".
    # 3. Найдите "Как вы входите в Google" -> "Пароли приложений".
    #    (Если нет, убедитесь, что включена двухфакторная аутентификация).
    # 4. Создайте новый пароль для "Другое (собственное название)" (например, "News Aggregator").
    # 5. Сгенерированный 16-значный пароль вставьте сюда:
    "SENDER_PASSWORD": "", # <--- ЗАМЕНИТЕ НА ПАРОЛЬ ПРИЛОЖЕНИЯ
    "RECEIVER_EMAIL": "", # <--- ЗАМЕНИТЕ НА EMAIL ПОЛУЧАТЕЛЯ
    "SMTP_SERVER": "smtp.gmail.com", # Для Gmail
    "SMTP_PORT": 587 # Стандартный порт для TLS
}

# --- НАСТРОЙКИ DISCORD (НЕОБЯЗАТЕЛЬНО) ---
DISCORD_WEBHOOK_URL = "" # <--- Вставьте URL вебхука Discord, если используете

# --- Функции парсинга ---
def scrape_news(source_name, config):
    print(f"Собираем новости с {source_name} ({config['url']})...")
    articles = []
    try:
        response = requests.get(config["url"], headers=HEADERS, timeout=15)
        response.raise_for_status() # Вызывает исключение для ошибок HTTP (4xx или 5xx)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Найдем все контейнеры статей
        article_containers = soup.select(config["selectors"]["article"])

        if not article_containers:
            print(f"Внимание: Не найдено контейнеров статей для {source_name} с селектором '{config['selectors']['article']}'. Возможно, селектор устарел или неверен.")
            # Для отладки можно раскомментировать, чтобы увидеть часть HTML
            # print("Первые 1000 символов полученного HTML для отладки:")
            # print(response.text[:1000])
            # print("---")
            return [] # Возвращаем пустой список, если статьи не найдены

        for container in article_containers:
            title_tag = container.select_one(config["selectors"]["title"])
            link_tag = container.select_one(config["selectors"]["link"])
            summary_tag = container.select_one(config["selectors"]["summary"])

            title = title_tag.get_text(strip=True) if title_tag else "N/A"
            link = link_tag['href'] if link_tag and 'href' in link_tag.attrs else "N/A"
            summary = summary_tag.get_text(strip=True) if summary_tag else "Краткое описание недоступно."

            # Проверяем, является ли ссылка относительной, и делаем ее абсолютной
            if link and not link.startswith("http") and link != "N/A":
                link = urljoin(config["url"], link)

            articles.append({
                "source": source_name,
                "title": title,
                "link": link,
                "summary": summary
            })
        print(f"Найдено {len(articles)} новостей с {source_name}.")
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при сборе новостей с {source_name}: {e}")
    except Exception as e:
        print(f"Непредвиденная ошибка при обработке {source_name}: {e}")
    
    time.sleep(2) # Задержка для вежливого сбора данных
    return articles

def aggregate_all_news(sources):
    all_articles = []
    for source_name, config in sources.items():
        articles = scrape_news(source_name, config)
        all_articles.extend(articles)
    return all_articles

def display_news_console(articles):
    print("\n--- Ежедневный Агрегатор Игровых Новостей ---")
    print(f"Дата: {datetime.date.today().strftime('%Y-%m-%d')}\n")
    if not articles:
        print("Новостей не найдено.")
        return

    for article in articles:
        print(f"Источник: {article['source']}")
        print(f"Заголовок: {article['title']}")
        print(f"Ссылка: {article['link']}")
        print(f"Краткое описание: {article['summary']}\n")

def generate_html_report(articles, filename):
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Ежедневный Агрегатор Игровых Новостей</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; background-color: #f4f4f4; color: #333; }}
            .container {{ max-width: 900px; margin: auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #0056b3; text-align: center; }}
            .date {{ text-align: center; color: #666; margin-bottom: 30px; }}
            .news-item {{ border-bottom: 1px solid #eee; padding-bottom: 15px; margin-bottom: 15px; }}
            .news-item:last-child {{ border-bottom: none; }}
            .news-source {{ font-size: 0.9em; color: #555; }}
            .news-title {{ font-size: 1.2em; margin: 5px 0; }}
            .news-title a {{ color: #0056b3; text-decoration: none; }}
            .news-title a:hover {{ text-decoration: underline; }}
            .news-summary {{ font-size: 0.95em; color: #444; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Ежедневный Агрегатор Игровых Новостей</h1>
            <p class="date">Дата: {datetime.date.today().strftime('%Y-%m-%d')}</p>
    """

    if not articles:
        html_content += "<p>Новостей не найдено.</p>"
    else:
        for article in articles:
            html_content += f"""
            <div class="news-item">
                <p class="news-source"><strong>Источник:</strong> {article['source']}</p>
                <h2 class="news-title"><a href="{article['link']}" target="_blank">{article['title']}</a></h2>
                <p class="news-summary">{article['summary']}</p>
            </div>
            """

    html_content += """
        </div>
    </body>
    </html>
    """

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"HTML-отчет сохранен в {filename}")

def send_email_report(articles):
    if not EMAIL_CONFIG["ENABLED"]:
        return

    subject = f"Ежедневный Агрегатор Игровых Новостей - {datetime.date.today().strftime('%Y-%m-%d')}"
    body_text = "Ежедневный Агрегатор Игровых Новостей\n\n"
    if not articles:
        body_text += "Новостей не найдено."
    else:
        for article in articles:
            body_text += f"Источник: {article['source']}\n"
            body_text += f"Заголовок: {article['title']}\n"
            body_text += f"Ссылка: {article['link']}\n"
            body_text += f"Краткое описание: {article['summary']}\n\n"

    msg = MIMEText(body_text, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = EMAIL_CONFIG["SENDER_EMAIL"]
    msg['To'] = EMAIL_CONFIG["RECEIVER_EMAIL"]

    try:
        with smtplib.SMTP(EMAIL_CONFIG["SMTP_SERVER"], EMAIL_CONFIG["SMTP_PORT"]) as server:
            server.starttls() # Включаем TLS шифрование
            server.login(EMAIL_CONFIG["SENDER_EMAIL"], EMAIL_CONFIG["SENDER_PASSWORD"])
            server.send_message(msg)
        print("Отчет по электронной почте отправлен успешно.")
    except Exception as e:
        print(f"Ошибка при отправке отчета по электронной почте: {e}. Убедитесь, что EMAIL_CONFIG верен и для Gmail используется 'Пароль приложения'.")

def send_discord_report(articles):
    if not DISCORD_WEBHOOK_URL:
        return

    content = f"**Ежедневный Агрегатор Игровых Новостей - {datetime.date.today().strftime('%Y-%m-%d')}**\n\n"
    if not articles:
        content += "Новостей не найдено."
    else:
        for article in articles:
            content += f"**[{article['source']}]** [{article['title']}]({article['link']})\n"
            content += f"{article['summary']}\n\n"
            if len(content) > 1800: # Discord webhook limit is 2000 characters per message
                break

    payload = {
        "content": content
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("Отчет в Discord отправлен успешно.")
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при отправке отчета в Discord: {e}")

# --- Главная функция ---
def run_aggregator():
    print("Запуск агрегатора новостей...")
    articles = aggregate_all_news(NEWS_SOURCES)
    
    display_news_console(articles)
    send_email_report(articles)
    send_discord_report(articles)
    print("Агрегатор новостей завершил работу.")

if __name__ == "__main__":
    run_aggregator()
    input("Нажмите Enter, чтобы выйти...")