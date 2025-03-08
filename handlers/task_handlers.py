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

# ------------------ Глобальные словари и счётчики ------------------
TASKS = {}  # TASKS[chat_id] = список объектов тасков
TASK_COUNTER = 1
GLITCH_COUNTER = 1
FIX_COUNTER = 1

# ------------------ Функции для проверки ролей ------------------
def get_user(call: types.CallbackQuery) -> str:
    """Возвращает юзернейм в формате '@username'."""
    return "@" + (call.from_user.username or "unknown")

def is_creator(call: types.CallbackQuery, chat_id: int) -> bool:
    """Возвращает True, если вызывающий пользователь – создатель проекта."""
    return get_user(call) == PROJECTS.get(chat_id, {}).get("creator_username", "@unknown")

def is_dev(call: types.CallbackQuery, card: dict) -> bool:
    """Возвращает True, если вызывающий пользователь – назначенный разработчик карточки."""
    return get_user(call) == card.get("dev", "")

def is_tester(call: types.CallbackQuery, card: dict) -> bool:
    """Возвращает True, если вызывающий пользователь – назначенный тестировщик карточки."""
    return get_user(call) == card.get("tester", "")

# ------------------ Вспомогательные функции ------------------
def now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def format_user(user: str) -> str:
    """Возвращает имя без ведущего символа '@'."""
    return user.lstrip("@")

def build_task_base_text(idx: int, desc: str, dev: str, tester: str) -> str:
    """Формирует базовый текст карточки задачи типа 'ТЗ' без строки статуса."""
    return (
        f"#ТЗ-{idx}: (ТТ)\n"
        f"--{desc}\n"
        f"D::#{format_user(dev)} T::#{format_user(tester)}"
    )

def status_line_new(creator: str) -> str:
    dt = datetime.datetime.now().strftime("%d.%m %H:%M")
    return f"#new {dt} P::#{format_user(creator)}"

def status_line_work(dev: str) -> str:
    dt = datetime.datetime.now().strftime("%d.%m %H:%M")
    return f"#work {dt} D::#{format_user(dev)}"

def status_line_test(tester: str) -> str:
    dt = datetime.datetime.now().strftime("%d.%m %H:%M")
    return f"#test {dt} T::#{format_user(tester)}"

def status_line_accept(creator: str) -> str:
    dt = datetime.datetime.now().strftime("%d.%m %H:%M")
    return f"#accept {dt} P::#{format_user(creator)}"

def status_line_closed() -> str:
    dt = datetime.datetime.now().strftime("%d.%m %H:%M")
    return f"#closed {dt}"

def build_task_text(idx: int, prefix: str, creator: str, dev: str, tester: str, desc: str, status: str) -> str:
    """
    Формирует текст карточки задачи/глюка/правки.
    Для задач типа "ТЗ" используются отдельные строки для каждого статуса.
    """
    if prefix == "ТЗ":
        if status == "new":
            return (
                f"{build_task_base_text(idx, desc, dev, tester)}\n"
                f"{status_line_new(creator)}"
            )
        elif status == "work":
            return status_line_work(dev)
        elif status == "test":
            return status_line_test(tester)
        elif status == "accept":
            return status_line_accept(creator)
        elif status == "closed":
            return status_line_closed()
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
    """Обновляет карточку проекта (для ТЗ, без глюков и правок)."""
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

# ------------------ Команды и переходы ------------------

# Обнуляем глобальные словари и счётчики (если требуется)
TASKS = {}
TASK_COUNTER = 1
GLITCH_COUNTER = 1
FIX_COUNTER = 1

# /addTask может вызывать только создатель проекта
@dp.message_handler(Command("addTask"))
async def cmd_add_task(message: types.Message, state: FSMContext):
    await message.delete()
    if message.chat.id not in PROJECTS:
        await message.answer("В этом чате нет проекта.")
        return
    proj = PROJECTS[message.chat.id]
    user = "@" + (message.from_user.username or "unknown")
    if user != proj.get("creator_username"):
        await message.answer("Только создатель проекта может добавлять задачи.")
        return
    # Выбор разработчика
    devs = proj.get("devs", [])
    testers = proj.get("testers", [])
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

