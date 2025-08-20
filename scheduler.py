import logging
import time
from threading import Thread
import schedule

JOB_TIME = "09:30"
DINNER_TIME = "11:55"
WATER_TIME = "15:55"

#Запуск планировщика
def run_scheduler(send_func): 
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logging.error(f"Ошибка в шедулере: {str(e)}")

def setup_scheduler(send_func): 
    """
    Установка уведомлений для планировщика
    
        send_func: Функция отправки
    """
    try:
        schedule.every().day.at(JOB_TIME).do(
            send_func,
            "Кто опоздал на работу — тот <s>пыська</s> плохой человек!",
            parse_mode="HTML"
        )
        schedule.every().day.at(DINNER_TIME).do(
            send_func,
            "Пора идти на обед!"
        )
        schedule.every().day.at(WATER_TIME).do(
            send_func,
            "Пора идти за водой!"
        )
    except Exception as e:
        logging.error(f"Ошибка при настройке расписания: {str(e)}")

    #Запуска планировщика в отдельном потоке
    scheduler_thread = Thread( 
        target=run_scheduler,
        args=(send_func,),
        daemon=True
    )
    scheduler_thread.start()