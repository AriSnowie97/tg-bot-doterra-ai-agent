# Special
from aiogram.fsm.state import State, StatesGroup


class AskStates(StatesGroup):
    """FSM-стани для команди /ask."""
    waiting_for_question = State()


class UploadKBStates(StatesGroup):
    """FSM-стани для завантаження MD-файлів у базу знань (kb_bot)."""
    waiting_for_file = State()
    waiting_for_slug = State()


class ScreeningStates(StatesGroup):
    """FSM-стани для скринінгу протипоказань перед рекомендацією олій.

    Блоки 1–3 зберігаються між повідомленнями через FSMContext.data:
        screening_mode    — 'inactive' | 'active' | 'red_flag'
        screening_history — накопичений текст розмови (скарга + відповіді)
        original_complaint — перше повідомлення-скарга (для RAG-пошуку)
    """
    in_progress = State()   # Скринінг активний, очікуємо відповіді на питання
