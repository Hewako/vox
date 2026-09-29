"""Главное окно Vox."""
import re
import time
import threading
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    __version__, LANGUAGES, get_combo_values, is_separator,
    get_model_choices, model_to_internal, model_to_display,
    UI_LANGUAGES, UI_LANG_NAME_TO_CODE,
    get_lang_name_by_code, get_font,
    BG, BG_CARD, BG_INPUT, FG, FG_SUBTLE, FG_DIM,
    ACCENT, ACCENT_HOVER, BORDER, SUCCESS, DANGER, DANGER_HOVER,
    LOG_FILE,
    WARN_DURATION_MIN,
    FONT_SIZE_ORDER,
)
import i18n
from i18n import t
from core.state import request_cancel, reset_cancel
from core.settings import load_settings, save_settings
from core.models import resolve_model
from core.cache import cleanup_cache, clear_all_cache, cache_size_mb
from core.utils import (
    check_deps, get_icon_base64, notify, open_in_finder, open_file, fmt_time,
    fmt_size, play_sound, get_media_info, estimate_processing_time,
)
from core.transcriber import transcribe_one
from ui.widgets import FlatButton, FlatCheckbox
from ui.preview import show_preview
from ui.about import show_about

logger = logging.getLogger(__name__)


# ─── Размеры главного окна ───────────────────────────────────
WIN_BASE_W = 760
WIN_BASE_H = 1020
WIN_MIN_W = 680
WIN_MIN_H = 900

SETTINGS_COLS_WIDE = 800
SETTINGS_COLS_NARROW = 2


def _font_label(key):
    return t(f"font_{key}")


# ═══════════════════════════════════════════════════════════════
#  Точка входа
# ═══════════════════════════════════════════════════════════════
def run_gui(initial_files=None):
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD
        root = TkinterDnD.Tk()
        dnd_const = DND_FILES
    except ImportError:
        root = tk.Tk()
        dnd_const = None

    root.withdraw()
    root.update_idletasks()

    try:
        from ui.splash import Splash
        splash = Splash(root, duration_ms=1200)
        root.update()
    except Exception as e:
        logger.debug(f"splash failed: {e}")
        splash = None

    from ui.setup_wizard import has_any_model, show_wizard

    if not has_any_model():
        if splash:
            splash.close()
        root.deiconify()
        root.update()
        if not show_wizard(root):
            root.destroy()
            return
        root.lift()

    root._vox_state = {
        "selected_files": [],
        "last_results": [],
        "is_running": {"value": False},
        "preview_window": {"win": None},
        "dnd_const": dnd_const,
        "detected_lang": {"code": None, "prob": None},
    }

    if initial_files:
        root._vox_state["selected_files"].extend(initial_files)

    _setup_styles()
    _build_ui(root)

    root.deiconify()
    root.lift()

    root.mainloop()


# ═══════════════════════════════════════════════════════════════
#  Пересборка интерфейса
# ═══════════════════════════════════════════════════════════════
def _rebuild_ui(root):
    root.attributes("-alpha", 0.0)
    try:
        for w in root.winfo_children():
            w.destroy()
        _build_ui(root)
        root.update_idletasks()
    finally:
        root.attributes("-alpha", 1.0)


# ═══════════════════════════════════════════════════════════════
#  Авто-подстройка размера окна
# ═══════════════════════════════════════════════════════════════
def _autosize_window(root):
    root.update_idletasks()
    req_w = root.winfo_reqwidth()
    req_h = root.winfo_reqheight()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()

    target_w = max(WIN_BASE_W, req_w)
    target_h = max(WIN_BASE_H, req_h)

    target_w = min(target_w, screen_w - 40)
    target_h = min(target_h, screen_h - 120)

    root.geometry(f"{target_w}x{target_h}")


