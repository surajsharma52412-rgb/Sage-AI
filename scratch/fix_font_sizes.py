import glob

ui_files = glob.glob('ui/**/*.py', recursive=True)
count = 0
for f in ui_files:
    with open(f, 'r', encoding='utf-8') as fp:
        content = fp.read()
    if '10.5px' in content:
        num = content.count('10.5px')
        new_content = content.replace('10.5px', '11px')
        with open(f, 'w', encoding='utf-8') as fp:
            fp.write(new_content)
        count += num
        print(f"Updated {f}: replaced {num} instances")
print(f"Total replaced: {count}")
