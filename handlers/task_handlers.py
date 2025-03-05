# handlers/task_handlers.py

import datetime
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from aiogram.utils.exceptions import MessageToDeleteNotFound

from loader import dp, bot
from states.bot_states import (
    NewTaskStates, EditTaskStates, CommentStates,
    NewGlitchStates, NewFixStates
)
from handlers.project_handlers import PROJECTS
from keyboards.keyboards import (
    task_init_keyboard, task_after_confirm_keyboard,
    task_work_keyboard, task_test_keyboard, task_accept_keyboard,
    glitch_or_fix_keyboard, glitch_skip_image_keyboard,
    glitch_work_keyboard, glitch_accept_keyboard
)

TASKS = {}  # TASKS[chat_id] = list of tasks / glitch / fix
TASK_COUNTER = 1
GLITCH_COUNTER = 1
FIX_COUNTER = 1

def now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def build_task_text(idx: int, prefix: str, dev: str, tester: str, desc: str, status: str) -> str:
    """
    prefix – "ТЗ", "Глюк", "Правка"
    idx – локальный счётчик
    """
    return (
        f"{prefix}{idx} #{status}\n"
        f"D: {dev}\nT: {tester}\n"
        f"Дата: {now_str()}\n"
        f"Описание: {desc}"
    )

def find_card(chat_id: int, message_id: int):
    arr = TASKS.get(chat_id, [])
    for obj in arr:
        if obj["message_id"] == message_id:
            return obj
    return None

async def update_project_card(chat_id: int):
    """
    Обновляем только задачи типа "ТЗ". Глюки/правки не вносим в карточку проекта.
    """
    from handlers.project_handlers import PROJECTS
    if chat_id not in PROJECTS:
        return

    arr = TASKS.get(chat_id, [])
    project_obj = PROJECTS[chat_id]
    base_text = project_obj["pinned_text"].split("\n\nЗадачи:")[0]

    tasks_only = [x for x in arr if x["type"] == "ТЗ"]
    if tasks_only:
        block = "\n\nЗадачи:"
        for t in tasks_only:
            idx = t["local_id"]
            desc = t["desc"]
            dev = t["dev"]
            block += f"\nТЗ{idx}: {desc} ({dev})"
        final_text = base_text + block
    else:
        final_text = base_text

    project_obj["pinned_text"] = final_text
    PROJECTS[chat_id] = project_obj

    msg_id = project_obj["message_id"]
    file_id = project_obj.get("image_file_id")
    try:
        if file_id:
            media = types.InputMediaPhoto(file_id, caption=final_text)
            await bot.edit_message_media(media, chat_id, msg_id)
        else:
            await bot.edit_message_text(final_text, chat_id, msg_id)
    except Exception as e:
        print(f"Ошибка при update_project_card: {e}")

#############################
# Создание Таска /addTask
#############################

@dp.message_handler(Command("addTask"))
async def cmd_add_task(message: types.Message, state: FSMContext):
    await message.delete()
    if message.chat.id not in PROJECTS:
        await message.answer("В этом чате нет проекта.")
        return

    devs = PROJECTS[message.chat.id].get("devs", [])
    testers = PROJECTS[message.chat.id].get("testers", [])

    if len(devs) == 0:
        await state.update_data(task_dev="@noDev")
    elif len(devs) == 1:
        await state.update_data(task_dev=devs[0])
    else:
        kb = types.InlineKeyboardMarkup()
        for d in devs:
            kb.add(types.InlineKeyboardButton(d, callback_data=f"task_dev_pick:{d}"))
        dev_msg = await message.answer("Выберите разработчика:", reply_markup=kb)
        await state.update_data(dev_msg=dev_msg.message_id)
        return

    if len(testers) == 0:
        await state.update_data(task_tester="@noTester")
    elif len(testers) == 1:
        await state.update_data(task_tester=testers[0])
    else:
        kb2 = types.InlineKeyboardMarkup()
        for t in testers:
            kb2.add(types.InlineKeyboardButton(t, callback_data=f"task_test_pick:{t}"))
        test_msg = await message.answer("Выберите тестировщика:", reply_markup=kb2)
        await state.update_data(test_msg=test_msg.message_id)
        return

    ask_desc = await message.answer("Введите описание (ТЗ):")
    await state.update_data(ask_desc=ask_desc.message_id)
    await NewTaskStates.waiting_for_task_description.set()

