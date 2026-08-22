import os
import json
from pathlib import Path
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.content.parser import DoterraMarkdownParser

def main():
    parser = DoterraMarkdownParser()
    docs = parser.parse_directory(Path("src/content/docs"))
    products = parser.parse_directory(Path("src/content/products"))
    advice = parser.parse_directory(Path("src/content/advice"))
    symphony = parser.parse_directory(Path("src/content/symphony_of_the_cells"))
    
    all_chunks = docs + products + advice + symphony
    all_chunks.sort(key=lambda c: (c.product_slug, c.order))
    data = [c.to_dict() for c in all_chunks]
    
    out_path = Path("all_chunks.json")
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(data)} chunks to all_chunks.json")

if __name__ == "__main__":
    main()
