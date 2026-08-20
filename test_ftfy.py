import sys, io, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
import ftfy

docs = Path('src/content/docs')

# Тест на Blends3
blend_file = next(f for f in docs.glob('07*Blends3.md'))
raw_text = blend_file.read_text(encoding='utf-8-sig', errors='replace')
fixed = ftfy.fix_text(raw_text)

print('FIXED text (first 600):')
print(fixed[:600])
print()

# Знайдемо H2 заголовки
h2s = re.findall(r'^## (.+)$', fixed, re.MULTILINE)
print('H2 headings (first 15):')
for h in h2s[:15]:
    print(f'  {repr(h.rstrip())}')
