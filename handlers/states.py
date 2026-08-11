# Special
from aiogram.fsm.state import State, StatesGroup


class AskStates(StatesGroup):
    """FSM-стани для команди /ask."""
    waiting_for_question = State()


class UploadKBStates(StatesGroup):
    """FSM-стани для завантаження MD-файлів у базу знань (kb_bot)."""
    waiting_for_file = State()
    waiting_for_slug = State()
