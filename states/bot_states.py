from aiogram.dispatcher.filters.state import StatesGroup, State

# Проект
class NewProjectStates(StatesGroup):
    waiting_for_project_name = State()
    waiting_for_project_description = State()
    waiting_for_project_image = State()

class EditProjectStates(StatesGroup):
    waiting_for_new_project_description = State()

class ProjectTeamStates(StatesGroup):
    waiting_for_team_username = State()
    waiting_for_team_confirmation = State()

# Таск
class NewTaskStates(StatesGroup):
    waiting_for_task_description = State()
    waiting_for_task_photo = State()
    waiting_for_task_dev = State()
    waiting_for_task_tester = State()

class EditTaskStates(StatesGroup):
    waiting_for_new_task_text = State()

class CommentStates(StatesGroup):
    waiting_for_comment_text = State()

# Глюк / Правка
class NewGlitchStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_description = State()

class NewFixStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_description = State()
