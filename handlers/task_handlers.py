import datetime
import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from aiogram.utils.exceptions import MessageToDeleteNotFound

from loader import dp, bot
from states.bot_states import (
    NewTaskStates, EditTaskStates, CommentStates,
    NewGlitchStates, NewFixStates
)
from handlers.project_handlers import PROJECTS, generate_project_text
from keyboards.keyboards import (
    task_init_keyboard, task_after_confirm_keyboard,
    task_work_keyboard, task_test_keyboard, task_accept_keyboard,
    glitch_or_fix_keyboard, glitch_skip_image_keyboard,
    glitch_work_keyboard, glitch_test_keyboard, glitch_accept_keyboard,
    fix_work_keyboard, fix_test_keyboard, fix_accept_keyboard,
    task_skip_image_keyboard, fix_skip_image_keyboard
)

logging.basicConfig(level=logging.INFO)

TASKS = {}  # TASKS[chat_id] = list of tasks / glitch / fix
TASK_COUNTER = 1
GLITCH_COUNTER = 1
FIX_COUNTER = 1


def now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def build_task_text(idx: int, prefix: str, creator: str, dev: str, tester: str, desc: str, status: str) -> str:
    """Формирует текст карточки задачи/глюка/правки."""
    return (
        f"{prefix}-{idx}\n"
        f"P: {creator}\n"
        f"D: {dev}\n"
        f"T: {tester}\n"
        f"Дата: {now_str()}\n"
        f"Описание: {desc}\n"
        f"#{status}"
    )


def find_card(chat_id: int, message_id: int):
    for obj in TASKS.get(chat_id, []):
        if obj["message_id"] == message_id:
            return obj
    return None


async def update_project_card(chat_id: int):
    """Обновляет карточку проекта для ТЗ (глюки и правки не включаются)."""
    if chat_id not in PROJECTS:
        return
    arr = TASKS.get(chat_id, [])
    project_obj = PROJECTS[chat_id]
    base_text = generate_project_text(project_obj).replace("\n-- сюда добавляются таски", "").strip()
    tasks_only = [x for x in arr if x["type"] == "ТЗ"]
    if tasks_only:
        tasks_lines = "".join(f"\nТЗ-{t['local_id']}: {t['desc']} ({t['dev']})" for t in tasks_only)
        final_text = base_text + tasks_lines
    else:
        final_text = base_text
    project_obj["pinned_text"] = final_text
    PROJECTS[chat_id] = project_obj
    msg_id = project_obj["message_id"]
    file_id = project_obj.get("photo_id")
    try:
        if file_id:
            media = types.InputMediaPhoto(file_id, caption=final_text)
            await bot.edit_message_media(media, chat_id, msg_id)
        else:
            await bot.edit_message_text(final_text, chat_id, msg_id)
    except Exception as e:
        if "Message is not modified" in str(e):
            pass
        else:
            logging.error(f"Ошибка при update_project_card: {e}")


####################################
# Создание основной задачи (ТЗ)
####################################

@dp.message_handler(Command("addTask"))
async def cmd_add_task(message: types.Message, state: FSMContext):
    await message.delete()
    if message.chat.id not in PROJECTS:
        await message.answer("В этом чате нет проекта.")
        return
    # Выбор разработчика
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
    # Выбор тестировщика
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

# Обработчики выбора разработчика/тестировщика и описания для ТЗ
@dp.callback_query_handler(lambda c: c.data.startswith("task_dev_pick:"))
async def on_dev_pick(call: types.CallbackQuery, state: FSMContext):
    dev = call.data.split("task_dev_pick:")[1]
    data = await state.get_data()
    if data.get("dev_msg"):
        try:
            await bot.delete_message(call.message.chat.id, data["dev_msg"])
        except:
            pass
    await state.update_data(task_dev=dev)
    await call.answer(f"Разработчик {dev} выбран")
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
    test = call.data.split("task_test_pick:")[1]
    data = await state.get_data()
    if data.get("test_msg"):
        try:
            await bot.delete_message(call.message.chat.id, data["test_msg"])
        except:
            pass
    await state.update_data(task_tester=test)
    await call.answer(f"Тестировщик {test} выбран")
    ask_desc = await call.message.answer("Введите описание (ТЗ):")
    await state.update_data(ask_desc=ask_desc.message_id)
    await NewTaskStates.waiting_for_task_description.set()

