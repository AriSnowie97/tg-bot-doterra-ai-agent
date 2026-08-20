import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

docs = Path('src/content/docs')
blend_file = next(f for f in docs.glob('07*Blends3.md'))
raw = blend_file.read_bytes()[3:]  # skip BOM

# D0 A0 D1 9E D0 A1 D0 82
# D0 A0 в utf-8 = U+0420 = Р (кирилична)
# D1 9E в utf-8 = U+045E = ў (кирилична)
# Але 'Рў' в cp1251 = 0xD0 0xAE??? Нi!
# В cp1251: Р = 0xD0, ў = 0xAE -> але D0 AE != D0 A0 D1 9E

# Значить raw bytes D0 A0 D1 9E це UTF-8 рядок 'Рў'
# Але в cp1251 'Рў' це байти D0 AE -- не те

# Спробуємо iнший пiдхiд: ftfy (fix text for you)
# Або вручну: D0 A0 D1 9E --
# Якщо ми читаємо це як cp1251 байти D0=208 A0=160 D1=209 9E=158...
# В cp1251: 208=Р, 160=неперевна пробiл, 209=С, 158=...  
# Нi, це не спрацьовує

# Спробуємо другий варiант: файл є cp1252, не utf-8
# Якщо читати raw як cp1252:
# D0 = Ð, A0 = non-breaking space, D1 = Ñ, 9E = ž
# 'Ð ÑžÐ Â·...' -- теж не те

# Правильний пiдхiд: mojibake типу windows-1252 -> latin-1 -> utf-8
# Тобто: оригiнал utf-8 -> неправильно прочитаний як windows-1252 -> збережений utf-8

# Перевiримо: вiзьмемо cp1251 текст i зашифруємо через windows-1252
# 'Третiй' в cp1251: D2 F0 E5 F2 B3 E9 (Т, р, е, т, i, й)
# В windows-1252: D2=Ò, F0=ð, E5=å...
# В utf-8 це: Ò=0xC3 0x92, ð=0xC3 0xB0...

# Але нашi raw bytes для 'Рў' = D0 A0 D1 9E
# Якщо D0 9E = Р (Р=D0 A0, але D0 9E це?) нi...

# OK, тут iнше: 
# Bytes D0 A0 = в utf-8 = 'Р' (U+0420)
# Bytes D1 9E = в utf-8 = 'ў' (U+045E)  
# Тепер: 'Рў' якщо encoded в cp1251 = D0 AE
# Але якщо 'Рў' закодовано в raw UTF-8 bytes i тi bytes прочитанi як cp1251:
# D0=210='Р', A0=160=' ', D1=209='С', 9E=158=...
# cp1251 не має 0x9E!

# Правильно зрозумiти:
# Текст 'Третiй' в utf-8 = D0 A2 D1 80 D0 B5 D1 82 D1 96 D0 B9
# Якщо цi bytes читати як windows-1252:
# D0=Ð, A2=â, D1=Ñ, 80=€, D0=Ð, B5=µ, D1=Ñ, 82=‚, D1=Ñ, 96=â€"(n-dash), D0=Ð, B9=¹

# В utf-8 ці символи:
# Ð=0xC3 0x90, â=0xC3 0xA2, Ñ=0xC3 0x91, €=0xE2 0x82 0xAC, µ=0xC2 0xB5
# Але наш raw: D0 A2 ... то raw[0]=0xD0=208

# Стривай! raw[0] = 0xD0... Але ми вже знаємо: raw = utf-8 bytes
# raw.decode('utf-8') дає 'Р' (U+0420) для bytes D0 A0

# Якщо raw bytes = D0 A0 i ми читаємо як windows-1252:
# D0=Ð (U+00D0=208), A0=\xa0 (no-break space)
# Ð\xa0 в utf-8 = C3 90 C2 A0... але нам треба записати це назад

# Правильний шлях виправлення:
# text_wrong = file.read_text(encoding='utf-8')  # те що у нас
# fix: text_wrong.encode('raw_unicode_escape').decode('utf-8')? нi...

# Спробуємо просто: ftfy-like fix
# Якщо символ в unicode range Cyrillic (0400-04FF), i вiн МАЄ бути через double-encoding,
# то його utf-8 bytes (2 bytes) читали як cp1251 символи

# Наприклад: 'Р' (D0 A0) -> D0 + A0
# В cp1251: D0=208='Р', A0=160=неперевна пробiл (not a valid char in cp1251 actually)
# Хм, cp1251 0xA0 = non-breaking space

# Новий варiант: encoded utf-8, потiм помилково decoded latin-1, потiм saved utf-8
# text_orig_utf8_bytes -> decode_latin1 -> save_utf8
# Fix: read_utf8 -> encode_latin1 -> decode_utf8
# Але encode latin-1 не працює для символiв > U+00FF

# Оскiльки нашi символи в unicode > U+00FF (4xx, 201A, etc),
# вони НЕ можуть бути закодованi в latin-1 напряму

# ВИСНОВОК: Це ftfy-проблема типу 'utf-8 decoded as cp1252'
# Тобто: original bytes (utf-8) -> decoded as cp1252 -> saved as utf-8

# Fix: text.encode('cp1252').decode('utf-8')
# Але encode('cp1252') не спрацьовує для U+045E, U+0402, U+201A etc

# Єдиний варiант -- ftfy бiблiотека або кастомна таблиця

# Перевiримо: чи є в системi ftfy?
try:
    import ftfy
    fixed = ftfy.fix_text(blend_file.read_text(encoding='utf-8', errors='replace'))
    print('ftfy result (first 400):')
    print(fixed[:400])
except ImportError:
    print('ftfy not installed')
    # Перевiримо що реально в ascii-частинi файлу -- заголовки мають бути читабельнi
    text = blend_file.read_text(encoding='utf-8', errors='replace')
    import re
    h2s = re.findall(r'^## (.+)$', text, re.MULTILINE)
    print(f'H2 headings (raw, first 10):')
    for h in h2s[:10]:
        print(f'  {repr(h.rstrip())}')
