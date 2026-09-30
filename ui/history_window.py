"""
History window.

Shows a list of past transcriptions grouped by date. Double-click
opens the result file in Finder; right-click offers more actions.
Layout uses a ttk.Treeview with the status icon in column #0.
"""
import logging
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from config import (
    ACCENT,
    BG,
    BG_CARD,
    BG_INPUT,
    BORDER,
    DANGER,
    DANGER_HOVER,
    FG,
    FG_DIM,
    FG_SUBTLE,
    FONT_SIZE_ORDER,
    get_font,
)
from core import history
from core.utils import open_in_finder
from i18n import t
from ui.widgets import FlatButton

logger = logging.getLogger(__name__)


# ─── Geometry ────────────────────────────────────────────────
WIN_W = 780
WIN_H = 620

ICON_SIZE = 16
_ASSETS = Path(__file__).parent.parent / "assets"


# ─── Helpers ─────────────────────────────────────────────────
def _human_time(ts):
    """Format a finished_at timestamp as HH:MM."""
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%H:%M")
    except Exception:
        return "—"


def _human_duration(seconds):
    """Format a duration in seconds as 1:23 or 1:02:05 or '—'."""
    if seconds is None:
        return "—"
    try:
        s = int(seconds)
    except Exception:
        return "—"
    if s <= 0:
        return "—"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}:{s:02d}"
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}"


def _group_label(ts):
    """
    Return a short human label for the group of an entry: Today,
    Yesterday, or a date like '30 Sep' / '28 Sep 2025'.
    """
    try:
        d = date.fromtimestamp(float(ts))
    except Exception:
        return t("history_title")

    today = date.today()
    if d == today:
        return t("history_today")
    if d == today - timedelta(days=1):
        return t("history_yesterday")

    same_year = d.year == today.year
    if same_year:
        return d.strftime("%-d %b")
    return d.strftime("%-d %b %Y")


def _group_key(ts):
    """Stable sort/group key for an entry: 'YYYY-MM-DD'."""
    try:
        return date.fromtimestamp(float(ts)).isoformat()
    except Exception:
        return "0000-00-00"


