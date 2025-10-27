import logging
import telebot
import re
import schedule
from config import TOKEN
from scheduler import setup_scheduler, remove_scheduled_job
from database import db

bot = telebot.TeleBot(TOKEN)

jobs_dict = dict()
    
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
    if db.event_exists(chat_id, time_key):
        events = db.get_events_by_chat(chat_id)
        message_text = events.get(time_key, "")
        send_to_chat(message_text, chat_id, parse_mode='HTML')

def is_valid_input(text, context):
    if context == 'add':
        #Для добавления: HH:MM Текст
        pattern = r'^([0-1][0-9]|2[0-3]):([0-5][0-9])\s+.+$'
    elif context == 'remove':
        #Для удаления: HH:MM
        pattern = r'^([0-1][0-9]|2[0-3]):([0-5][0-9])$'
    else:
        return False
        
    return re.match(pattern, text) is not None

def restore_scheduled_jobs():
    logging.info("Восстановление заданий планировщика из БД")
    schedule.clear()
    jobs_dict.clear()
    logging.info("Старые задания планировщика очищены")

    all_events = db.get_all_events()  
    for chat_id, events in all_events.items():
        if chat_id not in jobs_dict:
            jobs_dict[chat_id] = {}
        for time_key in events.keys():
            job = schedule.every().day.at(time_key).do(
                send_scheduled_notification, 
                chat_id, 
                time_key
            )
            jobs_dict[chat_id][time_key] = job
            logging.info(f"Восстановлено задание: chat_id={chat_id}, time={time_key}")
            
    logging.info("Задания планировщика восстановлены")

@bot.message_handler(commands=['start'])
def start(message):
    try:
        chat_id = message.chat.id

        #Добавление событий по умолчанию
        if not db.get_events_by_chat(chat_id):
            default_events = {
                "09:30": "Кто опоздал на работу — тот <s>пыська</s> плохой человек!",
                "11:55": "Пора идти на обед!",
                "15:55": "Пора идти за водой!"
            }

            for time_key, text in default_events.items():
                db.add_event(chat_id, time_key, text)
                job = schedule.every().day.at(time_key).do(
                        send_scheduled_notification, 
                        chat_id, 
                        time_key
                    )
                if chat_id not in jobs_dict:
                    jobs_dict[chat_id] = dict()
                jobs_dict[chat_id][time_key] = job
                logging.info(f"Добавлено событие по умолчанию: {time_key}")
        
        events = db.get_events_by_chat(chat_id)
        for time_key in events.keys():
            if chat_id not in jobs_dict:
                jobs_dict[chat_id] = dict()
            if time_key not in jobs_dict[chat_id]:
                job = schedule.every().day.at(time_key).do(
                    send_scheduled_notification,
                    chat_id,
                    time_key
                )
                jobs_dict[chat_id][time_key] = job
                logging.info(f"Загружено существующее событие: {time_key}")
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

@bot.message_handler(commands=['add'])
def add_new_reminder(message):
    bot.send_message(message.chat.id, "Введите новое событие в формате: HH:MM Текст")
    bot.register_next_step_handler(message, add_new_schedule)

#Обработка ввода нового события
def add_new_schedule(message):
        chat_id = message.chat.id

        #Обработка прерывания командами
        if message.text.startswith('/'):
            bot.process_new_messages([message]) 
            return
        
        try:
            if is_valid_input(message.text, 'add'):
                parts = message.text.split()
                time = parts[0]
                text = ' '.join(parts[1:])

                db.add_event(chat_id, time, text)

                #Создаем задание в планировщике
                job = schedule.every().day.at(time).do(send_scheduled_notification, chat_id, time)

                #Создание пустого расписания если такое отсутствует
                if chat_id not in jobs_dict:
                    jobs_dict[chat_id] = dict()
                jobs_dict[chat_id][time] = job

                bot.send_message(chat_id, f"Новое событие добавлено: {time} {text}", parse_mode="HTML")
                logging.info(f"Добавлено новое событие: chat_id={chat_id}, time={time}")
            else:
                bot.send_message(message.chat.id, "Неправильный формат. Нужно: HH:MM Текст. Введите заново")
                bot.register_next_step_handler(message, add_new_schedule)
        
        except ValueError as e:
            bot.send_message(chat_id, f"Ошибка времени: {e}")    
        except Exception as e:
            bot.send_message(chat_id, f"Ошибка: {e}")

@bot.message_handler(commands=['remove'])
def remove_reminder(message):
    bot.send_message(message.chat.id, "Введите время события, которое нужно удалить в формате HH:MM")
    bot.register_next_step_handler(message, delete_schedule)

#Обработка удаления события
def delete_schedule(message):
    chat_id = message.chat.id

    #Обработка прерывания командами
    if message.text.startswith('/'):
        bot.process_new_messages([message])
        return
    
    try:
        if not is_valid_input(message.text, 'remove'):
            bot.send_message(chat_id, "Неправильный формат. Нужно: HH:MM. Введите заново")
            bot.register_next_step_handler(message, delete_schedule)
            return
            
        delete_time = message.text

        #Проверяем существование события
        if not db.event_exists(chat_id, delete_time):
            bot.send_message(chat_id, f"Событие на {delete_time} не найдено")
            return
        
        #Удаляем из базы данных
        db.remove_event(chat_id, delete_time)

        #Удаляем из планировщика
        if remove_scheduled_job(jobs_dict, chat_id, delete_time):
            logging.info(f"Удалена задача на {delete_time} в чате {chat_id}")
        else:
            logging.warning(f"Задача на {delete_time} не найдена в планировщике для чата {chat_id}")   
        
        bot.send_message(chat_id, f"Событие на {delete_time} удалено")
        logging.info(f"Удалено событие: {delete_time}")
            
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при удалении: {e}")

@bot.message_handler(commands=['list'])
def show_reminders_list(message):
    chat_id = message.chat.id

    events = db.get_events_by_chat(chat_id)
    if not events:
        bot.send_message(chat_id, "Список событий пуст")
        return
    
    result = "Ваши напоминания:\n\n"
    for time, event in sorted(events.items()):
        result += f"{time} : {event}\n"
    
    bot.send_message(chat_id, result, parse_mode='HTML')

@bot.message_handler(commands=['help'])
def show_help(message):
    chat_id = message.chat.id

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
restore_scheduled_jobs()
setup_scheduler()
bot.infinity_polling()

