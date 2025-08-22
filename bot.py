import logging
import telebot
import re
import schedule
from config import TOKEN
from scheduler import setup_scheduler, remove_scheduled_job

#Настройка бота
bot = telebot.TeleBot(TOKEN)

active_chats = set()
user_states = dict()

#События по умолчанию
schedules_dict = {
    "09:30": "Кто опоздал на работу — тот <s>пыська</s> плохой человек!", 
    "11:55": "Пора идти на обед!", 
    "16:25": "Пора идти за водой!"
    }

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
                "chat not found",
                "user is deactivated"
            ]):
                logging.warning(f"Чат {chat_id} недоступен: {str(e)}")
                broken_chats.add(chat_id)
            else:
                logging.error(f"Ошибка в чате {chat_id}: {str(e)}")

        except Exception as e:
            logging.critical(f"Неизвестная ошибка: {str(e)}")

#Отправка уведомления по конкретному времени
def send_scheduled_notification(time_key):
    if time_key in schedules_dict:
        message_text = schedules_dict[time_key]
        #Отправляем только если есть активные чаты
        if active_chats:
            send_to_all(message_text)
        else:
            logging.warning(f"Нет активных чатов для отправки уведомления {time_key}")

#Добавляем изначальные события в шедулер
for time_key in schedules_dict:
    schedule.every().day.at(time_key).do(send_scheduled_notification, time_key)

#Проверяем формат для ввода нового события: HH:MM Текст
def is_valid_schedule_input(text):
    pattern = r'^([0-1][0-9]|2[0-3]):([0-5][0-9])\s+.+$'
    if not re.match(pattern, text):
        return False
    return True

#Проверяем формат ввода для удаления события: HH:MM
def is_valid_remove_input(text):
    pattern = r'^([0-1][0-9]|2[0-3]):([0-5][0-9])$'
    if not re.match(pattern, text):
        return False
    return True

#Обработчик команды  /start
@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id = message.from_user.id
        user_states.pop(user_id, None)

        active_chats.add(message.chat.id)
        bot.send_message(message.chat.id, "Вы подписались на уведомления!")
        logging.info(f"Пользователь {user_id} подписался на уведомления")
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

        #Обработка прерывания командами
        if message.text.startswith('/'):
            user_states.pop(user_id, None)
            bot.process_new_messages([message]) 
            return
        
        try:
            if is_valid_schedule_input(message.text):
                parts = message.text.split()
                time = parts[0]
                text = ' '.join(parts[1:])
                schedules_dict[time] = text
                #Создаем задание в планировщике
                schedule.every().day.at(time).do(send_scheduled_notification, time)

                bot.send_message(message.chat.id, f"Новое событие добавлено: {time} {text}", parse_mode="HTML")
                logging.info(f"Добавлено новое событие: {time} {text}")
            else:
                bot.send_message(message.chat.id, "Неправильный формат. Нужно: HH:MM Текст. Введите заново")
                bot.register_next_step_handler(message, add_new_schedule)
        
        except ValueError as e:
            bot.send_message(message.chat.id, f"Ошибка времени: {e}")    
        except Exception as e:
            bot.send_message(message.chat.id, f"Ошибка: {e}")
        finally:
            user_states.pop(user_id, None)

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

    #Обработка прерывания командами
    if message.text.startswith('/'):
        user_states.pop(user_id, None)
        bot.process_new_messages([message])
        return
    
    try:
        if not is_valid_remove_input(message.text):
            bot.send_message(message.chat.id, "Неправильный формат. Нужно: HH:MM. Введите заново")
            bot.register_next_step_handler(message, delete_schedule)
            return
            
        delete_time = message.text
        
        #Проверяем существование события
        if delete_time not in schedules_dict:
            bot.send_message(message.chat.id, f"Событие на {delete_time} не найдено.")
            return
        
        #Удаляем из планировщика
        remove_scheduled_job(delete_time)
        
        del schedules_dict[delete_time]
        
        bot.send_message(message.chat.id, f"Событие на {delete_time} удалено")
        logging.info(f"Удалено событие: {delete_time}")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при у    далении: {e}")
    finally:
        user_states.pop(user_id, None)

#Обработка команды "Показать все события"
@bot.message_handler(commands=['list'])
def show_reminders_list(message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)

    if not schedules_dict:
        bot.send_message(message.chat.id, "Список событий пуст")
        return
    
    result = "Ваши напоминания:\n\n"
    for time, event in sorted(schedules_dict.items()):
        result += f"{time} : {event}\n"
    
    bot.send_message(message.chat.id, result, parse_mode='HTML')

#Импорт и настройка планировщика
setup_scheduler(send_to_all)
bot.infinity_polling()

