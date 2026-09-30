"""Vox main window."""
import logging
import re
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import i18n
from config import (
    ACCENT,
    ACCENT_HOVER,
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
    LANGUAGES,
    LOG_FILE,
    SUCCESS,
    UI_LANGUAGES,
    WARN_DURATION_MIN,
    __version__,
    get_font,
    get_lang_name_by_code,
)
from core.cache import cache_size_mb, cleanup_cache, clear_all_cache
from core.models import resolve_model
from core.settings import load_settings
from core.state import request_cancel, reset_cancel
from core.transcriber import transcribe_one
from core.updater import check_for_update_if_due
from core.utils import (
    check_deps,
    estimate_processing_time,
    fmt_time,
    get_icon_base64,
    get_media_info,
    notify,
    open_file,
    open_in_finder,
    play_sound,
)
from i18n import t
from ui.about import show_about
from ui.preview import show_preview
from ui.settings_icon import SettingsIconPlayer
from ui.settings_window import show_settings_window
from ui.widgets import FlatButton

logger = logging.getLogger(__name__)


# ─── Window sizes ────────────────────────────────────────────
WIN_BASE_W = 760
WIN_BASE_H = 720
WIN_MIN_W = 680
WIN_MIN_H = 640

AUTO_UPDATE_DELAY_MS = 1500


# ═══════════════════════════════════════════════════════════════
#  Entry point
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

    root.after(AUTO_UPDATE_DELAY_MS, lambda: _auto_check_update(root))

    root.mainloop()


# ═══════════════════════════════════════════════════════════════
#  Auto update check on startup
# ═══════════════════════════════════════════════════════════════
def _auto_check_update(root):
    def worker():
        try:
            data = check_for_update_if_due()
        except Exception as e:
            logger.error(f"auto update check failed: {e}")
            return

        if not data:
            return

        def open_window():
            try:
                from ui.updater_window import show_update_window
                show_update_window(root, data)
            except Exception as e:
                logger.error(f"could not open update window: {e}")

        root.after(0, open_window)

    threading.Thread(target=worker, daemon=True).start()


# ═══════════════════════════════════════════════════════════════
#  UI rebuild
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
#  Autosize
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
#  Build UI
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
    f_small = get_font(font_size_key, "small")
    f_btn = get_font(font_size_key, "btn")

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

    # ── Header ───────────────────────────────────────────────
    header = tk.Frame(root, bg=BG)
    header.pack(fill="x", padx=24, pady=(20, 4))

    title_block = tk.Frame(header, bg=BG)
    title_block.pack(side="left", anchor="n")

    ttk.Label(title_block, text="Vox",
              style="Title.TLabel").pack(anchor="w")
    ttk.Label(title_block, text=t("app_subtitle"),
              style="Subtle.TLabel").pack(anchor="w", pady=(2, 0))

    # Right side: only the settings icon now.
    settings_col = tk.Frame(header, bg=BG)
    settings_col.pack(side="right", anchor="n")

    tk.Label(settings_col, text=t("settings_label"),
             bg=BG, fg=FG_DIM,
             font=f_small).pack(anchor="center", pady=(0, 4))

    settings_btn = tk.Label(settings_col,
                            bg=BG,
                            bd=0,
                            highlightthickness=0,
                            padx=4, pady=2,
                            cursor="pointinghand")
    settings_btn.pack(anchor="center")

    settings_player = SettingsIconPlayer(root, settings_btn)
    settings_player.show_idle()

    def on_settings_enter(event):
        settings_btn.config(bg=BG_INPUT)

    def on_settings_leave(event):
        settings_btn.config(bg=BG)

    def on_settings_click(event):
        if is_running["value"]:
            messagebox.showwarning(
                "Vox",
                "Cannot open settings while a job is running.\n"
                "Wait for it to finish or cancel.")
            return
        settings_player.play_once()

        def apply_and_rebuild():
            _rebuild_ui(root)
            _autosize_window(root)

        show_settings_window(root, on_apply=apply_and_rebuild)

    settings_btn.bind("<Enter>", on_settings_enter)
    settings_btn.bind("<Leave>", on_settings_leave)
    settings_btn.bind("<Button-1>", on_settings_click)

    # ── Files card ───────────────────────────────────────────
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
                ("Media", "*.mp4 *.mov *.mkv *.avi *.webm *.m4a "
                          "*.mp3 *.wav *.aac *.flac *.ogg"),
                ("All files", "*.*")])
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

    # ── Progress ─────────────────────────────────────────────
    prog_wrap = tk.Frame(root, bg=BG)
    prog_wrap.pack(fill="x", padx=24, pady=(20, 0))

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

    # ── Bottom buttons ───────────────────────────────────────
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

        # Read all live settings from settings.json — they are managed
        # by the settings window and saved there on Apply.
        live = load_settings()
        raw_lang = live.get("lang", "English")
        language = LANGUAGES.get(raw_lang, "auto")

        use_vad = live.get("vad", True)
        use_cache = live.get("cache", True)
        save_srt = live.get("srt", False)
        play_on_done = live.get("sound_on_done", True)
        workers = int(live.get("workers", "1"))
        chosen_model = live.get("model", "Авто")
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

    # ── Footer ───────────────────────────────────────────────
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

    # ── Close ────────────────────────────────────────────────
    def on_close():
        if is_running["value"]:
            if not messagebox.askyesno("Vox", "Transcription running. Quit?"):
                return
            request_cancel()
            time.sleep(0.4)
        # Settings are saved by the settings window; nothing to flush here.
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
