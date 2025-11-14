import logging
import telebot
import re
from config import TOKEN
from database import db, Database
from scheduler import Scheduler, DAYS_MAP, REVERSE_DAYS_MAP


class ReminderBot:
    def __init__(self, token, db: Database):
        self.bot = telebot.TeleBot(token)
        self.db = db
        self.scheduler = Scheduler()
        self._register_handlers()
        self.jobs_dict = {} 
    
    def send_to_chat(self, text, chat_id, parse_mode=None, thread_id=None):
        """Отправка сообщения с поддержкой тем (message_thread_id)"""
        try:
            self.bot.send_message(
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
            
    def send_scheduled_notification(self, chat_id, time_key):
        if self.db.event_exists(chat_id, time_key):
            events = self.db.get_events_by_chat(chat_id)
            event = events.get(time_key)
            if not event:
                return
            message_text = event["message"] 
            thread_id = self.db.get_chat_thread_id(chat_id)
            self.send_to_chat(message_text, chat_id, parse_mode='HTML', thread_id=thread_id)


    def is_valid_input(self, text, context):
        if context == 'add':
            return re.match(r'^([0-1][0-9]|2[0-3]):([0-5][0-9])\s+.+$', text) is not None
        elif context == 'remove':
            return re.match(r'^([0-1][0-9]|2[0-3]):([0-5][0-9])$', text) is not None
        return False

    def restore_scheduled_jobs(self):
        self.scheduler.restore_jobs(self.db.get_all_events, self.send_scheduled_notification)
        
    def _register_handlers(self):
        self.bot.message_handler(commands=['start'])(self.start)
        self.bot.message_handler(commands=['add'])(self.add_new_reminder)
        self.bot.message_handler(commands=['remove'])(self.remove_reminder)
        self.bot.message_handler(commands=['list'])(self.show_reminders_list)
        self.bot.message_handler(commands=['help'])(self.show_help)
    
    def start(self, message):
        chat_id = message.chat.id
        thread_id = message.message_thread_id
        self.db.set_chat_thread_id(chat_id, thread_id)

        # Добавление событий по умолчанию, если их нет
        if not self.db.get_events_by_chat(chat_id):
            default_days_list = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
            default_events = {
                "09:30": "Кто опоздал на работу — тот <s>пыська</s> плохой человек!",
                "11:55": "Пора идти на обед!",
                "15:55": "Пора идти за водой!"  
            }
            for time_key, text in default_events.items():
                self.db.add_event(chat_id, time_key, text,  ",".join(default_days_list) if default_days_list else None)

        # Загрузка всех событий в планировщик
        events = self.db.get_events_by_chat(chat_id)
        for time_key in events:
            self.scheduler.add_job(chat_id, time_key, self.send_scheduled_notification)

        help_text = """
    Бот для создания напоминаний

<b>Команды</b>
/start - подписаться на уведомления
/add - добавить напоминание
/remove - удалить напоминание
/list - показать все напоминания
/help - помощь
"""
        self.send_to_chat(help_text, chat_id, parse_mode='HTML', thread_id=thread_id)
        self.send_to_chat("Вы подписались на уведомления!", chat_id, thread_id=thread_id)
        logging.info(f"Чат {chat_id} (thread={thread_id}) инициализирован")
        
    def add_new_reminder(self, message):
        chat_id = message.chat.id
        thread_id = message.message_thread_id
        self.db.set_chat_thread_id(chat_id, thread_id)
        self.send_to_chat("Введите новое событие в формате: HH:MM Текст", chat_id, thread_id=thread_id)
        self.bot.register_next_step_handler(message, self.add_new_schedule)
        
    def add_new_schedule(self, message):
        chat_id = message.chat.id
        thread_id = self.db.get_chat_thread_id(chat_id)

        if message.text.startswith('/'):
            self.bot.process_new_messages([message])
            return

        if self.is_valid_input(message.text, 'add'):
            time_key, text = message.text.split(maxsplit=1)
            self.send_to_chat(
                "Укажите дни недели (например: понедельник,вторник,четверг или понедельник-пятница или все):", 
                chat_id, 
                thread_id=thread_id
            )
            self.bot.register_next_step_handler(
                message,
                lambda msg: self.ask_days(msg, time_key, text)
            )
        else:
            self.send_to_chat(
                "Неправильный формат. Нужно: HH:MM Текст. Введите заново",
                chat_id,
                thread_id=thread_id
            )
            self.bot.register_next_step_handler(message, self.add_new_schedule)

    
    def ask_days(self, message, time_key, text):
        chat_id = message.chat.id
        thread_id = self.db.get_chat_thread_id(chat_id)

        raw = message.text.strip().lower()

        if raw == 'все':
            days_list = None
            days_display = 'каждый день'
        elif '-' in raw:
            start, end = [d.strip() for d in raw.split('-')]
            try:
                days_values = list(DAYS_MAP.values())
                i1, i2 = days_values.index(DAYS_MAP[start]), days_values.index(DAYS_MAP[end])
                if i1 <= i2:
                    days_list = days_values[i1:i2+1]
                else:
                    days_list = days_values[i1:] + days_values[:i2+1]
                days_display = ", ".join(REVERSE_DAYS_MAP[d] for d in days_list)
            except KeyError:
                self.send_to_chat(
                    "Некорректный диапазон дней. Попробуйте ещё раз.",
                    chat_id,
                    thread_id=thread_id
                )
                self.bot.register_next_step_handler(
                    message,
                    lambda msg: self.ask_days(msg, time_key, text)
                )
                return
        else:
            days_list = [DAYS_MAP[d.strip()] for d in raw.split(',') if d.strip() in DAYS_MAP]
            days_display = ", ".join(REVERSE_DAYS_MAP[d] for d in days_list) if days_list else 'каждый день'

        # Сохраняем событие и создаём задачу
        self.db.add_event(chat_id, time_key, text, ",".join(days_list) if days_list else None)
        self.scheduler.add_job(chat_id, time_key, self.send_scheduled_notification, days_list)

        self.send_to_chat(
            f"Напоминание добавлено: {time_key} {text}\nДни: {days_display}",
            chat_id,
            thread_id=thread_id
        )
        logging.info(
            f"Добавлено событие: chat_id={chat_id}, time={time_key}, text={text}, days={days_display}"
        )

        
    def remove_reminder(self, message):
        chat_id = message.chat.id
        thread_id = message.message_thread_id
        self.db.set_chat_thread_id(chat_id, thread_id)
        self.send_to_chat("Введите время события для удаления (HH:MM):", chat_id, thread_id=thread_id)
        self.bot.register_next_step_handler(message, self.delete_schedule)

    def delete_schedule(self, message):
        chat_id = message.chat.id
        thread_id = self.db.get_chat_thread_id(chat_id)

        if message.text.startswith('/'):
            self.bot.process_new_messages([message])
            return

        if not self.is_valid_input(message.text, 'remove'):
            self.send_to_chat("Неправильный формат. Нужно: HH:MM", chat_id, thread_id=thread_id)
            self.bot.register_next_step_handler(message, self.delete_schedule)
            return

        time_key = message.text
        if not self.db.event_exists(chat_id, time_key):
            self.send_to_chat(f"Событие на {time_key} не найдено", chat_id, thread_id=thread_id)
            return

        # Получаем дни события для отображения
        events = self.db.get_events_by_chat(chat_id)
        event_data = events.get(time_key, {})
        days = event_data.get('days')
        if days:
            days_display = ", ".join(REVERSE_DAYS_MAP[d] for d in days.split(','))
        else:
            days_display = 'каждый день'

        # Удаляем из БД и планировщика
        self.db.remove_event(chat_id, time_key)
        self.scheduler.remove_job(chat_id, time_key)

        self.send_to_chat(f"Событие на {time_key} удалено ({days_display})", chat_id, thread_id=thread_id)
        logging.info(f"Удалено событие: chat_id={chat_id}, time={time_key}, days={days_display}")


        
    def show_reminders_list(self, message):
        chat_id = message.chat.id
        thread_id = message.message_thread_id
        self.db.set_chat_thread_id(chat_id, thread_id)

        events = self.db.get_events_by_chat(chat_id)
        if not events:
            self.send_to_chat("Список напоминаний пуст", chat_id, thread_id=thread_id)
            return

        lines = []
        for time_key, data in sorted(events.items()):
            text = data['message']
            days = data.get('days')
            if days:
                current_days = days.split(',')
                if len(current_days) > 1:
                    days_display = f"{REVERSE_DAYS_MAP[current_days[0]]} - {REVERSE_DAYS_MAP[current_days[len(current_days) - 1]]}"
                    #days_display = ", ".join(REVERSE_DAYS_MAP[d] for d in days.split(','))
                else:
                    days_display = REVERSE_DAYS_MAP[current_days[0]]
            else:
                days_display = 'каждый день'
            lines.append(f"{time_key}: {text} - ({days_display})")

        self.send_to_chat("Ваши напоминания:\n\n" + "\n".join(lines), chat_id, parse_mode='HTML', thread_id=thread_id)


        
    def show_help(self, message):
        chat_id = message.chat.id
        thread_id = message.message_thread_id
        self.db.set_chat_thread_id(chat_id, thread_id)

        help_text = """
    Бот для создания напоминаний

    <b>Команды</b>
    /start - подписаться на уведомления
    /add - добавить напоминание
    /remove - удалить напоминание
    /list - показать все напоминания
    /help - помощь
    """
        self.send_to_chat(help_text, chat_id, parse_mode='HTML', thread_id=thread_id)

if __name__ == "__main__":
    # Создаём объект базы данных
    db = Database()

    # Создаём объект бота
    reminder_bot = ReminderBot(TOKEN, db)

    # Восстанавливаем задачи из базы
    reminder_bot.scheduler.restore_jobs(db.get_all_events, reminder_bot.send_scheduled_notification)

    # Запускаем планировщик (отдельный поток)
    reminder_bot.scheduler.run()

    # Запускаем бота
    reminder_bot.bot.polling(non_stop=True)