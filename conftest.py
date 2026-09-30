"""Root conftest so pytest finds the project modules.

Placing this file at the project root makes pytest add the repo root
to sys.path, which is required for `from core import updater` and
similar imports inside the tests/ folder.
"""