# ─── Main entry ──────────────────────────────────────────────
def show_history_window(root, on_retry=None):
    """
    Open the history window.

    root      -- parent Tk window
    on_retry  -- callback(source_path) -> bool. Called when the user
                 clicks Retry. Must return True if a transcription
                 started. If True, the history window closes.
    """
    entries = history.list_entries()

    # ── Build the window ─────────────────────────────────────
    win = tk.Toplevel(root)
    win.title(t("history_title"))
    win.geometry(f"{WIN_W}x{WIN_H}")
    win.resizable(True, True)
    win.minsize(560, 400)
    win.configure(bg=BG)
    win.transient(root)
    win.grab_set()

    root.update_idletasks()
    x = root.winfo_rootx() + (root.winfo_width() - WIN_W) // 2
    y = root.winfo_rooty() + (root.winfo_height() - WIN_H) // 3
    win.geometry(f"{WIN_W}x{WIN_H}+{max(x, 40)}+{max(y, 40)}")

    # Fonts — inherit font size preference from settings.
    from core.settings import load_settings
    font_size_key = load_settings().get("font_size", "medium")
    if font_size_key not in FONT_SIZE_ORDER:
        font_size_key = "medium"
    f_ui = get_font(font_size_key, "ui")
    f_small = get_font(font_size_key, "small")
    f_btn = get_font(font_size_key, "btn")

    # ── Header ───────────────────────────────────────────────
    header = tk.Frame(win, bg=BG)
    header.pack(fill="x", padx=24, pady=(20, 4))

    tk.Label(header, text=t("history_title"),
             bg=BG, fg=FG,
             font=(f_ui[0], f_ui[1] + 8, "bold")).pack(anchor="w")

    # ── Icons for status ─────────────────────────────────────
    icon_ok = None
    icon_err = None
    try:
        img_ok = Image.open(_ASSETS / "status_ok.png").convert("RGBA")
        img_ok = img_ok.resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
        icon_ok = ImageTk.PhotoImage(img_ok)

        img_err = Image.open(_ASSETS / "status_error.png").convert("RGBA")
        img_err = img_err.resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
        icon_err = ImageTk.PhotoImage(img_err)
    except Exception as e:
        logger.warning(f"history: could not load status icons: {e}")

    # Keep references so PhotoImages are not garbage-collected.
    win._icon_ok = icon_ok
    win._icon_err = icon_err

    # ── Empty state ──────────────────────────────────────────
    if not entries:
        empty = tk.Frame(win, bg=BG_CARD)
        empty.pack(fill="both", expand=True, padx=24, pady=(12, 0))
        tk.Label(empty, text=t("history_empty"),
                 bg=BG_CARD, fg=FG_SUBTLE,
                 font=(f_ui[0], f_ui[1] + 2)).pack(expand=True)

        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(fill="x", padx=24, pady=(16, 20))

        def close_empty(event=None):
            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()

        FlatButton(btn_row, t("history_close_btn"), close_empty,
                   bg=BG_INPUT, hover=BORDER, fg=FG,
                   padx=18, pady=10, font=f_btn).pack(side="right")
        win.bind("<Escape>", close_empty)
        win.protocol("WM_DELETE_WINDOW", close_empty)
        win.lift()
        win.focus_force()
        return win

    # ── Treeview ─────────────────────────────────────────────
    tree_wrap = tk.Frame(win, bg=BG_CARD)
    tree_wrap.pack(fill="both", expand=True, padx=24, pady=(12, 0))

    style = ttk.Style(win)
    style.configure("History.Treeview",
                    background=BG_CARD,
                    fieldbackground=BG_CARD,
                    foreground=FG,
                    bordercolor=BG_CARD,
                    rowheight=26,
                    font=f_ui)
    style.configure("History.Treeview.Heading",
                    background=BG_CARD,
                    foreground=FG_SUBTLE,
                    borderwidth=0,
                    font=(f_ui[0], f_ui[1] - 1))
    style.map("History.Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", "white")])

    columns = ("name", "time", "duration", "language", "status")
    tree = ttk.Treeview(tree_wrap, columns=columns,
                        show="tree headings",
                        style="History.Treeview",
                        selectmode="browse")
    tree.heading("#0", text="", anchor="w")
    tree.column("#0", width=36, stretch=False, anchor="center")
    tree.heading("name", text="", anchor="w")
    tree.column("name", width=280, stretch=True, anchor="w")
    tree.heading("time", text="", anchor="w")
    tree.column("time", width=70, stretch=False, anchor="w")
    tree.heading("duration", text="", anchor="w")
    tree.column("duration", width=80, stretch=False, anchor="w")
    tree.heading("language", text="", anchor="w")
    tree.column("language", width=100, stretch=False, anchor="w")
    tree.heading("status", text="", anchor="w")
    tree.column("status", width=90, stretch=False, anchor="w")

    # Scrollbar
    sb = tk.Scrollbar(tree_wrap, command=tree.yview,
                      bd=0, relief="flat",
                      bg=BG_CARD, troughcolor=BG_CARD,
                      activebackground=BORDER,
                      highlightthickness=0, width=10)
    sb.pack(side="right", fill="y")
    tree.config(yscrollcommand=sb.set)
    tree.pack(fill="both", expand=True)

    # ── Populate ─────────────────────────────────────────────
    # Group entries by date. Entries are already newest-first.
    groups = {}
    for e in entries:
        key = _group_key(e.get("finished_at"))
        groups.setdefault(key, []).append(e)

    # Insert group parents and children.
    for key in sorted(groups.keys(), reverse=True):
        group_entries = groups[key]
        label = _group_label(group_entries[0].get("finished_at"))
        parent_id = f"group:{key}"

        tree.insert("", "end", iid=parent_id, text="",
                    values=(label, "", "", "", ""),
                    tags=("group",))
        for e in group_entries:
            eid = e.get("id", "")
            name = Path(e.get("source", "")).name or "—"

            status = e.get("status", "")
            if status == "ok":
                icon = icon_ok
                status_text = ""
            else:
                icon = icon_err
                status_text = e.get("error") or ""

            tree.insert(parent_id, "end", iid=eid,
                        text=" ",
                        image=icon if icon else "",
                        values=(
                            name,
                            _human_time(e.get("finished_at")),
                            _human_duration(e.get("duration")),
                            e.get("language", "") or "",
                            status_text,
                        ))

        tree.item(parent_id, open=True)

    # Style: group rows are dim, dimmed-italic.
    tree.tag_configure("group", foreground=FG_DIM,
                       font=(f_ui[0], f_ui[1] - 1, "italic"))

    # ── Entry lookup ─────────────────────────────────────────
    by_id = {e.get("id"): e for e in entries if e.get("id")}

    def _selected_entry():
        sel = tree.selection()
        if not sel:
            return None
        iid = sel[0]
        if iid.startswith("group:"):
            return None
        return by_id.get(iid)

    # ── Actions ──────────────────────────────────────────────
    def open_result(entry=None):
        e = entry or _selected_entry()
        if not e:
            return
        path = e.get("output", "")
        if not path or not Path(path).exists():
            messagebox.showwarning("Vox", t("history_no_output"))
            return
        open_in_finder(Path(path))

    def open_source(entry=None):
        e = entry or _selected_entry()
        if not e:
            return
        path = e.get("source", "")
        if not path or not Path(path).exists():
            messagebox.showwarning("Vox", t("history_no_source"))
            return
        open_in_finder(Path(path))

    def retry(entry=None):
        e = entry or _selected_entry()
        if not e:
            return
        src = e.get("source", "")
        if not src or not Path(src).exists():
            messagebox.showwarning("Vox", t("history_no_source"))
            return

        if on_retry is None:
            return
        try:
            started = on_retry(src)
        except Exception as ex:
            logger.error(f"history: retry callback failed: {ex}")
            return

        if started:
            close()

    def delete_entry(entry=None):
        e = entry or _selected_entry()
        if not e:
            return
        if not messagebox.askyesno("Vox", t("history_delete_confirm")):
            return
        history.delete(e.get("id", ""))
        tree.delete(e.get("id", ""))

    def close(event=None):
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()

    # ── Double-click and right-click ─────────────────────────
    def on_double(event):
        iid = tree.identify_row(event.y)
        if not iid or iid.startswith("group:"):
            return
        open_result(by_id.get(iid))

    def show_context_menu(event):
        iid = tree.identify_row(event.y)
        if not iid or iid.startswith("group:"):
            return
        tree.selection_set(iid)
        entry = by_id.get(iid)
        if not entry:
            return

        menu = tk.Menu(win, tearoff=0,
                       bg=BG_CARD, fg=FG,
                       activebackground=ACCENT, activeforeground="white",
                       bd=0, relief="flat")
        menu.add_command(label=t("history_open_result"),
                         command=lambda: open_result(entry))
        menu.add_command(label=t("history_open_source"),
                         command=lambda: open_source(entry))
        menu.add_separator()
        menu.add_command(label=t("history_retry"),
                         command=lambda: retry(entry))
        menu.add_command(label=t("history_delete"),
                         command=lambda: delete_entry(entry))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    tree.bind("<Double-1>", on_double)
    tree.bind("<Button-2>", show_context_menu)   # macOS right-click
    tree.bind("<Button-3>", show_context_menu)   # fallback

    # ── Bottom buttons ───────────────────────────────────────
    def clear_all():
        if not messagebox.askyesno(t("history_clear_btn"),
                                    t("history_clear_confirm")):
            return
        n = history.clear()
        # Remove all children from the tree.
        for iid in list(tree.get_children("")):
            tree.delete(iid)
        messagebox.showinfo(
            t("history_cleared_title"),
            t("history_cleared_text", n=n))
        close()
        close()

    btn_row = tk.Frame(win, bg=BG)
    btn_row.pack(fill="x", padx=24, pady=(12, 20))

    FlatButton(btn_row, t("history_close_btn"), close,
               bg=BG_INPUT, hover=BORDER, fg=FG,
               padx=18, pady=10, font=f_btn).pack(side="right")

    FlatButton(btn_row, t("history_clear_btn"), clear_all,
               bg=BG_INPUT, hover=DANGER_HOVER, fg=DANGER,
               padx=18, pady=10, font=f_btn).pack(side="right", padx=(0, 8))

    # ── Keyboard ─────────────────────────────────────────────
    win.bind("<Escape>", close)
    win.protocol("WM_DELETE_WINDOW", close)

    win.lift()
    win.focus_force()
    return win
