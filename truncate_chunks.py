import os
import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))
load_dotenv(project_root / ".env")

from src.storage.storage import _conn_create

def truncate_chunks():
    print("Truncating knowledge_chunks table...")
    conn = _conn_create()
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE knowledge_chunks;")
    conn.commit()
    conn.close()
    print("Truncated!")

if __name__ == "__main__":
    truncate_chunks()
