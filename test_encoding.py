import sys, io, re, json
from pathlib import Path

sys.path.insert(0, '.')

docs = Path('src/content/docs')
# Беремо найбільший Blends3
blend_file = next(f for f in docs.glob('07*Blends3.md'))
raw = blend_file.read_bytes()[3:]  # skip BOM

# Спробуємо рiзнi комбiнацii
combos = [
    ('utf-8', 'utf-8'),
]

# Оскiльки символи в unicode range 1000-8500 -- це кириличнi коди
# 'Р' = U+0420 (Р у кирилицi), 'ў' = U+045E (Ўкраiнська)  
# Цi символи не входять в latin-1 (256 символiв)
# Значить це НЕ double-utf8

# Спробуємо: прочитати як utf-8 i подивитись на bytes самих символiв
text = raw.decode('utf-8')
# Знайдемо 'РўСЂРµ' i подивимось unicode codepoints
sample = text[118:140]
print('Sample unicode codepoints:')
for c in sample:
    print(f'  {repr(c)} = U+{ord(c):04X}')

# 'Р' U+0420, 'ў' U+045E -> разом 0420 045E
# CP1251 bytes for 'Т' = D2, 'р' = F0 -> 0x D2 F0 -> в utf-8: D2 = 0xC3 0x92, F0 = 0xF0 = 4-byte
# Але 'Р' U+0420 в utf-8 = D0 A0 -> D0=208, A0=160
# 'ў' U+045E в utf-8 = D1 9E -> D1=209, 9E=158

# Якщо дивитись на raw bytes:
raw_sample = raw[118:140]
print()
print('Raw bytes at same position:')
print(' '.join(f'{b:02X}' for b in raw_sample))

# D0 A0 = 'Р', D1 9E = 'ў' (U+045E)
# Але D0 A0 D1 9E в UTF-8 це два символи: U+0420 (Р) i U+045E (ў)
# В CP1251: байт D0 = 'П', D1 = 'Р', 9E = ...
# Отже: файл справдi UTF-8, але текст ВСЕРЕДИНІ мiстить cp1251 байти
# якi були записанi як окремi UTF-8 символи (кожен байт -> cp1251 символ)

# Спроба: encode кожен символ назад в latin-1 (як cp1251 байт)
# i decode через cp1251
try:
    # Для рядку де є лише кириличний текст + ASCII
    fixed_chars = []
    for c in text:
        if ord(c) < 256:
            fixed_chars.append(c.encode('latin-1'))
        elif 0x400 <= ord(c) <= 0x4FF:  # Cyrillic block  
            # Конвертуємо unicode codepoint назад в cp1251 byte
            b = c.encode('cp1251', errors='replace')
            fixed_chars.append(b)
        else:
            fixed_chars.append(c.encode('utf-8', errors='replace'))
    
    raw_fixed = b''.join(fixed_chars)
    fixed_text = raw_fixed.decode('cp1251', errors='replace')
    print()
    print('ATTEMPT RESULT (first 400 chars):')
    print(fixed_text[:400])
except Exception as e:
    print(f'Error: {e}')
    import traceback; traceback.print_exc()
