import logging
import time
from threading import Thread
import schedule

DAYS_MAP = {
    'понедельник': 'monday',
    'вторник': 'tuesday',
    'среда': 'wednesday',
    'четверг': 'thursday',
    'пятница': 'friday',
    'суббота': 'saturday',
    'воскресенье': 'sunday',
}

#обратный словарь для вывода на русском
REVERSE_DAYS_MAP = {v: k for k, v in DAYS_MAP.items()}

class Scheduler:
    def __init__(self):
        self.jobs_dict = {}
        
    def add_job(self, chat_id, time_key, callback, days_list=None):
        try:
            if chat_id not in self.jobs_dict:
                self.jobs_dict[chat_id] = {}

            if time_key in self.jobs_dict[chat_id]:
                return

            if days_list:
                for day in days_list:
                    job = getattr(schedule.every(), day).at(time_key).do(callback, chat_id, time_key)
                    self.jobs_dict[chat_id].setdefault(time_key, []).append(job)
            else:
                job = schedule.every().day.at(time_key).do(callback, chat_id, time_key)
                self.jobs_dict[chat_id][time_key] = [job]

            logging.info(f"Добавлено задание: chat_id={chat_id}, time={time_key}, days={days_list or 'каждый день'}")

        except Exception as e:
            logging.error(f"Ошибка при создании задачи: {str(e)}")

            
    def remove_job(self, chat_id, delete_time):
        try:
            if chat_id in self.jobs_dict and delete_time in self.jobs_dict[chat_id]:
                job = self.jobs_dict[chat_id][delete_time]
                schedule.cancel_job(job)
                del self.jobs_dict[chat_id][delete_time]
                return True
            return False
        except Exception as e:
            logging.error(f"Ошибка при удалении задачи: {str(e)}")
            
    def restore_jobs(self, get_all_events_func, callback):
        logging.info("Восстановление заданий из БД")
        schedule.clear()
        self.jobs_dict.clear()
        
        all_events = get_all_events_func()
        for chat_id, events in all_events.items():
            for time_key, event_data in events.items():
                text = event_data['message']
                days = event_data.get('days')
                days_list = days.split(',') if days else None
                self.add_job(chat_id, time_key, callback, days_list)

        logging.info("Восстановление завершено")
        
    def run_scheduler(self):
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logging.error(f"Ошибка в шедулере: {e}")
                time.sleep(5)

    def run(self):
        try:
            thread = Thread(
                target=self.run_scheduler, 
                daemon=True, 
                name="SchedulerThread"
                )
            thread.start()
        except Exception as e:
            logging.error(f"Ошибка при запуске потока шедулера: {str(e)}")
              
