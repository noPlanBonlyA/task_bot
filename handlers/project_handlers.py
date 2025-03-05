# handlers/project_handlers.py

import datetime
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from aiogram.utils.exceptions import MessageToDeleteNotFound

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
# project[chat_id] = {
#   "creator_username": "@User",  # кто создал
#   "message_id": ...,
#   "devs": [...],
#   "testers": [...],
#   "pinned_text": ...
# }
#############################
PROJECTS = {}

def get_now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def is_project_creator(call: types.CallbackQuery, project):
    user = "@" + (call.from_user.username or "unknown")
    return (user == project.get("creator_username"))

@dp.message_handler(Command("newProject"))
async def cmd_new_project(message: types.Message, state: FSMContext):
    """
    Создаём новый проект. Только админ/creator?
    Предположим, что кто угодно может,
    но вы можете проверить username.
    """
    await message.delete()
    text = (
        f"Проект: (пока не указано)\n"
        f"Описание: (пока не указано)\n"
        f"Создан: {get_now_str()}\n"
        f"Creator: @{message.from_user.username}\n\n"
        f"Команда:\nРазработчики:\nТестировщики:"
    )
    msg = await message.answer(text)
    try:
        await bot.pin_chat_message(message.chat.id, msg.message_id)
    except Exception as e:
        print(f"Не удалось закрепить: {e}")

    PROJECTS[message.chat.id] = {
        "creator_username": f"@{message.from_user.username}",
        "message_id": msg.message_id,
        "devs": [],
        "testers": [],
        "pinned_text": text,
        "desc": ""
    }

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
        except:
            pass
    name = message.text
    await message.delete()

    proj = PROJECTS.get(message.chat.id, {})
    proj["name"] = name
    PROJECTS[message.chat.id] = proj

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
        except:
            pass
    desc = message.text
    await message.delete()
    proj = PROJECTS.get(message.chat.id, {})
    proj["desc"] = desc
    PROJECTS[message.chat.id] = proj

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
        except:
            pass
    try:
        await call.message.delete()
    except:
        pass

    # Обновляем pinned_text
    proj = PROJECTS.get(call.message.chat.id, {})
    desc = proj.get("desc", "")
    new_txt = (
        f"Проект: {proj.get('name','(none)')}\n"
        f"Описание: {desc}\n"
        f"Создан: {get_now_str()}\n"
        f"Creator: {proj.get('creator_username','@unknown')}\n\n"
        f"Команда:\nРазработчики:\nТестировщики:"
    )
    proj["pinned_text"] = new_txt
    PROJECTS[call.message.chat.id] = proj

    # Редактируем
    try:
        await bot.edit_message_text(new_txt, call.message.chat.id, proj["message_id"])
    except Exception as e:
        print(f"err finalizing project: {e}")

    await call.answer("Пропущена картинка")
    await state.finish()

