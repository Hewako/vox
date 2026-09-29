"""
Vox — конфигурация сборки .app через py2app.

После сборки скрипт автоматически:
  · копирует Vox.app в /Applications
  · чистит xattr (иначе macOS не даст запустить)
  · удаляет build/ и dist/ (чтобы не было дублей в Launchpad)

Так что после `python3 setup.py py2app` в Программах будет ровно один Vox.
"""
import shutil
import subprocess
import sys
from pathlib import Path

from setuptools import setup


APP = ['main.py']
DATA_FILES = ['icon_data.py']

OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.icns',
    'plist': {
        'CFBundleName': 'Vox',
        'CFBundleDisplayName': 'Vox',
        'CFBundleIdentifier': 'com.hewako.vox',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '11.0',
    },
    'packages': ['tkinterdnd2', 'core', 'ui'],
    'includes': ['config', 'i18n', 'tkinter', 'tkinter.ttk',
                 'tkinter.filedialog', 'tkinter.messagebox'],
    'excludes': ['numpy', 'scipy', 'pandas', 'matplotlib', 'PIL',
                 'pytest', 'setuptools', 'distutils'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)


# ═══════════════════════════════════════════════════════════════
#  Пост-обработка: копируем в /Applications и чистим dist
# ═══════════════════════════════════════════════════════════════
def _post_build():
    here = Path(__file__).parent.resolve()
    built_app = here / 'dist' / 'Vox.app'
    target_app = Path('/Applications/Vox.app')

    if not built_app.exists():
        print('\n! dist/Vox.app не найден — сборка, возможно, упала.')
        sys.exit(1)

    print('\n▸ Копирую в /Applications...')
    if target_app.exists():
        shutil.rmtree(target_app)
    subprocess.run(['cp', '-R', str(built_app), str(target_app)], check=True)

    print('▸ Чищу xattr...')
    subprocess.run(['xattr', '-cr', str(target_app)], check=False)

    print('▸ Удаляю build/ и dist/ (чтобы не было дублей в Launchpad)...')
    shutil.rmtree(here / 'dist', ignore_errors=True)
    shutil.rmtree(here / 'build', ignore_errors=True)

    print('\n✓ Готово. Vox лежит в /Applications/Vox.app')
    print('  Запустить: open /Applications/Vox.app')


if 'py2app' in sys.argv:
    _post_build()