@dp.callback_query_handler(lambda c: c.data.startswith("task_dev_pick:"))
async def on_dev_pick(call: types.CallbackQuery, state: FSMContext):
    # Выбор разработчика может выполнять только создатель
    if not is_creator(call, call.message.chat.id):
        await call.answer("Только создатель проекта может выбирать разработчика", show_alert=True)
        return
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
    # Выбор тестировщика может выполнять только создатель
    if not is_creator(call, call.message.chat.id):
        await call.answer("Только создатель проекта может выбирать тестировщика", show_alert=True)
        return
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
    base_text = build_task_base_text(idx, desc, dev, tester)
    status_new = status_line_new(creator)
    full_text = base_text + "\n" + status_new
    kb = task_init_keyboard()
    if photo:
        msg = await bot.send_photo(chat_id, photo=photo, caption=full_text, reply_markup=kb)
    else:
        msg = await bot.send_message(chat_id, full_text, reply_markup=kb)
    TASKS.setdefault(chat_id, []).append({
        "type": "ТЗ",
        "local_id": idx,
        "message_id": msg.message_id,
        "dev": dev,
        "tester": tester,
        "desc": desc,
        "photo": photo,
        "status": "new",
        "base_text": base_text,
        "statuses": [status_new]
    })
    await update_project_card(chat_id)

# ------------------ Обработчики для создания глюков ------------------