@dp.message_handler(state=NewTaskStates.waiting_for_task_description, content_types=types.ContentType.TEXT)
async def on_task_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if data.get("ask_desc"):
        try:
            await bot.delete_message(message.chat.id, data["ask_desc"])
        except:
            pass
    desc = message.text
    await message.delete()
    await state.update_data(task_description=desc)
    # Для задачи используем клавиатуру с callback "skip_task_image"
    ask_photo = await message.answer("Отправьте фото для задачи или 'Пропустить':", reply_markup=task_skip_image_keyboard())
    await state.update_data(task_photo_ask=ask_photo.message_id)
    await NewTaskStates.waiting_for_task_photo.set()

@dp.callback_query_handler(lambda c: c.data == "skip_task_image", state=NewTaskStates.waiting_for_task_photo)
async def skip_task_photo(call: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        if data.get("task_photo_ask"):
            try:
                await bot.delete_message(call.message.chat.id, data["task_photo_ask"])
            except MessageToDeleteNotFound:
                pass
            except Exception as e:
                logging.error(f"Ошибка при удалении task_photo_ask: {e}")
        try:
            await call.message.delete()
        except MessageToDeleteNotFound:
            pass
        except Exception as e:
            logging.error(f"Ошибка при удалении сообщения: {e}")
        await state.update_data(task_photo=None)
        await finalize_task_creation(call.message.chat.id, state)
        await call.answer("Пропущено фото")
        await state.finish()
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

@dp.message_handler(state=NewTaskStates.waiting_for_task_photo, content_types=types.ContentType.PHOTO)
async def on_task_photo(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        if data.get("task_photo_ask"):
            try:
                await bot.delete_message(message.chat.id, data["task_photo_ask"])
            except:
                pass
    except Exception as e:
        logging.error(f"Ошибка при удалении ask_photo: {e}")
    photo_id = message.photo[-1].file_id
    await message.delete()
    await state.update_data(task_photo=photo_id)
    await finalize_task_creation(message.chat.id, state)
    await state.finish()

async def finalize_task_creation(chat_id: int, state: FSMContext):
    global TASK_COUNTER
    data = await state.get_data()
    dev = data.get("task_dev", "@noDev")
    tester = data.get("task_tester", "@noTester")
    desc = data.get("task_description", "")
    photo = data.get("task_photo")
    creator = PROJECTS[chat_id].get("creator_username", "@unknown")
    idx = TASK_COUNTER
    TASK_COUNTER += 1
    text = build_task_text(idx, "ТЗ", creator, dev, tester, desc, "new")
    kb = task_init_keyboard()
    if photo:
        msg = await bot.send_photo(chat_id, photo=photo, caption=text, reply_markup=kb)
    else:
        msg = await bot.send_message(chat_id, text, reply_markup=kb)
    TASKS.setdefault(chat_id, []).append({
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

####################################
# Обработчики создания глюка
####################################

@dp.callback_query_handler(lambda c: c.data == "choose_glitch")
async def on_choose_glitch(call: types.CallbackQuery, state: FSMContext):
    try:
        base = find_card(call.message.chat.id, call.message.message_id)
        dev = base["dev"] if base else "@noDev"
        test = base["tester"] if base else "@noTester"
        await call.message.delete()
        await state.update_data(glitch_dev=dev, glitch_tester=test)
        ask = await bot.send_message(call.message.chat.id, "Отправьте картинку для Глюка или 'Пропустить':",
                                     reply_markup=glitch_skip_image_keyboard())
        await state.update_data(gl_ask_img=ask.message_id)
        await NewGlitchStates.waiting_for_photo.set()
        await call.answer("Переход к созданию глюка")
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "skip_glitch_image", state=NewGlitchStates.waiting_for_photo)
async def on_skip_gl_img(call: types.CallbackQuery, state: FSMContext):
    try:
        logging.info("skip_glitch_image: начало")
        data = await state.get_data()
        if data.get("gl_ask_img"):
            try:
                await bot.delete_message(call.message.chat.id, data["gl_ask_img"])
                logging.info("skip_glitch_image: удалено gl_ask_img")
            except MessageToDeleteNotFound:
                logging.info("skip_glitch_image: gl_ask_img не найдено")
            except Exception as e:
                logging.error(f"skip_glitch_image: ошибка при удалении gl_ask_img: {e}")
        try:
            await call.message.delete()
            logging.info("skip_glitch_image: сообщение удалено")
        except MessageToDeleteNotFound:
            logging.info("skip_glitch_image: сообщение не найдено")
        except Exception as e:
            logging.error(f"skip_glitch_image: ошибка при удалении сообщения: {e}")
        await state.update_data(glitch_photo=None)
        ask = await bot.send_message(call.message.chat.id, "Введите описание глюка:")
        await state.update_data(gl_ask_desc=ask.message_id)
        await NewGlitchStates.waiting_for_description.set()
        await call.answer("Пропущено фото")
        logging.info("skip_glitch_image: завершено")
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

@dp.message_handler(state=NewGlitchStates.waiting_for_photo, content_types=types.ContentType.PHOTO)
async def on_gl_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if data.get("gl_ask_img"):
        try:
            await bot.delete_message(message.chat.id, data["gl_ask_img"])
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
    dev = data.get("glitch_dev", "@noDev")
    test = data.get("glitch_tester", "@noTester")
    photo = data.get("glitch_photo")
    if data.get("gl_ask_desc"):
        try:
            await bot.delete_message(message.chat.id, data["gl_ask_desc"])
        except:
            pass
    await message.delete()
    desc = message.text
    idx = GLITCH_COUNTER
    GLITCH_COUNTER += 1
    # Для глюка считаем статус "work" по умолчанию
    text = build_task_text(idx, "Глюк", "@unknown", dev, test, desc, "work")
    kb = glitch_work_keyboard()
    if photo:
        new_msg = await message.answer_photo(photo, caption=text, reply_markup=kb)
    else:
        new_msg = await message.answer(text, reply_markup=kb)
    TASKS.setdefault(message.chat.id, []).append({
        "type": "Глюк",
        "local_id": idx,
        "message_id": new_msg.message_id,
        "dev": dev,
        "tester": test,
        "desc": desc,
        "photo": photo,
        "status": "work"
    })
    await state.finish()

####################################
# Обработчики создания правки
####################################

@dp.callback_query_handler(lambda c: c.data == "choose_fix")
async def on_choose_fix(call: types.CallbackQuery, state: FSMContext):
    try:
        base = find_card(call.message.chat.id, call.message.message_id)
        dev = base["dev"] if base else "@noDev"
        test = base["tester"] if base else "@noTester"
        await call.message.delete()
        await state.update_data(fix_dev=dev, fix_tester=test)
        # Используем новую клавиатуру для правок с callback "skip_fix_image"
        ask = await bot.send_message(call.message.chat.id, "Отправьте картинку для Правки или 'Пропустить':",
                                     reply_markup=fix_skip_image_keyboard())
        await state.update_data(fix_ask_img=ask.message_id)
        await NewFixStates.waiting_for_photo.set()
        await call.answer("Переход к созданию правки")
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "skip_fix_image", state=NewFixStates.waiting_for_photo)
async def skip_fix_image(call: types.CallbackQuery, state: FSMContext):
    try:
        logging.info("skip_fix_image: начало")
        data = await state.get_data()
        if data.get("fix_ask_img"):
            try:
                await bot.delete_message(call.message.chat.id, data["fix_ask_img"])
                logging.info("skip_fix_image: удалено fix_ask_img")
            except MessageToDeleteNotFound:
                logging.info("skip_fix_image: fix_ask_img не найдено")
            except Exception as e:
                logging.error(f"skip_fix_image: ошибка при удалении fix_ask_img: {e}")
        try:
            await call.message.delete()
            logging.info("skip_fix_image: сообщение удалено")
        except MessageToDeleteNotFound:
            logging.info("skip_fix_image: сообщение не найдено")
        except Exception as e:
            logging.error(f"skip_fix_image: ошибка при удалении сообщения: {e}")
        await state.update_data(fix_photo=None)
        ask = await bot.send_message(call.message.chat.id, "Введите описание Правки:")
        await state.update_data(fix_ask_desc=ask.message_id)
        await NewFixStates.waiting_for_description.set()
        await call.answer("Пропущено фото")
        logging.info("skip_fix_image: завершено")
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

@dp.message_handler(state=NewFixStates.waiting_for_photo, content_types=types.ContentType.PHOTO)
async def on_fix_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if data.get("fix_ask_img"):
        try:
            await bot.delete_message(message.chat.id, data["fix_ask_img"])
        except:
            pass
    photo_id = message.photo[-1].file_id
    await message.delete()
    await state.update_data(fix_photo=photo_id)
    ask = await message.answer("Введите описание Правки:")
    await state.update_data(fix_ask_desc=ask.message_id)
    await NewFixStates.waiting_for_description.set()

@dp.message_handler(state=NewFixStates.waiting_for_description, content_types=types.ContentType.TEXT)
async def on_fix_desc(message: types.Message, state: FSMContext):
    global FIX_COUNTER
    data = await state.get_data()
    dev = data.get("fix_dev", "@noDev")
    test = data.get("fix_tester", "@noTester")
    photo = data.get("fix_photo")
    if data.get("fix_ask_desc"):
        try:
            await bot.delete_message(message.chat.id, data["fix_ask_desc"])
        except:
            pass
    await message.delete()
    desc = message.text
    idx = FIX_COUNTER
    FIX_COUNTER += 1
    text = build_task_text(idx, "Правка", "@unknown", dev, test, desc, "work")
    kb = fix_work_keyboard()  # можно заменить на fix_work_keyboard или использовать glitch_work_keyboard, если одинаковы
    if photo:
        new_msg = await message.answer_photo(photo, caption=text, reply_markup=kb)
    else:
        new_msg = await message.answer(text, reply_markup=kb)
    TASKS.setdefault(message.chat.id, []).append({
        "type": "Правка",
        "local_id": idx,
        "message_id": new_msg.message_id,
        "dev": dev,
        "tester": test,
        "desc": desc,
        "photo": photo,
        "status": "work"
    })
    await state.finish()

####################################
# Обработчики переходов и комментариев
####################################

@dp.callback_query_handler(lambda c: c.data == "task_confirm")
async def on_task_confirm(call: types.CallbackQuery):
    msg = call.message
    old_txt = msg.caption if msg.photo else msg.text
    kb = task_after_confirm_keyboard()
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=old_txt, reply_markup=kb)
        else:
            await bot.edit_message_text(old_txt, msg.chat.id, msg.message_id, reply_markup=kb)
    except Exception as e:
        logging.error(f"Ошибка при confirm: {e}")
    await call.answer("Таск подтверждён")

@dp.callback_query_handler(lambda c: c.data == "task_edit_init")
async def on_task_edit_init(call: types.CallbackQuery, state: FSMContext):
    msg = call.message
    await state.update_data(edit_chat_id=msg.chat.id, edit_msg_id=msg.message_id)
    ask = await msg.answer("Введите новое описание (ТЗ):")
    await state.update_data(edit_ask_msg=ask.message_id)
    await EditTaskStates.waiting_for_new_task_text.set()
    await call.answer()

@dp.message_handler(state=EditTaskStates.waiting_for_new_task_text, content_types=types.ContentType.TEXT)
async def on_edit_task_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["edit_chat_id"]
    msg_id = data["edit_msg_id"]
    if data.get("edit_ask_msg"):
        try:
            await bot.delete_message(chat_id, data["edit_ask_msg"])
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
    ttype = card_obj["type"]
    dev = card_obj["dev"]
    test = card_obj["tester"]
    photo_id = card_obj["photo"]
    creator = PROJECTS[chat_id].get("creator_username", "@unknown")
    text = build_task_text(idx, ttype, creator, dev, test, new_desc, old_status)
    if old_status == "new":
        kb = task_init_keyboard()
    elif old_status == "work":
        kb = task_work_keyboard()
    elif old_status == "test":
        kb = task_test_keyboard()
    elif old_status == "accept":
        kb = task_accept_keyboard()
    else:
        kb = None
    try:
        if photo_id:
            await bot.edit_message_caption(chat_id, msg_id, caption=text, reply_markup=kb)
        else:
            await bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb)
    except Exception as e:
        logging.error(f"Ошибка редактирования: {e}")
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
        await update_project_card(call.message.chat.id)
        await call.answer("Таск удалён.")
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "task_comment")
async def on_task_comment(call: types.CallbackQuery, state: FSMContext):
    msg = call.message
    await state.update_data(
        comment_chat_id=msg.chat.id,
        comment_msg_id=msg.message_id,
        old_text=(msg.caption if msg.photo else msg.text),
        old_kb=msg.reply_markup,
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
    new_txt = data["old_text"] + f"\nКомментарий(@{message.from_user.username or 'unknown'}): {message.text}"
    await message.delete()
    try:
        if data["is_photo"]:
            await bot.edit_message_caption(chat_id, msg_id, caption=new_txt, reply_markup=data["old_kb"])
        else:
            await bot.edit_message_text(new_txt, chat_id, msg_id, reply_markup=data["old_kb"])
    except Exception as e:
        await message.answer(f"Ошибка комментария: {e}")
    await state.finish()

#############################
# Переходы статусов для ТЗ
#############################

@dp.callback_query_handler(lambda c: c.data == "task_in_work")
async def on_task_in_work_main(call: types.CallbackQuery):
    msg = call.message
    old = msg.caption if msg.photo else msg.text
    new_txt = old + "\n#work"
    kb = task_work_keyboard()
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
    card_obj = find_card(msg.chat.id, msg.message_id)
    if not card_obj:
        await call.answer("Объект не найден", show_alert=True)
        return
    current_status = card_obj.get("status", "new")
    if current_status == "work":
        new_txt = old + "\n#test"
        kb = task_test_keyboard()
        card_obj["status"] = "test"
        ans = "Таск -> test"
    elif current_status == "test":
        new_txt = old + "\n#accept"
        kb = task_accept_keyboard()
        card_obj["status"] = "accept"
        ans = "Таск -> accept"
    else:
        await call.answer("Неверный переход", show_alert=True)
        return
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_txt, reply_markup=kb)
        else:
            await bot.edit_message_text(new_txt, msg.chat.id, msg.message_id, reply_markup=kb)
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    await call.answer(ans)

