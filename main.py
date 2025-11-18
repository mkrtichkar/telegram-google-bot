from flask import Flask, request
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

BOT_TOKEN = "8467886457:AAHjSg0XaSk-BZdLvl3l12tQKoIslgdBAIw"
CHAT_MODE = "group"  # "group" = бот слушает группы, "private" = только личку

SPREADSHEET_ID = "1wzKqxKmbHUbu0wmSiG8UgogmyjSIMu2PUc9LOz6VVmw"
SHEET_NAME = "Заявки"

app = Flask(__name__)

# Авторизация Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" not in data:
        return "no message"

    msg = data["message"]
    text = msg.get("text", "")

    # Если бот в группе — принимаем только group сообщений
    if CHAT_MODE == "group":
        if "chat" in msg and msg["chat"]["type"] not in ["group", "supergroup"]:
            return "ignored"

    # Автор сообщения
    user = msg.get("from", {})
    manager = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()

    # Дата
    msg_date = datetime.datetime.fromtimestamp(msg["date"]) + datetime.timedelta(hours=3)  # Москва UTC+3

    # ИНН (10-12 цифр)
    import re
    m_inn = re.search(r"\b\d{10}\b|\b\d{12}\b", text)
    inn = m_inn.group(0) if m_inn else ""

    # Ссылка
    m_link = re.search(r"https?://\S+", text)
    link = m_link.group(0) if m_link else ""

    # Тип заявки
    lower = text.lower()
    ztype = ""
    if "#заявка" in lower:
        ztype = "Заявка"
    elif "#предложение" in lower:
        ztype = "Предложение"

    # Запись в таблицу
    row = [
        str(msg_date),
        manager,
        inn,
        ztype,
        link,
        "",
        "Новое",
        text
    ]

    sheet.append_row(row)

    return "ok"


@app.route("/")
def home():
    return "Bot is working!"


if __name__ == "__main__":
    app.run()