@dp.callback_query_handler(lambda c: c.data == "choose_glitch")
async def on_choose_glitch(call: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        # Если сохранён base_task_message_id, используем его, иначе — текущий ID
        base_id = data.get("base_task_message_id") or call.message.message_id
        base = find_card(call.message.chat.id, base_id)
        if not base:
            if is_creator(call, call.message.chat.id):
                proj = PROJECTS.get(call.message.chat.id, {})
                devs = proj.get("devs", [])
                testers = proj.get("testers", [])
                # Если списки пустые, используем дефолтные значения
                dev = devs[0] if devs else "@noDev"
                test = testers[0] if testers else "@noTester"
                base = {"dev": dev, "tester": test}
            else:
                await call.answer("Исходная задача не найдена", show_alert=True)
                return
        # Создание глюка могут выполнять создатель, назначенный разработчик или тестировщик
        if not (is_creator(call, call.message.chat.id) or is_dev(call, base) or is_tester(call, base)):
            await call.answer("Недостаточно прав для создания глюка", show_alert=True)
            return
        dev = base["dev"]
        test = base["tester"]
        await state.update_data(glitch_dev=dev, glitch_tester=test)
        try:
            await call.message.delete()
        except Exception:
            pass
        ask = await bot.send_message(
            call.message.chat.id,
            "Отправьте картинку для Глюка или 'Пропустить':",
            reply_markup=glitch_skip_image_keyboard()
        )
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
    ask_desc = await bot.send_message(message.chat.id, "Введите описание глюка:")
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
    base_text = f"#Глюк-{idx}\n--{desc}\nD::#{format_user(dev)} T::#{format_user(test)}"
    status = status_line_work(dev)
    full_text = base_text + "\n" + status
    kb = glitch_work_keyboard()
    if photo:
        new_msg = await message.answer_photo(photo, caption=full_text, reply_markup=kb)
    else:
        new_msg = await message.answer(full_text, reply_markup=kb)
    TASKS.setdefault(message.chat.id, []).append({
        "type": "Глюк",
        "local_id": idx,
        "message_id": new_msg.message_id,
        "dev": dev,
        "tester": test,
        "desc": desc,
        "photo": photo,
        "status": "work",
        "base_text": base_text,
        "statuses": [status]
    })
    await state.finish()

# ------------------ Обработчики для создания правки ------------------

@dp.callback_query_handler(lambda c: c.data == "choose_fix")
async def on_choose_fix(call: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        base_id = data.get("base_task_message_id") or call.message.message_id
        base = find_card(call.message.chat.id, base_id)
        if not base:
            if is_creator(call, call.message.chat.id):
                proj = PROJECTS.get(call.message.chat.id, {})
                devs = proj.get("devs", [])
                testers = proj.get("testers", [])
                dev = devs[0] if devs else "@noDev"
                test = testers[0] if testers else "@noTester"
                base = {"dev": dev, "tester": test}
            else:
                await call.answer("Исходная задача не найдена", show_alert=True)
                return
        # Создание правки могут выполнять только создатель или назначенный тестировщик
        if not (is_creator(call, call.message.chat.id) or is_tester(call, base)):
            await call.answer("Недостаточно прав для создания правки", show_alert=True)
            return
        dev = base["dev"]
        test = base["tester"]
        await state.update_data(fix_dev=dev, fix_tester=test)
        try:
            await call.message.delete()
        except Exception:
            pass
        ask = await bot.send_message(
            call.message.chat.id,
            "Отправьте картинку для Правки или 'Пропустить':",
            reply_markup=fix_skip_image_keyboard()
        )
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
    ask = await bot.send_message(message.chat.id, "Введите описание Правки:")
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
    base_text = f"#Правка-{idx}\n--{desc}\nD::#{format_user(dev)} T::#{format_user(test)}"
    status = status_line_work(dev)
    full_text = base_text + "\n" + status
    kb = fix_work_keyboard()
    if photo:
        new_msg = await message.answer_photo(photo, caption=full_text, reply_markup=kb)
    else:
        new_msg = await message.answer(full_text, reply_markup=kb)
    TASKS.setdefault(message.chat.id, []).append({
        "type": "Правка",
        "local_id": idx,
        "message_id": new_msg.message_id,
        "dev": dev,
        "tester": test,
        "desc": desc,
        "photo": photo,
        "status": "work",
        "base_text": base_text,
        "statuses": [status]
    })
    await state.finish()

# ------------------ Обработчики переходов и комментариев ------------------

@dp.callback_query_handler(lambda c: c.data == "task_confirm")
async def on_task_confirm(call: types.CallbackQuery):
    # Только создатель может подтверждать задачу
    if not is_creator(call, call.message.chat.id):
        await call.answer("Только создатель проекта может подтверждать задачу", show_alert=True)
        return
    msg = call.message
    card = find_card(msg.chat.id, msg.message_id)
    if not card:
        await call.answer("Объект не найден", show_alert=True)
        return
    if card["status"] != "new":
        await call.answer("Таск уже подтверждён", show_alert=True)
        return
    kb = task_after_confirm_keyboard()
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=msg.caption, reply_markup=kb)
        else:
            await bot.edit_message_text(msg.text, msg.chat.id, msg.message_id, reply_markup=kb)
    except Exception as e:
        logging.error(f"Ошибка при confirm: {e}")
    await call.answer("Таск подтверждён")

@dp.callback_query_handler(lambda c: c.data == "task_edit_init")
async def on_task_edit_init(call: types.CallbackQuery, state: FSMContext):
    # Только создатель может редактировать задачу
    if not is_creator(call, call.message.chat.id):
        await call.answer("Только создатель проекта может редактировать задачу", show_alert=True)
        return
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
    card = None
    for x in arr:
        if x["message_id"] == msg_id:
            card = x
            break
    if not card:
        return
    card["desc"] = new_desc
    old_status = card.get("status", "new")
    idx = card["local_id"]
    ttype = card["type"]
    dev = card["dev"]
    test = card["tester"]
    photo_id = card["photo"]
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
    # Только создатель может удалять задачу
    if not is_creator(call, call.message.chat.id):
        await call.answer("Только создатель проекта может удалять задачу", show_alert=True)
        return
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
    card = find_card(msg.chat.id, msg.message_id)
    user = get_user(call)
    if card:
        if card.get("status") == "work" and not (is_dev(call, card) or is_creator(call, msg.chat.id)):
            await call.answer("Комментарий может оставлять только разработчик или создатель проекта.", show_alert=True)
            return
        if card.get("status") == "test" and not (is_tester(call, card) or is_creator(call, msg.chat.id)):
            await call.answer("Комментарий может оставлять только тестировщик или создатель проекта.", show_alert=True)
            return
        if card.get("status") == "accept" and not is_creator(call, msg.chat.id):
            await call.answer("Комментарий в стадии accept может оставлять только создатель проекта.", show_alert=True)
            return
    state_data = await state.get_data()
    if state_data.get("comment_ask_id"):
        try:
            await bot.delete_message(msg.chat.id, state_data["comment_ask_id"])
        except Exception:
            pass
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
    new_txt = data["old_text"] + f"\nКомментарий(#{message.from_user.username or 'unknown'}): {message.text}"
    await message.delete()
    try:
        if data["is_photo"]:
            await bot.edit_message_caption(chat_id, msg_id, caption=new_txt, reply_markup=data["old_kb"])
        else:
            await bot.edit_message_text(new_txt, chat_id, msg_id, reply_markup=data["old_kb"])
    except Exception as e:
        await message.answer(f"Ошибка комментария: {e}")
    if "comment_ask_id" in data:
        try:
            await bot.delete_message(chat_id, data["comment_ask_id"])
        except Exception:
            pass
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "task_in_work")
async def on_task_in_work_main(call: types.CallbackQuery):
    # Переход в стадию work может выполнять только создатель или назначенный разработчик
    if not (is_creator(call, call.message.chat.id) or is_dev(call, find_card(call.message.chat.id, call.message.message_id))):
        await call.answer("Только создатель или назначенный разработчик могут начать выполнение", show_alert=True)
        return
    msg = call.message
    card = find_card(msg.chat.id, msg.message_id)
    if not card:
        await call.answer("Объект не найден", show_alert=True)
        return
    new_status = status_line_work(card["dev"])
    card["status"] = "work"
    statuses = card.get("statuses", [])
    statuses.append(new_status)
    card["statuses"] = statuses
    new_text = card["base_text"] + "\n" + "\n".join(statuses)
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_text, reply_markup=task_work_keyboard())
        else:
            await bot.edit_message_text(new_text, msg.chat.id, msg.message_id, reply_markup=task_work_keyboard())
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    await call.answer("Таск -> work")

