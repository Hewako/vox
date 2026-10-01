"""
Vox build script for py2app.

After the build it:
  · copies Vox.app to /Applications
  · strips xattr (so macOS lets the app run)
  · removes build/ and dist/ (no duplicate icons in Launchpad)

So after `python3 setup.py py2app` you end up with exactly one Vox
in Applications.
"""
import shutil
import subprocess
import sys
from pathlib import Path

from setuptools import setup

APP = ['main.py']

import glob  # noqa: E402

DATA_FILES = [
    'icon_data.py',
    'CHANGELOG.md',
    ('docs/changelog', ['docs/changelog/ru.md']),
    ('assets', glob.glob('assets/*.png')),
    ('assets/settings_anim', glob.glob('assets/settings_anim/*.png')),
]

OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.icns',
    'plist': {
        'CFBundleName': 'Vox',
        'CFBundleDisplayName': 'Vox',
        'CFBundleIdentifier': 'com.hewako.vox',
        'CFBundleVersion': '1.1.1',
        'CFBundleShortVersionString': '1.1.1',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '11.0',
    },
    'packages': ['tkinterdnd2', 'core', 'ui', 'certifi', 'PIL'],
    'includes': ['config', 'i18n', 'tkinter', 'tkinter.ttk',
                 'tkinter.filedialog', 'tkinter.messagebox',
                 'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL._imaging'],
    'excludes': ['numpy', 'scipy', 'pandas', 'matplotlib',
                 'pytest', 'setuptools', 'distutils'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)


# ═══════════════════════════════════════════════════════════════
#  Post-build: copy to /Applications and clean dist
# ═══════════════════════════════════════════════════════════════
def _post_build():
    here = Path(__file__).parent.resolve()
    built_app = here / 'dist' / 'Vox.app'
    target_app = Path('/Applications/Vox.app')

    if not built_app.exists():
        print('\n! dist/Vox.app not found — build probably failed.')
        sys.exit(1)

    print('\n▸ Copying to /Applications...')
    if target_app.exists():
        shutil.rmtree(target_app)
    subprocess.run(['cp', '-R', str(built_app), str(target_app)], check=True)

    print('▸ Stripping xattr...')
    subprocess.run(['xattr', '-cr', str(target_app)], check=False)

    print('▸ Removing build/ and dist/ (no duplicate icons in Launchpad)...')
    shutil.rmtree(here / 'dist', ignore_errors=True)
    shutil.rmtree(here / 'build', ignore_errors=True)

    print('\n✓ Done. Vox is in /Applications/Vox.app')
    print('  Launch: open /Applications/Vox.app')


if 'py2app' in sys.argv:
    _post_build()
