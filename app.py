import os
import telebot

TOKEN = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Salut ! Je suis en ligne grâce au Background Worker !")

print("Le bot est en cours de démarrage...")
bot.infinity_polling()