@dp.callback_query_handler(lambda c: c.data == "task_done")
async def on_task_done(call: types.CallbackQuery):
    # Переход из work в test – выполняется только создателем или назначенным разработчиком,
    # а переход из test в accept – только создателем или назначенным тестировщиком.
    msg = call.message
    card = find_card(msg.chat.id, msg.message_id)
    if not card:
        await call.answer("Объект не найден", show_alert=True)
        return
    current_status = card.get("status", "new")
    if current_status == "work":
        if not (is_creator(call, msg.chat.id) or is_dev(call, card)):
            await call.answer("Только создатель или назначенный разработчик могут завершить выполнение", show_alert=True)
            return
        new_status = status_line_test(card["tester"])
        card["status"] = "test"
        ans = "Таск -> test"
        new_kb = task_test_keyboard()
    elif current_status == "test":
        if not (is_creator(call, msg.chat.id) or is_tester(call, card)):
            await call.answer("Только создатель или назначенный тестировщик могут принять выполнение", show_alert=True)
            return
        new_status = status_line_accept(PROJECTS[msg.chat.id].get("creator_username", "@unknown"))
        card["status"] = "accept"
        ans = "Таск -> accept"
        new_kb = task_accept_keyboard()
    else:
        await call.answer("Неверный переход", show_alert=True)
        return
    statuses = card.get("statuses", [])
    statuses.append(new_status)
    card["statuses"] = statuses
    new_text = card["base_text"] + "\n" + "\n".join(statuses)
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_text, reply_markup=new_kb)
        else:
            await bot.edit_message_text(new_text, msg.chat.id, msg.message_id, reply_markup=new_kb)
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    await call.answer(ans)