@dp.callback_query_handler(lambda c: c.data.startswith("task_dev_pick:"))
async def on_dev_pick(call: types.CallbackQuery, state: FSMContext):
    dev_chosen = call.data.split("task_dev_pick:")[1]
    data = await state.get_data()
    dev_msg = data.get("dev_msg")
    if dev_msg:
        try:
            await bot.delete_message(call.message.chat.id, dev_msg)
        except:
            pass
    await state.update_data(task_dev=dev_chosen)
    await call.answer(f"Разработчик {dev_chosen} выбран")

    testers = PROJECTS[call.message.chat.id].get("testers", [])
    if len(testers) == 0:
        await state.update_data(task_tester="@noTester")
        ask_desc = await call.message.answer("Введите описание (ТЗ):")
        await state.update_data(ask_desc=ask_desc.message_id)
        await NewTaskStates.waiting_for_task_description.set()
    elif len(testers) == 1:
        await state.update_data(task_tester=testers[0])
        ask_desc = await call.message.answer("Введите описание (ТЗ):")
        await state.update_data(ask_desc=ask_desc.message_id)
        await NewTaskStates.waiting_for_task_description.set()
    else:
        kb2 = types.InlineKeyboardMarkup()
        for t in testers:
            kb2.add(types.InlineKeyboardButton(t, callback_data=f"task_test_pick:{t}"))
        m2 = await call.message.answer("Выберите тестировщика:", reply_markup=kb2)
        await state.update_data(test_msg=m2.message_id)

@dp.callback_query_handler(lambda c: c.data.startswith("task_test_pick:"))
async def on_test_pick(call: types.CallbackQuery, state: FSMContext):
    test_chosen = call.data.split("task_test_pick:")[1]
    data = await state.get_data()
    t_msg = data.get("test_msg")
    if t_msg:
        try:
            await bot.delete_message(call.message.chat.id, t_msg)
        except:
            pass
    await call.answer(f"Тестировщик {test_chosen} выбран")
    await state.update_data(task_tester=test_chosen)

    ask_desc = await call.message.answer("Введите описание (ТЗ):")
    await state.update_data(ask_desc=ask_desc.message_id)
    await NewTaskStates.waiting_for_task_description.set()

@dp.message_handler(state=NewTaskStates.waiting_for_task_description, content_types=types.ContentType.TEXT)
async def on_task_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    desc_ask = data.get("ask_desc")
    if desc_ask:
        try:
            await bot.delete_message(message.chat.id, desc_ask)
        except:
            pass
    desc = message.text
    await message.delete()

    await state.update_data(task_description=desc)
    ask_photo = await message.answer("Отправьте фото для задачи или 'Пропустить':",
                                     reply_markup=glitch_skip_image_keyboard())
    await state.update_data(task_photo_ask=ask_photo.message_id)
    await NewTaskStates.waiting_for_task_photo.set()

@dp.callback_query_handler(lambda c: c.data == "skip_glitch_image", state=NewTaskStates.waiting_for_task_photo)
async def skip_task_photo(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    p_ask = data.get("task_photo_ask")
    if p_ask:
        try:
            await bot.delete_message(call.message.chat.id, p_ask)
        except:
            pass
    try:
        await call.message.delete()
    except:
        pass
    await state.update_data(task_photo=None)
    await finalize_task_creation(call.message.chat.id, state)
    await call.answer("Пропущено фото")
    await state.finish()

@dp.message_handler(state=NewTaskStates.waiting_for_task_photo, content_types=types.ContentType.PHOTO)
async def on_task_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    p_ask = data.get("task_photo_ask")
    if p_ask:
        try:
            await bot.delete_message(message.chat.id, p_ask)
        except:
            pass
    photo_id = message.photo[-1].file_id
    await message.delete()

    await state.update_data(task_photo=photo_id)
    await finalize_task_creation(message.chat.id, state)
    await state.finish()

async def finalize_task_creation(chat_id: int, state: FSMContext):
    """
    Генерируем ТЗ с TASK_COUNTER
    """
    global TASK_COUNTER
    data = await state.get_data()
    dev = data.get("task_dev", "@noDev")
    tester = data.get("task_tester", "@noTester")
    desc = data.get("task_description", "")
    photo = data.get("task_photo")

    idx = TASK_COUNTER
    TASK_COUNTER += 1

    text = build_task_text(idx, "ТЗ", dev, tester, desc, "new")
    kb = task_init_keyboard()
    if photo:
        msg = await bot.send_photo(chat_id, photo=photo, caption=text, reply_markup=kb)
    else:
        msg = await bot.send_message(chat_id, text, reply_markup=kb)

    arr = TASKS.setdefault(chat_id, [])
    arr.append({
        "type": "ТЗ",
        "local_id": idx,
        "message_id": msg.message_id,
        "dev": dev,
        "tester": tester,
        "desc": desc,
        "photo": photo,
        "status": "new"
    })
    await update_project_card(chat_id)

#############################
# Подтверждение/Редактирование/Удаление/Комментарии
#############################

@dp.callback_query_handler(lambda c: c.data == "task_confirm")
async def on_task_confirm(call: types.CallbackQuery):
    msg = call.message
    old_txt = msg.caption if msg.photo else msg.text
    kb = task_after_confirm_keyboard()  # зелёная/принять справа
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=old_txt, reply_markup=kb)
        else:
            await bot.edit_message_text(old_txt, msg.chat.id, msg.message_id, reply_markup=kb)
    except Exception as e:
        print(f"Ошибка при confirm: {e}")
    await call.answer("Таск подтверждён")

