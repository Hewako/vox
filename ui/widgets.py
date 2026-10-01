"""Кастомные виджеты в стиле тёмной темы Vox."""
import tkinter as tk
from config import (
    BG_INPUT, BG_CARD, FG, FG_SUBTLE,
    ACCENT, ACCENT_HOVER,
)

class FlatButton:
    def __init__(self, parent, text, command, bg=ACCENT, fg="white",
                 hover=ACCENT_HOVER, disabled_bg=BG_INPUT,
                 disabled_fg=FG_SUBTLE, padx=20, pady=10, font=None):
        self.bg = bg
        self.hover = hover
        self.fg = fg
        self.disabled_bg = disabled_bg
        self.disabled_fg = disabled_fg
        self.command = command
        self._enabled = True

        self.lbl = tk.Label(
            parent, text=text,
            bg=bg, fg=fg,
            padx=padx, pady=pady,
            font=font or ("Helvetica", 12, "bold"),
            cursor="pointinghand")
        self.lbl.bind("<Button-1>", self._on_click)
        self.lbl.bind("<Enter>", lambda e: self._hover(True))
        self.lbl.bind("<Leave>", lambda e: self._hover(False))

    def _on_click(self, event):
        if self._enabled and self.command:
            self.command()

    def _hover(self, on):
        if not self._enabled:
            return
        self.lbl.config(bg=self.hover if on else self.bg)

    def pack(self, **kw):
        self.lbl.pack(**kw)

    def pack_forget(self):
        self.lbl.pack_forget()

    def grid(self, **kw):
        self.lbl.grid(**kw)

    def grid_forget(self):
        self.lbl.grid_forget()

    def place(self, **kw):
        self.lbl.place(**kw)

    def place_forget(self):
        self.lbl.place_forget()

    def set_style(self, bg=None, hover=None, fg=None, text=None):
        if bg:
            self.bg = bg
        if hover:
            self.hover = hover
        if fg:
            self.fg = fg
        if text:
            self.lbl.config(text=text)
        if self._enabled:
            self.lbl.config(bg=self.bg, fg=self.fg)

    def config(self, **kw):
        if "state" in kw:
            if kw["state"] == "disabled":
                self._enabled = False
                self.lbl.config(bg=self.disabled_bg, fg=self.disabled_fg,
                                cursor="arrow")
            else:
                self._enabled = True
                self.lbl.config(bg=self.bg, fg=self.fg,
                                cursor="pointinghand")
        if "text" in kw:
            self.lbl.config(text=kw["text"])

class FlatCheckbox:
    def __init__(self, parent, text, variable, bg=BG_CARD, fg=FG,
                 accent=FG, font=None):
        self.var = variable
        self.bg = bg
        self.fg = fg
        self.accent = accent
        self._on_char = "☑"
        self._off_char = "☐"

        self.frame = tk.Frame(parent, bg=bg)
        self.box = tk.Label(
            self.frame, text=self._symbol(), bg=bg,
            fg=accent if variable.get() else FG_SUBTLE,
            font=("Helvetica", 20, "bold"),
            cursor="pointinghand")
        self.box.pack(side="left")

        self.lbl = tk.Label(
            self.frame, text=text, bg=bg, fg=fg,
            font=font or ("Helvetica", 14),
            cursor="pointinghand")
        self.lbl.pack(side="left", padx=(6, 0))

        for w in (self.box, self.lbl):
            w.bind("<Button-1>", self._toggle)
            w.bind("<Enter>", lambda e: self._hover(True))
            w.bind("<Leave>", lambda e: self._hover(False))

    def _symbol(self):
        return self._on_char if self.var.get() else self._off_char

    def _toggle(self, event=None):
        self.var.set(not self.var.get())
        self._refresh()

    def _hover(self, on):
        color = self.accent if self.var.get() else FG
        if on:
            self.box.config(fg=color)
            self.lbl.config(fg=color)
        else:
            self._refresh()

    def _refresh(self):
        if self.var.get():
            self.box.config(text=self._on_char, fg=self.accent)
            self.lbl.config(fg=self.fg)
        else:
            self.box.config(text=self._off_char, fg=FG_SUBTLE)
            self.lbl.config(fg=self.fg)

    def pack(self, **kw):
        self.frame.pack(**kw)

    def grid(self, **kw):
        self.frame.grid(**kw)