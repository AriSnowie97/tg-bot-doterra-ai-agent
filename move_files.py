import os
import shutil
import glob

src = r"d:\Pictures\homework\codes\Python\VS Code\tg-bot-doterra-ai-agent\src\content\products"
dst = r"d:\Pictures\homework\codes\Python\VS Code\tg-bot-doterra-ai-agent\src\content\docs"

for filepath in glob.glob(os.path.join(src, "*.md")):
    filename = os.path.basename(filepath)
    dst_path = os.path.join(dst, filename)
    shutil.move(filepath, dst_path)
    print(f"Moved {filename} to docs/")
