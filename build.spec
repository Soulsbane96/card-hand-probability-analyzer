# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('Normal Deck.csv', '.'),
        ('icon.ico',            '.'),
        ('gui/check.svg',       'gui'),
        ('gui/radio_dot.svg',   'gui'),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='HandProbabilityAnalyzer',
    console=False,
    icon='icon.ico',
)
