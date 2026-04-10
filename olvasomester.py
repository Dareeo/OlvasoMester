import pyperclip
import tkinter as tk
from tkinter import ttk
import threading
import time
import os
import sys
import subprocess
import winreg
import pystray
from PIL import Image, ImageDraw, ImageTk
import logging
import io
import numpy as np
import sounddevice as sd
import re
import queue
import random
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

VERSION = "1.3"

UPDATE_SERVERS = [
    "https://olvasomester.dareeo.hu/version",
]

AUTHOR = 'D@reeo'
BILD_DATE = '2026.04.09'
CONTACT = 'dareeo@gmail.com'
URL = 'https://olvasomester.dareeo.hu'

# ---------------- THEME ----------------
TH_BG        = "#F5F0E8"
TH_BG2       = "#E8E0D0"
TH_FG        = "#1A1A1A"
TH_FG2       = "#4A4A4A"
TH_ACCENT    = "#C45000"
TH_ACCENT_FG = "#FFFFFF"
TH_LINK      = "#0055CC"
TH_FONT      = ("Segoe UI", 11)
TH_FONT_SM   = ("Segoe UI", 10)
TH_FONT_HEAD = ("Segoe UI", 13, "bold")


if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, '_MEIPASS', BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

PIPER_EXE = os.path.join(BUNDLE_DIR, "piper", "piper.exe")
PIPER_MODEL_DIR = os.path.join(BUNDLE_DIR, "piper", "models")

PIPER_MODELS = {
    "Anna": "hu_HU-anna-medium.onnx",
    "Berta": "hu_HU-berta-medium.onnx",
    "Imre": "hu_HU-imre-medium.onnx",
}

root = tk.Tk()
root.withdraw()

current_window = None
last_text = ""
running = True

_session_event = threading.Event()
_session_event.set()

REG_PATH = r"Software\OlvasoMester"


# ---------------- REGISTRY ----------------
def reg_set(name, value):
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH)
    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(value))
    winreg.CloseKey(key)


def reg_get(name, default):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH)
        val, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        if default is None:
            return val
        return type(default)(val)
    except:
        return default


# ---------------- WINDOW GEOMETRY ----------------
def save_geometry(win):
    try:
        geom = win.geometry()
        size, pos = geom.split('+', 1)
        w, h = map(int, size.split('x'))
        x, y = map(int, pos.split('+'))
        reg_set("x", x);
        reg_set("y", y)
        reg_set("w", w);
        reg_set("h", h)
        logging.info(f"Ablak pozíció mentve: {x},{y} méret: {w}x{h}")
    except Exception as e:
        logging.warning(f"save_geometry hiba: {e}")


def load_geometry():
    x = reg_get("x", None)
    y = reg_get("y", None)
    w = reg_get("w", 500)
    h = reg_get("h", 300)
    try:
        x = int(x) if x is not None else None
        y = int(y) if y is not None else None
    except:
        x = y = None
    return x, y, w, h


def default_geometry(win, w, h):
    """Első induláskor: jobb alsó sarok, tálcát figyelembe véve."""
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    margin = 40
    x = sw - w - margin
    y = sh - h - margin - 48
    return x, y


def bind_geometry_save(win):
    _timer = [None]

    def on_configure(e):
        if _timer[0]:
            win.after_cancel(_timer[0])
        _timer[0] = win.after(500, lambda: save_geometry(win))

    win.bind("<Configure>", on_configure)


# ---------------- TÁLCA IKON ----------------
def make_tray_icon():
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, size - 3, size - 3], fill=(230, 100, 30, 255))
    bx1, by1, bx2, by2 = 14, 14, 50, 52
    d.rectangle([bx1, by1, bx2, by2], fill=(255, 255, 255, 255))
    mx = (bx1 + bx2) // 2
    d.rectangle([mx - 2, by1, mx + 2, by2], fill=(230, 100, 30, 255))
    for y in [22, 29, 36, 43]:
        d.rectangle([bx1 + 4, y, mx - 5, y + 2], fill=(180, 180, 180, 255))
        d.rectangle([mx + 5, y, bx2 - 4, y + 2], fill=(180, 180, 180, 255))
    return img