@dp.callback_query_handler(lambda c: c.data == "task_reject_choice")
async def on_task_reject_main(call: types.CallbackQuery, state: FSMContext):
    card = find_card(call.message.chat.id, call.message.message_id)
    if not card:
        await call.answer("Объект не найден", show_alert=True)
        return
    # Если карточка в стадии test – разрешаем только тестировщику или создателю;
    # для остальных стадий – только создатель.
    if card["status"] == "test":
        if not (is_creator(call, call.message.chat.id) or is_tester(call, card)):
            await call.answer("Недостаточно прав для 'не принято'", show_alert=True)
            return
    else:
        if not is_creator(call, call.message.chat.id):
            await call.answer("Только создатель проекта может выполнять данное действие", show_alert=True)
            return
    await state.update_data(base_task_message_id=call.message.message_id)
    kb = glitch_or_fix_keyboard()
    await call.message.answer("Что создать: Глюк или Правка?", reply_markup=kb)
    await call.answer("Переход к созданию глюка/правки")

@dp.callback_query_handler(lambda c: c.data == "task_comment")
async def on_task_comment_fix(call: types.CallbackQuery, state: FSMContext):
    msg = call.message
    card = find_card(msg.chat.id, msg.message_id)
    user = get_user(call)
    if card:
        # Если статус "work": комментарии может оставлять только разработчик или создатель
        if card.get("status") == "work" and not (is_dev(call, card) or is_creator(call, msg.chat.id)):
            await call.answer("Комментарий может оставлять только разработчик или создатель проекта.", show_alert=True)
            return
        # Если статус "test": комментарии может оставлять только тестировщик или создатель
        if card.get("status") == "test" and not (is_tester(call, card) or is_creator(call, msg.chat.id)):
            await call.answer("Комментарий может оставлять только тестировщик или создатель проекта.", show_alert=True)
            return
        # Если статус "accept": разрешать комментарий может только создатель
        if card.get("status") == "accept" and not is_creator(call, msg.chat.id):
            await call.answer("Комментарий в стадии accept может оставлять только создатель проекта.", show_alert=True)
            return
    state_data = await state.get_data()
    if state_data.get("comment_ask_id"):
        try:
            await bot.delete_message(msg.chat.id, state_data["comment_ask_id"])
        except Exception:
            pass
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


@dp.callback_query_handler(lambda c: c.data == "task_fail_choice")
async def on_fix_fail_main(call: types.CallbackQuery):
    # Если правка в стадии accept, разрешать данное действие может только создатель
    card = find_card(call.message.chat.id, call.message.message_id)
    if card and card.get("status") == "accept" and not is_creator(call, call.message.chat.id):
        await call.answer("Недостаточно прав для 'не принято' в стадии accept", show_alert=True)
        return
    kb = glitch_or_fix_keyboard()
    await call.message.answer("Что создать: Глюк или Правка?", reply_markup=kb)
    await call.answer("Переход к созданию глюка/правки")


@dp.callback_query_handler(lambda c: c.data == "task_fail_choice")
async def on_glitch_fail_main(call: types.CallbackQuery):
    # Если глюк в стадии accept, разрешать данное действие может только создатель
    card = find_card(call.message.chat.id, call.message.message_id)
    if card and card.get("status") == "accept" and not is_creator(call, call.message.chat.id):
        await call.answer("Недостаточно прав для 'не принято' в стадии accept", show_alert=True)
        return
    kb = glitch_or_fix_keyboard()
    await call.message.answer("Что создать: Глюк или Правка?", reply_markup=kb)
    await call.answer("Переход к созданию глюка/правки")


