import sys
from pathlib import Path
import pytest

# Add project root to sys.path so tests can import src.* reliably across all environments (Linux CI, Windows, macOS)
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _no_real_user_memory_db(monkeypatch):
    """Тести ніколи не ходять у реальну БД за пам'яттю про користувача."""
    import src.memory_handlers as mh
    from src.storage.user_memory import StoredMemory

    monkeypatch.setattr(mh, "get_memory", lambda user_id: StoredMemory())
    monkeypatch.setattr(mh, "merge_facts", lambda user_id, tags, allergies: None)
    monkeypatch.setattr(mh, "set_consent", lambda user_id, consent: None)
    monkeypatch.setattr(mh, "delete_memory", lambda user_id: False)
