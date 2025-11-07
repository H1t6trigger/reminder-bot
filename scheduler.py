import logging
import time
from threading import Thread
import schedule

class Scheduler:
    def __init__(self):
        self.jobs_dict = {}
        
    def add_job(self, chat_id, time_key, callback):
        try:
            if chat_id not in self.jobs_dict:
                self.jobs_dict[chat_id] = {}
            if time_key not in self.jobs_dict[chat_id]:
                job = schedule.every().day.at(time_key).do(callback, chat_id, time_key)
                self.jobs_dict[chat_id][time_key] = job
        except Exception as e:
            logging.error(f"Ошибка при создании задачи: {str(e)}")
            return False
            
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
            return False
            
    def restore_jobs(self, get_all_events_func, callback):
        logging.info("Восстановление заданий из БД")
        schedule.clear()
        self.jobs_dict.clear()
        all_events = get_all_events_func()
        
        for chat_id, events in all_events.items():
            for time_key in events:
                self.add_job(chat_id, time_key, callback)
                logging.info(f"Восстановлено задание: chat_id={chat_id}, time={time_key}")
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
              
#----------------------------------------------------------------------------------------------------------------------------------#
#Запуск планировщика
# def run_scheduler(): 
#     while True:
#         try:
#             schedule.run_pending()
#             time.sleep(1)
#         except Exception as e:
#             logging.error(f"Ошибка в шедулере: {str(e)}")
#             time.sleep(5)

# #Настройка и запуск планировщика в отдельном потоке
# def setup_scheduler(): 
#     try:
#         scheduler_thread = Thread(
#             target=run_scheduler,
#             daemon=True,
#             name="SchedulerThread"
#         )
#         scheduler_thread.start()
        
#     except Exception as e:
#         logging.error(f"Ошибка при запуске потока шедулера: {str(e)}")

# #Удаление задания из планировщика по времени
# def remove_scheduled_job(jobs_dict, chat_id, delete_time):
#     try:
#         if chat_id in jobs_dict and delete_time in jobs_dict[chat_id]:
#             job = jobs_dict[chat_id][delete_time]
#             schedule.cancel_job(job)
#             del jobs_dict[chat_id][delete_time]
#             return True
#         return False
#     except Exception as e:
#         logging.error(f"Ошибка при удалении задачи: {str(e)}")
#         return False