# ═══════════════════════════════════════════════════════════════
#  Построение интерфейса
# ═══════════════════════════════════════════════════════════════
def _build_ui(root):
    settings = load_settings()

    ui_lang_code = settings.get("ui_lang", "en")
    if ui_lang_code not in UI_LANGUAGES:
        ui_lang_code = "en"
    i18n.set_lang(ui_lang_code)

    font_size_key = settings.get("font_size", "medium")
    if font_size_key not in FONT_SIZE_ORDER:
        font_size_key = "medium"

    f_ui = get_font(font_size_key, "ui")
    f_title = get_font(font_size_key, "title")
    f_small = get_font(font_size_key, "small")
    f_mono = get_font(font_size_key, "mono")
    f_btn = get_font(font_size_key, "btn")

    family = f_ui[0]
    # Подписи — крупные и жирные
    label_font = (family, f_ui[1] + 1, "bold")
    # Значение внутри combobox — обычный размер, без плюсов
    combo_font = (family, f_ui[1])

    root.option_add("*TCombobox*Listbox.font", combo_font)
    root.option_add("*TCombobox*Listbox.background", BG_INPUT)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "white")

    root.title(f"Vox {__version__}")
    root.minsize(WIN_MIN_W, WIN_MIN_H)
    root.resizable(True, True)
    root.configure(bg=BG)

    icon_b64 = get_icon_base64()
    if icon_b64:
        try:
            root.iconphoto(True, tk.PhotoImage(data=icon_b64))
        except Exception as e:
            logger.debug(f"icon load failed: {e}")

    st = root._vox_state
    selected_files = st["selected_files"]
    last_results = st["last_results"]
    is_running = st["is_running"]
    preview_window = st["preview_window"]
    DND_FILES = st["dnd_const"]
    detected = st["detected_lang"]
    dnd_ok = DND_FILES is not None

    default_lang = settings.get("lang", "English")
    if default_lang not in LANGUAGES:
        default_lang = "English"
    lang_var = tk.StringVar(value=default_lang)

    ui_lang_var = tk.StringVar(value=UI_LANGUAGES[ui_lang_code])

    # ── Заголовок ────────────────────────────────────────────
    header = tk.Frame(root, bg=BG)
    header.pack(fill="x", padx=24, pady=(20, 4))

    title_block = tk.Frame(header, bg=BG)
    title_block.pack(side="left", anchor="n")

    ttk.Label(title_block, text="Vox",
              style="Title.TLabel").pack(anchor="w")
    ttk.Label(title_block, text=t("app_subtitle"),
              style="Subtle.TLabel").pack(anchor="w", pady=(2, 0))

    ui_lang_block = tk.Frame(header, bg=BG)
    ui_lang_block.pack(side="right", anchor="n")

    tk.Label(ui_lang_block, text=t("ui_lang_label"),
             bg=BG, fg=FG_DIM,
             font=f_small).pack(anchor="e", pady=(0, 4))

    ui_lang_combo = ttk.Combobox(
        ui_lang_block, textvariable=ui_lang_var,
        values=list(UI_LANGUAGES.values()),
        state="readonly", width=16, font=combo_font)
    ui_lang_combo.pack(anchor="e")

    def on_ui_lang_change(event=None):
        if is_running["value"]:
            messagebox.showwarning(
                "Vox",
                "Нельзя сменить язык во время работы.\n"
                "Дождитесь завершения или отмените.")
            ui_lang_var.set(UI_LANGUAGES[i18n.get_lang()])
            return

        code = UI_LANG_NAME_TO_CODE.get(ui_lang_var.get(), "en")

        s = load_settings()
        s["ui_lang"] = code
        s["lang"] = lang_var.get()
        s["model"] = model_to_internal(model_var.get())
        s["vad"] = vad_var.get()
        s["cache"] = cache_var.get()
        s["srt"] = srt_var.get()
        s["sound_on_done"] = sound_var.get()
        s["workers"] = workers_var.get()
        s["font_size"] = font_size_key
        save_settings(s)

        i18n.set_lang(code)
        root.after_idle(lambda: _rebuild_ui(root))

    ui_lang_combo.bind("<<ComboboxSelected>>", on_ui_lang_change)

    # ── Карточка файлов ──────────────────────────────────────
    files_card = tk.Frame(root, bg=BG_CARD)
    files_card.pack(fill="both", expand=True, padx=24, pady=(16, 0))

    files_inner = tk.Frame(files_card, bg=BG_CARD)
    files_inner.pack(fill="both", expand=True, padx=16, pady=16)

    ttk.Label(files_inner, text=t("section_files"),
              style="Section.TLabel").pack(anchor="w")

    list_wrap = tk.Frame(files_inner, bg=BG_INPUT)
    list_wrap.pack(fill="both", expand=True, pady=(10, 10))

    listbox = tk.Listbox(
        list_wrap, height=6, selectmode=tk.EXTENDED,
        bg=BG_INPUT, fg=FG,
        selectbackground=ACCENT, selectforeground="white",
        bd=0, relief="flat", highlightthickness=0,
        font=f_ui, activestyle="none")
    listbox.pack(side="left", fill="both", expand=True, padx=10, pady=8)

    sb = tk.Scrollbar(list_wrap, command=listbox.yview,
                      bd=0, relief="flat",
                      bg=BG_INPUT, troughcolor=BG_INPUT,
                      activebackground=BORDER,
                      highlightthickness=0, width=10)
    sb.pack(side="right", fill="y", pady=8)
    listbox.config(yscrollcommand=sb.set)

    def refresh_list():
        listbox.delete(0, tk.END)
        for f in selected_files:
            listbox.insert(tk.END, f"  {Path(f).name}")

    def add_files(paths):
        for p in paths:
            if p and p not in selected_files:
                selected_files.append(p)
        refresh_list()

    def pick_files():
        paths = filedialog.askopenfilenames(
            title=t("btn_add_files"),
            filetypes=[
                ("Медиа", "*.mp4 *.mov *.mkv *.avi *.webm *.m4a "
                          "*.mp3 *.wav *.aac *.flac *.ogg"),
                ("Все файлы", "*.*")])
        add_files(paths)

    def pick_folder():
        d = filedialog.askdirectory(title=t("btn_add_folder"))
        if not d:
            return
        exts = {".mp4", ".mov", ".mkv", ".avi", ".webm",
                ".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg"}
        add_files([str(p) for p in Path(d).iterdir()
                   if p.suffix.lower() in exts])

    def clear_list():
        selected_files.clear()
        refresh_list()

    refresh_list()

    btn_row = tk.Frame(files_inner, bg=BG_CARD)
    btn_row.pack(fill="x")

    FlatButton(btn_row, t("btn_add_files"), pick_files,
               bg=BG_INPUT, hover=BORDER, fg=FG,
               padx=14, pady=7, font=f_btn).pack(side="left")
    FlatButton(btn_row, t("btn_add_folder"), pick_folder,
               bg=BG_INPUT, hover=BORDER, fg=FG,
               padx=14, pady=7, font=f_btn).pack(side="left", padx=8)
    FlatButton(btn_row, t("btn_clear_list"), clear_list,
               bg=BG_INPUT, hover=BORDER, fg=FG_SUBTLE,
               padx=14, pady=7, font=f_btn).pack(side="left")

    if dnd_ok:
        def on_drop(event):
            raw = event.data
            paths = re.findall(r"\{([^}]+)\}|(\S+)", raw)
            flat = [a or b for a, b in paths]
            add_files(flat)
        listbox.drop_target_register(DND_FILES)
        listbox.dnd_bind("<<Drop>>", on_drop)
        tk.Label(files_inner, text=t("hint_drop"),
                 bg=BG_CARD, fg=FG_SUBTLE,
                 font=(f_small[0], f_small[1], "italic")).pack(
                     anchor="w", pady=(8, 0))

    # ── Настройки (адаптивная раскладка) ─────────────────────
    opts_card = tk.Frame(root, bg=BG_CARD)
    opts_card.pack(fill="x", padx=24, pady=(12, 0))

    opts_inner = tk.Frame(opts_card, bg=BG_CARD)
    opts_inner.pack(fill="x", padx=16, pady=16)

    ttk.Label(opts_inner, text=t("section_settings"),
              style="Section.TLabel").grid(
                  row=0, column=0, columnspan=4, sticky="w", pady=(0, 16))

    saved_model = settings.get("model", "Авто")
    model_var = tk.StringVar(value=model_to_display(saved_model))

    vad_var = tk.BooleanVar(value=settings["vad"])
    cache_var = tk.BooleanVar(value=settings["cache"])
    srt_var = tk.BooleanVar(value=settings["srt"])
    sound_var = tk.BooleanVar(value=settings.get("sound_on_done", True))
    font_size_var = tk.StringVar(value=_font_label(font_size_key))
    workers_var = tk.StringVar(value=settings["workers"])

    prev_lang = {"value": default_lang}

    def on_lang_selected(event=None):
        val = lang_var.get()
        if is_separator(val):
            lang_var.set(prev_lang["value"])
        else:
            prev_lang["value"] = val

    def on_font_size_selected(event=None):
        label = font_size_var.get()
        new_key = None
        for k in FONT_SIZE_ORDER:
            if _font_label(k) == label:
                new_key = k
                break
        if not new_key:
            return

        if is_running["value"]:
            font_size_var.set(_font_label(font_size_key))
            return

        s = load_settings()
        s["font_size"] = new_key
        s["lang"] = lang_var.get()
        s["model"] = model_to_internal(model_var.get())
        s["vad"] = vad_var.get()
        s["cache"] = cache_var.get()
        s["srt"] = srt_var.get()
        s["sound_on_done"] = sound_var.get()
        s["workers"] = workers_var.get()
        save_settings(s)

        root.after_idle(lambda: (_rebuild_ui(root),
                                  _autosize_window(root)))

    def _cell_with_label(label_text):
        c = tk.Frame(opts_inner, bg=BG_CARD)
        tk.Label(c, text=label_text, bg=BG_CARD, fg=FG_SUBTLE,
                 font=label_font).pack(anchor="w", pady=(0, 6))
        return c

    def _cell_checkbox(text, var):
        c = tk.Frame(opts_inner, bg=BG_CARD)
        tk.Label(c, text=" ", bg=BG_CARD, fg=FG_SUBTLE,
                 font=label_font).pack(anchor="w", pady=(0, 6))
        FlatCheckbox(c, text, var, font=f_ui).pack(anchor="w")
        return c

    cells = []

    # 1. Язык
    c_lang = _cell_with_label(t("label_lang"))
    lang_combo = ttk.Combobox(
        c_lang, textvariable=lang_var,
        values=get_combo_values(), state="readonly",
        font=combo_font)
    lang_combo.pack(anchor="w", fill="x")
    lang_combo.bind("<<ComboboxSelected>>", on_lang_selected)
    cells.append(c_lang)

    # 2. Модель
    c_model = _cell_with_label(t("label_model"))
    ttk.Combobox(
        c_model, textvariable=model_var,
        values=get_model_choices(),
        state="readonly", font=combo_font).pack(
            anchor="w", fill="x")
    cells.append(c_model)

    # 3. Размер шрифта
    c_font = _cell_with_label(t("label_font_size"))
    font_size_combo = ttk.Combobox(
        c_font, textvariable=font_size_var,
        values=[_font_label(k) for k in FONT_SIZE_ORDER],
        state="readonly", font=combo_font)
    font_size_combo.pack(anchor="w", fill="x")
    font_size_combo.bind("<<ComboboxSelected>>", on_font_size_selected)
    cells.append(c_font)

    # 4. Одновременных задач
    c_workers = _cell_with_label(t("label_workers"))
    ttk.Combobox(
        c_workers, textvariable=workers_var,
        values=["1", "2", "3", "4"],
        state="readonly", font=combo_font).pack(
            anchor="w", fill="x")
    cells.append(c_workers)

    # 5–8. Галочки
    cells.append(_cell_checkbox(t("chk_vad"), vad_var))
    cells.append(_cell_checkbox(t("chk_cache"), cache_var))
    cells.append(_cell_checkbox(t("chk_srt"), srt_var))
    cells.append(_cell_checkbox(t("chk_sound"), sound_var))

    _layout_state = {"cols": None}

    def _relayout_settings(event=None):
        w = opts_inner.winfo_width()
        if w < 100:
            return

        cols = 4 if w >= SETTINGS_COLS_WIDE else SETTINGS_COLS_NARROW
        if _layout_state["cols"] == cols:
            return
        _layout_state["cols"] = cols

        for i, cell in enumerate(cells):
            r = i // cols + 1
            cc = i % cols
            cell.grid(row=r, column=cc, sticky="ew",
                      padx=(0, 20), pady=(0, 14))

        for cc in range(4):
            if cc < cols:
                opts_inner.grid_columnconfigure(
                    cc, weight=1, minsize=180)
            else:
                opts_inner.grid_columnconfigure(
                    cc, weight=0, minsize=0)

    opts_inner.bind("<Configure>", _relayout_settings)
    opts_inner.after(50, _relayout_settings)

    # ── Прогресс ─────────────────────────────────────────────
    prog_wrap = tk.Frame(root, bg=BG)
    prog_wrap.pack(fill="x", padx=24, pady=(16, 0))

    overall_var = tk.DoubleVar(value=0)
    ttk.Progressbar(prog_wrap, variable=overall_var,
                    maximum=100).pack(fill="x")

    tk.Label(prog_wrap, text=t("overall_progress"),
             bg=BG, fg=FG_DIM,
             font=f_small,
             anchor="w").pack(fill="x", pady=(4, 0))

    current_var = tk.DoubleVar(value=0)
    ttk.Progressbar(prog_wrap, variable=current_var,
                    maximum=100).pack(fill="x", pady=(6, 0))

    current_file_var = tk.StringVar(value="")
    tk.Label(prog_wrap, textvariable=current_file_var,
             bg=BG, fg=FG_SUBTLE,
             font=f_small,
             anchor="w").pack(fill="x", pady=(4, 0))

    info_row = tk.Frame(prog_wrap, bg=BG)
    info_row.pack(fill="x", pady=(8, 0))

    status_var = tk.StringVar(value=t("status_ready"))
    status_lbl = tk.Label(info_row, textvariable=status_var,
                          bg=BG, fg=FG_SUBTLE,
                          font=f_ui,
                          anchor="w", justify="left")
    status_lbl.pack(side="left", fill="x", expand=True)

    eta_var = tk.StringVar(value="")
    tk.Label(info_row, textvariable=eta_var,
             bg=BG, fg=ACCENT,
             font=(f_ui[0], f_ui[1], "bold")).pack(side="right")

    # ── Нижние кнопки ────────────────────────────────────────
    run_row = tk.Frame(root, bg=BG)
    run_row.pack(pady=(16, 0))

    def open_result():
        if last_results:
            open_in_finder(last_results[0])

    def preview_result():
        if not last_results:
            return
        path = last_results[0]
        if not path.exists():
            messagebox.showwarning("Vox", f"File not found:\n{path}")
            return
        preview_window["win"] = show_preview(root, path,
                                              preview_window["win"])

    open_btn = FlatButton(run_row, t("btn_open_result"), open_result,
                           bg=BG_INPUT, hover=BORDER, fg=FG,
                           padx=18, pady=10, font=f_btn)
    open_btn.pack(side="left", padx=(0, 8))
    if not last_results:
        open_btn.config(state="disabled")

    preview_btn = FlatButton(run_row, t("btn_preview"), preview_result,
                              bg=BG_INPUT, hover=BORDER, fg=FG,
                              padx=18, pady=10, font=f_btn)
    preview_btn.pack(side="left", padx=(0, 8))
    if not last_results:
        preview_btn.config(state="disabled")

    def ui(fn):
        root.after(0, fn)

    def set_running(run):
        is_running["value"] = run
        if run:
            start_btn.set_style(bg=DANGER, hover=DANGER_HOVER,
                                fg="white", text=t("btn_cancel"))
            start_btn.command = cancel
        else:
            start_btn.set_style(bg=ACCENT, hover=ACCENT_HOVER,
                                fg="white", text=t("btn_transcribe"))
            start_btn.command = start

    def cancel():
        if not is_running["value"]:
            return
        status_var.set(t("status_canceling"))
        logger.info("Cancel requested")
        request_cancel()

    def current_settings():
        return {
            "lang": lang_var.get(),
            "ui_lang": UI_LANG_NAME_TO_CODE.get(ui_lang_var.get(), "en"),
            "model": model_to_internal(model_var.get()),
            "vad": vad_var.get(),
            "cache": cache_var.get(),
            "srt": srt_var.get(),
            "sound_on_done": sound_var.get(),
            "workers": workers_var.get(),
            "font_size": font_size_key,
        }

    def _validate_long_files(files):
        if not settings.get("warn_long_files", True):
            return True

        for f in files:
            duration, size_mb = get_media_info(f)
            if duration is None:
                continue
            if duration < WARN_DURATION_MIN * 60:
                continue

            eta = estimate_processing_time(duration)
            answer = messagebox.askyesno(
                t("warn_long_file_title"),
                t("warn_long_file_text",
                  name=Path(f).name,
                  duration=fmt_time(duration),
                  eta=fmt_time(eta) if eta else "—"))
            if not answer:
                return False
        return True

    def on_detected_language(code, prob):
        detected["code"] = code
        detected["prob"] = prob

        name = get_lang_name_by_code(code) or code.upper()
        pct = int(round(prob * 100))

        def _update():
            status_var.set(t("detected_lang", lang=name, pct=pct))
            status_lbl.config(fg=ACCENT)

        ui(_update)

    def start():
        if not selected_files:
            messagebox.showwarning(t("msg_no_files_title"),
                                    t("msg_no_files_text"))
            return
        problems = check_deps()
        if problems:
            from ui.missing_deps import show_missing_deps
            missing = []
            for p in problems:
                if "whisper-cli" in p:
                    missing.append({"name": "whisper-cli",
                                    "hint": "brew install whisper-cpp"})
                elif "ffmpeg" in p and "ffprobe" not in p:
                    missing.append({"name": "ffmpeg",
                                    "hint": "brew install ffmpeg"})
                elif "ffprobe" in p:
                    missing.append({"name": "ffprobe",
                                    "hint": "brew install ffmpeg"})
                else:
                    missing.append({"name": p, "hint": ""})

            if show_missing_deps(root, missing):
                start()
            return

        if not _validate_long_files(selected_files):
            return

        save_settings(current_settings())
        reset_cancel()
        set_running(True)
        open_btn.config(state="disabled")
        preview_btn.config(state="disabled")
        overall_var.set(0)
        current_var.set(0)
        current_file_var.set("")
        status_lbl.config(fg=FG_SUBTLE)
        eta_var.set("")
        status_var.set(t("status_starting"))

        detected["code"] = None
        detected["prob"] = None

        raw_lang = lang_var.get()
        language = LANGUAGES.get(raw_lang, "auto")

        use_vad = vad_var.get()
        use_cache = cache_var.get()
        save_srt = srt_var.get()
        play_on_done = sound_var.get()
        workers = int(workers_var.get())
        chosen_model = model_to_internal(model_var.get())
        total = len(selected_files)

        start_time = time.time()
        progress_lock = threading.Lock()
        progress_map = {f: 0.0 for f in selected_files}

        def update_overall():
            with progress_lock:
                p = sum(progress_map.values()) / total if total else 0
            overall_var.set(p * 100)
            elapsed = time.time() - start_time
            if p > 0.03:
                remaining = elapsed / p - elapsed
                eta_var.set(t("eta_remaining", time=fmt_time(remaining)))
            elif elapsed > 2:
                eta_var.set(t("eta_estimate"))

        def update_current(x):
            current_var.set(x * 100)

        def process_one(media):
            model = resolve_model(chosen_model, media)

            def on_prog(x):
                with progress_lock:
                    progress_map[media] = x
                ui(update_overall)
                ui(lambda: update_current(x))

            ui(lambda: current_file_var.set(
                t("current_prefix", name=Path(media).name)))

            return transcribe_one(
                media, model, language, use_vad, save_srt=save_srt,
                on_progress=on_prog,
                on_status=lambda m: ui(lambda: status_var.set(
                    f"{Path(media).name} — {m}")),
                on_language=on_detected_language,
                use_cache=use_cache)

        def worker(media):
            try:
                out = process_one(media)
                with progress_lock:
                    progress_map[media] = 1.0
                ui(update_overall)
                ui(lambda: update_current(1.0))
                return (media, out, None)
            except Exception as e:
                with progress_lock:
                    progress_map[media] = 1.0
                ui(update_overall)
                ui(lambda: update_current(1.0))
                return (media, None, str(e))

        def runner():
            results = []
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = [ex.submit(worker, f) for f in selected_files]
                for fut in as_completed(futures):
                    results.append(fut.result())

            ok = [r[1] for r in results if r[1]]
            errs = [(r[0], r[2]) for r in results if r[2]
                    and "Отменено" not in r[2] and "Cancel" not in r[2]]
            cancelled = any(r[2] and ("Отменено" in r[2] or "Cancel" in r[2])
                            for r in results)

            cleanup_cache()

            def finish():
                set_running(False)
                last_results.clear()
                last_results.extend(ok)
                eta_var.set("")
                current_file_var.set("")

                if cancelled:
                    status_var.set(t("status_cancelled",
                                     ok=len(ok), total=total))
                    status_lbl.config(fg=DANGER)
                elif errs:
                    status_var.set(t("status_done_errors",
                                     ok=len(ok), total=total,
                                     errs=len(errs)))
                    status_lbl.config(fg=DANGER)
                else:
                    elapsed = time.time() - start_time
                    status_var.set(t("status_done_time",
                                     ok=len(ok), total=total,
                                     time=fmt_time(elapsed)))
                    status_lbl.config(fg=SUCCESS)

                if ok:
                    open_btn.config(state="normal")
                    preview_btn.config(state="normal")
                    overall_var.set(100)
                    current_var.set(100)

                if errs and not cancelled:
                    messagebox.showwarning(
                        t("msg_errors_title"),
                        "\n".join(f"{Path(m).name}: {e}"
                                  for m, e in errs[:5]))

                if not cancelled:
                    notify("Vox", t("status_done",
                                    ok=len(ok), total=total)
                           + (f", errors: {len(errs)}" if errs else ""))
                    if play_on_done and ok:
                        play_sound("done")
                else:
                    notify("Vox", t("status_cancelled",
                                    ok=len(ok), total=total))
                    if play_on_done:
                        play_sound("error")

                if ok:
                    open_in_finder(ok[0])

            ui(finish)

        threading.Thread(target=runner, daemon=True).start()

    start_btn = FlatButton(run_row, t("btn_transcribe"), start,
                            bg=ACCENT, hover=ACCENT_HOVER, fg="white",
                            padx=28, pady=10,
                            font=(f_btn[0], f_btn[1] + 1, "bold"))
    start_btn.pack(side="left", padx=(0, 8))

    if is_running["value"]:
        set_running(True)

    # ── Служебные кнопки ─────────────────────────────────────
    def act_about():
        show_about(root)

    def act_show_log():
        if LOG_FILE.exists():
            open_file(LOG_FILE)
        else:
            messagebox.showinfo("Vox", t("logs_empty"))

    def act_clear_cache():
        before = cache_size_mb()
        n = clear_all_cache()
        after = cache_size_mb()
        messagebox.showinfo(
            t("cache_cleared_title"),
            t("cache_cleared", n=n, before=before, after=after))

    footer = tk.Frame(root, bg=BG)
    footer.pack(fill="x", padx=24, pady=(16, 14))

    tk.Label(footer, text=f"Vox  v{__version__}",
             bg=BG, fg=FG_DIM,
             font=f_small).pack(side="left")

    FlatButton(footer, t("btn_clear_cache"), act_clear_cache,
               bg=BG_INPUT, hover=BORDER, fg=FG_SUBTLE,
               padx=12, pady=6, font=f_small).pack(side="right")

    FlatButton(footer, t("btn_logs"), act_show_log,
               bg=BG_INPUT, hover=BORDER, fg=FG_SUBTLE,
               padx=12, pady=6,
               font=f_small).pack(side="right", padx=(0, 8))

    FlatButton(footer, t("btn_about"), act_about,
               bg=BG_INPUT, hover=BORDER, fg=FG_SUBTLE,
               padx=12, pady=6,
               font=f_small).pack(side="right", padx=(0, 8))

    # ── Escape ───────────────────────────────────────────────
    def hk_cancel(event=None):
        if is_running["value"]:
            cancel()
        return "break"

    root.bind_all("<Escape>", hk_cancel)

    # ── Закрытие ─────────────────────────────────────────────
    def on_close():
        if is_running["value"]:
            if not messagebox.askyesno("Vox", "Transcription running. Quit?"):
                return
            request_cancel()
            time.sleep(0.4)
        save_settings(current_settings())
        logger.info("Vox closing")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    root.after(100, lambda: _autosize_window(root))


def _setup_styles():
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG,
                    font=("Helvetica", 12))
    style.configure("Subtle.TLabel", background=BG, foreground=FG_SUBTLE,
                    font=("Helvetica", 11))
    style.configure("Title.TLabel", background=BG, foreground=FG,
                    font=("Helvetica", 22, "bold"))
    style.configure("Section.TLabel", background=BG_CARD, foreground=FG,
                    font=("Helvetica", 12, "bold"))
    # Уменьшенный padding → поля Combobox ниже
    style.configure("TCombobox",
                    fieldbackground=BG_INPUT,
                    background=BG_INPUT,
                    foreground=FG,
                    arrowcolor=FG,
                    borderwidth=0,
                    padding=(6, 2),
                    selectbackground=BG_INPUT,
                    selectforeground=FG)
    style.map("TCombobox",
              fieldbackground=[("readonly", BG_INPUT)],
              foreground=[("readonly", FG)],
              selectbackground=[("readonly", BG_INPUT)],
              selectforeground=[("readonly", FG)],
              bordercolor=[("focus", ACCENT)])
    style.configure("TProgressbar", troughcolor=BG_INPUT,
                    background=ACCENT, borderwidth=0, thickness=8)