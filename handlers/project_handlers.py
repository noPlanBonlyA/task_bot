import datetime
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from loader import dp, bot
from states.bot_states import (
    NewProjectStates,
    EditProjectStates,
    ProjectTeamStates
)
from keyboards.keyboards import (
    project_skip_image_keyboard
)

#############################
# Глобальный словарь проектов
# PROJECTS[chat_id] = {
#   "creator_username": "@User",
#   "message_id": ...,
#   "devs": [...],
#   "testers": [...],
#   "desc": ...,
#   "name": ...,
#   "created": ...,
#   "confirmed": False,      # подтверждён ли проект
#   "photo_id": ... (если есть)
# }
#############################
PROJECTS = {}

def get_now_str():
    return datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

def is_project_creator(call: types.CallbackQuery, project):
    user = "@" + (call.from_user.username or "unknown")
    return user == project.get("creator_username")

def generate_project_text(proj: dict) -> str:
    """
    Формирует текст карточки проекта в требуемом формате:
    #проект: название (дата время)
    >>описание

    Команда: /team
    Проджект: юзер
    Разработчики: юзер
    Тестеры: юзер

    ТЗ: /addtask
    -- сюда добавляются таски
    """
    name = proj.get("name", "(пока не указано)")
    desc = proj.get("desc", "(пока не указано)")
    created = proj.get("created", get_now_str())
    creator = proj.get("creator_username", "@unknown")
    devs_list = proj.get("devs", [])
    testers_list = proj.get("testers", [])
    devs = "\n".join(devs_list) if devs_list else "(нет разработчиков)"
    testers = "\n".join(testers_list) if testers_list else "(нет тестировщиков)"
    text = (
        f"#проект: {name} ({created})\n"
        f">>{desc}\n\n"
        f"Команда: /team\n"
        f"Проджект: {creator}\n"
        f"Разработчики: {devs}\n"
        f"Тестеры: {testers}\n\n"
        f"ТЗ: /addtask\n"
        f"-- сюда добавляются таски"
    )
    return text

