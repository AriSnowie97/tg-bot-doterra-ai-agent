import os
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

docs_dir = Path("src/content/docs")

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")

CATEGORY_MAP = {
    "БАДи": "БАДи",
    "Догляд": "Догляд за собою",
    "ТовариДляДому": "Товари для дому",
    "ДифузориТаАксесуари": "Дифузори",
    "Дифузори": "Дифузори",
    "Набори": "Набори",
    "ЕфірніОлії": "Ефірні Олії",
}

def main():
    total_created = 0
    files_to_delete = []

    for file in docs_dir.glob("*_Гід_*.md"):
        print(f"Processing {file.name}...")
        content = file.read_text(encoding="utf-8")
        files_to_delete.append(file)
        
        # 1. Extract cover image
        image_match = re.search(r"^!\[.*?\]\(.*?\)", content, flags=re.MULTILINE)
        cover_image = image_match.group(0) if image_match else ""
        
        # 2. Determine category
        cat_match = re.search(r"^\d+_Гід_(.*?)_", file.name)
        raw_cat = cat_match.group(1) if cat_match else "Інше"
        category = CATEGORY_MAP.get(raw_cat, raw_cat)
        
        # 3. Find products
        # We look for lines like "## 1. Product Name" or "### 1.1 Product Name"
        # and capture everything until the next one.
        matches = list(re.finditer(r"^(#{2,3})\s+\d+(?:\.\d+)*\.?\s+(.*?)(?=\n^(?:#{2,3})\s+\d+|\Z)", content, flags=re.MULTILINE | re.DOTALL))
        
        for match in matches:
            header_level = match.group(1)
            full_header_line = match.group(2).split('\n')[0].strip()
            
            # Clean up title for slug
            clean_title = full_header_line.split("—")[0].split("-")[0].strip()
            slug = slugify(clean_title)
            
            # Skip if empty
            if not slug:
                continue
                
            body = match.group(0)
            
            # Replace the numbered header with a clean H1 header
            # E.g. "## 1. doTERRA Balance — Grounding Blend" -> "# doTERRA Balance — Grounding Blend"
            body = re.sub(r"^(#{2,3})\s+\d+(?:\.\d+)*\.?\s+", "# ", body, count=1)
            
            # We must ensure there is a category metadata line
            if "**Категорія:**" not in body:
                body = re.sub(r"^(# .+?\n)", f"\\1\n**Категорія:** {category}\n", body, count=1)
                
            # Add image at the top if it's not already there
            if cover_image and cover_image not in body:
                body = f"{cover_image}\n\n{body}"
                
            # Write to file
            out_file = docs_dir / f"{slug}.md"
            
            # If the file already exists, we skip creating to avoid overwriting manually created ones like lavender.md?
            # Actually, let's overwrite because the guides are the source of truth for these 89 products.
            out_file.write_text(body, encoding="utf-8")
            total_created += 1
            print(f"  -> Created {out_file.name}")
            
    print(f"\nTotal products extracted: {total_created}")
    
    # Delete old files and their json chunks
    for file in files_to_delete:
        print(f"Deleting {file.name}...")
        os.remove(file)
        
        json_chunk = file.parent / f"{file.stem}_chunks.json"
        if json_chunk.exists():
            os.remove(json_chunk)
            
    print("Done!")

if __name__ == "__main__":
    main()