@dp.callback_query_handler(lambda c: c.data == "task_reject_choice")
async def on_task_reject_main(call: types.CallbackQuery):
    kb = glitch_or_fix_keyboard()
    await call.message.answer("Что создать: Глюк или Правка?", reply_markup=kb)
    await call.answer("Переход к созданию глюка/правки")

@dp.callback_query_handler(lambda c: c.data == "task_fail_choice")
async def on_task_fail_main(call: types.CallbackQuery):
    kb = glitch_or_fix_keyboard()
    await call.message.answer("Что создать: Глюк или Правка?", reply_markup=kb)
    await call.answer("Переход к созданию глюка/правки")

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
# Переходы статусов для глюков
#############################

@dp.callback_query_handler(lambda c: c.data == "glitch_done")
async def on_glitch_done(call: types.CallbackQuery):
    msg = call.message
    old = msg.caption if msg.photo else msg.text
    card_obj = find_card(msg.chat.id, msg.message_id)
    if not card_obj:
        await call.answer("Объект не найден", show_alert=True)
        return
    if card_obj.get("status", "new") == "work":
        new_txt = old + "\n#test"
        kb = glitch_test_keyboard()
        card_obj["status"] = "test"
        ans = "Глюк -> test"
    elif card_obj.get("status") == "test":
        new_txt = old + "\n#accept"
        kb = glitch_accept_keyboard()
        card_obj["status"] = "accept"
        ans = "Глюк -> accept"
    else:
        await call.answer("Неверный переход", show_alert=True)
        return
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_txt, reply_markup=kb)
        else:
            await bot.edit_message_text(new_txt, msg.chat.id, msg.message_id, reply_markup=kb)
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    await call.answer(ans)

