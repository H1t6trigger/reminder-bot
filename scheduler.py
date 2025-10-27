import logging
import time
from threading import Thread
import schedule

#Запуск планировщика
def run_scheduler(): 
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logging.error(f"Ошибка в шедулере: {str(e)}")
            time.sleep(5)

#Настройка и запуск планировщика в отдельном потоке
def setup_scheduler(): 
    try:
        scheduler_thread = Thread(
            target=run_scheduler,
            daemon=True,
            name="SchedulerThread"
        )
        scheduler_thread.start()
        
    except Exception as e:
        logging.error(f"Ошибка при запуске потока шедулера: {str(e)}")

#Удаление задания из планировщика по времени
def remove_scheduled_job(jobs_dict, chat_id, delete_time):
    try:
        if chat_id in jobs_dict and delete_time in jobs_dict[chat_id]:
            job = jobs_dict[chat_id][delete_time]
            schedule.cancel_job(job)
            del jobs_dict[chat_id][delete_time]
            return True
        return False
    except Exception as e:
        logging.error(f"Ошибка при удалении задачи: {str(e)}")
        return False