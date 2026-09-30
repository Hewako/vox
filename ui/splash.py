"""Splash-окно при запуске приложения."""
import tkinter as tk

from config import BG, FG, FG_SUBTLE
from core.utils import get_icon_base64


class Splash:
    """
    Маленькое окно с иконкой и названием.
    Показывается во время загрузки приложения.
    """

    def __init__(self, root, duration_ms=1200):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.configure(bg=BG)
        self.win.attributes("-topmost", True)

        # ── Размеры и позиция ────────────────────────────────
        w, h = 320, 200
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2 - 40
        self.win.geometry(f"{w}x{h}+{x}+{y}")

        # ── Рамка ────────────────────────────────────────────
        outer = tk.Frame(self.win, bg=BG, highlightthickness=1,
                         highlightbackground="#3a3a3c")
        outer.pack(fill="both", expand=True)

        inner = tk.Frame(outer, bg=BG)
        inner.pack(expand=True)

        # ── Иконка ───────────────────────────────────────────
        icon_b64 = get_icon_base64()
        if icon_b64:
            try:
                img = tk.PhotoImage(data=icon_b64)
                factor = max(1, img.width() // 80)
                if factor > 1:
                    img = img.subsample(factor, factor)
                lbl = tk.Label(inner, image=img, bg=BG, bd=0)
                lbl.image = img
                lbl.pack(pady=(28, 12))
            except Exception:
                pass

        # ── Название ─────────────────────────────────────────
        tk.Label(inner, text="Vox",
                 bg=BG, fg=FG,
                 font=("Helvetica", 22, "bold")).pack()

        tk.Label(inner, text="Starting…",
                 bg=BG, fg=FG_SUBTLE,
                 font=("Helvetica", 11)).pack(pady=(6, 0))

        # ── Автозакрытие ─────────────────────────────────────
        if duration_ms > 0:
            self.win.after(duration_ms, self.close)

    def close(self):
        try:
            self.win.destroy()
        except Exception:
            pass