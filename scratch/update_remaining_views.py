import os

files_to_update = [
    'ui/components/multi_agent_view.py',
    'ui/components/knowledge_view.py',
    'ui/components/add_models_view.py',
    'ui/components/project_view.py',
    'ui/components/settings_dialog.py',
    'ui/components/general_settings_dialog.py',
    'ui/components/permission_dialog.py',
    'ui/components/model_selector_popup.py',
    'ui/components/live_working_panel.py',
    'ui/components/code_editor.py',
    'ui/components/syntax_highlighter.py',
]

replacements = [
    ('#0FE6B5', '#00D1FF'),
    ('#0fe6b5', '#00d1ff'),
    ('#0CC99D', '#00D1FF'),
    ('#3bfdd5', '#00BBE6'),
    ('#0a9372', '#008BB3'),
    ('#089673', '#008BB3'),
    ('#06a580', '#008BB3'),
    ('rgba(15, 230, 181,', 'rgba(0, 209, 255,'),
    ('rgba(12, 201, 157,', 'rgba(0, 209, 255,'),
    # Backgrounds to dark slate-black
    ('#050810', '#0A0F14'),
    ('#060913', '#0A0F14'),
    ('#070c18', '#0A0F14'),
    ('#080b16', '#0A0F14'),
    ('#080d1a', '#0A0F14'),
    ('#0a0e1a', '#0A0F14'),
    ('#0a0f1d', '#0A0F14'),
    ('#070e1b', '#0A0F14'),
    # Card surfaces to #162033
    ('#090e1a', '#162033'),
    ('#090f1d', '#162033'),
    ('#0b1222', '#162033'),
    ('#0b1322', '#162033'),
    ('#0c1424', '#162033'),
    ('#0c2333', '#162033'),
    ('#0e1424', '#162033'),
    ('#0e1b2c', '#162033'),
    ('#0e1c2a', '#162033'),
    ('#0f192c', '#162033'),
    ('#121c2e', '#162033'),
    ('#1a2236', '#162033'),
    ('#1f293d', '#162033'),
    ('#081726', '#162033'),
    ('#0a1120', '#162033'),
    # Borders
    ('rgba(255, 255, 255, 0.08)', '#273449'),
    ('rgba(255, 255, 255, 0.06)', '#273449'),
    ('rgba(255, 255, 255, 0.1)', '#273449'),
    ('rgba(255, 255, 255, 0.12)', '#273449'),
    # Primary font
    ('#f4f5fb', '#F8FAFC'),
    ('#8fa0b5', '#94A3B8'),
    ('#8b95ad', '#94A3B8'),
    ('#a0a8be', '#94A3B8'),
]

for path in files_to_update:
    if not os.path.exists(path):
        print('Skipping non-existent:', path)
        continue
    with open(path, 'r', encoding='utf-8') as f:
        code = f.read()

    for old, new in replacements:
        code = code.replace(old, new)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)

    print('Updated', path)
print('All views updated.')
