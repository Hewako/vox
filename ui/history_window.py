"""
History window.

Shows a list of past transcriptions grouped by date. Built on a
plain tk.Canvas instead of ttk.Treeview, because Tk 8.6 on macOS
does not reliably render images in Treeview column #0.
"""
import logging
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox

from PIL import Image, ImageTk

from config import (
    ACCENT,
    BG,
    BG_CARD,
    BG_INPUT,
    BORDER,
    DANGER,
    DANGER_HOVER,
    SUCCESS,
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
WIN_W = 820
WIN_H = 640

ICON_SIZE = 20
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
    """Return a short human label for the group of an entry."""
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

def _tint(img: Image.Image, rgb: tuple) -> Image.Image:
    """
    Replace the icon's RGB with a single color, keeping the original
    alpha as the mask. Produces a monochrome icon in the target color.
    """
    img = img.convert("RGBA")
    alpha = img.split()[-1]
    solid = Image.new("RGBA", img.size, rgb + (255,))
    solid.putalpha(alpha)
    return solid


def _hex_to_rgb(hex_color: str) -> tuple:
    """'#30d158' -> (48, 209, 88)."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

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

    win = tk.Toplevel(root)
    win.title(t("history_title"))
    win.geometry(f"{WIN_W}x{WIN_H}")
    win.resizable(True, True)
    win.minsize(620, 420)
    win.configure(bg=BG)
    win.transient(root)
    win.grab_set()

    root.update_idletasks()
    x = root.winfo_rootx() + (root.winfo_width() - WIN_W) // 2
    y = root.winfo_rooty() + (root.winfo_height() - WIN_H) // 3
    win.geometry(f"{WIN_W}x{WIN_H}+{max(x, 40)}+{max(y, 40)}")

    from core.settings import load_settings
    font_size_key = load_settings().get("font_size", "medium")
    if font_size_key not in FONT_SIZE_ORDER:
        font_size_key = "medium"
    f_ui = get_font(font_size_key, "ui")
    f_small = get_font(font_size_key, "small")
    f_btn = get_font(font_size_key, "btn")

    def close(event=None):
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()

    # ── Header ───────────────────────────────────────────────
    header = tk.Frame(win, bg=BG)
    header.pack(fill="x", padx=24, pady=(20, 4))
    tk.Label(header, text=t("history_title"),
             bg=BG, fg=FG,
             font=(f_ui[0], f_ui[1] + 8, "bold")).pack(anchor="w")

    # ── Empty state ──────────────────────────────────────────
    if not entries:
        empty = tk.Frame(win, bg=BG_CARD)
        empty.pack(fill="both", expand=True, padx=24, pady=(12, 0))
        tk.Label(empty, text=t("history_empty"),
                 bg=BG_CARD, fg=FG_SUBTLE,
                 font=(f_ui[0], f_ui[1] + 2)).pack(expand=True)

        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(fill="x", padx=24, pady=(16, 20))
        FlatButton(btn_row, t("history_close_btn"), close,
                   bg=BG_INPUT, hover=BORDER, fg=FG,
                   padx=18, pady=10, font=f_btn).pack(side="right")

        win.bind("<Escape>", close)
        win.protocol("WM_DELETE_WINDOW", close)
        win.lift()
        win.focus_force()
        return win

    # ── Icons ────────────────────────────────────────────────
    icon_ok = None
    icon_err = None
    try:
        ok_rgb = _hex_to_rgb(SUCCESS)     # green
        err_rgb = _hex_to_rgb(DANGER)     # red

        img_ok = Image.open(_ASSETS / "status_ok.png").convert("RGBA")
        img_ok = img_ok.resize((ICON_SIZE, ICON_SIZE),
                                Image.Resampling.LANCZOS)
        img_ok = _tint(img_ok, ok_rgb)
        icon_ok = ImageTk.PhotoImage(img_ok)

        img_err = Image.open(_ASSETS / "status_error.png").convert("RGBA")
        img_err = img_err.resize((ICON_SIZE, ICON_SIZE),
                                  Image.Resampling.LANCZOS)
        img_err = _tint(img_err, err_rgb)
        icon_err = ImageTk.PhotoImage(img_err)

        logger.info(f"history: loaded status icons at {ICON_SIZE}px")
    except Exception as e:
        logger.warning(f"history: could not load status icons: {e}")

    win._icon_ok = icon_ok
    win._icon_err = icon_err

    # ── Scrollable area ──────────────────────────────────────
    main = tk.Frame(win, bg=BG_CARD)
    main.pack(fill="both", expand=True, padx=24, pady=(12, 0))

    canvas = tk.Canvas(main, bg=BG_CARD, highlightthickness=0, bd=0)
    scrollbar = tk.Scrollbar(main, orient="vertical", command=canvas.yview,
                             bd=0, relief="flat",
                             bg=BG_CARD, troughcolor=BG_CARD,
                             activebackground=BORDER,
                             highlightthickness=0, width=10)
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(canvas, bg=BG_CARD)
    inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def update_scrollregion(event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def on_canvas_resize(event):
        canvas.itemconfig(inner_id, width=event.width)

    inner.bind("<Configure>", update_scrollregion)
    canvas.bind("<Configure>", on_canvas_resize)

    def on_mousewheel(event):
        if event.delta == 0:
            return
        step = -1 if event.delta > 0 else 1
        canvas.yview_scroll(step, "units")

    win.bind("<MouseWheel>", on_mousewheel)

    # ── State ────────────────────────────────────────────────
    entry_by_id = {e.get("id"): e for e in entries if e.get("id")}
    # iid -> [(widget, default_bg, default_fg_or_None), ...]
    row_widgets = {}
    # iid -> top-level Frame
    row_frames = {}
    selected_id = [None]

    def _paint_bg(widget, color):
        try:
            widget.config(bg=color)
        except tk.TclError:
            pass

    def _set_fg(widget, color):
        if isinstance(widget, tk.Label) and color is not None:
            try:
                widget.config(fg=color)
            except tk.TclError:
                pass

    def set_selected(iid):
        # Restore previous selection
        old = selected_id[0]
        if old is not None and old in row_widgets:
            for w, bg, fg in row_widgets[old]:
                _paint_bg(w, bg)
                _set_fg(w, fg)

        selected_id[0] = iid

        # Paint new selection
        if iid is not None and iid in row_widgets:
            for w, bg, fg in row_widgets[iid]:
                _paint_bg(w, ACCENT)
                if isinstance(w, tk.Label) and fg is not None:
                    _set_fg(w, "white")

    # ── Actions ──────────────────────────────────────────────
    def open_result(entry):
        path = entry.get("output", "")
        if not path or not Path(path).exists():
            messagebox.showwarning("Vox", t("history_no_output"))
            return
        open_in_finder(Path(path))

    def open_source(entry):
        path = entry.get("source", "")
        if not path or not Path(path).exists():
            messagebox.showwarning("Vox", t("history_no_source"))
            return
        open_in_finder(Path(path))

    def retry(entry):
        src = entry.get("source", "")
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

    def delete_entry(entry):
        if not messagebox.askyesno("Vox", t("history_delete_confirm")):
            return
        history.delete(entry.get("id", ""))
        iid = entry.get("id")
        f = row_frames.pop(iid, None)
        row_widgets.pop(iid, None)
        if f is not None:
            f.destroy()
        if not row_frames:
            for w in inner.winfo_children():
                w.destroy()
            tk.Label(inner, text=t("history_empty"),
                     bg=BG_CARD, fg=FG_SUBTLE,
                     font=(f_ui[0], f_ui[1] + 2)).pack(pady=40)

    def show_context_menu(event, entry):
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

    # ── Row builders ─────────────────────────────────────────
    def add_group_header(label_text):
        hdr = tk.Frame(inner, bg=BG_CARD)
        hdr.pack(fill="x", pady=(14, 4))
        tk.Label(hdr, text=label_text, bg=BG_CARD, fg=FG_DIM,
                 font=(f_ui[0], f_ui[1] - 1, "italic"),
                 anchor="w").pack(fill="x", padx=8)

    def add_row(entry):
        iid = entry.get("id")
        status = entry.get("status", "")

        icon = icon_ok if status == "ok" else icon_err
        name = Path(entry.get("source", "")).name or "—"
        time_str = _human_time(entry.get("finished_at"))
        dur_str = _human_duration(entry.get("duration"))
        lang_str = entry.get("language", "") or ""
        status_str = "" if status == "ok" else (entry.get("error") or "")

        row = tk.Frame(inner, bg=BG_CARD, cursor="hand2")
        row.pack(fill="x", pady=1)
        row_frames[iid] = row

        # Icon
        if icon is not None:
            icon_lbl = tk.Label(row, image=icon, bg=BG_CARD, bd=0)
            icon_lbl.image = icon
        else:
            icon_lbl = tk.Label(row, text="", bg=BG_CARD, width=2)
        icon_lbl.pack(side="left", padx=(10, 8), pady=5)

        # Name (flex)
        name_lbl = tk.Label(row, text=name, bg=BG_CARD, fg=FG,
                            font=f_ui, anchor="w")
        name_lbl.pack(side="left", fill="x", expand=True, pady=5)

        # Time (fixed width, chars)
        time_lbl = tk.Label(row, text=time_str, bg=BG_CARD, fg=FG_SUBTLE,
                            font=f_small, width=7, anchor="w")
        time_lbl.pack(side="left", padx=(8, 0), pady=5)

        # Duration
        dur_lbl = tk.Label(row, text=dur_str, bg=BG_CARD, fg=FG_SUBTLE,
                           font=f_small, width=7, anchor="w")
        dur_lbl.pack(side="left", pady=5)

        # Language
        lang_lbl = tk.Label(row, text=lang_str, bg=BG_CARD, fg=FG_SUBTLE,
                            font=f_small, width=12, anchor="w")
        lang_lbl.pack(side="left", pady=5)

        # Status code (red if error)
        status_fg = DANGER if status_str else FG_SUBTLE
        status_lbl = tk.Label(row, text=status_str, bg=BG_CARD, fg=status_fg,
                              font=f_small, width=6, anchor="w")
        status_lbl.pack(side="left", padx=(0, 10), pady=5)

        row_widgets[iid] = [
            (row,        BG_CARD, None),
            (icon_lbl,   BG_CARD, None),
            (name_lbl,   BG_CARD, FG),
            (time_lbl,   BG_CARD, FG_SUBTLE),
            (dur_lbl,    BG_CARD, FG_SUBTLE),
            (lang_lbl,   BG_CARD, FG_SUBTLE),
            (status_lbl, BG_CARD, status_fg),
        ]

        # Events
        def on_click(event, _iid=iid):
            set_selected(_iid)
            return "break"

        def on_double(event, _iid=iid):
            set_selected(_iid)
            e = entry_by_id.get(_iid)
            if e:
                open_result(e)
            return "break"

        def on_right(event, _entry=entry):
            set_selected(_entry.get("id"))
            show_context_menu(event, _entry)
            return "break"

        for w in (row, icon_lbl, name_lbl, time_lbl,
                  dur_lbl, lang_lbl, status_lbl):
            w.bind("<Button-1>", on_click)
            w.bind("<Double-1>", on_double)
            w.bind("<Button-2>", on_right)
            w.bind("<Button-3>", on_right)

    # ── Populate ─────────────────────────────────────────────
    groups = {}
    for e in entries:
        key = _group_key(e.get("finished_at"))
        groups.setdefault(key, []).append(e)

    for key in sorted(groups.keys(), reverse=True):
        group_entries = groups[key]
        add_group_header(_group_label(group_entries[0].get("finished_at")))
        for e in group_entries:
            add_row(e)

    # Set up scrollregion once the layout has settled.
    inner.update_idletasks()
    update_scrollregion()

    # ── Bottom buttons ───────────────────────────────────────
    def clear_all():
        if not messagebox.askyesno(t("history_clear_btn"),
                                    t("history_clear_confirm")):
            return
        n = history.clear()
        messagebox.showinfo(
            t("history_cleared_title"),
            t("history_cleared_text", n=n))
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
