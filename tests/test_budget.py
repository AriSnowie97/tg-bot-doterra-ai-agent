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

    def test_bulk_upsert_chunks_batching(self, monkeypatch):
        import src.storage.storage as storage_mod
        from unittest.mock import MagicMock

        # Mock DB connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = []  # no existing chunks
        monkeypatch.setattr(storage_mod, "_conn_create", lambda: mock_conn)
        monkeypatch.setattr(storage_mod, "register_vector", lambda c: None)
        monkeypatch.setattr(storage_mod, "create_embedding", lambda text: [0.1] * 768)
        monkeypatch.setattr(storage_mod, "іs_there_similar_embedding", lambda cur, chunk, emb: False)

        test_chunks = [
            {
                "chunk_id": f"chunk_{i}",
                "product_slug": f"prod_{i}",
                "section_key": "usage",
                "section_title": "Usage",
                "content": f"Content {i}",
                "char_count": 50,
                "tokens_approx": 12,
            }
            for i in range(10)
        ]

        progress_msgs = []
        # Run with batch_size=4, pause_seconds=0, chunk_delay=0 so test finishes immediately
        storage_mod.bulk_upsert_chunks(
            test_chunks,
            progress_callback=progress_msgs.append,
            batch_size=4,
            pause_seconds=0,
            chunk_delay=0,
        )

        # 10 chunks with batch_size=4 => 3 batches (4, 4, 2)
        assert any("План синхронізації" in msg for msg in progress_msgs)
        assert any("1/3" in msg for msg in progress_msgs)
        assert any("2/3" in msg for msg in progress_msgs)
        assert any("3/3" in msg for msg in progress_msgs)
        assert any("Успішно" in msg for msg in progress_msgs)