@dp.callback_query_handler(lambda c: c.data == "glitch_reject_choice")
async def on_glitch_reject(call: types.CallbackQuery):
    kb = glitch_or_fix_keyboard()
    await call.message.answer("Что создать: Глюк или Правка?", reply_markup=kb)
    await call.answer("Переход к созданию глюка/правки")

@dp.callback_query_handler(lambda c: c.data == "glitch_fail_choice")
async def on_glitch_fail(call: types.CallbackQuery):
    kb = glitch_or_fix_keyboard()
    await call.message.answer("Что создать: Глюк или Правка?", reply_markup=kb)
    await call.answer("Переход к созданию глюка/правки")

@dp.callback_query_handler(lambda c: c.data == "glitch_closed")
async def on_glitch_closed(call: types.CallbackQuery):
    msg = call.message
    old = msg.caption if msg.photo else msg.text
    new_txt = old + "\n#closed\nГлюк завершён."
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
    await call.answer("Глюк закрыт.")

#############################
# Переходы статусов для правок
#############################

@dp.callback_query_handler(lambda c: c.data == "fix_done")
async def on_fix_done(call: types.CallbackQuery):
    msg = call.message
    old = msg.caption if msg.photo else msg.text
    card_obj = find_card(msg.chat.id, msg.message_id)
    if not card_obj:
        await call.answer("Объект не найден", show_alert=True)
        return
    if card_obj.get("status", "new") == "work":
        new_txt = old + "\n#test"
        kb = fix_test_keyboard()
        card_obj["status"] = "test"
        ans = "Правка -> test"
    elif card_obj.get("status") == "test":
        new_txt = old + "\n#accept"
        kb = fix_accept_keyboard()
        card_obj["status"] = "accept"
        ans = "Правка -> accept"
    else:
        await call.answer("Неверный переход", show_alert=True)
        return
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_txt, reply_markup=kb)
        else:
            await bot.edit_message_text(new_txt, msg.chat.id, msg.message_id, reply_markup=kb)
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    await call.answer(ans)

