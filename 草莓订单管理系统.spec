# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/gd/Desktop/草莓订单管理系统/src/strawberry_order_management/app.py'],
    pathex=['/Users/gd/Desktop/草莓订单管理系统/src'],
    binaries=[],
    datas=[('/Users/gd/Desktop/草莓订单管理系统/src/strawberry_order_management/assets', 'strawberry_order_management/assets')],
    hiddenimports=['PySide6.QtSvg', 'PySide6.QtPrintSupport'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='草莓订单管理系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['/Users/gd/Desktop/草莓订单管理系统.app/Contents/Resources/AppIcon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='草莓订单管理系统',
)
app = BUNDLE(
    coll,
    name='草莓订单管理系统.app',
    icon='/Users/gd/Desktop/草莓订单管理系统.app/Contents/Resources/AppIcon.icns',
    bundle_identifier='local.codex.strawberry-order-management',
)