@dp.callback_query_handler(lambda c: c.data == "task_edit_init")
async def on_task_edit_init(call: types.CallbackQuery, state: FSMContext):
    msg = call.message
    await state.update_data(
        edit_chat_id=msg.chat.id,
        edit_msg_id=msg.message_id
    )
    ask = await msg.answer("Введите новое описание (ТЗ):")
    await state.update_data(edit_ask_msg=ask.message_id)
    await EditTaskStates.waiting_for_new_task_text.set()
    await call.answer()

@dp.message_handler(state=EditTaskStates.waiting_for_new_task_text, content_types=types.ContentType.TEXT)
async def on_edit_task_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["edit_chat_id"]
    msg_id = data["edit_msg_id"]
    ask_id = data["edit_ask_msg"]
    if ask_id:
        try:
            await bot.delete_message(chat_id, ask_id)
        except:
            pass
    new_desc = message.text
    await message.delete()

    arr = TASKS.get(chat_id, [])
    card_obj = None
    for x in arr:
        if x["message_id"] == msg_id:
            card_obj = x
            break
    if not card_obj:
        return
    card_obj["desc"] = new_desc
    old_status = card_obj.get("status", "new")
    idx = card_obj["local_id"]
    ttype = card_obj["type"]  # "ТЗ", "Глюк", "Правка"
    dev = card_obj["dev"]
    test = card_obj["tester"]
    photo_id = card_obj["photo"]

    text = build_task_text(idx, ttype, dev, test, new_desc, old_status)

    # Восстанавливаем нужную клавиатуру
    if old_status == "new":
        kb = task_init_keyboard()
    elif old_status == "work":
        kb = task_work_keyboard()
    elif old_status == "test":
        kb = task_test_keyboard()
    elif old_status == "accept":
        kb = task_accept_keyboard()
    else:
        kb = None  # closed?

    try:
        if photo_id:
            await bot.edit_message_caption(chat_id, msg_id, caption=text, reply_markup=kb)
        else:
            await bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb)
    except Exception as e:
        print(f"Ошибка редактирования: {e}")

    # Если это "ТЗ" – обновляем карточку проекта
    if ttype == "ТЗ":
        await update_project_card(chat_id)

    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "task_delete_init")
async def on_task_delete_init(call: types.CallbackQuery):
    try:
        await call.message.delete()
        arr = TASKS.setdefault(call.message.chat.id, [])
        arr = [x for x in arr if x["message_id"] != call.message.message_id]
        TASKS[call.message.chat.id] = arr
        # Обновляем проект, если это "ТЗ"
        # Или просто вызываем update_project_card
        await update_project_card(call.message.chat.id)
        await call.answer("Таск удалён.")
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "task_comment")
async def on_task_comment(call: types.CallbackQuery, state: FSMContext):
    msg = call.message
    old = msg.caption if msg.photo else msg.text
    kb = msg.reply_markup
    await state.update_data(
        comment_chat_id=msg.chat.id,
        comment_msg_id=msg.message_id,
        old_text=old,
        old_kb=kb,
        is_photo=bool(msg.photo)
    )
    ask = await msg.answer("Введите комментарий:")
    await state.update_data(comment_ask_id=ask.message_id)
    await CommentStates.waiting_for_comment_text.set()
    await call.answer()

