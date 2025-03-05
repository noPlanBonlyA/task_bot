# main.py

import logging
from aiogram import executor
from loader import dp

# Обязательно импортируем обработчики, чтобы они зарегистрировались в диспетчере
import handlers.project_handlers
import handlers.task_handlers

logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
