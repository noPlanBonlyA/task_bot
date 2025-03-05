# keyboards/keyboards.py

from aiogram import types

########################
# Проект
########################

def project_creation_keyboard():
    """
    Кнопки при создании проекта:
    - Подтвердить (✅)
    - Редактировать (✏️)
    - Удалить (❌)
    """
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("✅", callback_data="project_confirm"),
        types.InlineKeyboardButton("✏️", callback_data="project_edit"),
        types.InlineKeyboardButton("❌", callback_data="project_delete")
    )
    return kb

def project_skip_image_keyboard():
    """
    Кнопка "Пропустить" при запросе картинки проекта
    """
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Пропустить", callback_data="skip_project_image"))
    return keyboard

def project_team_keyboard():
    """
    При команде /team:
    - Добавить разработчика
    - Добавить тестировщика
    - Редактировать проект
    """
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("Добавить разработчика", callback_data="project_add_developer"),
        types.InlineKeyboardButton("Добавить тестировщика", callback_data="project_add_tester"),
        types.InlineKeyboardButton("✏️ Редактировать проект", callback_data="project_edit")
    )
    return kb

########################
# Таск
########################

def task_init_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅", callback_data="task_confirm"),
        types.InlineKeyboardButton("✏️", callback_data="task_edit_init"),
        types.InlineKeyboardButton("❌", callback_data="task_delete_init")
    )
    return kb

def task_after_confirm_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💬 Комментарии", callback_data="task_comment"),
        types.InlineKeyboardButton("🔵 В работу", callback_data="task_in_work")
    )
    return kb

def task_work_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💬 Комментарии", callback_data="task_comment"),
        types.InlineKeyboardButton("✅ Сделано", callback_data="task_done")
    )
    return kb

def task_test_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(

        types.InlineKeyboardButton("❌ Не сделано", callback_data="task_reject_choice"),
        types.InlineKeyboardButton("✅ Работает", callback_data="task_accept")
    )
    return kb

def task_accept_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("❌ Не работает", callback_data="task_fail_choice"),
        types.InlineKeyboardButton("✅ Принято", callback_data="task_closed")
    )
    return kb

########################
# Глюк / Правка
########################

def glitch_or_fix_keyboard():
    """
    Выбор «Глюк» или «Правка»
    """
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("Глюк", callback_data="choose_glitch"),
        types.InlineKeyboardButton("Правка", callback_data="choose_fix")
    )
    return kb

def glitch_skip_image_keyboard():
    """
    Кнопка «Пропустить» при запросе картинки
    """
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Пропустить", callback_data="skip_glitch_image"))
    return kb

def glitch_work_keyboard():
    """
    Статус work для глюка/правки:
    - ✅ Исправлено
    - 🟥 Комментарии
    """
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🟥 Комментарии", callback_data="glitch_comment"),
        types.InlineKeyboardButton("✅ Исправлено", callback_data="glitch_fixed")

    )
    return kb

def glitch_accept_keyboard():
    """
    Статус accept:
    - ❌ Не работает
    - ✅ Принято
    """
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("❌ Не работает", callback_data="glitch_fail"),
        types.InlineKeyboardButton("✅ Принято", callback_data="glitch_closed")
    )
    return kb
