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
def setup_scheduler(send_func): 
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
def remove_scheduled_job(delete_time):
    for job in schedule.get_jobs():
            if job.next_run:
                job_time = job.next_run.strftime("%H:%M")
                if job_time == delete_time:
                    schedule.cancel_job(job)