_app_icon = ImageTk.PhotoImage(make_tray_icon(), master=root)
root.iconphoto(True, _app_icon)

MAX_PARALLEL = 1


def split_into_chunks(text, max_chars=800):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    paragraphs = re.split(r'\n{2,}', text.strip())
    chunks = []
    for para in paragraphs:
        # Bekezdésen belüli sortörések → szóköz (pl. kézzel tördelt szöveg)
        para = re.sub(r'\n', ' ', para).strip()
        para = re.sub(r' {2,}', ' ', para)
        if not para:
            continue
        sentences = re.split(r'(?<=[.!?;])\s+', para)
        current = ""
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            if len(current) + len(sent) + 1 <= max_chars:
                current = (current + " " + sent).strip()
            else:
                if current:
                    chunks.append(current)
                if len(sent) > max_chars:
                    words = sent.split()
                    current = ""
                    for w in words:
                        if len(current) + len(w) + 1 <= max_chars:
                            current = (current + " " + w).strip()
                        else:
                            if current:
                                chunks.append(current)
                            current = w
                    if current:
                        chunks.append(current)
                    current = ""
                else:
                    current = sent
        if current:
            chunks.append(current)
    return [c for c in chunks if c.strip()]


def generate_one_chunk(text, rate, voice, stop_ev):
    """
    Egyetlen chunk generálása memóriába.
    Saját szálon fut, stop_ev esetén kilövi a Piper folyamatot.
    Visszaad: (audio_float32, samplerate, duration) vagy None.
    """
    model = os.path.join(PIPER_MODEL_DIR, PIPER_MODELS[voice])
    speed = max(0.5, min(2.0, rate / 100))
    length_scale = 1 / speed

    espeak_data = os.path.join(BUNDLE_DIR, "piper", "espeak-ng-data")

    # Windows: elrejtjük a CMD ablakot
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE

    try:
        cmd = [
            PIPER_EXE,
            "--model", model,
            "--output-raw",
            "--length-scale", str(length_scale),
        ]
        if os.path.isdir(espeak_data):
            cmd += ["--espeak-data", espeak_data]

        logging.debug(f"Piper cmd: {cmd}")

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=si,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        proc.stdin.write(text.encode("utf-8"))
        proc.stdin.close()

        buf = io.BytesIO()
        read_done = threading.Event()

        def reader():
            try:
                while True:
                    data = proc.stdout.read(8192)
                    if not data:
                        break
                    buf.write(data)
            finally:
                read_done.set()

        threading.Thread(target=reader, daemon=True).start()

        while not read_done.wait(timeout=0.05):
            if stop_ev.is_set():
                proc.kill()
                proc.wait()
                return None

        proc.wait()

        try:
            err = proc.stderr.read().decode("utf-8", errors="replace").strip()
            if err:
                logging.warning(f"Piper stderr: {err}")
        except:
            pass

        raw = buf.getvalue()
        if not raw:
            logging.error("Piper üres kimenetet adott — valószínűleg nem találja a modellt vagy az espeak adatokat")
            return None

        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        samplerate = 22050
        return audio, samplerate, len(audio) / samplerate

    except Exception as e:
        logging.error(f"Piper hiba: {e}")
        return None


