import os
import glob

def fix_text(text):
    try:
        # Try to fix cp1251 decoded as utf-8 incorrectly
        return text.encode('cp1251').decode('utf-8')
    except Exception:
        return text

def fix_mojibake(text):
    # Some common replacements if encode/decode fails
    replacements = {
        'РўРёРї:': 'Тип:',
        'РЎСѓРјС–С€': 'Суміш',
        'РґС–Рј': 'дім',
        'в–«пёЏ': '▫️',
        'рџ''': '👑', # This might be corrupted, let's skip manual replacing and rely on encode/decode
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

docs_dir = r"d:\Pictures\homework\codes\Python\VS Code\tg-bot-doterra-ai-agent\src\content\docs"
for filepath in glob.glob(os.path.join(docs_dir, "*.md")):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # If there is mojibake, it contains Cyrillic letter ER (Р) followed by other weird cyrillic like С, Ў etc.
    # Actually, the mojibake is UTF-8 bytes interpreted as Windows-1251, then saved as UTF-8.
    # So to reverse it: string.encode('cp1251').decode('utf-8')
    
    new_content = ""
    changed = False
    lines = content.split('\n')
    for line in lines:
        if 'Р' in line or 'С' in line or 'в–«' in line or 'рџ' in line:
            try:
                fixed_line = line.encode('cp1251').decode('utf-8')
                if fixed_line != line:
                    line = fixed_line
                    changed = True
            except Exception:
                pass
        new_content += line + '\n'
        
    # strip trailing newline if it didn't exist
    if not content.endswith('\n') and new_content.endswith('\n'):
        new_content = new_content[:-1]
        
    if changed and new_content != content:
        print(f"Fixed {os.path.basename(filepath)}")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
