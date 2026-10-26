import os
import telebot
from flask import Flask, request

TOKEN = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN, threaded=False) # Important pour Render
app = Flask(__name__)

# L'URL de ton service Render
URL = "https://faicall95-boop.onrender.com/"

@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=URL + TOKEN)
    return "Webhook configuré !", 200

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Salut ! Je suis en ligne !")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 10000)))
