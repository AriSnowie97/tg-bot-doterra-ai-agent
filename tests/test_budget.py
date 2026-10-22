import pytest
from src.LLMProvider.budget import GlobalLLMBudgetManager, BudgetExceededError


class TestLLMBudgetManager:
    def test_budget_consumption_under_limit(self):
        manager = GlobalLLMBudgetManager()
        for _ in range(10):
            manager.check_and_consume("generate")
            manager.check_and_consume("embed")

        stats = manager.get_stats()
        assert stats["generation_calls_past_hour"] == 10
        assert stats["generation_calls_past_24h"] == 10
        assert stats["total_generations"] == 10
        assert stats["total_embeddings"] == 10

    def test_budget_exceeded_hour_limit(self, monkeypatch):
        import src.LLMProvider.budget as budget_mod
        monkeypatch.setattr(budget_mod, "MAX_LLM_CALLS_PER_HOUR", 5)

        manager = GlobalLLMBudgetManager()
        for _ in range(5):
            manager.check_and_consume("generate")

        with pytest.raises(BudgetExceededError):
            manager.check_and_consume("generate")

    def test_embeddings_and_sync_mode_do_not_block(self, monkeypatch):
        import src.LLMProvider.budget as budget_mod
        monkeypatch.setattr(budget_mod, "MAX_LLM_CALLS_PER_HOUR", 2)
        monkeypatch.setattr(budget_mod, "MAX_LLM_CALLS_PER_DAY", 2)

        manager = GlobalLLMBudgetManager()
        # Embeddings for knowledge base are allowed in any quantity
        for _ in range(500):
            manager.check_and_consume("embed")

        stats = manager.get_stats()
        assert stats["total_embeddings"] == 500

        # Sync mode bypasses even generation calls
        manager.set_sync_mode(True)
        for _ in range(10):
            manager.check_and_consume("generate")

        manager.set_sync_mode(False)
