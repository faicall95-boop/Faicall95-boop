import os
import telebot
from flask import Flask
import threading

# On récupère le token
TOKEN = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)

# Un petit serveur web pour empêcher Render de couper le bot
app = Flask(__name__)

@app.route('/')
def home():
    return "Le bot est en ligne !"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Salut ! Je suis en ligne !")

# On lance le bot et le serveur en même temps
if __name__ == "__main__":
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 10000)))
