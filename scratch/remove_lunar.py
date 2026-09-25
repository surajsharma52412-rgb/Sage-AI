import os
import glob
import re

target_extensions = ('.py', '.json', '.html', '.sh', '.md', '.txt')
exclude_dirs = {'.git', '.venv', '__pycache__', 'brain', '.system_generated'}

replaced_count = 0
modified_files = 0

for root, dirs, files in os.walk('.'):
    # Skip excluded directories
    dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
    
    for f in files:
        if any(f.endswith(ext) for ext in target_extensions):
            file_path = os.path.join(root, f)
            try:
                with open(file_path, 'r', encoding='utf-8') as fp:
                    content = fp.read()
            except Exception:
                continue

            if re.search(r'sage', content, re.IGNORECASE):
                orig = content
                # Specific clean replacements
                content = content.replace("Sage AI", "Sage AI")
                content = content.replace("Sage AI", "Sage AI")
                content = content.replace("SAGE AI", "SAGE AI")
                content = content.replace("SAGE ENGINE", "SAGE ENGINE")
                content = content.replace("Sage Engine", "Sage Engine")
                content = content.replace("sage engine", "sage engine")
                content = content.replace("Sage-AI", "Sage-AI")
                content = content.replace("Sage Workspace", "Sage Workspace")
                content = content.replace("what is sage engine", "what is sage engine")
                content = content.replace("what is sage", "what is sage")
                content = content.replace("sage", "sage")
                content = content.replace("Sage", "Sage")
                content = content.replace("SAGE", "SAGE")

                if content != orig:
                    with open(file_path, 'w', encoding='utf-8') as fp:
                        fp.write(content)
                    modified_files += 1
                    print(f"Updated: {file_path}")

print(f"Finished: Modified {modified_files} files.")
