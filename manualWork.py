# Standard
from pathlib import Path
# Special
# Local
from src.storage import storage
from src.LLMProvider import GeminiFlashProvider
from src.embedding import create_embedding


def main():
    # storage.creating_table_for_chunks()
    # storage.upsert_file_of_chunks(Path("src/content/docs/frankincense_chunks.json"))
    # emb = create_embedding("Hello")
    # print(emb, len(emb))
    pass


if __name__ == "__main__":
    main()