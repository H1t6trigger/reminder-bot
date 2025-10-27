import sqlite3
import logging
from typing import Dict

class Database:
    def __init__(self, db_name: str = 'bot_database.db'):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn

    #Инициализация таблиц базы данных 
    def init_db(self):
        try:
            with self.get_connection() as conn:
                #Таблица для событий (events)
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id BIGINT NOT NULL,
                        time TEXT NOT NULL,
                        message TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(chat_id, time)
                    )
                ''')
                logging.info("База данных инициализирована успешно")
                
        except Exception as e:
            logging.error(f"Ошибка при инициализации базы данных: {str(e)}")
    
    #Методы для работы с событиями (events)

    #Добавление нового события
    def add_event(self, chat_id: int, time: str, message: str):
        try:
            with self.get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO events (chat_id, time, message) VALUES (?, ?, ?)",
                    (chat_id, time, message)
                )
                logging.info(f"Добавлено событие: chat_id={chat_id}, time={time}")
        except Exception as e:
            logging.error(f"Ошибка при добавлении события: {str(e)}")
    
    #Удаление события
    def remove_event(self, chat_id: int, time: str):
        try:
            with self.get_connection() as conn:
                conn.execute(
                    "DELETE FROM events WHERE chat_id = ? AND time = ?",
                    (chat_id, time)
                )
                logging.info(f"Удалено событие: chat_id={chat_id}, time={time}")
        except Exception as e:
            logging.error(f"Ошибка при удалении события: {str(e)}")

    #Получение всех событий для конкретного чата
    def get_events_by_chat(self, chat_id: int) -> Dict[str, str]:
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT time, message FROM events WHERE chat_id = ? ORDER BY time",
                    (chat_id,)
                )
                return {row['time']: row['message'] for row in cursor}
        except Exception as e:
            logging.error(f"Ошибка при получении событий для чата {chat_id}: {str(e)}")
            return {}
        
    #Проверка существования события
    def event_exists(self, chat_id: int, time: str) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM events WHERE chat_id = ? AND time = ?",
                    (chat_id, time)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logging.error(f"Ошибка при проверке события: {str(e)}")
            return False

    def get_all_events(self) -> Dict[int, Dict[str, str]]:
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT chat_id, time, message FROM events ORDER BY chat_id, time"
                )
                result = {}
                for row in cursor:
                    if row['chat_id'] not in result:
                        result[row['chat_id']] = {}
                    result[row['chat_id']][row['time']] = row['message']
                return result
        except Exception as e:
            logging.error(f"Ошибка при получении всех событий: {str(e)}")
            return {}

db = Database()