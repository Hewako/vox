"""
Changelog window.

Reads CHANGELOG.md from the project (or from the .app bundle) and
renders a subset of Markdown into a read-only Text widget:

- # / ## / ### headings
- - bullet lists
- blank lines
- inline **bold** and [text](url) links

No external Markdown library required.
"""
import logging
import re
import sys
import tkinter as tk
import webbrowser
from pathlib import Path

from config import (
    ACCENT,
    BG,
    BG_CARD,
    BORDER,
    FG,
)
from i18n import t
from ui.widgets import FlatButton

logger = logging.getLogger(__name__)


# ─── Geometry ────────────────────────────────────────────────
WIN_W = 720
WIN_H = 700


# ─── Locate CHANGELOG.md ─────────────────────────────────────
def _find_changelog():
    """
    Look for a localized CHANGELOG file.

    The fallback chain is:
        1. docs/changelog/<ui_lang>.md   (or .app Resources, same path)
        2. CHANGELOG.md                  (English, for GitHub)

    Returns a Path or None.
    """
    import i18n
    ui_lang = i18n.get_lang()

    project_root = Path(__file__).parent.parent
    resources_root = project_root

    exe = str(sys.executable)
    if ".app/Contents/MacOS/" in exe:
        app_root = Path(exe.split(".app/Contents/MacOS/")[0] + ".app")
        resources_root = app_root / "Contents" / "Resources"

    candidates = [
        resources_root / "docs" / "changelog" / f"{ui_lang}.md",
        project_root / "docs" / "changelog" / f"{ui_lang}.md",
        resources_root / "CHANGELOG.md",
        project_root / "CHANGELOG.md",
    ]

    for p in candidates:
        if p.exists():
            return p
    return None


def _read_changelog():
    p = _find_changelog()
    if p is None:
        return None
    try:
        return p.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"changelog: could not read {p}: {e}")
        return None


# ─── Markdown rendering ──────────────────────────────────────
_INLINE_RE = re.compile(r"(\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))")


def _setup_tags(w):
    w.tag_configure("h1", font=("Helvetica", 22, "bold"),
                    foreground=FG, spacing1=6, spacing3=10)
    w.tag_configure("h2", font=("Helvetica", 16, "bold"),
                    foreground=ACCENT, spacing1=16, spacing3=6)
    w.tag_configure("h3", font=("Helvetica", 13, "bold"),
                    foreground=FG, spacing1=10, spacing3=4)
    w.tag_configure("body", font=("Helvetica", 11),
                    foreground=FG, spacing3=2)
    w.tag_configure("bullet", font=("Helvetica", 11),
                    foreground=FG,
                    lmargin1=22, lmargin2=34,
                    spacing3=3)
    w.tag_configure("bold", font=("Helvetica", 11, "bold"),
                    foreground=FG)


def _insert_link(w, label, url, base_tag):
    tag = f"lnk_{abs(hash(url + label))}"
    w.tag_configure(tag, foreground=ACCENT, underline=True)
    w.insert(tk.END, label, (base_tag, tag))
    w.tag_bind(tag, "<Button-1>", lambda e, u=url: webbrowser.open(u))
    w.tag_bind(tag, "<Enter>",
               lambda e, ww=w: ww.config(cursor="pointinghand"))
    w.tag_bind(tag, "<Leave>",
               lambda e, ww=w: ww.config(cursor=""))


def _insert_inline(w, line, base_tag):
    for part in _INLINE_RE.split(line):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            w.insert(tk.END, part[2:-2], (base_tag, "bold"))
        elif part.startswith("[") and "](" in part:
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", part)
            if m:
                _insert_link(w, m.group(1), m.group(2), base_tag)
            else:
                w.insert(tk.END, part, base_tag)
        else:
            w.insert(tk.END, part, base_tag)


def _render_markdown(w, md_text):
    _setup_tags(w)

    for raw in md_text.splitlines():
        line = raw.rstrip()

        if not line:
            w.insert(tk.END, "\n", "body")
        elif line.startswith("### "):
            _insert_inline(w, line[4:], "h3")
            w.insert(tk.END, "\n", "h3")
        elif line.startswith("## "):
            _insert_inline(w, line[3:], "h2")
            w.insert(tk.END, "\n", "h2")
        elif line.startswith("# "):
            _insert_inline(w, line[2:], "h1")
            w.insert(tk.END, "\n", "h1")
        elif line.startswith("- "):
            w.insert(tk.END, "\u2022  ", "bullet")
            _insert_inline(w, line[2:], "bullet")
            w.insert(tk.END, "\n", "bullet")
        else:
            _insert_inline(w, line, "body")
            w.insert(tk.END, "\n", "body")


# ─── Public entry ────────────────────────────────────────────
def show_changelog_window(root):
    win = tk.Toplevel(root)
    win.title(t("changelog_title"))
    win.geometry(f"{WIN_W}x{WIN_H}")
    win.resizable(True, True)
    win.minsize(520, 400)
    win.configure(bg=BG)
    win.transient(root)

    root.update_idletasks()
    x = root.winfo_rootx() + (root.winfo_width() - WIN_W) // 2
    y = root.winfo_rooty() + (root.winfo_height() - WIN_H) // 3
    win.geometry(f"{WIN_W}x{WIN_H}+{max(x, 40)}+{max(y, 40)}")

    header = tk.Frame(win, bg=BG)
    header.pack(fill="x", padx=24, pady=(20, 4))
    tk.Label(header, text=t("changelog_title"),
             bg=BG, fg=FG,
             font=("Helvetica", 20, "bold")).pack(anchor="w")

    body = tk.Frame(win, bg=BG_CARD)
    body.pack(fill="both", expand=True, padx=24, pady=(12, 0))

    scroll = tk.Scrollbar(body, orient="vertical",
                          bd=0, relief="flat",
                          bg=BG_CARD, troughcolor=BG_CARD,
                          activebackground=BORDER,
                          highlightthickness=0, width=10)
    scroll.pack(side="right", fill="y")

    text_widget = tk.Text(
        body,
        bg=BG_CARD, fg=FG,
        bd=0, relief="flat", highlightthickness=0,
        wrap="word",
        padx=20, pady=16,
        font=("Helvetica", 11),
        cursor="arrow",
        yscrollcommand=scroll.set,
    )
    text_widget.pack(side="left", fill="both", expand=True)
    scroll.config(command=text_widget.yview)

    md = _read_changelog()
    if md is None:
        text_widget.insert(tk.END, t("changelog_missing"), "body")
    else:
        _render_markdown(text_widget, md)

    text_widget.config(state="disabled")

    btn_row = tk.Frame(win, bg=BG)
    btn_row.pack(fill="x", padx=24, pady=(12, 20))
    FlatButton(btn_row, t("changelog_close_btn"), win.destroy,
               bg=BG, hover=BORDER, fg=FG,
               padx=18, pady=10,
               font=("Helvetica", 11)).pack(side="right")

    win.bind("<Escape>", lambda e: win.destroy())
    win.protocol("WM_DELETE_WINDOW", win.destroy)

    win.lift()
    win.focus_force()
    return win
