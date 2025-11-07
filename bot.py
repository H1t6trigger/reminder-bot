import logging
import telebot
import re
import schedule
from config import TOKEN
from scheduler import setup_scheduler, remove_scheduled_job
from database import db

bot = telebot.TeleBot(TOKEN)
jobs_dict = {}

def send_to_chat(text, chat_id, parse_mode=None, thread_id=None):
    """Отправка сообщения с поддержкой тем (message_thread_id)"""
    try:
        bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            message_thread_id=thread_id
        )
    except telebot.apihelper.ApiTelegramException as e:
        error_msg = str(e).lower()
        if any(phrase in error_msg for phrase in [
            "bot was blocked", "bot was kicked", "chat not found", "user is deactivated"
        ]):
            logging.warning(f"Чат {chat_id} недоступен: {e}")
        else:
            logging.error(f"Ошибка отправки в чат {chat_id}: {e}")
    except Exception as e:
        logging.critical(f"Неизвестная ошибка: {e}")

def send_scheduled_notification(chat_id, time_key):
    """Отправка запланированного уведомления с учётом темы чата"""
    if db.event_exists(chat_id, time_key):
        events = db.get_events_by_chat(chat_id)
        message_text = events.get(time_key, "")
        thread_id = db.get_chat_thread_id(chat_id)
        send_to_chat(message_text, chat_id, parse_mode='HTML', thread_id=thread_id)

def is_valid_input(text, context):
    if context == 'add':
        return re.match(r'^([0-1][0-9]|2[0-3]):([0-5][0-9])\s+.+$', text) is not None
    elif context == 'remove':
        return re.match(r'^([0-1][0-9]|2[0-3]):([0-5][0-9])$', text) is not None
    return False

def restore_scheduled_jobs():
    logging.info("Восстановление заданий из БД")
    schedule.clear()
    jobs_dict.clear()

    all_events = db.get_all_events()
    for chat_id, events in all_events.items():
        if chat_id not in jobs_dict:
            jobs_dict[chat_id] = {}
        for time_key in events:
            job = schedule.every().day.at(time_key).do(
                send_scheduled_notification, chat_id, time_key
            )
            jobs_dict[chat_id][time_key] = job
            logging.info(f"Восстановлено задание: chat_id={chat_id}, time={time_key}")
    logging.info("Восстановление завершено")

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    thread_id = message.message_thread_id
    db.set_chat_thread_id(chat_id, thread_id)

    # Добавление событий по умолчанию, если их нет
    if not db.get_events_by_chat(chat_id):
        default_events = {
            "09:30": "Кто опоздал на работу — тот <s>пыська</s> плохой человек!",
            "11:55": "Пора идти на обед!",
            "15:55": "Пора идти за водой!"
        }
        for time_key, text in default_events.items():
            db.add_event(chat_id, time_key, text)

    # Загрузка всех событий в планировщик
    events = db.get_events_by_chat(chat_id)
    if chat_id not in jobs_dict:
        jobs_dict[chat_id] = {}
    for time_key in events:
        if time_key not in jobs_dict[chat_id]:
            job = schedule.every().day.at(time_key).do(
                send_scheduled_notification, chat_id, time_key
            )
            jobs_dict[chat_id][time_key] = job

    help_text = """
Бот для создания напоминаний

<b>Команды</b>
/start - подписаться на уведомления
/add - добавить напоминание
/remove - удалить напоминание
/list - показать все напоминания
/help - помощь
"""
    send_to_chat(help_text, chat_id, parse_mode='HTML', thread_id=thread_id)
    send_to_chat("Вы подписались на уведомления!", chat_id, thread_id=thread_id)
    logging.info(f"Чат {chat_id} (thread={thread_id}) инициализирован")

@bot.message_handler(commands=['add'])
def add_new_reminder(message):
    chat_id = message.chat.id
    thread_id = message.message_thread_id
    db.set_chat_thread_id(chat_id, thread_id)
    send_to_chat("Введите новое событие в формате: HH:MM Текст", chat_id, thread_id=thread_id)
    bot.register_next_step_handler(message, add_new_schedule)

def add_new_schedule(message):
    chat_id = message.chat.id
    thread_id = db.get_chat_thread_id(chat_id)

    if message.text.startswith('/'):
        bot.process_new_messages([message])
        return

    if is_valid_input(message.text, 'add'):
        parts = message.text.split(maxsplit=1)
        time, text = parts[0], parts[1]
        db.add_event(chat_id, time, text)

        if chat_id not in jobs_dict:
            jobs_dict[chat_id] = {}
        if time not in jobs_dict[chat_id]:
            job = schedule.every().day.at(time).do(send_scheduled_notification, chat_id, time)
            jobs_dict[chat_id][time] = job

        send_to_chat(f"Новое событие добавлено: {time} {text}", chat_id, parse_mode="HTML", thread_id=thread_id)
        logging.info(f"Добавлено событие: chat_id={chat_id}, time={time}")
    else:
        send_to_chat("Неправильный формат. Нужно: HH:MM Текст. Введите заново", chat_id, thread_id=thread_id)
        bot.register_next_step_handler(message, add_new_schedule)

@bot.message_handler(commands=['remove'])
def remove_reminder(message):
    chat_id = message.chat.id
    thread_id = message.message_thread_id
    db.set_chat_thread_id(chat_id, thread_id)
    send_to_chat("Введите время события для удаления (HH:MM):", chat_id, thread_id=thread_id)
    bot.register_next_step_handler(message, delete_schedule)

def delete_schedule(message):
    chat_id = message.chat.id
    thread_id = db.get_chat_thread_id(chat_id)

    if message.text.startswith('/'):
        bot.process_new_messages([message])
        return

    if not is_valid_input(message.text, 'remove'):
        send_to_chat("Неправильный формат. Нужно: HH:MM", chat_id, thread_id=thread_id)
        bot.register_next_step_handler(message, delete_schedule)
        return

    time_key = message.text
    if not db.event_exists(chat_id, time_key):
        send_to_chat(f"Событие на {time_key} не найдено", chat_id, thread_id=thread_id)
        return

    db.remove_event(chat_id, time_key)
    if remove_scheduled_job(jobs_dict, chat_id, time_key):
        logging.info(f"Задача удалена: {time_key} в чате {chat_id}")

    send_to_chat(f"Событие на {time_key} удалено", chat_id, thread_id=thread_id)

@bot.message_handler(commands=['list'])
def show_reminders_list(message):
    chat_id = message.chat.id
    thread_id = message.message_thread_id
    db.set_chat_thread_id(chat_id, thread_id)

    events = db.get_events_by_chat(chat_id)
    if not events:
        send_to_chat("Список напоминаний пуст", chat_id, thread_id=thread_id)
        return

    text = "Ваши напоминания:\n\n" + "\n".join(f"{t} : {m}" for t, m in sorted(events.items()))
    send_to_chat(text, chat_id, parse_mode='HTML', thread_id=thread_id)

@bot.message_handler(commands=['help'])
def show_help(message):
    chat_id = message.chat.id
    thread_id = message.message_thread_id
    db.set_chat_thread_id(chat_id, thread_id)

    help_text = """
Бот для создания напоминаний

<b>Команды</b>
/start - подписаться на уведомления
/add - добавить напоминание
/remove - удалить напоминание
/list - показать все напоминания
/help - помощь
"""
    send_to_chat(help_text, chat_id, parse_mode='HTML', thread_id=thread_id)

# Запуск
if __name__ == '__main__':
    restore_scheduled_jobs()
    setup_scheduler()
    bot.infinity_polling()