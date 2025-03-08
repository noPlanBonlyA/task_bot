from aiogram import types

# --- Клавиатуры для проекта ---
def project_skip_image_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Пропустить", callback_data="skip_project_image"))
    return kb

def project_action_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("❌", callback_data="project_delete"),
        types.InlineKeyboardButton("✏️", callback_data="project_edit"),
        types.InlineKeyboardButton("✅", callback_data="project_confirm")
    )
    return kb

def project_edit_only_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✏️", callback_data="project_edit"))
    return kb

def team_member_confirm_keyboard(username: str, role: str):
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("❌", callback_data=f"delete_team:{role}:{username}"),
        types.InlineKeyboardButton("✏️", callback_data=f"edit_team:{role}:{username}"),
        types.InlineKeyboardButton("✅", callback_data=f"confirm_team:{role}:{username}")
    )
    return kb

# --- Клавиатуры для задач ---
def task_init_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("❌", callback_data="task_delete_init"),
        types.InlineKeyboardButton("✏️", callback_data="task_edit_init"),
        types.InlineKeyboardButton("✅", callback_data="task_confirm")
    )
    return kb

def task_after_confirm_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🗨️", callback_data="task_comment"),
        types.InlineKeyboardButton("🚀", callback_data="task_in_work")
    )
    return kb

def task_work_keyboard():
    """
    Стадия work: кнопки с желтым кружком.
    """
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💬", callback_data="task_comment"),
        types.InlineKeyboardButton("🟡Сделано", callback_data="task_done")
    )
    return kb

def task_test_keyboard():
    """
    Стадия test: формируются три кнопки:
      - Левый: "🟠 Не сделано" (callback "task_reject_choice")
      - Средний: "💬 Комментарий" (callback "task_comment")
      - Правый: "🟠 Сделано" (callback "task_done")
    """
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("🟠Не сделано", callback_data="task_reject_choice"),
        types.InlineKeyboardButton("💬Комментарий", callback_data="task_comment"),
        types.InlineKeyboardButton("🟠Сделано", callback_data="task_done")
    )
    return kb

def task_accept_keyboard():
    """
    Стадия accept: формируются три кнопки, причем кнопка "Принять" размещается слева:
      - Левый: "🔴 Принять" (callback "task_closed")
      - Средний: "💬 Комментарий" (callback "task_comment")
      - Правый: "🔴 Не сделано" (callback "task_fail_choice")
    """
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("🔴Не сделано", callback_data="task_fail_choice"),
        types.InlineKeyboardButton("💬Комментарий", callback_data="task_comment"),
        types.InlineKeyboardButton("🔴Сделано", callback_data="task_closed")

    )
    return kb

# --- Клавиатуры для глюка/правки ---

def glitch_or_fix_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("Глюк", callback_data="choose_glitch"),
        types.InlineKeyboardButton("Правка", callback_data="choose_fix")
    )
    return kb

def glitch_skip_image_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Пропустить", callback_data="skip_glitch_image"))
    return kb

def glitch_work_keyboard():
    """
    Стадия work для глюка: синий.
    """
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💬 Комментарий", callback_data="glitch_comment"),
        types.InlineKeyboardButton("🔵Сделано", callback_data="glitch_done")
    )
    return kb

def glitch_test_keyboard():
    """
    Стадия test для глюка: голубой.
    """
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("🟦Не сделано", callback_data="glitch_reject_choice"),
        types.InlineKeyboardButton("💬Комментарий", callback_data="glitch_comment"),
        types.InlineKeyboardButton("🟦Сделано", callback_data="glitch_done")
    )
    return kb

def glitch_accept_keyboard():
    """
    Стадия accept для глюка: фиолетовый.
    """
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("🟣Не сделано", callback_data="glitch_fail_choice"),
        types.InlineKeyboardButton("💬Комментарий", callback_data="glitch_comment"),
        types.InlineKeyboardButton("🟣Сделано", callback_data="glitch_closed")
    )
    return kb

# --- Клавиатуры для правки ---
def fix_work_keyboard():
    """
    Стадия work для правки: синий.
    """
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💬Комментарий", callback_data="fix_comment"),
        types.InlineKeyboardButton("🔵Сделано", callback_data="fix_done")
    )
    return kb

def fix_test_keyboard():
    """
    Стадия test для правки: голубой.
    """
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("🟦Не сделано", callback_data="fix_reject_choice"),
        types.InlineKeyboardButton("💬Комментарий", callback_data="fix_comment"),
        types.InlineKeyboardButton("🟦Сделано", callback_data="fix_done")
    )
    return kb

def fix_accept_keyboard():
    """
    Стадия accept для правки: фиолетовый.
    """
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("🟣Не сделано", callback_data="fix_fail_choice"),
        types.InlineKeyboardButton("💬Комментарий", callback_data="fix_comment"),
        types.InlineKeyboardButton("🟣Сделано", callback_data="fix_closed")
    )
    return kb


def task_skip_image_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Пропустить", callback_data="skip_task_image"))
    return kb


def fix_skip_image_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Пропустить", callback_data="skip_fix_image"))
    return kb
def glitch_rework_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💬 Комментарий", callback_data="glitch_comment"),
        types.InlineKeyboardButton("🟢 Исправлено", callback_data="glitch_fixed")
    )
    return kb

def glitch_retest_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔴 Не работает", callback_data="glitch_fail"),
        types.InlineKeyboardButton("🟢 Принять", callback_data="glitch_accept")
    )
    return kb