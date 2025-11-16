import os
import sqlite3
import logging
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self, db_name: str = None):
        self.db_name = db_name or os.getenv('DATABASE_PATH', 'bot_database.db')
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_name), exist_ok=True)
            with self.get_connection() as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id BIGINT NOT NULL,
                    time TEXT NOT NULL,
                    message TEXT NOT NULL,
                    days TEXT,  -- вот это новое поле
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(chat_id, time)
                )
                ''')

                #Таблица настроек чата 
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS chat_settings (
                        chat_id BIGINT PRIMARY KEY,
                        thread_id INTEGER
                    )
                ''')

                logging.info("База данных инициализирована успешно")
        except Exception as e:
            logging.error(f"Ошибка при инициализации БД: {str(e)}")


    def add_event(self, chat_id: int, time: str, message: str, days: Optional[str] = None):
        try:
            with self.get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO events (chat_id, time, message, days) VALUES (?, ?, ?, ?)",
                    (chat_id, time, message, days)
                )
        except Exception as e:
            logging.error(f"Ошибка добавления события: {e}")

    def remove_event(self, chat_id: int, time: str):
        try:
            with self.get_connection() as conn:
                conn.execute(
                    "DELETE FROM events WHERE chat_id = ? AND time = ?",
                    (chat_id, time)
                )
        except Exception as e:
            logging.error(f"Ошибка удаления события: {e}")

    def get_events_by_chat(self, chat_id: int) -> Dict[str, dict]:
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT time, message, days FROM events WHERE chat_id = ? ORDER BY time",
                    (chat_id,)
                )
                return {
                    row['time']: {"message": row['message'], "days": row['days']}
                    for row in cursor
                }
        except Exception as e:
            logging.error(f"Ошибка получения событий для чата {chat_id}: {e}")
            return {}

    def event_exists(self, chat_id: int, time: str) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM events WHERE chat_id = ? AND time = ?",
                    (chat_id, time)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logging.error(f"Ошибка проверки события: {e}")
            return False

    def get_all_events(self) -> Dict[int, Dict[str, Dict[str, str]]]:
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT chat_id, time, message, days FROM events ORDER BY chat_id, time"
                )
                result = {}
                for row in cursor:
                    chat_id = row['chat_id']
                    if chat_id not in result:
                        result[chat_id] = {}
                    result[chat_id][row['time']] = {
                        "message": row['message'],
                        "days": row['days'] if 'days' in row.keys() else None
                    }
                return result
        except Exception as e:
            logging.error(f"Ошибка получения всех событий: {e}")
            return {}

    def set_chat_thread_id(self, chat_id: int, thread_id: Optional[int]):
        try:
            with self.get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO chat_settings (chat_id, thread_id) VALUES (?, ?)",
                    (chat_id, thread_id)
                )
        except Exception as e:
            logging.error(f"Ошибка сохранения thread_id для чата {chat_id}: {e}")

    def get_chat_thread_id(self, chat_id: int) -> Optional[int]:
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT thread_id FROM chat_settings WHERE chat_id = ?",
                    (chat_id,)
                )
                row = cursor.fetchone()
                return row['thread_id'] if row else None
        except Exception as e:
            logging.error(f"Ошибка получения thread_id для чата {chat_id}: {e}")
            return None

db = Database()