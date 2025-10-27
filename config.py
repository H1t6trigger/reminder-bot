import os
import datetime
import logging
import sys
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

TIMEZONES = {"UTC": 0, "MSK": 1, "CHL": 3}
OFFSET = datetime.timedelta(TIMEZONES['UTC'])
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