# ---------------- LEJÁTSZÁS ----------------
def play_audio_blocking(audio, samplerate, stop_ev):
    """
    Callback-alapú lejátszás: a sounddevice pontosan jelzi mikor ért véget,
    nem időzítés alapján döntünk. stop_ev esetén azonnal leáll.
    """
    finished = threading.Event()
    pos = [0]

    def callback(outdata, frames, time_info, status):
        if stop_ev.is_set():
            raise sd.CallbackStop()

        remaining = len(audio) - pos[0]
        if remaining == 0:
            raise sd.CallbackStop()

        n = min(frames, remaining)
        outdata[:n, 0] = audio[pos[0]:pos[0] + n]
        if n < frames:
            outdata[n:] = 0
        pos[0] += n

    try:
        with sd.OutputStream(
                samplerate=samplerate,
                channels=1,
                dtype='float32',
                callback=callback,
                finished_callback=finished.set
        ):
            while not finished.wait(timeout=0.05):
                if stop_ev.is_set():
                    break
    except Exception as e:
        logging.error(f"Lejátszási hiba: {e}")


def stop_audio():
    try:
        sd.stop()
    except:
        pass


def highlight_chunk(chunk_text, widget, duration, stop_ev, search_from_char):
    """
    Szavanként kiemeli a chunk szavait a widget szövegében.
    A szavak pozícióját karakteraritmetikával számítja a chunk_text-en belül
    (search_from_char + offset) — nincs widget.search() hívás szavanként,
    így nem találhat rossz egyezést ismétlődő szavaknál.
    A delay arányos a szó hosszával a jobb szinkronért.
    """
    words = chunk_text.split()
    if not words or duration <= 0:
        return

    # Szavak pozíciói a chunk_text-en belül
    offsets = []
    idx = 0
    for word in words:
        start = chunk_text.find(word, idx)
        if start == -1:
            offsets.append(None)
        else:
            offsets.append(start)
            idx = start + len(word)

    total_chars = sum(len(w) for w in words) or 1
    delays = [duration * len(w) / total_chars for w in words]

    for word, offset, delay in zip(words, offsets, delays):
        if stop_ev.is_set():
            return
        if offset is not None:
            abs_start = search_from_char + offset
            w_start = f"1.0+{abs_start}c"
            w_end   = f"1.0+{abs_start + len(word)}c"
            try:
                widget.tag_remove("hl", "1.0", "end")
                widget.tag_add("hl", w_start, w_end)
                widget.tag_config("hl", background=TH_ACCENT, foreground=TH_ACCENT_FG)
                widget.see(w_start)
            except Exception:
                pass
        time.sleep(delay)


def schedule_close():
    sec = reg_get("auto_close", 0)
    if sec <= 0:
        return
    threading.Timer(sec, lambda: root.after(0, on_close)).start()

def stop_current():
    _session_event.set()
    stop_audio()