@dp.message_handler(state=NewProjectStates.waiting_for_project_image, content_types=types.ContentType.PHOTO)
async def on_project_image(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ask_img_id = data.get("ask_img_id")
    if ask_img_id:
        try:
            await bot.delete_message(message.chat.id, ask_img_id)
        except:
            pass
    photo_id = message.photo[-1].file_id
    await message.delete()

    proj = PROJECTS.get(message.chat.id, {})
    desc = proj.get("desc","")
    new_txt = (
        f"Проект: {proj.get('name','(none)')}\n"
        f"Описание: {desc}\n"
        f"Создан: {get_now_str()}\n"
        f"Creator: {proj.get('creator_username','@unknown')}\n\n"
        f"Команда:\nРазработчики:\nТестировщики:"
    )
    proj["pinned_text"] = new_txt
    proj["photo_id"] = photo_id
    PROJECTS[message.chat.id] = proj

    try:
        media = types.InputMediaPhoto(photo_id, caption=new_txt)
        await bot.edit_message_media(media, message.chat.id, proj["message_id"])
    except Exception as e:
        print(f"Failed set project image: {e}")

    await state.finish()

########################################
# Доп. функции для добавления dev/test
########################################

@dp.message_handler(Command("team"))
async def cmd_team(message: types.Message):
    """
    Покажем кнопки для добавления dev/test.
    Но только creator может нажимать?
    """
    await message.delete()
    proj = PROJECTS.get(message.chat.id)
    if not proj:
        await message.answer("Нет проекта в этом чате.")
        return
    user = "@" + (message.from_user.username or "unknown")
    if user != proj["creator_username"]:
        await message.answer("Только creator может управлять командой.")
        return

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("Добавить разработчика", callback_data="project_add_developer"),
        types.InlineKeyboardButton("Добавить тестировщика", callback_data="project_add_tester"),
        types.InlineKeyboardButton("Закрыть", callback_data="team_close")
    )
    msg = await message.answer("Управление командой:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "team_close")
async def on_team_close(call: types.CallbackQuery):
    try:
        await call.message.delete()
        await call.answer()
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "project_add_developer")
async def on_add_dev(call: types.CallbackQuery):
    proj = PROJECTS.get(call.message.chat.id)
    user = "@" + (call.from_user.username or "unknown")
    if user != proj["creator_username"]:
        await call.answer("Нет прав добавлять dev", show_alert=True)
        return

    ask = await call.message.answer("Введите @username разработчика:")
    await call.answer()
    await dp.current_state(chat=call.message.chat.id, user=call.from_user.id).update_data(
        ask_dev_msg=ask.message_id
    )
    await ProjectTeamStates.waiting_for_developer.set()

@dp.message_handler(state=ProjectTeamStates.waiting_for_developer, content_types=types.ContentType.TEXT)
async def on_dev_username(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ask_id = data.get("ask_dev_msg")
    if ask_id:
        try:
            await bot.delete_message(message.chat.id, ask_id)
        except:
            pass
    dev_username = message.text.strip()
    await message.delete()

    proj = PROJECTS.get(message.chat.id, {})
    devs = proj.get("devs", [])
    if dev_username not in devs:
        devs.append(dev_username)
    proj["devs"] = devs

    # обновим pinned_text
    pinned = proj["pinned_text"].split("\nТестировщики:")[0]
    pinned += f"\nТестировщики:"
    # Или лучше парсить – упрощаем
    pinned = pinned.replace("Разработчики:\n","Разработчики:\n" + "\n".join(devs) + "\n")
    proj["pinned_text"] = pinned
    PROJECTS[message.chat.id] = proj

    # пробуем edit
    try:
        await bot.edit_message_caption(
            message.chat.id,
            proj["message_id"],
            caption=pinned
        )
    except:
        pass

    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "project_add_tester")
async def on_add_tester(call: types.CallbackQuery):
    proj = PROJECTS.get(call.message.chat.id)
    user = "@" + (call.from_user.username or "unknown")
    if user != proj["creator_username"]:
        await call.answer("Нет прав добавлять tester", show_alert=True)
        return

    ask = await call.message.answer("Введите @username тестировщика:")
    await call.answer()
    await dp.current_state(chat=call.message.chat.id, user=call.from_user.id).update_data(
        ask_test_msg=ask.message_id
    )
    await ProjectTeamStates.waiting_for_tester.set()

@dp.message_handler(state=ProjectTeamStates.waiting_for_tester, content_types=types.ContentType.TEXT)
async def on_tester_username(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ask_id = data.get("ask_test_msg")
    if ask_id:
        try:
            await bot.delete_message(message.chat.id, ask_id)
        except:
            pass
    test_username = message.text.strip()
    await message.delete()

    proj = PROJECTS.get(message.chat.id, {})
    testers = proj.get("testers", [])
    if test_username not in testers:
        testers.append(test_username)
    proj["testers"] = testers

    pinned = proj["pinned_text"]
    # Аналогично, аккуратно добавляем testers
    pinned = pinned.replace("Тестировщики:", "Тестировщики:\n" + "\n".join(testers))
    proj["pinned_text"] = pinned
    PROJECTS[message.chat.id] = proj

    try:
        await bot.edit_message_caption(message.chat.id, proj["message_id"], caption=pinned)
    except:
        pass

    await state.finish()
