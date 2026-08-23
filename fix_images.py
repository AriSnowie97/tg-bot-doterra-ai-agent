import re
import time
import requests
from pathlib import Path

docs_dir = Path(r"d:\Pictures\homework\codes\Python\VS Code\tg-bot-doterra-ai-agent\src\content\docs")

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    updated_count = 0
    total_count = 0
    
    for md_file in docs_dir.rglob('*.md'):
        try:
            text = md_file.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
            
        total_count += 1
        
        # Extract any doterra.com link
        link_match = re.search(r'(https://www\.doterra\.com[^\s\)]+)', text)
        if not link_match:
            continue
            
        url = link_match.group(1).strip()
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                html = response.text
                og_match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
                if og_match:
                    img_url = og_match.group(1).replace("&amp;", "&")
                    # If relative, make absolute (usually og:image is absolute, but just in case)
                    if img_url.startswith("/"):
                        img_url = "https://www.doterra.com" + img_url
                        
                    new_img_md = f"![doTERRA Product]({img_url})"
                    
                    # Remove ALL existing image markdowns first to ensure no unsplash images are left
                    text_no_img = re.sub(r'^!\[.*?\]\(.*?\)\s*\n?', '', text, flags=re.MULTILINE)
                    text_no_img = text_no_img.strip()
                    
                    new_text = new_img_md + "\n\n" + text_no_img + "\n"
                        
                    if text != new_text:
                        md_file.write_text(new_text, encoding='utf-8')
                        updated_count += 1
                        print(f"Updated: {md_file.name}")
            else:
                pass
                
        except Exception as e:
            pass
            
        time.sleep(0.2)

    print(f"Processed {total_count} files.")
    print(f"Updated {updated_count} files.")

if __name__ == "__main__":
    main()