@dp.callback_query_handler(lambda c: c.data == "task_comment")
async def on_task_comment_glitch(call: types.CallbackQuery, state: FSMContext):
    msg = call.message
    card = find_card(msg.chat.id, msg.message_id)
    user = get_user(call)
    if card:
        # Если статус "work": комментарии может оставлять только разработчик или создатель
        if card.get("status") == "work" and not (is_dev(call, card) or is_creator(call, msg.chat.id)):
            await call.answer("Комментарий может оставлять только разработчик или создатель проекта.", show_alert=True)
            return
        # Если статус "test": комментарии может оставлять только тестировщик или создатель
        if card.get("status") == "test" and not (is_tester(call, card) or is_creator(call, msg.chat.id)):
            await call.answer("Комментарий может оставлять только тестировщик или создатель проекта.", show_alert=True)
            return
        # Если статус "accept": разрешать комментарий может только создатель
        if card.get("status") == "accept" and not is_creator(call, msg.chat.id):
            await call.answer("Комментарий в стадии accept может оставлять только создатель проекта.", show_alert=True)
            return
    state_data = await state.get_data()
    if state_data.get("comment_ask_id"):
        try:
            await bot.delete_message(msg.chat.id, state_data["comment_ask_id"])
        except Exception:
            pass
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


@dp.callback_query_handler(lambda c: c.data == "task_fail_choice")
async def on_task_fail_main(call: types.CallbackQuery):
    # Если задача в стадии accept, разрешать данное действие может только создатель
    card = find_card(call.message.chat.id, call.message.message_id)
    if card and card.get("status") == "accept" and not is_creator(call, call.message.chat.id):
        await call.answer("Недостаточно прав для 'не принято' в стадии accept", show_alert=True)
        return
    kb = glitch_or_fix_keyboard()
    await call.message.answer("Что создать: Глюк или Правка?", reply_markup=kb)
    await call.answer("Переход к созданию глюка/правки")


@dp.callback_query_handler(lambda c: c.data == "task_closed")
async def on_task_closed(call: types.CallbackQuery):
    # Закрывать задачу может только создатель
    if not is_creator(call, call.message.chat.id):
        await call.answer("Только создатель проекта может закрывать задачу", show_alert=True)
        return
    msg = call.message
    card = find_card(msg.chat.id, msg.message_id)
    if not card:
        await call.answer("Объект не найден", show_alert=True)
        return
    new_status = status_line_closed() + "\nТаск завершён."
    card["status"] = "closed"
    statuses = card.get("statuses", [])
    statuses.append(new_status)
    card["statuses"] = statuses
    new_text = card["base_text"] + "\n" + "\n".join(statuses)
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_text)
        else:
            await bot.edit_message_text(new_text, msg.chat.id, msg.message_id)
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    await call.answer("Таск закрыт.")

# ------------------ Обработчики для глюков ------------------

@dp.callback_query_handler(lambda c: c.data == "glitch_done")
async def on_glitch_done(call: types.CallbackQuery):
    msg = call.message
    card = find_card(msg.chat.id, msg.message_id)
    if not card:
        await call.answer("Объект не найден", show_alert=True)
        return
    if card.get("status", "new") == "work":
        if not (is_creator(call, msg.chat.id) or is_dev(call, card)):
            await call.answer("Только создатель или назначенный разработчик могут завершить выполнение", show_alert=True)
            return
        new_status = status_line_test(card["tester"])
        card["status"] = "test"
        ans = "Глюк -> test"
    elif card.get("status") == "test":
        if not (is_creator(call, msg.chat.id) or is_tester(call, card)):
            await call.answer("Только создатель или назначенный тестировщик могут принять выполнение", show_alert=True)
            return
        new_status = status_line_accept(PROJECTS[msg.chat.id].get("creator_username", "@unknown"))
        card["status"] = "accept"
        ans = "Глюк -> accept"
    else:
        await call.answer("Неверный переход", show_alert=True)
        return
    statuses = card.get("statuses", [])
    statuses.append(new_status)
    card["statuses"] = statuses
    new_text = card["base_text"] + "\n" + "\n".join(statuses)
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_text, reply_markup=glitch_test_keyboard())
        else:
            await bot.edit_message_text(new_text, msg.chat.id, msg.message_id, reply_markup=glitch_test_keyboard())
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    await call.answer(ans)