@dp.message_handler(state=CommentStates.waiting_for_comment_text, content_types=types.ContentType.TEXT)
async def on_comment_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["comment_chat_id"]
    msg_id = data["comment_msg_id"]
    old_text = data["old_text"]
    kb = data["old_kb"]
    is_photo = data["is_photo"]
    ask_cmt_id = data.get("comment_ask_id")
    if ask_cmt_id:
        try:
            await bot.delete_message(chat_id, ask_cmt_id)
        except:
            pass
    user = "@" + (message.from_user.username or "unknown")
    new_txt = old_text + f"\nКомментарий({user}): {message.text}"
    await message.delete()

    try:
        if is_photo:
            await bot.edit_message_caption(chat_id, msg_id, caption=new_txt, reply_markup=kb)
        else:
            await bot.edit_message_text(new_txt, chat_id, msg_id, reply_markup=kb)
    except Exception as e:
        await message.answer(f"Ошибка комментария: {e}")
    await state.finish()

#############################
# Статусы (В работу, Сделано, Работает, Принято)
#############################

@dp.callback_query_handler(lambda c: c.data == "task_in_work")
async def on_task_in_work(call: types.CallbackQuery):
    msg = call.message
    old = msg.caption if msg.photo else msg.text
    new_txt = old + "\n#work"
    kb = task_work_keyboard()  # галочка справа
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_txt, reply_markup=kb)
        else:
            await bot.edit_message_text(new_txt, msg.chat.id, msg.message_id, reply_markup=kb)
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    card_obj = find_card(msg.chat.id, msg.message_id)
    if card_obj:
        card_obj["status"] = "work"
    await call.answer("Таск -> work")

@dp.callback_query_handler(lambda c: c.data == "task_done")
async def on_task_done(call: types.CallbackQuery):
    msg = call.message
    old = msg.caption if msg.photo else msg.text
    new_txt = old + "\n#test"
    kb = task_test_keyboard()  # работет справа
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_txt, reply_markup=kb)
        else:
            await bot.edit_message_text(new_txt, msg.chat.id, msg.message_id, reply_markup=kb)
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    card_obj = find_card(msg.chat.id, msg.message_id)
    if card_obj:
        card_obj["status"] = "test"
    await call.answer("Таск -> test")

@dp.callback_query_handler(lambda c: c.data == "task_accept")
async def on_task_accept(call: types.CallbackQuery):
    msg = call.message
    old = msg.caption if msg.photo else msg.text
    new_txt = old + "\n#accept"
    kb = task_accept_keyboard()  # принято справа
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_txt, reply_markup=kb)
        else:
            await bot.edit_message_text(new_txt, msg.chat.id, msg.message_id, reply_markup=kb)
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    card_obj = find_card(msg.chat.id, msg.message_id)
    if card_obj:
        card_obj["status"] = "accept"
    await call.answer("Таск -> accept")

@dp.callback_query_handler(lambda c: c.data == "task_closed")
async def on_task_closed(call: types.CallbackQuery):
    msg = call.message
    old = msg.caption if msg.photo else msg.text
    new_txt = old + "\n#closed\nТаск завершён."
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_txt)
        else:
            await bot.edit_message_text(new_txt, msg.chat.id, msg.message_id)
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    card_obj = find_card(msg.chat.id, msg.message_id)
    if card_obj:
        card_obj["status"] = "closed"
    await call.answer("Таск закрыт.")

#############################
# Не сделано / Не работает => Глюк / Правка
#############################

@dp.callback_query_handler(lambda c: c.data == "task_reject_choice")
async def on_task_reject(call: types.CallbackQuery):
    kb = glitch_or_fix_keyboard()
    await call.message.answer("Что создать: Глюк или Правка?", reply_markup=kb)
    await call.answer()

@dp.callback_query_handler(lambda c: c.data == "task_fail_choice")
async def on_task_fail(call: types.CallbackQuery):
    kb = glitch_or_fix_keyboard()
    await call.message.answer("Что создать: Глюк или Правка?", reply_markup=kb)
    await call.answer()

#############################
# Глюк (idx=GLITCH_COUNTER), dev/test из исходной карточки
#############################

@dp.callback_query_handler(lambda c: c.data == "choose_glitch")
async def on_choose_glitch(call: types.CallbackQuery, state: FSMContext):
    base = find_card(call.message.chat.id, call.message.message_id)
    dev = base["dev"] if base else "@noDev"
    test = base["tester"] if base else "@noTester"
    await call.message.delete()
    await state.update_data(glitch_dev=dev, glitch_tester=test)
    ask = await call.message.answer("Отправьте картинку для Глюка или 'Пропустить':",
                                    reply_markup=glitch_skip_image_keyboard())
    await state.update_data(gl_ask_img=ask.message_id)
    await NewGlitchStates.waiting_for_photo.set()
    await call.answer()

