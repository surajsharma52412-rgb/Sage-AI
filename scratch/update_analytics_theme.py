for path in ['ui/components/analytics_view.py', 'ui/components/usage_dialog.py']:
    with open(path, 'r', encoding='utf-8') as f:
        code = f.read()

    code = code.replace('#0FE6B5', '#00D1FF')
    code = code.replace('#0fe6b5', '#00d1ff')
    code = code.replace('#040711', '#0A0F14')
    code = code.replace('#050811', '#0A0F14')
    code = code.replace('#080d19', '#0A0F14')
    code = code.replace('#081220', '#162033')
    code = code.replace('#08101e', '#162033')
    code = code.replace('#0a1120', '#162033')
    code = code.replace('#0c1424', '#162033')
    code = code.replace('rgba(15, 230, 181,', 'rgba(0, 209, 255,')
    code = code.replace('rgba(255, 255, 255, 0.08)', '#273449')
    code = code.replace('rgba(255, 255, 255, 0.06)', '#273449')
    code = code.replace('rgba(255, 255, 255, 0.1)', '#273449')
    code = code.replace('rgba(79, 128, 255, 0.25)', '#273449')
    code = code.replace('rgba(168, 85, 247, 0.25)', '#273449')
    code = code.replace('("#00D1FF", "#0a9372")', '("#00D1FF", "#008BB3")')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)

    print('Updated', path)
