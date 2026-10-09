"""Settings window."""
import logging
import tkinter as tk
from tkinter import ttk

import i18n
from config import (
    ACCENT,
    ACCENT_HOVER,
    BG,
    BG_CARD,
    BG_INPUT,
    BORDER,
    FG,
    FG_SUBTLE,
    FONT_SIZE_ORDER,
    LANGUAGES,
    UI_LANG_NAME_TO_CODE,
    UI_LANGUAGES,
    get_combo_values,
    get_font,
    get_model_choices,
    is_separator,
    model_to_display,
    model_to_internal,
)
from core.settings import load_settings, save_settings
from i18n import t
from ui.widgets import FlatButton, FlatCheckbox

logger = logging.getLogger(__name__)

# Window geometry
WIN_W = 640
WIN_H = 560

def _font_label(key):
    return t(f"font_{key}")

def show_settings_window(root, on_apply=None):
    """
    Open the settings window.

    root      -- the main Tk window (parent for the Toplevel)
    on_apply  -- optional callback invoked after settings were saved,
                 so the caller can rebuild the main window
    """
    settings = load_settings()

    # Build the Toplevel
    win = tk.Toplevel(root)
    win.title(t("settings_title"))
    win.resizable(False, False)
    win.configure(bg=BG)
    win.transient(root)
    win.grab_set()

    # Center on the parent
    root.update_idletasks()
    x = root.winfo_rootx() + (root.winfo_width() - WIN_W) // 2
    y = root.winfo_rooty() + (root.winfo_height() - WIN_H) // 3
    win.geometry(f"{WIN_W}x{WIN_H}+{max(x, 40)}+{max(y, 40)}")

    # Fonts
    font_size_key = settings.get("font_size", "medium")
    if font_size_key not in FONT_SIZE_ORDER:
        font_size_key = "medium"

    f_ui = get_font(font_size_key, "ui")
    f_small = get_font(font_size_key, "small")
    f_btn = get_font(font_size_key, "btn")
    family = f_ui[0]
    label_font = (family, f_ui[1] + 1, "bold")
    combo_font = (family, f_ui[1])

    # Combobox dropdown styling
    win.option_add("*TCombobox*Listbox.font", combo_font)
    win.option_add("*TCombobox*Listbox.background", BG_INPUT)
    win.option_add("*TCombobox*Listbox.foreground", FG)
    win.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    win.option_add("*TCombobox*Listbox.selectForeground", "white")

    # Header
    header = tk.Frame(win, bg=BG)
    header.pack(fill="x", padx=24, pady=(20, 4))

    tk.Label(header, text=t("settings_title"),
             bg=BG, fg=FG,
             font=(family, f_ui[1] + 6, "bold")).pack(anchor="w")

    # Buffer variables (initialized from current settings)
    ui_lang_code = settings.get("ui_lang", "en")
    if ui_lang_code not in UI_LANGUAGES:
        ui_lang_code = "en"

    default_lang = settings.get("lang", "English")
    if default_lang not in LANGUAGES:
        default_lang = "English"

    ui_lang_var    = tk.StringVar(value=UI_LANGUAGES[ui_lang_code])
    lang_var       = tk.StringVar(value=default_lang)
    model_var      = tk.StringVar(
        value=model_to_display(settings.get("model", "Авто")))
    font_size_var  = tk.StringVar(value=_font_label(font_size_key))
    workers_var    = tk.StringVar(value=settings.get("workers", "1"))
    vad_var        = tk.BooleanVar(value=settings.get("vad", True))
    cache_var      = tk.BooleanVar(value=settings.get("cache", True))
    srt_var        = tk.BooleanVar(value=settings.get("srt", False))
    sound_var      = tk.BooleanVar(
        value=settings.get("sound_on_done", True))
    no_context_var = tk.BooleanVar(
        value=settings.get("no_context", True))

    # Track previous non-separator language value
    prev_lang = {"value": default_lang}

    # Body (scrollable if needed)
    body = tk.Frame(win, bg=BG_CARD)
    body.pack(fill="both", expand=True, padx=24, pady=(12, 0))

    body_inner = tk.Frame(body, bg=BG_CARD)
    body_inner.pack(fill="both", expand=True, padx=20, pady=20)

    body_inner.grid_columnconfigure(0, weight=1)
    body_inner.grid_columnconfigure(1, weight=1)

    def cell_label(row, col, text):
        lbl = tk.Label(body_inner, text=text,
                       bg=BG_CARD, fg=FG_SUBTLE,
                       font=label_font, anchor="w")
        lbl.grid(row=row, column=col, sticky="ew",
                 padx=(0, 16), pady=(0, 4))
        return lbl

    def cell_combo(row, col, var, values, on_select=None):
        cb = ttk.Combobox(body_inner, textvariable=var,
                          values=values, state="readonly",
                          font=combo_font)
        cb.grid(row=row + 1, column=col, sticky="ew",
                padx=(0, 16), pady=(0, 18))
        if on_select:
            cb.bind("<<ComboboxSelected>>", on_select)
        return cb

    def cell_checkbox(row, col, text, var):
        # Empty label to keep alignment with rows that have a label
        tk.Label(body_inner, text=" ",
                 bg=BG_CARD, fg=FG_SUBTLE,
                 font=label_font).grid(row=row, column=col,
                                       sticky="ew",
                                       padx=(0, 16), pady=(0, 4))
        FlatCheckbox(body_inner, text, var, font=f_ui,
                     bg=BG_CARD).grid(row=row + 1, column=col,
                                       sticky="w",
                                       padx=(0, 16), pady=(0, 18))

    # Row 0-1: Interface language + Transcription language
    cell_label(0, 0, t("ui_lang_label"))
    cell_combo(0, 0, ui_lang_var,
               list(UI_LANGUAGES.values()))

    cell_label(0, 1, t("label_lang"))

    def on_lang_selected(event=None):
        val = lang_var.get()
        if is_separator(val):
            lang_var.set(prev_lang["value"])
        else:
            prev_lang["value"] = val

    cell_combo(0, 1, lang_var,
               get_combo_values(),
               on_select=on_lang_selected)

    # Row 2-3: Model + Font size
    cell_label(2, 0, t("label_model"))
    cell_combo(2, 0, model_var,
               get_model_choices())

    cell_label(2, 1, t("label_font_size"))
    cell_combo(2, 1, font_size_var,
               [_font_label(k) for k in FONT_SIZE_ORDER])

    # Row 4-5: Workers + (empty second column)
    cell_label(4, 0, t("label_workers"))
    cell_combo(4, 0, workers_var, ["1", "2", "3", "4"])

    # Row 6-7: VAD + Cache
    cell_checkbox(6, 0, t("chk_vad"), vad_var)
    cell_checkbox(6, 1, t("chk_cache"), cache_var)

    # Row 8-9: SRT + Sound
    cell_checkbox(8, 0, t("chk_srt"), srt_var)
    cell_checkbox(8, 1, t("chk_sound"), sound_var)

    cell_checkbox(10, 0, t("chk_no_context"), no_context_var)

    # Buttons
    btn_row = tk.Frame(win, bg=BG)
    btn_row.pack(fill="x", padx=24, pady=(16, 20))

    # The Apply button is on the right (primary action).
    # Cancel is to its left (secondary).

    def do_apply(event=None):
        # Convert localized strings back to internal values.
        new_ui_lang = UI_LANG_NAME_TO_CODE.get(ui_lang_var.get(), "en")

        new_font_label = font_size_var.get()
        new_font_key = font_size_key
        for k in FONT_SIZE_ORDER:
            if _font_label(k) == new_font_label:
                new_font_key = k
                break

        new_settings = {
            "ui_lang":        new_ui_lang,
            "lang":           lang_var.get(),
            "model":          model_to_internal(model_var.get()),
            "vad":            vad_var.get(),
            "cache":          cache_var.get(),
            "srt":            srt_var.get(),
            "sound_on_done":  sound_var.get(),
            "no_context":     no_context_var.get(),
            "workers":        workers_var.get(),
            "font_size":      new_font_key,
            "warn_long_files": settings.get("warn_long_files", True),
        }
        save_settings(new_settings)
        logger.info(f"Settings applied: {new_settings}")

        # Set language globally so the main window rebuilds with it
        i18n.set_lang(new_ui_lang)

        close()
        if on_apply:
            try:
                on_apply()
            except Exception as e:
                logger.error(f"settings on_apply failed: {e}")

    def do_cancel(event=None):
        close()

    def close():
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()

    # Layout: Cancel on the left, Apply on the right.
    FlatButton(btn_row, t("settings_btn_cancel"), do_cancel,
               bg=BG_INPUT, hover=BORDER, fg=FG_SUBTLE,
               padx=18, pady=10, font=f_btn).pack(side="left")

    FlatButton(btn_row, t("settings_btn_apply"), do_apply,
               bg=ACCENT, hover=ACCENT_HOVER, fg="white",
               padx=20, pady=10,
               font=(f_btn[0], f_btn[1], "bold")).pack(side="right")

    # Keyboard
    win.bind("<Escape>", do_cancel)
    win.bind("<Return>", do_apply)
    win.protocol("WM_DELETE_WINDOW", do_cancel)

    # Focus the window so Enter/Esc work immediately
    win.lift()
    win.focus_force()
    return win
