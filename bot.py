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
schedules_dict = {
    "private": {},
    "groups": {} 
}
jobs_dict = {
    "private": {},
    "groups": {} 
}

#Определяет тип чата и возвращает соответствующий контекст
def get_chat_context(message):
    chat_type = message.chat.type
    chat_id = message.chat.id
    user_id = message.from_user.id

    if chat_type == "private":
        return {
            "type": "private",
            "storage_key": user_id,
            "chat_id": chat_id,
            "user_id": user_id
        }
    else:
        return {
            "type": "group",
            "storage_key": chat_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "group_name": message.chat.title
        }
    
#Возвращает соответствующие словари для данного контекста
def get_storage_dicts(context):
    storage_type = "groups" if context["type"] == "group" else "private"
    return schedules_dict[storage_type], jobs_dict[storage_type]

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
def send_scheduled_notification(context, time_key):
    storage_type = 'groups' if context['type'] == 'group' else 'private'
    storage_key = context['storage_key']
    chat_id = context["chat_id"]
    if storage_key in schedules_dict[storage_type] and time_key in schedules_dict[storage_type][storage_key]:
        message_text = schedules_dict[storage_type][storage_key][time_key]
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

        context =  get_chat_context(message)
        s_dict, j_dict = get_storage_dicts(context)

        active_chats.add(chat_id)

        #Добавление событий по умолчанию
        if context["storage_key"] not in s_dict:
            s_dict[context["storage_key"]] = {
                "09:30": "Кто опоздал на работу — тот <s>пыська</s> плохой человек!",
                "11:55": "Пора идти на обед!",
                "15:55": "Пора идти за водой!"
            }
        if context["storage_key"] not in j_dict:
            j_dict[context["storage_key"]] = {}
            for time_key in ["09:30", "11:55", "15:55"]:
                job = schedule.every().day.at(time_key).do(
                    send_scheduled_notification, 
                    context, 
                    time_key
                )
                j_dict[context["storage_key"]][time_key] = job

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
        context = get_chat_context(message)
        s_dict, j_dict = get_storage_dicts(context)
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
                if context["storage_key"] not in s_dict:
                    s_dict[context["storage_key"]] = dict()
                if context["storage_key"] not in j_dict:
                    j_dict[context["storage_key"]] = dict()

                s_dict[context["storage_key"]][time] = text

                #Создаем задание в планировщике
                job = schedule.every().day.at(time).do(send_scheduled_notification, context, time)

                j_dict[context["storage_key"]][time] = job
                bot.send_message(context["chat_id"], f"Новое событие добавлено: {time} {text}", parse_mode="HTML")
                user_states.pop(user_id, None)
            else:
                bot.send_message(message.chat.id, "Неправильный формат. Нужно: HH:MM Текст. Введите заново")
                bot.register_next_step_handler(message, add_new_schedule)
        
        except ValueError as e:
            bot.send_message(context["chat_id"], f"Ошибка времени: {e}")    
        except Exception as e:
            bot.send_message(context["chat_id"], f"Ошибка: {e}")

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
    context = get_chat_context(message)
    s_dict, j_dict = get_storage_dicts(context)

    #Обработка прерывания командами
    if message.text.startswith('/'):
        user_states.pop(user_id, None)
        bot.process_new_messages([message])
        return
    
    try:
        if not is_valid_input(message, message.text):
            bot.send_message(message.chat.id, "Неправильный формат. Нужно: HH:MM. Введите заново")
            bot.register_next_step_handler(message, delete_schedule)
            return
            
        delete_time = message.text
        
        #Проверяем существование события
        if context['storage_key'] not in s_dict or delete_time not in s_dict[context['storage_key']]:
            bot.send_message(message.chat.id, f"Событие на {delete_time} не найдено.")
            return
        
        #Удаляем из планировщика
        if remove_scheduled_job(j_dict, context['storage_key'], delete_time):
            logging.info(f"Удалена задача на {delete_time}")
        else:
            logging.warning(f"Задача на {delete_time} не найдена в планировщике")   
        
        del s_dict[context['storage_key']][delete_time]
        
        bot.send_message(message.chat.id, f"Событие на {delete_time} удалено")
        user_states.pop(user_id, None)
        logging.info(f"Удалено событие: {delete_time}")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при удалении: {e}")


#Обработка команды "Показать все события"
@bot.message_handler(commands=['list'])
def show_reminders_list(message):
    user_id = message.from_user.id
    context = get_chat_context(message)
    s_dict, _ = get_storage_dicts(context)
    user_states.pop(user_id, None)

    if context['storage_key'] not in s_dict or not s_dict[context['storage_key']]:
        bot.send_message(message.chat.id, "Список событий пуст")
        return
    
    result = "Ваши напоминания:\n\n"
    for time, event in sorted(s_dict[context['storage_key']].items()):
        result += f"{time} : {event}\n"
    
    bot.send_message(message.chat.id, result, parse_mode='HTML')

@bot.message_handler(commands=['help'])
def show_help(message):
    user_id = message.from_user.id
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

    bot.send_message(message.chat.id, help_text, parse_mode='HTML')

#Импорт и настройка планировщика
setup_scheduler(send_to_chat)
bot.infinity_polling()