def project_control_keyboard(confirmed: bool = False) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру управления проектом:
    До подтверждения – кнопки удаления, редактирования и подтверждения.
    После подтверждения – только кнопка редактирования.
    """
    kb = InlineKeyboardMarkup()
    if not confirmed:
        kb.add(
            InlineKeyboardButton("❌", callback_data="project_delete"),
            InlineKeyboardButton("✏️", callback_data="project_edit"),
            InlineKeyboardButton("✅", callback_data="project_confirm")
        )
    else:
        kb.add(
            InlineKeyboardButton("✏️", callback_data="project_edit")
        )
    return kb

async def update_project_message(chat_id, proj):
    """
    Обновляет сообщение карточки проекта с новым текстом и актуальной клавиатурой.
    Если картинка установлена – редактирует медиа, иначе – текст.
    Игнорирует ошибку "Message is not modified".
    """
    text = generate_project_text(proj)
    keyboard = project_control_keyboard(confirmed=proj.get("confirmed", False))
    try:
        if "photo_id" in proj:
            media = types.InputMediaPhoto(proj["photo_id"], caption=text)
            await bot.edit_message_media(media, chat_id, proj["message_id"], reply_markup=keyboard)
        else:
            await bot.edit_message_text(text, chat_id, proj["message_id"], reply_markup=keyboard,  disable_web_page_preview=True)
    except Exception as e:
        if "Message is not modified" in str(e):
            pass
        else:
            print(f"Ошибка обновления карточки: {e}")

@dp.message_handler(Command("newProject"))
async def cmd_new_project(message: types.Message, state: FSMContext):
    """
    Создание нового проекта. Любой пользователь может создать проект.
    Карточка проекта создаётся с inline‑клавиатурой управления.
    """
    await message.delete()
    created = get_now_str()
    proj = {
        "creator_username": f"@{message.from_user.username}",
        "message_id": None,
        "devs": [],
        "testers": [],
        "desc": "",
        "name": "",
        "created": created,
        "confirmed": False
    }
    text = generate_project_text(proj)
    keyboard = project_control_keyboard(confirmed=False)
    msg = await message.answer(text, reply_markup=keyboard)
    try:
        await bot.pin_chat_message(message.chat.id, msg.message_id)
    except Exception as e:
        print(f"Не удалось закрепить: {e}")

    proj["message_id"] = msg.message_id
    PROJECTS[message.chat.id] = proj

    ask_name = await message.answer("Введите название проекта:")
    await state.update_data(ask_name_id=ask_name.message_id)
    await NewProjectStates.waiting_for_project_name.set()

@dp.message_handler(state=NewProjectStates.waiting_for_project_name, content_types=types.ContentType.TEXT)
async def on_project_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ask_name_id = data.get("ask_name_id")
    if ask_name_id:
        try:
            await bot.delete_message(message.chat.id, ask_name_id)
        except Exception:
            pass
    name = message.text
    await message.delete()

    proj = PROJECTS.get(message.chat.id, {})
    proj["name"] = name
    PROJECTS[message.chat.id] = proj

    await update_project_message(message.chat.id, proj)

    ask_desc = await message.answer("Введите описание проекта:")
    await state.update_data(ask_desc_id=ask_desc.message_id)
    await NewProjectStates.waiting_for_project_description.set()

@dp.message_handler(state=NewProjectStates.waiting_for_project_description, content_types=types.ContentType.TEXT)
async def on_project_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ask_desc_id = data.get("ask_desc_id")
    if ask_desc_id:
        try:
            await bot.delete_message(message.chat.id, ask_desc_id)
        except Exception:
            pass
    desc = message.text
    await message.delete()

    proj = PROJECTS.get(message.chat.id, {})
    proj["desc"] = desc
    PROJECTS[message.chat.id] = proj

    await update_project_message(message.chat.id, proj)

    ask_img = await message.answer("Отправьте картинку или 'Пропустить':",
                                   reply_markup=project_skip_image_keyboard())
    await state.update_data(ask_img_id=ask_img.message_id)
    await NewProjectStates.waiting_for_project_image.set()

@dp.callback_query_handler(lambda c: c.data == "skip_project_image", state=NewProjectStates.waiting_for_project_image)
async def skip_project_image(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ask_img_id = data.get("ask_img_id")
    if ask_img_id:
        try:
            await bot.delete_message(call.message.chat.id, ask_img_id)
        except Exception:
            pass
    try:
        await call.message.delete()
    except Exception:
        pass

    # Обновляем сообщение карточки (картинка не установлена)
    proj = PROJECTS.get(call.message.chat.id, {})
    PROJECTS[call.message.chat.id] = proj
    await update_project_message(call.message.chat.id, proj)

    await call.answer("Пропущена картинка")
    await state.finish()

@dp.message_handler(state=NewProjectStates.waiting_for_project_image, content_types=types.ContentType.PHOTO)
async def on_project_image(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ask_img_id = data.get("ask_img_id")
    if ask_img_id:
        try:
            await bot.delete_message(message.chat.id, ask_img_id)
        except Exception:
            pass
    photo_id = message.photo[-1].file_id
    await message.delete()

    proj = PROJECTS.get(message.chat.id, {})
    proj["photo_id"] = photo_id
    PROJECTS[message.chat.id] = proj

    await update_project_message(message.chat.id, proj)
    await state.finish()

########################################
# Новый поток управления командой /team
########################################

@dp.message_handler(Command("team"))
async def cmd_team(message: types.Message):
    """
    Выводит сообщение с выбором: кого добавить.
    Только создатель проекта может управлять командой.
    """
    await message.delete()
    proj = PROJECTS.get(message.chat.id)
    if not proj:
        await message.answer("Нет проекта в этом чате.")
        return
    user = "@" + (message.from_user.username or "unknown")
    if user != proj["creator_username"]:
        await message.answer("Только создатель проекта может управлять командой.")
        return

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("Разработчик", callback_data="team_add_developer"),
        InlineKeyboardButton("Тестер", callback_data="team_add_tester"),
        InlineKeyboardButton("Закрыть", callback_data="team_close")
    )
    await message.answer("Кого вы хотите добавить?", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "team_close")
async def on_team_close(call: types.CallbackQuery):
    try:
        await call.message.delete()
        await call.answer()
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "team_add_developer")
async def on_add_dev(call: types.CallbackQuery, state: FSMContext):
    proj = PROJECTS.get(call.message.chat.id)
    # Ограничение: только создатель проекта может добавлять участников
    if not is_project_creator(call, proj):
        await call.answer("Только создатель проекта может управлять командой.", show_alert=True)
        return
    try:
        await call.message.delete()
    except Exception:
        pass
    ask = await bot.send_message(call.message.chat.id, "Введите @username разработчика:")
    await dp.current_state(chat=call.message.chat.id, user=call.from_user.id).update_data(team_role="developer", team_prompt_msg=ask.message_id)
    await ProjectTeamStates.waiting_for_team_username.set()
    await call.answer()

@dp.callback_query_handler(lambda c: c.data == "team_add_tester")
async def on_add_tester(call: types.CallbackQuery, state: FSMContext):
    proj = PROJECTS.get(call.message.chat.id)
    if not is_project_creator(call, proj):
        await call.answer("Только создатель проекта может управлять командой.", show_alert=True)
        return
    try:
        await call.message.delete()
    except Exception:
        pass
    ask = await bot.send_message(call.message.chat.id, "Введите @username тестировщика:")
    await dp.current_state(chat=call.message.chat.id, user=call.from_user.id).update_data(team_role="tester", team_prompt_msg=ask.message_id)
    await ProjectTeamStates.waiting_for_team_username.set()
    await call.answer()

@dp.message_handler(state=ProjectTeamStates.waiting_for_team_username, content_types=types.ContentType.TEXT)
async def on_team_username(message: types.Message, state: FSMContext):
    data = await state.get_data()
    username_candidate = message.text.strip()
    try:
        await message.delete()
    except Exception:
        pass
    team_prompt_msg = data.get("team_prompt_msg")
    if team_prompt_msg:
        try:
            await bot.delete_message(message.chat.id, team_prompt_msg)
        except Exception:
            pass
    text = f"Вы хотите добавить {username_candidate} в " + ("разработчики?" if data.get("team_role") == "developer" else "тестеры?")
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("Нет, изменить", callback_data="team_change_username"),
        InlineKeyboardButton("Да", callback_data="team_confirm_username")
    )
    await state.update_data(team_username_candidate=username_candidate)
    await bot.send_message(message.chat.id, text, reply_markup=kb,  disable_web_page_preview=True)
    await ProjectTeamStates.waiting_for_team_confirmation.set()

@dp.callback_query_handler(lambda c: c.data == "team_change_username", state=ProjectTeamStates.waiting_for_team_confirmation)
async def on_team_change_username(call: types.CallbackQuery, state: FSMContext):
    try:
        await call.message.delete()
    except Exception:
        pass
    data = await state.get_data()
    role = data.get("team_role")
    prompt = "Введите @username разработчика:" if role == "developer" else "Введите @username тестировщика:"
    ask = await bot.send_message(call.message.chat.id, prompt)
    await dp.current_state(chat=call.message.chat.id, user=call.from_user.id).update_data(team_prompt_msg=ask.message_id)
    await ProjectTeamStates.waiting_for_team_username.set()
    await call.answer("Введите username заново")

@dp.callback_query_handler(lambda c: c.data == "team_confirm_username", state=ProjectTeamStates.waiting_for_team_confirmation)
async def on_team_confirm_username(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    team_role = data.get("team_role")
    username_candidate = data.get("team_username_candidate")
    try:
        await call.message.delete()
    except Exception:
        pass
    proj = PROJECTS.get(call.message.chat.id, {})
    if team_role == "developer":
        devs = proj.get("devs", [])
        if username_candidate not in devs:
            devs.append(username_candidate)
        proj["devs"] = devs
    elif team_role == "tester":
        testers = proj.get("testers", [])
        if username_candidate not in testers:
            testers.append(username_candidate)
        proj["testers"] = testers
    PROJECTS[call.message.chat.id] = proj
    await update_project_message(call.message.chat.id, proj)
    await state.finish()
    await call.answer("Пользователь добавлен")

########################################
# Остальные обработчики (редактирование, подтверждение и т.д.)
########################################

@dp.callback_query_handler(lambda c: c.data == "project_delete")
async def on_project_delete(call: types.CallbackQuery):
    proj = PROJECTS.get(call.message.chat.id)
    if not is_project_creator(call, proj):
        await call.answer("Только создатель проекта может управлять проектом.", show_alert=True)
        return
    try:
        await bot.delete_message(call.message.chat.id, call.message.message_id)
        PROJECTS.pop(call.message.chat.id, None)
        await call.answer("Проект удалён")
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "project_edit")
async def on_project_edit(call: types.CallbackQuery, state: FSMContext):
    proj = PROJECTS.get(call.message.chat.id)
    if not proj:
        await call.answer("Нет проекта для редактирования", show_alert=True)
        return
    if not is_project_creator(call, proj):
        await call.answer("Только создатель проекта может редактировать его.", show_alert=True)
        return
    ask = await call.message.answer("Введите новое описание проекта:")
    await dp.current_state(chat=call.message.chat.id, user=call.from_user.id).update_data(edit_desc_msg=ask.message_id)
    await EditProjectStates.waiting_for_new_project_description.set()
    await call.answer()

@dp.message_handler(state=EditProjectStates.waiting_for_new_project_description, content_types=types.ContentType.TEXT)
async def on_new_project_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ask_id = data.get("edit_desc_msg")
    if ask_id:
        try:
            await bot.delete_message(message.chat.id, ask_id)
        except Exception:
            pass
    new_desc = message.text
    await message.delete()
    proj = PROJECTS.get(message.chat.id, {})
    proj["desc"] = new_desc
    PROJECTS[message.chat.id] = proj
    await update_project_message(message.chat.id, proj)
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "project_confirm")
async def on_project_confirm(call: types.CallbackQuery):
    proj = PROJECTS.get(call.message.chat.id)
    if not proj:
        await call.answer("Нет проекта для подтверждения", show_alert=True)
        return
    if not is_project_creator(call, proj):
        await call.answer("Только создатель проекта может подтверждать его.", show_alert=True)
        return
    proj["confirmed"] = True
    PROJECTS[call.message.chat.id] = proj
    await update_project_message(call.message.chat.id, proj)
    await call.answer("Проект подтверждён")
