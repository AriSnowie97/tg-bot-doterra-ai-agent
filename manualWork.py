# Standard
from pathlib import Path
# Special
# Local
from src.storage import storage


def main():
    storage.creating_table_for_chunks()
    storage.upsert_file_of_chunks(Path("src\\content\\docs\\frankincense_chunks.json"))


if __name__ == "__main__":
    main()