import logging
import telebot
import re
import schedule
from config import TOKEN
from scheduler import setup_scheduler, remove_scheduled_job

bot = telebot.TeleBot(TOKEN)

active_chats = set()
user_states = dict()

#Разделение личных и групповых чатов
schedules_dict = dict()
jobs_dict = dict()
    
#Отправка сообщения чату
def send_to_chat(text, chat_id, parse_mode=None):
    try:
        bot.send_message(chat_id, text, parse_mode=parse_mode)
    except telebot.apihelper.ApiTelegramException as e:
        error_message = str(e).lower()
        if any(phrase in error_message for phrase in [
            "bot was blocked", 
            "bot was kicked",
            "chat not found",
            "user is deactivated"
        ]):
            logging.warning(f"Чат {chat_id} недоступен: {str(e)}")
        else:
            logging.error(f"Ошибка в чате {chat_id}: {str(e)}")

    except Exception as e:
        logging.critical(f"Неизвестная ошибка: {str(e)}")

#Отправка уведомления по конкретному времени
def send_scheduled_notification(chat_id, time_key):
    if chat_id in schedules_dict and time_key in schedules_dict[chat_id]:
        message_text = schedules_dict[chat_id][time_key]
        #Отправляем только если есть активные чаты
        if chat_id in active_chats:
            send_to_chat(message_text, chat_id, parse_mode='HTML')
        else:
            logging.warning(f"Чат {chat_id} неактивен для отправки уведомления {time_key}")

def is_valid_input(message, text):
    user_id = message.from_user.id
        
    if user_states[user_id] == "adding_event":
        pattern = r'^([0-1][0-9]|2[0-3]):([0-5][0-9])\s+.+$'
    elif user_states[user_id] == "removing_event":
        pattern = r'^([0-1][0-9]|2[0-3]):([0-5][0-9])$'
    if not re.match(pattern, text):
        return False
    return True

#Обработчик команды  /start
@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        user_states.pop(user_id, None)
        active_chats.add(chat_id)

        #Добавление событий по умолчанию
        if chat_id not in schedules_dict:
            schedules_dict[chat_id] = {
                "09:30": "Кто опоздал на работу — тот <s>пыська</s> плохой человек!",
                "11:55": "Пора идти на обед!",
                "15:55": "Пора идти за водой!"
            }
        if chat_id not in jobs_dict:
            jobs_dict[chat_id] = dict()
            for time_key in ["09:30", "11:55", "15:55"]:
                job = schedule.every().day.at(time_key).do(
                    send_scheduled_notification, 
                    chat_id, 
                    time_key
                )
                jobs_dict[chat_id][time_key] = job

        help_text = """
Бот для создания напоминаний

<b>Команды</b>
/start - подписаться на уведомления
/add - добавить напоминание
/remove - удалить напоминание
/list - показать все действующие напоминания
/help - помощь
"""
        bot.send_message(chat_id, help_text, parse_mode='HTML')
        bot.send_message(chat_id, "Вы подписались на уведомления!")
        logging.info(f"Чат {chat_id} подписался на уведомления")
    except Exception as e:
        logging.error(f"Ошибка в команде /start: {str(e)}")

#Обработка команды /add
@bot.message_handler(commands=['add'])
def add_new_reminder(message):
    user_id = message.from_user.id
    user_states[user_id] = 'adding_event'
    bot.send_message(message.chat.id, "Введите новое событие в формате: HH:MM Текст")
    bot.register_next_step_handler(message, add_new_schedule)

#Обработка ввода нового события
def add_new_schedule(message):
        user_id = message.from_user.id
        chat_id = message.chat.id

        #Обработка прерывания командами
        if message.text.startswith('/'):
            user_states.pop(user_id, None)
            bot.process_new_messages([message]) 
            return
        
        try:
            if is_valid_input(message, message.text):
                parts = message.text.split()
                time = parts[0]
                text = ' '.join(parts[1:])

                #Создание пустого расписания если такое отсутствует
                if chat_id not in schedules_dict:
                    schedules_dict[chat_id] = dict()
                if chat_id not in jobs_dict:
                    jobs_dict[chat_id] = dict()

                schedules_dict[chat_id][time] = text

                #Создаем задание в планировщике
                job = schedule.every().day.at(time).do(send_scheduled_notification, chat_id, time)

                jobs_dict[chat_id][time] = job
                bot.send_message(chat_id, f"Новое событие добавлено: {time} {text}", parse_mode="HTML")
                user_states.pop(user_id, None)
            else:
                bot.send_message(message.chat.id, "Неправильный формат. Нужно: HH:MM Текст. Введите заново")
                bot.register_next_step_handler(message, add_new_schedule)
        
        except ValueError as e:
            bot.send_message(chat_id, f"Ошибка времени: {e}")    
        except Exception as e:
            bot.send_message(chat_id, f"Ошибка: {e}")

#Обработка команды /remove
@bot.message_handler(commands=['remove'])
def remove_reminder(message):
    user_id = message.from_user.id
    user_states[user_id] = 'removing_event'
    bot.send_message(message.chat.id, "Введите время события, которое нужно удалить в формате HH:MM")
    bot.register_next_step_handler(message, delete_schedule)

#Обработка удаления события
def delete_schedule(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    #Обработка прерывания командами
    if message.text.startswith('/'):
        user_states.pop(user_id, None)
        bot.process_new_messages([message])
        return
    
    try:
        if not is_valid_input(message, message.text):
            bot.send_message(chat_id, "Неправильный формат. Нужно: HH:MM. Введите заново")
            bot.register_next_step_handler(message, delete_schedule)
            return
            
        delete_time = message.text
        
        #Проверяем существование события
        if chat_id not in schedules_dict or delete_time not in schedules_dict[chat_id]:
            bot.send_message(chat_id, f"Событие на {delete_time} не найдено.")
            return
        
        #Удаляем из планировщика
        if remove_scheduled_job(jobs_dict, chat_id, delete_time):
            logging.info(f"Удалена задача на {delete_time} в чате {chat_id}")
        else:
            logging.warning(f"Задача на {delete_time} не найдена в планировщике для чата {chat_id}")   
        
        del schedules_dict[chat_id][delete_time]
        
        bot.send_message(chat_id, f"Событие на {delete_time} удалено")
        user_states.pop(user_id, None)
        logging.info(f"Удалено событие: {delete_time}")
            
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при удалении: {e}")


#Обработка команды "Показать все события"
@bot.message_handler(commands=['list'])
def show_reminders_list(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_states.pop(user_id, None)

    if chat_id not in schedules_dict or not schedules_dict[chat_id]:
        bot.send_message(chat_id, "Список событий пуст")
        return
    
    result = "Ваши напоминания:\n\n"
    for time, event in sorted(schedules_dict[chat_id].items()):
        result += f"{time} : {event}\n"
    
    bot.send_message(chat_id, result, parse_mode='HTML')

@bot.message_handler(commands=['help'])
def show_help(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_states.pop(user_id, None)
    help_text = """
Бот для создания напоминаний

<b>Команды</b>
/start - подписаться на уведомления
/add - добавить напоминание
/remove - удалить напоминание
/list - показать все действующие напоминания
/help - помощь
"""

    bot.send_message(chat_id, help_text, parse_mode='HTML')

#Импорт и настройка планировщика
setup_scheduler(send_to_chat)
bot.infinity_polling()

