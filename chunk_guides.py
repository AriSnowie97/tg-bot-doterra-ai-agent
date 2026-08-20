import sys, re, json
from pathlib import Path
import ftfy

sys.path.insert(0, ".")
from src.content.parser import DoterraMarkdownParser

docs = Path("src/content/docs")
ALL_CHUNKS = Path("all_chunks.json")

existing = json.loads(ALL_CHUNKS.read_text(encoding="utf-8"))
existing_slugs = {c["product_slug"] for c in existing}
print(f"Existing chunks: {len(existing)} ({len(existing_slugs)} products)")

guide_files = sorted(f for f in docs.glob("*.md") if f.stem[0].isdigit())
print(f"Guide files found: {len(guide_files)}")

parser = DoterraMarkdownParser()
new_chunks = []
stats = {"ok": 0, "skip": 0}

for gf in guide_files:
    slug = "guide-" + re.sub(r"[^\w]+", "-", gf.stem.lower()).strip("-")
    slug = slug.replace("--", "-")
    
    if slug in existing_slugs:
        print(f"  SKIP [{slug}]")
        stats["skip"] += 1
        continue
    
    print(f"  Processing: {gf.name}")
    print(f"  Slug: {slug}")
    
    raw_text = gf.read_text(encoding="utf-8-sig", errors="replace")
    fixed_text = ftfy.fix_text(raw_text)
    
    chunks = parser.parse_text(fixed_text, product_slug=slug, source_file=str(gf))
    
    if not chunks:
        print("    WARN: 0 chunks!")
        stats["skip"] += 1
        continue
    
    print(f"    OK: {len(chunks)} chunks")
    new_chunks.extend(c.to_dict() for c in chunks)
    stats["ok"] += 1

if new_chunks:
    all_data = existing + new_chunks
    ALL_CHUNKS.write_text(json.dumps(all_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nAdded {len(new_chunks)} new chunks")
    print(f"Total: {len(all_data)} chunks")
else:
    print("\nNo new chunks added")

ok_count = stats["ok"]
skip_count = stats["skip"]
print(f"Summary: OK={ok_count}, skip={skip_count}")
