import pytest
from src.LLMProvider.budget import GlobalLLMBudgetManager, BudgetExceededError


class TestLLMBudgetManager:
    def test_budget_consumption_under_limit(self):
        manager = GlobalLLMBudgetManager()
        # Should not raise
        for _ in range(10):
            manager.check_and_consume("generate")
            manager.check_and_consume("embed")

        stats = manager.get_stats()
        assert stats["calls_past_hour"] == 20
        assert stats["calls_past_24h"] == 20
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

    def test_budget_exceeded_day_limit(self, monkeypatch):
        import src.LLMProvider.budget as budget_mod
        monkeypatch.setattr(budget_mod, "MAX_LLM_CALLS_PER_DAY", 3)

        manager = GlobalLLMBudgetManager()
        for _ in range(3):
            manager.check_and_consume("embed")

        with pytest.raises(BudgetExceededError):
            manager.check_and_consume("embed")
