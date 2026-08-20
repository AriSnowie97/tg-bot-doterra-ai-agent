import os
import re
from pathlib import Path

docs_dir = Path("src/content/docs")

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")

total_products = 0

for file in docs_dir.glob("*_Гід_*.md"):
    content = file.read_text(encoding="utf-8")
    
    # Matches ## 1. Product Name OR ### 1.1 Product Name
    # But wait, earlier I saw ## 1. doTERRA Balance — Grounding Blend
    # Let's match line starting with ## or ### followed by digits and dot.
    matches = re.finditer(r"^(#{2,3})\s+\d+(?:\.\d+)*\.?\s+(.*?)(?=\n^(?:#{2,3})\s|\Z)", content, flags=re.MULTILINE | re.DOTALL)
    
    products = []
    for match in matches:
        title_line = match.group(2).split('\n')[0].strip()
        # Some titles have " — " or " - " which we can split or just slugify
        slug = slugify(title_line.split("—")[0].split("-")[0].strip())
        
        # But wait, does this capture the rest of the text for the product?
        body = match.group(0)
        products.append((title_line, slug, len(body)))
        total_products += 1
        
    print(f"{file.name}: {len(products)} products")
    if len(products) > 0:
        print(f"  Example: {products[0][0]} -> {products[0][1]}")

print(f"Total extracted: {total_products}")
