# PyInstaller spec for the GarageTEC desktop app (onedir).
# Build:  pyinstaller garagetec.spec --noconfirm
# Output: dist/GarageTEC/GarageTEC.exe
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

datas = []
binaries = []
hiddenimports = []

# --- App data read at runtime via __file__-relative paths -------------------
datas += [
    ('web/frontend/dist', 'web/frontend/dist'),          # prebuilt UI (served as static)
    ('store/schema.sql', 'store'),                        # DB schema (init_db reads this)
    ('assets', 'assets'),                                 # splash html + icons
    ('coach/norms/norms.json', 'coach/norms'),            # population norms
    ('coach/norms/pro_reference/golftec_reference.json', 'coach/norms/pro_reference'),
    ('coach/norms/pro_reference/pro_reference.json', 'coach/norms/pro_reference'),
    ('coach/norms/pro_reference/supplementary_reference.json', 'coach/norms/pro_reference'),
]

# --- Heavy native packages PyInstaller can't fully trace on its own ---------
# mediapipe ships .tflite/.binarypb model assets + native libs; onnxruntime and
# cv2 ship native runtimes; webview (pywebview) bundles JS + WebView2 loader
# DLLs and platform backends loaded dynamically via clr/pythonnet.
for pkg in ('mediapipe', 'onnxruntime', 'cv2', 'webview'):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# --- Lazy / dynamic imports outside the static import graph -----------------
hiddenimports += [
    'anthropic',              # coach.backend.make_backend("cloud")
    'vision.pose_rtm',        # vision.make_pose_estimator factory (lazy)
    'socketio',                # python-socketio client (OpenFlight enrichment)
    'engineio',
    'engineio.async_drivers.threading',
    # pywebview Windows backend (loaded by name at runtime) + pythonnet bridge.
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'clr',
    'clr_loader',
    'clr_loader.netfx',
]
hiddenimports += collect_submodules('uvicorn')  # loop/protocol/lifespan impls

a = Analysis(
    ['run_app.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # NOTE: matplotlib is a hard dependency of mediapipe.solutions.drawing_utils,
    # so it must NOT be excluded even though we never plot anything.
    excludes=['pytest'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GarageTEC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # windowed app: no raw terminal; splash shows instead
    disable_windowed_traceback=False,
    icon='assets/garagetec.ico',
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='GarageTEC',
)