@dp.callback_query_handler(lambda c: c.data == "fix_reject_choice")
async def on_fix_reject(call: types.CallbackQuery):
    kb = glitch_or_fix_keyboard()
    await call.message.answer("Что создать: Глюк или Правка?", reply_markup=kb)
    await call.answer("Переход к созданию глюка/правки")

@dp.callback_query_handler(lambda c: c.data == "fix_fail_choice")
async def on_fix_fail(call: types.CallbackQuery):
    kb = glitch_or_fix_keyboard()
    await call.message.answer("Что создать: Глюк или Правка?", reply_markup=kb)
    await call.answer("Переход к созданию глюка/правки")

@dp.callback_query_handler(lambda c: c.data == "fix_closed")
async def on_fix_closed(call: types.CallbackQuery):
    msg = call.message
    old = msg.caption if msg.photo else msg.text
    new_txt = old + "\n#closed\nПравка завершена."
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
    await call.answer("Правка закрыта.")

#############################
# Обработчики выбора создания глюка и правок
#############################

@dp.callback_query_handler(lambda c: c.data == "choose_glitch")
async def on_choose_glitch(call: types.CallbackQuery, state: FSMContext):
    try:
        base = find_card(call.message.chat.id, call.message.message_id)
        dev = base["dev"] if base else "@noDev"
        test = base["tester"] if base else "@noTester"
        await call.message.delete()
        await state.update_data(glitch_dev=dev, glitch_tester=test)
        ask = await bot.send_message(call.message.chat.id, "Отправьте картинку для Глюка или 'Пропустить':",
                                     reply_markup=glitch_skip_image_keyboard())
        await state.update_data(gl_ask_img=ask.message_id)
        await NewGlitchStates.waiting_for_photo.set()
        await call.answer("Переход к созданию глюка")
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "choose_fix")
async def on_choose_fix(call: types.CallbackQuery, state: FSMContext):
    try:
        base = find_card(call.message.chat.id, call.message.message_id)
        dev = base["dev"] if base else "@noDev"
        test = base["tester"] if base else "@noTester"
        await call.message.delete()
        await state.update_data(fix_dev=dev, fix_tester=test)
        ask = await bot.send_message(call.message.chat.id, "Отправьте картинку для Правки или 'Пропустить':",
                                     reply_markup=fix_skip_image_keyboard())
        await state.update_data(fix_ask_img=ask.message_id)
        await NewFixStates.waiting_for_photo.set()
        await call.answer("Переход к созданию правки")
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