def streaming_reader(text, text_widget, my_event):
    """
    Párhuzamos generálás + sorrend-megőrző lejátszás.

    Minden chunkhoz azonnal elindul egy saját generáló szál.
    Az eredmények egy indexelt dict-be kerülnek.
    A consumer sorban, index szerint veszi ki és játssza le őket —
    így soha nem kell várni: mire az 1. chunk lejátszása véget ér,
    a 2-3-4. már rég kész a memóriában.
    """
    chunks = split_into_chunks(text)
    if not chunks:
        return

    rate = reg_get("rate", 100)
    voice = reg_get("voice", "Anna")

    n = len(chunks)
    logging.info(f"Streaming indul: {n} chunk, max {MAX_PARALLEL} párhuzamos Piper")

    MISSING = object()
    results = [MISSING] * n
    results_lock = threading.Lock()
    ready_events = [threading.Event() for _ in range(n)]
    sem = threading.Semaphore(MAX_PARALLEL)

    def generate_worker(i, chunk):
        if my_event.is_set():
            with results_lock:
                results[i] = None
            ready_events[i].set()
            return

        sem.acquire()
        try:
            if my_event.is_set():
                with results_lock:
                    results[i] = None
                return

            logging.info(f"Chunk {i + 1}/{n} generálás: "
                         f"'{chunk[:50]}{'...' if len(chunk) > 50 else ''}'")
            result = generate_one_chunk(chunk, rate, voice, my_event)

            with results_lock:
                results[i] = result

            if result:
                logging.info(f"Chunk {i + 1} kész: {result[2]:.2f}s")
            else:
                logging.warning(f"Chunk {i + 1} sikertelen")
        finally:
            sem.release()
            ready_events[i].set()

    for i, chunk in enumerate(chunks):
        t = threading.Thread(target=generate_worker, args=(i, chunk), daemon=True)
        t.start()

    # ------------------------------------------------------------------ #
    # CONSUMER — sorban, index szerint játssza le a kész chunkokat       #
    # ------------------------------------------------------------------ #
    def consumer():
        search_pos = 0
        for i, chunk_text in enumerate(chunks):
            while not ready_events[i].wait(timeout=0.05):
                if my_event.is_set():
                    stop_audio()
                    logging.info("Consumer leállítva")
                    return

            if my_event.is_set():
                stop_audio()
                logging.info("Consumer leállítva")
                return

            with results_lock:
                result = results[i]

            if result is None:
                logging.warning(f"Chunk {i + 1} kihagyva (hiba vagy stop)")
                continue

            audio, samplerate, duration = result

            chunk_start = search_pos
            first_words = chunk_text.split()
            if first_words:
                try:
                    found = text_widget.search(
                        first_words[0], f"1.0+{search_pos}c", stopindex="end", exact=True
                    )
                    if found:
                        chunk_start = int(text_widget.count("1.0", found)[0])
                except Exception:
                    pass

            logging.info(f"Lejátszás chunk {i + 1}/{n}: "
                         f"'{chunk_text[:50]}{'...' if len(chunk_text) > 50 else ''}'")

            hl = threading.Thread(
                target=highlight_chunk,
                args=(chunk_text, text_widget, duration, my_event, chunk_start),
                daemon=True
            )
            hl.start()
            play_audio_blocking(audio, samplerate, my_event)
            hl.join(timeout=0.3)

            search_pos = chunk_start + len(chunk_text)

        if not my_event.is_set():
            logging.info("Felolvasás befejezve")
            schedule_close()

    threading.Thread(target=consumer, daemon=True).start()


# ---------------- START ----------------
def start(text):
    global _session_event

    logging.info(f"Új felolvasás indul ({len(text)} karakter)")

    _session_event.set()
    stop_audio()
    time.sleep(0.05)
    _session_event = threading.Event()

    try:
        current_window.text_widget.tag_remove("hl", "1.0", "end")
    except:
        pass

    threading.Thread(
        target=streaming_reader,
        args=(text, current_window.text_widget, _session_event),
        daemon=True
    ).start()


# ---------------- UI ----------------
def on_close():
    logging.info("Ablak bezárva, felolvasás leállítva")
    stop_current()
    if current_window:
        current_window.withdraw()


def show(text):
    global current_window

    x, y, w, h = load_geometry()

    if current_window is None:
        current_window = tk.Toplevel(root)
        current_window.title("OlvasóMester")
        current_window.attributes("-topmost", True)

        if x is not None:
            current_window.geometry(f"{w}x{h}+{x}+{y}")
        else:
            w, h = 500, 300
            current_window.geometry(f"{w}x{h}")
            current_window.update_idletasks()
            dx, dy = default_geometry(current_window, w, h)
            current_window.geometry(f"{w}x{h}+{dx}+{dy}")
            logging.info(f"Első indulás, alapértelmezett pozíció: {dx},{dy}")

        current_window.configure(bg=TH_BG)
        txt = tk.Text(
            current_window, font=("Segoe UI", 20), wrap="word",
            bg=TH_BG, fg=TH_FG, insertbackground=TH_FG,
            relief="flat", padx=16, pady=12,
            selectbackground=TH_ACCENT, selectforeground=TH_ACCENT_FG,
        )
        txt.pack(expand=True, fill="both")
        current_window.text_widget = txt

        bind_geometry_save(current_window)
        current_window.protocol("WM_DELETE_WINDOW", on_close)

    current_window.deiconify()
    current_window.lift()
    current_window.text_widget.delete("1.0", "end")
    current_window.text_widget.insert("1.0", text)

    start(text)


