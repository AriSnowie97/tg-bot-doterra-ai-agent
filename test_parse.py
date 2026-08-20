import sys, io, re, json
from pathlib import Path

sys.path.insert(0, '.')
from src.content.parser import DoterraMarkdownParser

docs = Path('src/content/docs')
blend_file = next(f for f in docs.glob('07*Blends3.md'))
parser = DoterraMarkdownParser()
chunks = parser.parse_file(blend_file)
print(f'Parsed {len(chunks)} chunks')
for c in chunks[:3]:
    print(f'  [{c.product_slug}] [{c.section_key}] {c.char_count}chars')
    print(f'  Content: {repr(c.content[:80])}')
