import os
from flask import Flask, request
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import re
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8467886457:AAHjSg0XaSk-BZdLvl3l12tQKoIslgdBAIw"
SPREADSHEET_ID = "1wzKqxKmbHUbu0wmSiG8UgogmyjSIMu2PUc9LOz6VVmw"
SHEET_NAME = "Заявки"

app = Flask(__name__)

# Авторизация Google Sheets
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    logger.info("Успешная авторизация в Google Sheets")
except Exception as e:
    logger.error(f"Ошибка авторизации в Google Sheets: {e}")
    raise

def extract_info(text):
    """Извлекает информацию из текста сообщения"""
    # ИНН (10 или 12 цифр)
    inn_match = re.search(r'\b\d{10}\b|\b\d{12}\b', text)
    inn = inn_match.group(0) if inn_match else ""
    
    # Ссылка на CRM
    link_match = re.search(r'https?://[^\s]+', text)
    link = link_match.group(0) if link_match else ""
    
    # Тип заявки
    text_lower = text.lower()
    if '#заявка' in text_lower:
        ztype = 'Заявка'
    elif '#предложение' in text_lower:
        ztype = 'Предложение'
    else:
        ztype = ''
    
    return inn, link, ztype

def send_telegram_message(chat_id, text):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения в Telegram: {e}")

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        logger.info(f"Получены данные: {data}")

        if "message" not in data:
            return "no message", 200

        msg = data["message"]
        
        # Игнорируем сообщения не из групп/супергрупп
        if "chat" in msg and msg["chat"]["type"] not in ["group", "supergroup"]:
            return "ignored - not a group", 200
        
        # Игнорируем служебные сообщения
        if "text" not in msg:
            return "ignored - no text", 200

        text = msg.get("text", "").strip()
        
        # Проверяем, содержит ли сообщение нужные хештеги
        if "#заявка" not in text.lower() and "#предложение" not in text.lower():
            return "ignored - no hashtag", 200

        # Информация о менеджере
        user = msg.get("from", {})
        first_name = user.get('first_name', '')
        last_name = user.get('last_name', '')
        username = user.get('username', '')
        
        manager = f"{first_name} {last_name}".strip()
        if not manager:
            manager = f"@{username}" if username else "Неизвестный"
        
        # Дата и время (Москва UTC+3)
        msg_date = datetime.datetime.fromtimestamp(msg["date"]) + datetime.timedelta(hours=3)
        date_str = msg_date.strftime("%Y-%m-%d %H:%M:%S")
        
        # Извлекаем информацию из текста
        inn, link, ztype = extract_info(text)
        
        # Проверяем, что есть обязательные поля
        if not inn:
            send_telegram_message(msg["chat"]["id"], "⚠️ ИНН не найден в сообщении. Укажите ИНН (10 или 12 цифр).")
            return "no inn", 200
        
        if not link:
            send_telegram_message(msg["chat"]["id"], "⚠️ Ссылка на CRM не найдена в сообщении.")
            return "no link", 200
        
        # Подготавливаем данные для записи
        row = [
            date_str,           # Дата
            manager,            # Менеджер
            inn,                # ИНН
            ztype,              # Тип (Заявка/Предложение)
            link,               # Ссылка на CRM
            "",                 # Номер заказа в единике (пусто)
            "Новое",           # Текущий статус
            text               # Комментарий/оригинальный текст
        ]
        
        # Записываем в Google Sheets
        sheet.append_row(row)
        logger.info(f"Данные записаны в таблицу: {row}")
        
        # Отправляем подтверждение в чат
        success_message = f"✅ Данные успешно записаны!\nИНН: {inn}\nТип: {ztype}"
        send_telegram_message(msg["chat"]["id"], success_message)
        
        return "ok", 200
        
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        return "error", 500

@app.route("/")
def home():
    return "Bot is working!"

@app.route("/test")
def test():
    """Тестовый маршрут для проверки подключения к таблице"""
    try:
        # Пытаемся прочитать первую строку таблицы
        values = sheet.row_values(1)
        return f"Table connection OK. First row: {values}"
    except Exception as e:
        return f"Table connection ERROR: {e}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