def check_updates():
    if not reg_get("auto_update", 0):
        return

    def _ver_tuple(v):
        try:
            return tuple(int(x) for x in v.split("."))
        except Exception:
            return (0,)

    def _fetch():
        servers = UPDATE_SERVERS[:]
        random.shuffle(servers)
        for url in servers:
            try:
                logging.info(f"Frissítés ellenőrzése: {url}")
                with urllib.request.urlopen(url, timeout=5) as resp:
                    remote = resp.read().decode("utf-8").strip()
                if _ver_tuple(remote) > _ver_tuple(VERSION):
                    logging.info(f"Új verzió elérhető: {remote} (jelenlegi: {VERSION})")
                    root.after(0, lambda r=remote, u=url: _show_update_popup(r, u))
                else:
                    logging.info(f"A verzió naprakész ({VERSION})")
                return
            except Exception as e:
                logging.warning(f"Szerver elérhetetlen ({url}): {e}")
        logging.info("Frissítés ellenőrzése sikertelen: egyetlen szerver sem érhető el")

    threading.Thread(target=_fetch, daemon=True).start()


def _show_update_popup(remote_version, server_url):
    zip_url = server_url.rsplit("/", 1)[0] + "/olvasomester.zip"
    dest = os.path.join(BASE_DIR, "olvasomester.zip")

    popup = tk.Toplevel(root)
    popup.title("Frissítés")
    popup.resizable(False, False)
    popup.attributes("-topmost", True)
    popup.configure(bg=TH_BG)

    w, h = 380, 160
    x = (popup.winfo_screenwidth() // 2) - w // 2
    y = (popup.winfo_screenheight() // 2) - h // 2
    popup.geometry(f"{w}x{h}+{x}+{y}")

    content = tk.Frame(popup, bg=TH_BG)
    content.pack(expand=True, fill="both", padx=24, pady=(20, 0))

    msg_lbl = tk.Label(
        content,
        text="Új verzió elérhető. Frissíted?",
        bg=TH_BG, fg=TH_FG, font=TH_FONT,
        wraplength=332, justify="center",
    )
    msg_lbl.pack()

    # Link label — csak sikeres letöltés után jelenik meg
    path_lbl = tk.Label(
        content, text="", bg=TH_BG, fg=TH_LINK,
        font=(*TH_FONT_SM[:2], "underline"), cursor="hand2",
        wraplength=332, justify="center",
    )

    btn_frame = tk.Frame(popup, bg=TH_BG)
    btn_frame.pack(pady=(12, 16))

    def _switch_to_close():
        """Eltávolítja az összes gombot és csak Bezárás marad."""
        for w in btn_frame.winfo_children():
            w.destroy()
        tk.Button(
            btn_frame, text="Bezárás", width=10, command=popup.destroy,
            bg=TH_BG2, fg=TH_FG, font=TH_FONT,
            relief="flat", activebackground=TH_BG2, activeforeground=TH_FG,
            cursor="hand2",
        ).pack()

    def _show_manual_link():
        msg_lbl.config(
            text="A letöltés nem sikerült.\nKérlek próbáld meg manuálisan frissíteni\naz alábbi linken keresztül:"
        )
        path_lbl.config(text=zip_url)
        path_lbl.pack(pady=(6, 0))
        path_lbl.bind("<Button-1>", lambda e: __import__("webbrowser").open(zip_url))
        _switch_to_close()

    def on_ok():
        ok_btn.config(state="disabled")
        cancel_btn.config(state="disabled")
        msg_lbl.config(text="Letöltés folyamatban...")

        def _download():
            try:
                logging.info(f"Frissítés letöltése: {zip_url} → {dest}")
                req = urllib.request.urlopen(zip_url, timeout=15)
                if req.status != 200:
                    raise ValueError(f"HTTP {req.status}")
                with open(dest, "wb") as f:
                    f.write(req.read())
                logging.info("Letöltés kész")

                def _on_success():
                    msg_lbl.config(text="Letöltés kész!")
                    path_lbl.config(text=dest)
                    path_lbl.pack(pady=(4, 0))
                    path_lbl.bind("<Button-1>", lambda e: subprocess.Popen(
                        ["explorer", "/select,", dest]
                    ))
                    _switch_to_close()

                root.after(0, _on_success)

            except urllib.error.HTTPError as e:
                code = e.code
                logging.error(f"Letöltési HTTP hiba: {code} {e.reason}")
                root.after(0, lambda c=code: (
                    msg_lbl.config(text=f"Hiba ({c}). Próbáld meg később."),
                    _switch_to_close(),
                ))
            except OSError as e:
                logging.error(f"Fájl írási hiba: {e}")
                root.after(0, _show_manual_link)
            except Exception as e:
                logging.error(f"Letöltési hiba: {e}")
                root.after(0, lambda: (
                    msg_lbl.config(text="Hiba. Próbáld meg később."),
                    _switch_to_close(),
                ))

        threading.Thread(target=_download, daemon=True).start()

    ok_btn = tk.Button(
        btn_frame, text="OK", width=10, command=on_ok,
        bg=TH_ACCENT, fg=TH_ACCENT_FG, font=TH_FONT,
        relief="flat", activebackground="#c85518", activeforeground=TH_ACCENT_FG,
        cursor="hand2",
    )
    ok_btn.pack(side="left", padx=8)

    cancel_btn = tk.Button(
        btn_frame, text="Mégse", width=10, command=popup.destroy,
        bg=TH_BG2, fg=TH_FG, font=TH_FONT,
        relief="flat", activebackground=TH_BG2, activeforeground=TH_FG,
        cursor="hand2",
    )
    cancel_btn.pack(side="left", padx=8)


def open_settings():
    logging.info("Beállítások ablak megnyitva")
    win = tk.Toplevel(root)
    win.title("Beállítások")
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.configure(bg=TH_BG)

    w, h = 400, 340
    x = (win.winfo_screenwidth() // 2) - w // 2
    y = (win.winfo_screenheight() // 2) - h // 2
    win.geometry(f"{w}x{h}+{x}+{y}")

    lbl_cfg = dict(bg=TH_BG, fg=TH_FG2, font=TH_FONT_SM, anchor="w")
    pad = {"padx": 24, "pady": (10, 0)}

    style = ttk.Style(win)
    style.theme_use("clam")
    style.configure("Accent.Horizontal.TScale",
        background=TH_ACCENT, troughcolor=TH_BG2,
        bordercolor=TH_BG, darkcolor=TH_BG2, lightcolor=TH_BG2,
    )
    style.map("Accent.Horizontal.TScale",
        background=[("active", TH_ACCENT), ("pressed", TH_ACCENT), ("!active", TH_ACCENT)],
    )
    style.configure("Dark.TCombobox",
        fieldbackground=TH_BG2, background=TH_BG2,
        foreground=TH_FG, selectbackground=TH_BG2,
        selectforeground=TH_FG, arrowcolor=TH_FG,
        bordercolor=TH_BG2, lightcolor=TH_BG2, darkcolor=TH_BG2,
    )
    style.map("Dark.TCombobox",
        fieldbackground=[("readonly", TH_BG2)],
        foreground=[("readonly", TH_FG)],
        selectbackground=[("readonly", TH_BG2)],
        selectforeground=[("readonly", TH_FG)],
    )

    def make_scale(parent, label, from_, to, reg_key, fmt, log_msg):
        row = tk.Frame(parent, bg=TH_BG)
        row.pack(fill="x", padx=24, pady=(10, 0))
        tk.Label(row, text=label, **lbl_cfg).pack(side="left")
        val_lbl = tk.Label(row, text=fmt(reg_get(reg_key, from_)), bg=TH_BG, fg=TH_ACCENT, font=TH_FONT_SM)
        val_lbl.pack(side="right")
        var = tk.DoubleVar(value=reg_get(reg_key, from_))
        def on_change(v):
            iv = int(float(v))
            reg_set(reg_key, iv)
            val_lbl.config(text=fmt(iv))
            logging.info(log_msg(iv))
        ttk.Scale(parent, from_=from_, to=to, orient="horizontal",
                  variable=var, command=on_change,
                  style="Accent.Horizontal.TScale",
        ).pack(fill="x", padx=24, pady=(2, 0))

    tk.Label(win, text="Beállítások", **dict(lbl_cfg, fg=TH_FG, font=TH_FONT_HEAD)).pack(
        anchor="w", padx=24, pady=(18, 8))

    make_scale(win, "Felolvasás sebessége (%):", 50, 200, "rate",
               lambda v: f"{v}%", lambda v: f"Sebesség: {v}%")

    tk.Label(win, text="Felolvasó hangja:", **lbl_cfg).pack(fill="x", **pad)
    voice_var = tk.StringVar(value=reg_get("voice", "Anna"))
    voice_combo = ttk.Combobox(
        win, textvariable=voice_var,
        values=list(PIPER_MODELS.keys()),
        state="readonly", width=22, style="Dark.TCombobox"
    )
    voice_combo.pack(anchor="w", padx=24, pady=(4, 0))

    def on_voice_change(e):
        reg_set("voice", voice_var.get())
        logging.info(f"Hang: {voice_var.get()}")

    voice_combo.bind("<<ComboboxSelected>>", on_voice_change)

    make_scale(win, "Automatikus ablakbezárás:", 0, 60, "auto_close",
               lambda v: f"{v} mp" if v > 0 else "ki", lambda v: f"Auto close: {v} mp")

    auto_update_var = tk.BooleanVar(value=bool(reg_get("auto_update", 0)))

    def on_auto_update_change():
        reg_set("auto_update", int(auto_update_var.get()))
        logging.info(f"Automatikus frissítés: {auto_update_var.get()}")

    tk.Checkbutton(
        win, text="Automatikus frissítés",
        variable=auto_update_var, anchor="w",
        command=on_auto_update_change,
        bg=TH_BG, fg=TH_FG2, selectcolor=TH_BG2,
        activebackground=TH_BG, activeforeground=TH_FG2,
        font=TH_FONT_SM, borderwidth=0,
    ).pack(fill="x", padx=24, pady=(10, 0))

    tk.Button(
        win, text="OK", command=win.destroy, width=10,
        bg=TH_ACCENT, fg=TH_ACCENT_FG, font=TH_FONT,
        relief="flat", activebackground="#c85518", activeforeground=TH_ACCENT_FG,
        cursor="hand2",
    ).pack(pady=(16, 18))


def open_about():
    about = tk.Toplevel(root)
    about.title("Névjegy")
    about.resizable(False, False)
    about.attributes("-topmost", True)
    about.configure(bg=TH_BG)

    w, h = 520, 490
    x = (about.winfo_screenwidth() // 2) - w // 2
    y = (about.winfo_screenheight() // 2) - h // 2
    about.geometry(f"{w}x{h}+{x}+{y}")

    tk.Label(
        about, text=f"OlvasóMester v{VERSION}",
        bg=TH_BG, fg=TH_ACCENT, font=TH_FONT_HEAD, anchor="w"
    ).pack(fill="x", padx=28, pady=(22, 0))

    tk.Frame(about, bg=TH_ACCENT, height=2).pack(fill="x", padx=28, pady=(4, 14))

    tk.Label(
        about,
        text=(
            "Ez az alkalmazás a vágólap tartalmát olvassa fel.\n\n"
            "A felolvasó ablak méretezhető, és a pozíciója elmentésre kerül.\n\n"
            "A tálca ikonra kattintva hozható elő a beállítások menü, ahol módosítható:\n"
            "  • a felolvasás sebessége\n"
            "  • a felolvasó hangja\n"
            "  • a felolvasás befejezése után mennyi ideig maradjon nyitva az ablak\n"
            "  •  keressen-e automatikusan frissítést\n\n"
            "Az aktuális felolvasás bármikor megszakítható a felolvasó ablak bezárásával."
        ),
        bg=TH_BG, fg=TH_FG, font=TH_FONT,
        justify="left", wraplength=464, anchor="w"
    ).pack(fill="x", padx=28, pady=(0, 12))

    tk.Frame(about, bg=TH_BG2, height=1).pack(fill="x", padx=28, pady=(0, 10))

    tk.Label(about, text=AUTHOR, bg=TH_BG, fg=TH_FG2, font=TH_FONT_SM, anchor="w").pack(fill="x", padx=28)
    tk.Label(about, text=BILD_DATE, bg=TH_BG, fg=TH_FG2, font=TH_FONT_SM, anchor="w").pack(fill="x", padx=28)

    mailto = f"mailto:{CONTACT}?subject=Kapcsolatfelvétel - OlvasóMester v{VERSION}"
    email_link = tk.Label(about, text=CONTACT, bg=TH_BG, fg=TH_LINK,
                          font=(*TH_FONT_SM[:2], "underline"), cursor="hand2", anchor="w")
    email_link.pack(fill="x", padx=28)
    email_link.bind("<Button-1>", lambda e: __import__("webbrowser").open(mailto))

    link = tk.Label(about, text=URL, bg=TH_BG, fg=TH_LINK,
                    font=(*TH_FONT_SM[:2], "underline"), cursor="hand2", anchor="w")
    link.pack(fill="x", padx=28)
    link.bind("<Button-1>", lambda e: __import__("webbrowser").open(URL))

    tk.Button(
        about, text="OK", command=about.destroy, width=10,
        bg=TH_ACCENT, fg=TH_ACCENT_FG, font=TH_FONT,
        relief="flat", activebackground="#c85518", activeforeground=TH_ACCENT_FG,
        cursor="hand2",
    ).pack(pady=(10, 10))


# ---------------- CLIPBOARD WATCHER ----------------
def watcher():
    global last_text
    while running:
        try:
            txt = pyperclip.paste()
        except:
            time.sleep(0.5)
            continue

        if txt != last_text and txt.strip():
            logging.info(f"Új vágólap szöveg: {len(txt)} karakter")
            last_text = txt
            root.after(0, show, txt)

        time.sleep(0.3)

def tray():
    icon_img = make_tray_icon()
    icon = pystray.Icon("OlvasóMester", icon_img, "OlvasóMester")
    icon.menu = pystray.Menu(
        pystray.MenuItem("Beállítások", lambda: root.after(0, open_settings)),
        pystray.MenuItem("Névjegy", lambda: root.after(0, open_about)),
        pystray.MenuItem("Kilépés", lambda: os._exit(0))
    )
    icon.run()


# ---------------- MAIN ----------------
if __name__ == "__main__":
    logging.info(f"OlvasóMester v{VERSION} indul...")
    reg_set("version", VERSION)
    if reg_get("firstrun", 0) != 1:
        reg_set("auto_update", 1)
        reg_set("rate", 100)
        root.after(0, open_about)
        root.after(0, open_settings)

        reg_set("firstrun", 1)

    check_updates()

    logging.info(f"BASE_DIR: {BASE_DIR}")
    logging.info(f"PIPER_EXE: {PIPER_EXE}")
    logging.info(f"PIPER_MODEL_DIR: {PIPER_MODEL_DIR}")

    threading.Thread(target=watcher, daemon=True).start()
    threading.Thread(target=tray, daemon=True).start()

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass