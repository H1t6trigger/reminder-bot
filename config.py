import os
import datetime
import logging
import sys
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

TIMEZONES = {"UTC": 0, "MSK": 3, "CHL": 5}
OFFSET = datetime.timedelta(hours=TIMEZONES["CHL"])
TIMEZONE = datetime.timezone(OFFSET)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', mode='a'),  
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)

logging.info("Конфигурация загружена успешно")