import logging
import telebot
from config import TOKEN, active_chats

#Настройка бота
bot = telebot.TeleBot(TOKEN)

#Отправка всем активным чатам с обработкой ошибок
def send_to_all(text, parse_mode=None):
    broken_chats = set()

    for chat_id in active_chats:
        try:
            bot.send_message(chat_id, text, parse_mode=parse_mode)

        except telebot.apihelper.ApiTelegramException as e:
            error_message = str(e).lower()
            if any(phrase in error_message for phrase in [
                "bot was blocked", 
                "bot was kicked",
                "chat not found"
            ]):
                logging.warning(f"Чат {chat_id} недоступен: {str(e)}")
                broken_chats.add(chat_id)
            else:
                logging.error(f"Ошибка в чате {chat_id}: {str(e)}")

        except Exception as e:
            logging.critical(f"Неизвестная ошибка: {str(e)}")

#Удаляем недоступные чаты
    if broken_chats:
        active_chats.difference_update(broken_chats)
        logging.info(f"Удалены заблокированные чаты: {broken_chats}")

#Обработчик команды  /start
@bot.message_handler(commands=['start'])
def start(message):
    try:
        active_chats.add(message.chat.id)
        bot.send_message(message.chat.id, "Вы подписались на уведомления!")
    except Exception as e:
        logging.error(f"Ошибка в команде /start: {str(e)}")

#Импорт и настройка планировщика
from scheduler import setup_scheduler
setup_scheduler(send_to_all)

bot.infinity_polling()