@dp.callback_query_handler(lambda c: c.data == "glitch_reject_choice")
async def on_glitch_reject(call: types.CallbackQuery):
    # Если задача в стадии test – разрешаем только тестировщику или создателю
    card = find_card(call.message.chat.id, call.message.message_id)
    if card and card.get("status") == "test":
        if not (is_creator(call, call.message.chat.id) or is_tester(call, card)):
            await call.answer("Недостаточно прав для 'не принято'", show_alert=True)
            return
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
    card = find_card(msg.chat.id, msg.message_id)
    if not card:
        await call.answer("Объект не найден", show_alert=True)
        return
    # Закрывать глюк может выполнять только создатель
    if not is_creator(call, msg.chat.id):
        await call.answer("Только создатель проекта может закрывать глюки", show_alert=True)
        return
    if card.get("status", "").strip().lower() != "accept":
        await call.answer("Неверный переход: глюк должен быть в состоянии 'accept'", show_alert=True)
        return
    new_status = status_line_closed()
    card["status"] = "closed"
    statuses = card.get("statuses", [])
    statuses.append(new_status)
    card["statuses"] = statuses
    new_text = card["base_text"] + "\n" + "\n".join(statuses)
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_text)
        else:
            await bot.edit_message_text(new_text, msg.chat.id, msg.message_id)
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    await call.answer("Глюк закрыт.")

# ------------------ Обработчики для правок ------------------

@dp.callback_query_handler(lambda c: c.data == "fix_done")
async def on_fix_done(call: types.CallbackQuery):
    msg = call.message
    card = find_card(msg.chat.id, msg.message_id)
    if not card:
        await call.answer("Объект не найден", show_alert=True)
        return
    if card.get("status", "new") == "work":
        if not (is_creator(call, msg.chat.id) or is_dev(call, card)):
            await call.answer("Только создатель или назначенный разработчик могут завершить выполнение", show_alert=True)
            return
        new_status = status_line_test(card["tester"])
        card["status"] = "test"
        ans = "Правка -> test"
        new_kb = fix_test_keyboard()
    elif card.get("status") == "test":
        if not (is_creator(call, msg.chat.id) or is_tester(call, card)):
            await call.answer("Только создатель или назначенный тестировщик могут принять выполнение", show_alert=True)
            return
        new_status = status_line_accept(PROJECTS[msg.chat.id].get("creator_username", "@unknown"))
        card["status"] = "accept"
        ans = "Правка -> accept"
        new_kb = fix_accept_keyboard()
    else:
        await call.answer("Неверный переход", show_alert=True)
        return
    statuses = card.get("statuses", [])
    statuses.append(new_status)
    card["statuses"] = statuses
    new_text = card["base_text"] + "\n" + "\n".join(statuses)
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_text, reply_markup=new_kb)
        else:
            await bot.edit_message_text(new_text, msg.chat.id, msg.message_id, reply_markup=new_kb)
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    await call.answer(ans)
@dp.callback_query_handler(lambda c: c.data == "task_comment")
async def on_task_comment_fix(call: types.CallbackQuery, state: FSMContext):
    msg = call.message
    card = find_card(msg.chat.id, msg.message_id)
    user = get_user(call)
    # Для карточек типа "Правка" в стадии accept разрешаем комментарии только создателю
    if card and card.get("type") == "Правка" and card.get("status") == "accept":
        if not is_creator(call, msg.chat.id):
            await call.answer("Комментарий в стадии accept может оставлять только создатель проекта.", show_alert=True)
            return
    # Остальная логика обработки комментария (оставляем без изменений)
    state_data = await state.get_data()
    if state_data.get("comment_ask_id"):
        try:
            await bot.delete_message(msg.chat.id, state_data["comment_ask_id"])
        except Exception:
            pass
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
@dp.callback_query_handler(lambda c: c.data == "fix_reject_choice")
async def on_fix_reject(call: types.CallbackQuery):
    # Для правок в стадии test, кнопка reject может нажиматься только тестировщиком или создателем
    card = find_card(call.message.chat.id, call.message.message_id)
    if card and card.get("status") == "test":
        if not (is_creator(call, call.message.chat.id) or is_tester(call, card)):
            await call.answer("Недостаточно прав для 'не принято'", show_alert=True)
            return
    if card and card.get("status") == "accept":
        if not (is_creator(call, call.message.chat.id)):
            await call.answer("Недостаточно прав для 'не принято'", show_alert=True)
            return
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
    card = find_card(msg.chat.id, msg.message_id)
    if not card:
        await call.answer("Объект не найден", show_alert=True)
        return
    # Закрывать правку может выполнять только создатель, и только если статус равен "accept"
    if not is_creator(call, msg.chat.id):
        await call.answer("Только создатель проекта может закрывать правки", show_alert=True)
        return
    if card.get("status", "").strip().lower() != "accept":
        await call.answer("Неверный переход: правка должна быть в состоянии 'accept'", show_alert=True)
        return
    new_status = status_line_closed()
    card["status"] = "closed"
    statuses = card.get("statuses", [])
    statuses.append(new_status)
    card["statuses"] = statuses
    new_text = card["base_text"] + "\n" + "\n".join(statuses)
    try:
        if msg.photo:
            await bot.edit_message_caption(msg.chat.id, msg.message_id, caption=new_text)
        else:
            await bot.edit_message_text(new_text, msg.chat.id, msg.message_id)
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return
    await call.answer("Правка закрыта.")

