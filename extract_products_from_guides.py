
import re, json, sys
from pathlib import Path
import ftfy

sys.path.insert(0, '.')
from src.content.parser import DoterraMarkdownParser, ContentChunk

docs = Path('src/content/docs')
ALL_CHUNKS = Path('all_chunks.json')

existing = json.loads(ALL_CHUNKS.read_text(encoding='utf-8'))
existing_slugs = set(c['product_slug'] for c in existing)
print('Existing chunks:', len(existing), '/', len(existing_slugs), 'products')

parser = DoterraMarkdownParser()
new_chunks = []

def slugify(name):
    s = re.sub(r'[^\w]+', '-', name.lower()).strip('-')
    return re.sub(r'-+', '-', s)

# ============================================================
# 1. BLENDS -- extract each product from Blends3 (most complete)
# ============================================================
blend_file = next(f for f in docs.glob('07*Blends3.md'))
text_raw = blend_file.read_text(encoding='utf-8-sig', errors='replace')
text = ftfy.fix_text(text_raw)

# Split by numbered H2: ## N. Product Name
# Each block starts at numbered H2 and ends before next numbered H2
pattern = re.compile(r'^## (\d+)\. (.+?)$', re.MULTILINE)
matches = list(pattern.finditer(text))

print(f'\nBlends3: found {len(matches)} numbered products')

for i, m in enumerate(matches):
    prod_name = m.group(2).strip().rstrip('\r')
    slug = slugify(prod_name)
    
    # Get content: from this H2 to the next numbered H2
    start = m.start()
    end = matches[i+1].start() if i+1 < len(matches) else len(text)
    block = text[start:end]
    
    if slug in existing_slugs:
        print(f'  SKIP [{slug}]')
        continue
    
    # Parse this block as a mini-document
    # Replace numbered H2 with H1 so parser treats it as product header
    block_fixed = re.sub(r'^## \d+\. ', '# ', block, count=1, flags=re.MULTILINE)
    # Make non-numbered H2 in same block into H2 (keep as sections)
    # They are already H2 in the text
    
    chunks = parser.parse_text(block_fixed, product_slug=slug, source_file=str(blend_file))
    
    if not chunks:
        print(f'  WARN [{slug}] 0 chunks')
        continue
    
    print(f'  OK [{slug}] {len(chunks)} chunks')
    new_chunks.extend(c.to_dict() for c in chunks)
    existing_slugs.add(slug)

# ============================================================
# 2. SUPPLEMENTS -- extract each product from H3 sections
# ============================================================
supp_file = next(f for f in docs.glob('02*.md'))
text_supp_raw = supp_file.read_text(encoding='utf-8-sig', errors='replace')
text_supp = ftfy.fix_text(text_supp_raw)

# H3: ### N.M Product Name
h3_pattern = re.compile(r'^### (\d+\.\d+)\s+(.+?)$', re.MULTILINE)
h3_matches = list(h3_pattern.finditer(text_supp))

print(f'\nSupplements: found {len(h3_matches)} H3 products')

# Also need H2 for sections (to detect boundaries)
h2_pattern = re.compile(r'^## .+$', re.MULTILINE)

for i, m in enumerate(h3_matches):
    prod_name = m.group(2).strip().rstrip('\r')
    
    # Fix: replace dōTERRA (unicode) with doTERRA for slug
    prod_name_slug = prod_name.replace('dōTERRA', 'doTERRA').replace('vEO', 'vEO')
    slug = slugify(prod_name_slug)
    
    # For known aliases -- map to existing slug
    ALIAS = {
        'eo-mega': 'eo-mega-plus',  # EO Mega+ already in chunks
        'pb-assist': 'pb-assist-plus',  # PB Assist+ = pb-assist-plus
        'pb-restore-probiome-complex': 'pb-restore',  # already in chunks
        'doterra-lifelong-vitality-pack-llv': 'lifelong-vitality-pack',  # LLV already in
    }
    resolved_slug = ALIAS.get(slug, slug)
    
    if resolved_slug in existing_slugs:
        print(f'  SKIP [{slug}] (resolved: {resolved_slug})')
        continue
    
    # Get content block: from this H3 to next H3 or H2
    start = m.start()
    # Next boundary: next h3 or h2
    next_h3 = h3_matches[i+1].start() if i+1 < len(h3_matches) else len(text_supp)
    # Find any H2 between start and next_h3
    next_h2_match = h2_pattern.search(text_supp, start + 1)
    if next_h2_match and next_h2_match.start() < next_h3:
        next_h2 = next_h2_match.start()
    else:
        next_h2 = len(text_supp)
    end = min(next_h3, next_h2)
    
    block = text_supp[start:end]
    
    # Convert H3 to H1 (product title), H4 to H2 (sections)
    block_fixed = re.sub(r'^### \d+\.\d+\s+', '# ', block, count=1, flags=re.MULTILINE)
    block_fixed = re.sub(r'^#### ', '## ', block_fixed, flags=re.MULTILINE)
    block_fixed = re.sub(r'^### ', '## ', block_fixed, flags=re.MULTILINE)
    
    chunks = parser.parse_text(block_fixed, product_slug=resolved_slug, source_file=str(supp_file))
    
    if not chunks:
        print(f'  WARN [{resolved_slug}] 0 chunks')
        continue
    
    print(f'  OK [{resolved_slug}] {len(chunks)} chunks')
    new_chunks.extend(c.to_dict() for c in chunks)
    existing_slugs.add(resolved_slug)

# ============================================================
# Save
# ============================================================
if new_chunks:
    all_data = existing + new_chunks
    ALL_CHUNKS.write_text(json.dumps(all_data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nAdded {len(new_chunks)} new chunks')
    print(f'Total: {len(all_data)} chunks in all_chunks.json')
else:
    print('\nNo new chunks added')
