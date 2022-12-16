import telebot
from lib import *

bot = telebot.TeleBot(config.TOKEN)
game = Game(config.GAME_SIZE)
processing(config.STREETS_PATH, game)
chat_dict = {}


@bot.message_handler(commands=['start'])
def start_menu(message):
    create_start_menu(bot, message, chat_dict)


@bot.callback_query_handler(lambda call: True)
def menu(call: telebot.types.CallbackQuery):
    create_menu(bot, call, game, chat_dict)


# Run
if __name__ == '__main__':
    bot.polling(none_stop=True)
