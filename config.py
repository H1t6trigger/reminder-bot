import datetime
import logging
import sys

TOKEN = '8427333691:AAF6tIBprUk3y48o86hYsWdcp8p-5LiQbPM'

#Настройки времени
TIMEZONES = {"MSK": 1, "CHL": 3}
OFFSET = datetime.timedelta(0)
TIMEZONE = datetime.timezone(OFFSET)

active_chats = set()

#Настройки логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', mode='a'),
        logging.StreamHandler(sys.stdout)   
    ],
    force=True
)