# ------------------ Обработчики для создания глюка и правок ------------------

@dp.callback_query_handler(lambda c: c.data == "choose_glitch")
async def on_choose_glitch(call: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        # Используем сохранённый base_task_message_id; если отсутствует, берем текущий ID
        base_id = data.get("base_task_message_id") or call.message.message_id
        base = find_card(call.message.chat.id, base_id)
        if not base:
            await call.answer("Исходная задача не найдена", show_alert=True)
            return
        # Создание глюка могут выполнять создатель, назначенный разработчик или тестировщик
        if not (is_creator(call, call.message.chat.id) or is_dev(call, base) or is_tester(call, base)):
            await call.answer("Недостаточно прав для создания глюка", show_alert=True)
            return
        dev = base["dev"]
        test = base["tester"]
        await state.update_data(glitch_dev=dev, glitch_tester=test)
        try:
            await call.message.delete()
        except Exception:
            pass
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
        data = await state.get_data()
        base_id = data.get("base_task_message_id") or call.message.message_id
        base = find_card(call.message.chat.id, base_id)
        if not base:
            await call.answer("Исходная задача не найдена", show_alert=True)
            return
        # Создание правки могут выполнять только создатель или назначенный тестировщик
        if not (is_creator(call, call.message.chat.id) or is_tester(call, base)):
            await call.answer("Недостаточно прав для создания правки", show_alert=True)
            return
        dev = base["dev"]
        test = base["tester"]
        await state.update_data(fix_dev=dev, fix_tester=test)
        try:
            await call.message.delete()
        except Exception:
            pass
        ask = await bot.send_message(call.message.chat.id, "Отправьте картинку для Правки или 'Пропустить':",
                                     reply_markup=fix_skip_image_keyboard())
        await state.update_data(fix_ask_img=ask.message_id)
        await NewFixStates.waiting_for_photo.set()
        await call.answer("Переход к созданию правки")
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

# Конец файла