@dp.callback_query_handler(lambda c: c.data == "skip_glitch_image", state=NewGlitchStates.waiting_for_photo)
async def on_skip_gl_img(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ask_img = data.get("gl_ask_img")
    if ask_img:
        try:
            await bot.delete_message(call.message.chat.id, ask_img)
        except:
            pass
    try:
        await call.message.delete()
    except:
        pass
    await state.update_data(glitch_photo=None)
    ask_desc = await call.message.answer("Введите описание глюка:")
    await state.update_data(gl_ask_desc=ask_desc.message_id)
    await NewGlitchStates.waiting_for_description.set()
    await call.answer()

@dp.message_handler(state=NewGlitchStates.waiting_for_photo, content_types=types.ContentType.PHOTO)
async def on_gl_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ask_img = data.get("gl_ask_img")
    if ask_img:
        try:
            await bot.delete_message(message.chat.id, ask_img)
        except:
            pass
    photo_id = message.photo[-1].file_id
    await message.delete()
    await state.update_data(glitch_photo=photo_id)
    ask_desc = await message.answer("Введите описание глюка:")
    await state.update_data(gl_ask_desc=ask_desc.message_id)
    await NewGlitchStates.waiting_for_description.set()

@dp.message_handler(state=NewGlitchStates.waiting_for_description, content_types=types.ContentType.TEXT)
async def on_gl_desc(message: types.Message, state: FSMContext):
    global GLITCH_COUNTER
    data = await state.get_data()
    dev = data["glitch_dev"]
    test = data["glitch_tester"]
    photo = data.get("glitch_photo")
    ask_desc = data.get("gl_ask_desc")
    if ask_desc:
        try:
            await bot.delete_message(message.chat.id, ask_desc)
        except:
            pass
    await message.delete()
    desc = message.text

    idx = GLITCH_COUNTER
    GLITCH_COUNTER += 1

    text = build_task_text(idx, "Глюк", dev, test, desc, "work")
    kb = glitch_work_keyboard()  # зелёная (Исправлено) справа
    if photo:
        msg = await message.answer_photo(photo, caption=text, reply_markup=kb)
    else:
        msg = await message.answer(text, reply_markup=kb)

    arr = TASKS.setdefault(message.chat.id, [])
    arr.append({
        "type": "Глюк",
        "local_id": idx,
        "message_id": msg.message_id,
        "dev": dev,
        "tester": test,
        "desc": desc,
        "photo": photo,
        "status": "work"
    })
    # Не добавляем в карточку проекта
    await state.finish()

#############################
# Правка (idx=FIX_COUNTER), dev/test из исходной карточки
#############################

@dp.callback_query_handler(lambda c: c.data == "choose_fix")
async def on_choose_fix(call: types.CallbackQuery, state: FSMContext):
    base = find_card(call.message.chat.id, call.message.message_id)
    dev = base["dev"] if base else "@noDev"
    test = base["tester"] if base else "@noTester"
    await call.message.delete()
    await state.update_data(fix_dev=dev, fix_tester=test)
    ask = await call.message.answer("Отправьте картинку для Правки или 'Пропустить':",
                                    reply_markup=glitch_skip_image_keyboard())
    await state.update_data(fix_ask_img=ask.message_id)
    await NewFixStates.waiting_for_photo.set()
    await call.answer()

@dp.callback_query_handler(lambda c: c.data == "skip_glitch_image", state=NewFixStates.waiting_for_photo)
async def on_skip_fix_img(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ask_img = data.get("fix_ask_img")
    if ask_img:
        try:
            await bot.delete_message(call.message.chat.id, ask_img)
        except:
            pass
    try:
        await call.message.delete()
    except:
        pass
    await state.update_data(fix_photo=None)
    ask_d = await call.message.answer("Введите описание Правки:")
    await state.update_data(fix_ask_desc=ask_d.message_id)
    await NewFixStates.waiting_for_description.set()
    await call.answer()

@dp.message_handler(state=NewFixStates.waiting_for_photo, content_types=types.ContentType.PHOTO)
async def on_fix_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ask_img = data.get("fix_ask_img")
    if ask_img:
        try:
            await bot.delete_message(message.chat.id, ask_img)
        except:
            pass
    photo_id = message.photo[-1].file_id
    await message.delete()
    await state.update_data(fix_photo=photo_id)
    ask_desc = await message.answer("Введите описание Правки:")
    await state.update_data(fix_ask_desc=ask_desc.message_id)
    await NewFixStates.waiting_for_description.set()

@dp.message_handler(state=NewFixStates.waiting_for_description, content_types=types.ContentType.TEXT)
async def on_fix_desc(message: types.Message, state: FSMContext):
    global FIX_COUNTER
    data = await state.get_data()
    dev = data["fix_dev"]
    test = data["fix_tester"]
    photo = data.get("fix_photo")
    ask_desc = data.get("fix_ask_desc")
    if ask_desc:
        try:
            await bot.delete_message(message.chat.id, ask_desc)
        except:
            pass
    await message.delete()
    desc = message.text

    idx = FIX_COUNTER
    FIX_COUNTER += 1

    text = build_task_text(idx, "Правка", dev, test, desc, "work")
    kb = glitch_work_keyboard()  # Исправлено справа
    if photo:
        msg = await message.answer_photo(photo, caption=text, reply_markup=kb)
    else:
        msg = await message.answer(text, reply_markup=kb)

    arr = TASKS.setdefault(message.chat.id, [])
    arr.append({
        "type": "Правка",
        "local_id": idx,
        "message_id": msg.message_id,
        "dev": dev,
        "tester": test,
        "desc": desc,
        "photo": photo,
        "status": "work"
    })
    await state.finish()

#############################
# Исправлено (glitch_fixed)
#############################

@dp.callback_query_handler(lambda c: c.data == "glitch_fixed")
async def on_glitch_fixed(call: types.CallbackQuery):
    msg = call.message
    old_txt = msg.caption if msg.photo else msg.text
    new_txt = old_txt + f"\n#accept\nИсправлено: {now_str()}"
    kb = glitch_accept_keyboard()  # Принято справа
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_txt, reply_markup=kb)
        else:
            await bot.edit_message_text(new_txt, msg.chat.id, msg.message_id, reply_markup=kb)
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    obj = find_card(msg.chat.id, msg.message_id)
    if obj:
        obj["status"] = "accept"
    await call.answer("Исправлено -> accept")

@dp.callback_query_handler(lambda c: c.data == "glitch_comment")
async def on_glitch_comment(call: types.CallbackQuery, state: FSMContext):
    msg = call.message
    old = msg.caption if msg.photo else msg.text
    kb = msg.reply_markup
    await state.update_data(
        comment_chat_id=msg.chat.id,
        comment_msg_id=msg.message_id,
        old_text=old,
        old_kb=kb,
        is_photo=bool(msg.photo)
    )
    ask = await msg.answer("Введите комментарий для Глюка/Правки:")
    await state.update_data(comment_ask_id=ask.message_id)
    await CommentStates.waiting_for_comment_text.set()
    await call.answer()

@dp.callback_query_handler(lambda c: c.data == "glitch_fail")
async def on_glitch_fail(call: types.CallbackQuery):
    """
    Не работает => создаём новую правку
    """
    base_obj = find_card(call.message.chat.id, call.message.message_id)
    dev = base_obj["dev"] if base_obj else "@noDev"
    test = base_obj["tester"] if base_obj else "@noTester"

    await call.message.delete()
    await call.answer("Создаём новую правку...")

    from states.bot_states import NewFixStates
    s = dp.current_state(chat=call.message.chat.id, user=call.from_user.id)
    await s.update_data(fix_dev=dev, fix_tester=test)

    ask = await call.message.answer("Отправьте картинку для Правки или 'Пропустить':",
                                    reply_markup=glitch_skip_image_keyboard())
    await s.update_data(fix_ask_img=ask.message_id)
    await s.set_state(NewFixStates.waiting_for_photo)

@dp.callback_query_handler(lambda c: c.data == "glitch_closed")
async def on_glitch_closed(call: types.CallbackQuery):
    msg = call.message
    old = msg.caption if msg.photo else msg.text
    new_txt = old + "\nПринято!"
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_txt)
        else:
            await bot.edit_message_text(new_txt, msg.chat.id, msg.message_id)
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    obj = find_card(msg.chat.id, msg.message_id)
    if obj:
        obj["status"] = "closed"
    await call.answer("Глюк/Правка закрыта")
