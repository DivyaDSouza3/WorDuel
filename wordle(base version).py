import tkinter as tk
from tkinter import messagebox
import random
import base64
import urllib.parse
import urllib.request
import ssl
import os

# Try to import pillow (preferred). If not available, we'll fallback.
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

MAX_ATTEMPTS = 6

THEME = {
    "bg": "#f4f1ff",
    "muted": "#6b6480",
    "primary": "#b9a6ff",
    "yellow": "#fff0b8",
    "green": "#b8e8c8",
    "grey": "#d6d6e5"
}


WORDS_BY_LENGTH = {
    3: ["cat", "dog", "sun", "car", "map", "bag", "hot", "cup", "key", "ice", "pen", "jam", "egg", "owl", "fox"],
    4: ["moon", "book", "code", "play", "fish", "tree", "lamp", "road", "star", "home", "milk", "cake", "ship", "rain"],
    5: ["apple", "house", "light", "plant", "table", "chair", "spark", "brand", "until", "ghost", "brown", "water", "mouse", "heart"],
    6: ["planet", "garden", "silver", "random", "buffer", "friend", "castle", "bridge", "flight"],
    7: ["marbles", "monster", "picture", "charger", "balance", "battery", "journey", "vintage"],
}

DEFAULT_WORDLIST_URL = "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt"

def load_valid_words(local_path="wordlist.txt", fallback_url=DEFAULT_WORDLIST_URL):
    words = set()
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                for line in f:
                    w = line.strip().lower()
                    if w:
                        words.add(w)
            if words:
                return words
        except Exception:
            pass
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(fallback_url, context=ctx, timeout=10) as resp:
            for raw in resp:
                try:
                    w = raw.decode("utf-8").strip().lower()
                except Exception:
                    continue
                if w:
                    words.add(w)
        if words:
            try:
                with open(local_path, "w", encoding="utf-8") as f:
                    for w in sorted(words):
                        f.write(w + "\n")
            except Exception:
                pass
            return words
    except Exception:
        pass
    return words

VALID_WORDS = load_valid_words()

class DuelLinkFlow:
    @staticmethod
    def create_initial_link(word_length, secretA):
        payload = f"{word_length}:{secretA}"
        code = DuelLinkFlow._b64_encode(payload)
        return f"friendwordle://load?w={urllib.parse.quote(code)}"

    @staticmethod
    def decode_initial_link(link_text):
        if "w=" in link_text:
            parsed = urllib.parse.urlparse(link_text)
            q = urllib.parse.parse_qs(parsed.query)
            if "w" in q:
                b64 = q["w"][0]
            else:
                idx = link_text.find("w=")
                b64 = link_text[idx + 2:]
        else:
            b64 = link_text
        decoded = DuelLinkFlow._b64_decode(b64)
        if ":" not in decoded:
            raise ValueError("Malformed initial payload")
        length_s, secret = decoded.split(":", 1)
        return int(length_s), secret

    @staticmethod
    def create_return_link(word_length, secretB, attempts_taken, guessed_bool):
        g = "1" if guessed_bool else "0"
        payload = f"ret:{word_length}:{secretB}:{attempts_taken}:{g}"
        code = DuelLinkFlow._b64_encode(payload)
        return f"friendwordle://ret?w={urllib.parse.quote(code)}"

    @staticmethod
    def decode_return_link(link_text):
        if "w=" in link_text:
            parsed = urllib.parse.urlparse(link_text)
            q = urllib.parse.parse_qs(parsed.query)
            if "w" in q:
                b64 = q["w"][0]
            else:
                idx = link_text.find("w=")
                b64 = link_text[idx + 2:]
        else:
            b64 = link_text
        decoded = DuelLinkFlow._b64_decode(b64)
        if not decoded.startswith("ret:"):
            raise ValueError("Not a return payload")
        parts = decoded.split(":", 4)
        if len(parts) != 5:
            raise ValueError("Malformed return payload")
        _, length_s, secretB, attempts_s, guessed_flag = parts
        return int(length_s), secretB, int(attempts_s), guessed_flag == "1"

    @staticmethod
    def _b64_encode(s: str) -> str:
        b = s.encode("utf-8")
        return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")

    @staticmethod
    def _b64_decode(s: str) -> str:
        padding = "=" * (-len(s) % 4)
        raw = base64.urlsafe_b64decode((s + padding).encode("ascii"))
        return raw.decode("utf-8")

class WordleEngine:
    @staticmethod
    def check_guess(guess: str, secret: str):
        n = len(secret)
        result = ["grey"] * n
        counts = {}
        for i in range(n):
            if guess[i] == secret[i]:
                result[i] = "green"
            else:
                counts[secret[i]] = counts.get(secret[i], 0) + 1
        for i in range(n):
            if result[i] == "green":
                continue
            g = guess[i]
            if counts.get(g, 0) > 0:
                result[i] = "yellow"
                counts[g] -= 1
        return result

class SingleGameWindow:
    def __init__(self, master, secret_word, word_length, title="WorDuel — Single", on_finish=None, show_header=True):
        self.master = master
        self.secret = secret_word.lower()
        self.word_length = word_length
        self.attempt = 0
        self.attempts_used = None
        self.on_finish = on_finish
        self.guessed = False
        self.key_buttons = {}

        self.win = tk.Toplevel(master)
        self.win.title(title)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self.win.configure(bg=THEME["bg"])
        self.win.geometry("900x650")
        self.win.minsize(700,500)

        if show_header:
            tk.Label(self.win, text=f"Guess a {word_length}-letter word", bg=THEME["bg"], fg=THEME["muted"],
                     font=("Helvetica", 14, "bold")).pack(pady=(8, 4))

        self.grid_frame = tk.Frame(self.win, bg=THEME["bg"])
        self.grid_frame.pack(padx=8, pady=8)

        self.cells = []
        for r in range(MAX_ATTEMPTS):
            row = []
            for c in range(word_length):
                lbl = tk.Label(self.grid_frame, text="", width=3, height=1,
                               bg="white", relief="solid", bd=1, font=("Helvetica", 16, "bold"))
                lbl.grid(row=r, column=c, padx=4, pady=4, ipadx=8, ipady=8)
                row.append(lbl)
            self.cells.append(row)

        entry_frame = tk.Frame(self.win, bg=THEME["bg"])
        entry_frame.pack(pady=(6, 8))
        tk.Label(entry_frame, text="Your guess:", bg=THEME["bg"], fg=THEME["muted"]).grid(row=0, column=0, padx=(0, 8))
        self.guess_var = tk.StringVar()
        self.guess_entry = tk.Entry(entry_frame, textvariable=self.guess_var, width=24, font=("Helvetica", 14))
        self.guess_entry.grid(row=0, column=1, padx=(0, 8))
        self.guess_entry.bind("<Return>", lambda e: self.submit_guess())
        self.submit_btn = tk.Button(entry_frame, text="Submit", command=self.submit_guess, bg=THEME["primary"], fg="white")
        self.submit_btn.grid(row=0, column=2)

        self._build_keyboard()
        tk.Label(self.win, text="Colors: green=correct pos, yellow=present, grey=absent",
                 bg=THEME["bg"], fg=THEME["muted"]).pack(pady=(4, 4))
        self.status_lbl = tk.Label(self.win, text=f"Attempts left: {MAX_ATTEMPTS - self.attempt}", bg=THEME["bg"], fg=THEME["muted"])
        self.status_lbl.pack(pady=(0, 8))

        self.enable(True)
        self.win.lift()
        self.guess_entry.focus_set()

    def _build_keyboard(self):
        keyboard_frame = tk.Frame(self.win, bg=THEME["bg"])
        keyboard_frame.pack(pady=(6, 8))
        rows = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
        for r in rows:
            rframe = tk.Frame(keyboard_frame, bg=THEME["bg"])
            rframe.pack(pady=3)
            for ch in r:
                btn = tk.Button(rframe, text=ch, width=3, height=1, command=lambda c=ch: self._on_key_click(c))
                btn.pack(side="left", padx=3)
                self.key_buttons[ch.lower()] = btn
        bottom = tk.Frame(keyboard_frame, bg=THEME["bg"])
        bottom.pack(pady=3)
        back_btn = tk.Button(bottom, text="⟵", width=6, command=self._on_backspace)
        back_btn.pack(side="left", padx=3)
        enter_btn = tk.Button(bottom, text="Enter", width=8, command=self.submit_guess)
        enter_btn.pack(side="left", padx=3)

    def _on_key_click(self, ch):
        cur = self.guess_var.get()
        if len(cur) < self.word_length:
            self.guess_var.set(cur + ch.lower())
            self.guess_entry.icursor(tk.END)

    def _on_backspace(self):
        cur = self.guess_var.get()
        self.guess_var.set(cur[:-1])
        self.guess_entry.icursor(tk.END)

    def _shake_row(self, row_widgets):
        base_pads = []
        for lbl in row_widgets:
            info = lbl.grid_info()
            base = info.get('padx', 4)
            try:
                base = int(base)
            except Exception:
                base = 4
            base_pads.append(base)
        seq = [0, 6, -6, 4, -4, 0]
        def step(i=0):
            if i >= len(seq):
                for lbl, bp in zip(row_widgets, base_pads):
                    lbl.grid_configure(padx=bp)
                return
            off = seq[i]
            for j, lbl in enumerate(row_widgets):
                newpad = max(0, base_pads[j] + off)
                lbl.grid_configure(padx=newpad)
            self.win.after(40, lambda: step(i+1))
        step(0)

    def submit_guess(self):
        guess = self.guess_var.get().strip().lower()
        if len(guess) != self.word_length or not guess.isalpha():
            if self.attempt < MAX_ATTEMPTS:
                self._shake_row(self.cells[self.attempt])
            return
        if VALID_WORDS and guess not in VALID_WORDS:
            if self.attempt < MAX_ATTEMPTS:
                self._shake_row(self.cells[self.attempt])
            return
        colors = WordleEngine.check_guess(guess, self.secret)
        row_labels = self.cells[self.attempt]
        for i, ch in enumerate(guess):
            row_labels[i].config(text=ch.upper())
            if colors[i] == "green":
                row_labels[i].config(bg=THEME["green"])
            elif colors[i] == "yellow":
                row_labels[i].config(bg=THEME["yellow"])
            else:
                row_labels[i].config(bg=THEME["grey"])
        self._update_keyboard(colors, guess)
        self.attempt += 1
        self.status_lbl.config(text=f"Attempts left: {MAX_ATTEMPTS - self.attempt}")
        self.guess_var.set("")
        if guess == self.secret:
            self.guessed = True
            self.attempts_used = self.attempt
            messagebox.showinfo("Solved", f"You guessed the word in {self.attempts_used} attempts.")
            self.finish()
            return
        if self.attempt >= MAX_ATTEMPTS:
            self.guessed = False
            self.attempts_used = MAX_ATTEMPTS + 1
            messagebox.showinfo("Game over", f"No attempts left. The word was: {self.secret}")
            self.finish()

    def _update_keyboard(self, colors, guess):
        def rank(col):
            return {"green": 3, "yellow": 2, "grey": 1}.get(col, 0)
        for c, col in zip(guess, colors):
            btn = self.key_buttons.get(c)
            if not btn:
                continue
            current_bg = btn.cget("bg")
            cur_rank = 0
            if current_bg == THEME["green"]:
                cur_rank = 3
            elif current_bg == THEME["yellow"]:
                cur_rank = 2
            elif current_bg == THEME["grey"]:
                cur_rank = 1
            new_rank = rank(col)
            if new_rank > cur_rank:
                btn.config(bg=THEME["green"] if col == "green" else THEME["yellow"] if col == "yellow" else THEME["grey"])

    def enable(self, flag: bool):
        state = "normal" if flag else "disabled"
        try:
            self.guess_entry.config(state=state)
            self.submit_btn.config(state=state)
        except Exception:
            pass
        for btn in self.key_buttons.values():
            try:
                btn.config(state=state)
            except Exception:
                pass

    def finish(self):
        if self.on_finish:
            self.on_finish(self.attempts_used, self.guessed)

    def _on_close(self):
        if self.attempts_used is None:
            self.attempts_used = MAX_ATTEMPTS + 1
            self.guessed = False
            if self.on_finish:
                self.on_finish(self.attempts_used, self.guessed)
        self.win.destroy()

class PlayerPanel(tk.Frame):
    def __init__(self, parent, player_id, title, word_length, secret_word, on_finish, on_guess):
        super().__init__(parent, bg=THEME["bg"])
        self.player_id = player_id
        self.title = title
        self.word_length = word_length
        self.secret = secret_word.lower()
        self.on_finish = on_finish
        self.on_guess = on_guess
        self.attempt = 0
        self.attempts_used = None
        self.guessed = False
        self.key_buttons = {}

        tk.Label(self, text=title, font=("Helvetica", 14, "bold"), bg=THEME["bg"]).pack(pady=(8, 4))
        grid = tk.Frame(self, bg=THEME["bg"])
        grid.pack()
        self.cells = []
        for r in range(MAX_ATTEMPTS):
            row = []
            for c in range(word_length):
                lbl = tk.Label(grid, text="", width=3, height=1, bg="white", relief="solid", bd=1, font=("Helvetica", 14, "bold"))
                lbl.grid(row=r, column=c, padx=4, pady=4, ipadx=6, ipady=6)
                row.append(lbl)
            self.cells.append(row)

        inp = tk.Frame(self, bg=THEME["bg"])
        inp.pack(pady=(6, 6))
        tk.Label(inp, text="Guess:", bg=THEME["bg"]).grid(row=0, column=0, padx=(0,8))
        self.guess_var = tk.StringVar()
        self.guess_entry = tk.Entry(inp, textvariable=self.guess_var, width=18)
        self.guess_entry.grid(row=0, column=1, padx=(0,8))
        self.guess_entry.bind("<Return>", lambda e: self.submit_guess())
        self.submit_btn = tk.Button(inp, text="Submit", command=self.submit_guess, bg=THEME["primary"], fg="white")
        self.submit_btn.grid(row=0, column=2)

        kb_frame = tk.Frame(self, bg=THEME["bg"])
        kb_frame.pack(pady=(6, 6))
        rows = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
        for r in rows:
            rframe = tk.Frame(kb_frame, bg=THEME["bg"])
            rframe.pack(pady=2)
            for ch in r:
                b = tk.Button(rframe, text=ch, width=3, command=lambda c=ch: self._on_key(c))
                b.pack(side="left", padx=2)
                self.key_buttons[ch.lower()] = b
        bot = tk.Frame(kb_frame, bg=THEME["bg"])
        bot.pack(pady=2)
        tk.Button(bot, text="⌫", width=6, command=self._backspace).pack(side="left", padx=4)
        tk.Button(bot, text="Enter", width=8, command=self.submit_guess).pack(side="left", padx=4)

        self.status_lbl = tk.Label(self, text=f"Attempts left: {MAX_ATTEMPTS - self.attempt}", bg=THEME["bg"])
        self.status_lbl.pack(pady=(6, 4))

    def _on_key(self, ch):
        cur = self.guess_var.get()
        if len(cur) < self.word_length:
            self.guess_var.set(cur + ch.lower())
            self.guess_entry.icursor(tk.END)

    def _backspace(self):
        cur = self.guess_var.get()
        self.guess_var.set(cur[:-1])
        self.guess_entry.icursor(tk.END)

    def _shake_row(self, row_widgets):
        base_pads = []
        for lbl in row_widgets:
            info = lbl.grid_info()
            base = info.get('padx', 4)
            try:
                base = int(base)
            except Exception:
                base = 4
            base_pads.append(base)
        seq = [0, 6, -6, 4, -4, 0]
        def step(i=0):
            if i >= len(seq):
                for lbl, bp in zip(row_widgets, base_pads):
                    lbl.grid_configure(padx=bp)
                return
            off = seq[i]
            for j, lbl in enumerate(row_widgets):
                newpad = max(0, base_pads[j] + off)
                lbl.grid_configure(padx=newpad)
            self.after(40, lambda: step(i+1))
        step(0)

    def submit_guess(self):
        guess = self.guess_var.get().strip().lower()
        if len(guess) != self.word_length or not guess.isalpha():
            if self.attempt < MAX_ATTEMPTS:
                self._shake_row(self.cells[self.attempt])
            return
        if VALID_WORDS and guess not in VALID_WORDS:
            if self.attempt < MAX_ATTEMPTS:
                self._shake_row(self.cells[self.attempt])
            return
        colors = WordleEngine.check_guess(guess, self.secret)
        row_labels = self.cells[self.attempt]
        for i, ch in enumerate(guess):
            row_labels[i].config(text=ch.upper())
            if colors[i] == "green":
                row_labels[i].config(bg=THEME["green"])
            elif colors[i] == "yellow":
                row_labels[i].config(bg=THEME["yellow"])
            else:
                row_labels[i].config(bg=THEME["grey"])
        self._update_keyboard(colors, guess)
        self.attempt += 1
        self.status_lbl.config(text=f"Attempts left: {MAX_ATTEMPTS - self.attempt}")
        self.guess_var.set("")
        if self.on_guess:
            self.on_guess(self.player_id)
        if guess == self.secret:
            self.guessed = True
            self.attempts_used = self.attempt
            messagebox.showinfo("Solved", f"{self.title} guessed the word in {self.attempts_used} attempts.")
            self.finish()
            return
        if self.attempt >= MAX_ATTEMPTS:
            self.guessed = False
            self.attempts_used = MAX_ATTEMPTS + 1
            messagebox.showinfo("No attempts left", f"{self.title} did not guess the word. The secret was: {self.secret}")
            self.finish()

    def _update_keyboard(self, colors, guess):
        def rank(col):
            return {"green": 3, "yellow": 2, "grey": 1}.get(col, 0)
        for c, col in zip(guess, colors):
            btn = self.key_buttons.get(c)
            if not btn:
                continue
            cur_bg = btn.cget("bg")
            cur_rank = 0
            if cur_bg == THEME["green"]:
                cur_rank = 3
            elif cur_bg == THEME["yellow"]:
                cur_rank = 2
            elif cur_bg == THEME["grey"]:
                cur_rank = 1
            new_rank = rank(col)
            if new_rank > cur_rank:
                btn.config(bg=THEME["green"] if col == "green" else THEME["yellow"] if col == "yellow" else THEME["grey"])

    def enable(self, flag: bool):
        state = "normal" if flag else "disabled"
        try:
            self.guess_entry.config(state=state)
            self.submit_btn.config(state=state)
        except Exception:
            pass
        for b in self.key_buttons.values():
            try:
                b.config(state=state)
            except Exception:
                pass

    def finish(self):
        if self.attempts_used is None:
            self.attempts_used = MAX_ATTEMPTS + 1
            self.guessed = False
        if self.on_finish:
            self.on_finish(self.player_id, self.attempts_used, self.guessed)

# -------------------------
# Asset scanning & helpers (case-insensitive keys)
# -------------------------
ASSETS_DIR = "assets"
DISPLAY_SIZE = 160  # working size for composed images

def find_layer_files():
    candidates = []
    places = [os.getcwd()]
    if os.path.isdir(ASSETS_DIR):
        places.append(os.path.join(os.getcwd(), ASSETS_DIR))
    for p in places:
        try:
            for fn in os.listdir(p):
                if fn.lower().endswith(".png"):
                    candidates.append(os.path.join(p, fn))
        except Exception:
            pass

    bases = {}
    exprs = {}
    outfits = {}
    for full in candidates:
        fn = os.path.basename(full)
        lfn = fn.lower()
        if lfn.startswith("base_"):
            key = fn[len("base_"):].rsplit(".", 1)[0].lower()
            bases[key] = full
        elif lfn.startswith("expr_"):
            key = fn[len("expr_"):].rsplit(".", 1)[0].lower()
            exprs[key] = full
        elif lfn.startswith("outfit_"):
            key = fn[len("outfit_"):].rsplit(".", 1)[0].lower()
            outfits[key] = full
    return bases, exprs, outfits

def load_and_prepare_image(path, target_size=DISPLAY_SIZE):
    if not PIL_AVAILABLE or not path:
        return None
    try:
        im = Image.open(path).convert("RGBA")
        if im.width != target_size or im.height != target_size:
            im = im.resize((target_size, target_size), resample=Image.NEAREST)
        return im
    except Exception:
        return None

def compose_layers(base_im, outfit_im, expr_im):
    if not PIL_AVAILABLE:
        return None
    size = None
    for im in (base_im, outfit_im, expr_im):
        if im is not None:
            size = im.size
            break
    if size is None:
        return None
    out = Image.new("RGBA", size, (0,0,0,0))
    # Order: base -> outfit -> expr
    if base_im is not None:
        out = Image.alpha_composite(out, base_im)
    if outfit_im is not None:
        out = Image.alpha_composite(out, outfit_im)
    if expr_im is not None:
        out = Image.alpha_composite(out, expr_im)
    return out

# -------------------------
# Inline creator: username centered; toggles + preview first; base thumbnails AND Create/Cancel moved beneath toggles/preview
# -------------------------
class InlinePopupCharacterCreator:
    def __init__(self, parent_frame, on_done):
        self.parent = parent_frame
        self.on_done = on_done

        # find assets with lowercase keys
        self.available_bases, self.available_exprs, self.available_outfits = find_layer_files()

        # state (use lowercase keys)
        self.username_var = tk.StringVar(value="Player")
        self.color_key = next(iter(self.available_bases.keys()), "default")
        self.expr_key = next(iter(self.available_exprs.keys()), "smile")
        self.outfit_key = next(iter(self.available_outfits.keys()), "casual")

        # which category is currently active for arrow cycling: "base"/"expr"/"outfit"
        self.active_category = "base"

        # caches
        self.pil_cache = {}
        self.tk_cache = {}

        # popup as centered card
        self.popup = tk.Frame(self.parent, bg="white", bd=2, relief="ridge")
        w = 660
        h = 460
        self.popup.place(relx=0.5, rely=0.5, anchor="center", width=w, height=h)

        header = tk.Label(self.popup, text="Customize Character", bg="white", fg=THEME["muted"], font=("Helvetica", 16, "bold"))
        header.pack(pady=(8,6))

        # central vertical layout
        content = tk.Frame(self.popup, bg="white")
        content.pack(fill="both", expand=True, padx=16, pady=6)

        # Username centered
        uname_frame = tk.Frame(content, bg="white")
        uname_frame.pack(pady=(4, 8))
        tk.Label(uname_frame, text="Username:", bg="white").pack(side="left", padx=(0,6))
        tk.Entry(uname_frame, textvariable=self.username_var, width=26).pack(side="left")

        # Preview area (toggles + preview + arrows)
        preview_card = tk.Frame(content, bg="white")
        preview_card.pack(pady=(6,6))

        # category toggles centered
        toggles = tk.Frame(preview_card, bg="white")
        toggles.pack(pady=(0,6))
        self.toggle_buttons = {}
        for cat in ("base", "expr", "outfit"):
            b = tk.Button(toggles, text=cat.capitalize(), width=8,
                          command=lambda c=cat: self._set_active_category(c))
            b.pack(side="left", padx=4)
            self.toggle_buttons[cat] = b
        self._highlight_active_toggle()

        # preview with arrows
        pv = tk.Frame(preview_card, bg="white")
        pv.pack()
        left_arrow = tk.Button(pv, text="<", width=3, command=lambda: self._cycle_active(-1))
        left_arrow.grid(row=0, column=0, padx=(8,6), pady=6)
        self.preview_w = 220
        self.preview_h = 220
        if PIL_AVAILABLE and (self.available_bases or self.available_exprs or self.available_outfits):
            self.preview_label_img = tk.Label(pv, bg="white")
            self.preview_label_img.grid(row=0, column=1)
        else:
            self.preview_canvas = tk.Canvas(pv, width=self.preview_w, height=self.preview_h, bg="#1e3a8a", highlightthickness=0)
            self.preview_canvas.grid(row=0, column=1)
        right_arrow = tk.Button(pv, text=">", width=3, command=lambda: self._cycle_active(1))
        right_arrow.grid(row=0, column=2, padx=(6,8), pady=6)

        # active label under preview (compact)
        self.active_label = tk.Label(preview_card, text=self._active_label_text(), bg="white")
        self.active_label.pack(pady=(6,0))

        # --- Now: base thumbnails AND action buttons moved underneath preview/toggles ---
        thumbs_and_actions = tk.Frame(content, bg="white")
        thumbs_and_actions.pack(pady=(8,4))

        # base thumbnails centered under preview
        self.base_thumb_container = tk.Frame(thumbs_and_actions, bg="white")
        self.base_thumb_container.pack(pady=(0,8))

        # action buttons (Create / Cancel) placed underneath outfit/expression options as requested
        action_row = tk.Frame(thumbs_and_actions, bg="white")
        action_row.pack(pady=(4,0))
        tk.Button(action_row, text="Create and Continue", bg=THEME["primary"], fg="white", command=self._submit).pack(side="left", padx=8)
        tk.Button(action_row, text="Cancel", command=self._cancel).pack(side="left", padx=8)

        # populate base thumbnails and initial draw
        self._populate_base_thumbnails()
        self._redraw_preview()

    def _populate_base_thumbnails(self):
        # only populate base thumbnails centered under preview
        for w in self.base_thumb_container.winfo_children():
            w.destroy()

        def make_thumb(frame, key, path):
            key_l = key.lower()
            if PIL_AVAILABLE and path:
                pil_img = load_and_prepare_image(path, target_size=64)
                if pil_img is not None:
                    tkimg = ImageTk.PhotoImage(pil_img)
                    self.tk_cache[("base", key_l)] = tkimg
                    btn = tk.Button(frame, image=tkimg, bd=1, relief="solid",
                                    command=lambda k=key_l: self._on_base_selected(k))
                    btn.pack(side="left", padx=6, pady=2)
                    return
            # fallback to text button
            btn = tk.Button(frame, text=key.capitalize(), command=lambda k=key.lower(): self._on_base_selected(k))
            btn.pack(side="left", padx=6, pady=2)

        if self.available_bases:
            for key, path in sorted(self.available_bases.items()):
                make_thumb(self.base_thumb_container, key, path)
        else:
            for key in ("amber", "blue"):
                make_thumb(self.base_thumb_container, key, None)

    def _on_base_selected(self, key):
        self.color_key = key.lower()
        self.active_category = "base"
        self._highlight_active_toggle()
        self._redraw_preview()

    def _get_list_for_category(self, cat):
        if cat == "base":
            return list(self.available_bases.keys()) if self.available_bases else ["amber", "blue"]
        if cat == "expr":
            return list(self.available_exprs.keys()) if self.available_exprs else ["smile", "wink"]
        return list(self.available_outfits.keys()) if self.available_outfits else ["casual", "armor"]

    def _set_active_category(self, cat):
        self.active_category = cat
        self._highlight_active_toggle()
        self.active_label.config(text=self._active_label_text())

    def _highlight_active_toggle(self):
        for c, b in self.toggle_buttons.items():
            if c == self.active_category:
                b.config(relief="sunken", bg=THEME["primary"], fg="white")
            else:
                b.config(relief="raised", bg="white", fg="black")

    def _cycle_active(self, delta):
        lst = self._get_list_for_category(self.active_category)
        if not lst:
            return
        cur = getattr(self, f"{self.active_category}_key", None)
        cur = (cur or "").lower()
        try:
            i = lst.index(cur)
        except ValueError:
            i = 0
        i = (i + delta) % len(lst)
        new = lst[i]
        if self.active_category == "base":
            self.color_key = new
        elif self.active_category == "expr":
            self.expr_key = new
        else:
            self.outfit_key = new
        self._redraw_preview()

    def _active_label_text(self):
        if self.active_category == "base":
            return f"Base: {self.color_key}"
        if self.active_category == "expr":
            return f"Expr: {self.expr_key}"
        return f"Outfit: {self.outfit_key}"

    def _submit(self):
        name = self.username_var.get().strip()
        if not name:
            messagebox.showerror("Invalid", "Please enter a username.")
            return
        profile = {
            "username": name,
            "base": self.color_key,
            "expression": self.expr_key,
            "outfit": self.outfit_key
        }
        self.destroy()
        if callable(self.on_done):
            profile = {k: (v.lower() if isinstance(v, str) else v) for k, v in profile.items()}
            self.on_done(profile)

    def _cancel(self):
        profile = {
            "username": self.username_var.get().strip() or "Player",
            "base": self.color_key,
            "expression": self.expr_key,
            "outfit": self.outfit_key
        }
        self.destroy()
        if callable(self.on_done):
            profile = {k: (v.lower() if isinstance(v, str) else v) for k, v in profile.items()}
            self.on_done(profile)

    def destroy(self):
        try:
            self.popup.destroy()
        except Exception:
            pass

    def _redraw_preview(self):
        self.active_label.config(text=self._active_label_text())

        if PIL_AVAILABLE and (self.available_bases or self.available_exprs or self.available_outfits):
            base_path = self.available_bases.get(self.color_key)
            expr_path = self.available_exprs.get(self.expr_key)
            outfit_path = self.available_outfits.get(self.outfit_key)

            base_im = load_and_prepare_image(base_path, target_size=DISPLAY_SIZE) if base_path else None
            expr_im = load_and_prepare_image(expr_path, target_size=DISPLAY_SIZE) if expr_path else None
            outfit_im = load_and_prepare_image(outfit_path, target_size=DISPLAY_SIZE) if outfit_path else None

            composed = compose_layers(base_im, outfit_im, expr_im)
            if composed is not None:
                preview_small = composed.resize((self.preview_w, self.preview_h), resample=Image.NEAREST)
                tkimg = ImageTk.PhotoImage(preview_small)
                self.tk_cache[("composed_preview",)] = tkimg
                if hasattr(self, "preview_label_img"):
                    self.preview_label_img.config(image=tkimg)
                elif hasattr(self, "preview_canvas"):
                    # fallback: place image on label if canvas existed
                    self.preview_label_img = tk.Label(self.popup, image=tkimg, bg="white")
                    self.preview_label_img.image = tkimg
                return

        # fallback canvas draw
        if hasattr(self, "preview_canvas"):
            c = self.preview_canvas
            c.delete("all")
            c.create_rectangle(0,0,self.preview_w,self.preview_h, fill="#1e3a8a", outline="")
            c.create_oval(40,20,180,180, fill="#ffd27f", outline="#000", width=3)
            c.create_rectangle(60,130,160,200, fill="#2b6cb0", outline="#123")
            if self.expr_key and "wink" in self.expr_key:
                c.create_line(80,70,100,70, fill="#0f172a", width=4)
            else:
                c.create_rectangle(90,70,100,82, fill="#0f172a", outline="")
                c.create_rectangle(130,70,140,82, fill="#0f172a", outline="")

# -------------------------
# Main application with avatar display
# -------------------------
class MainApp:
    def __init__(self, root, profile=None):
        self.root = root
        self.profile = profile or {}
        self.root.title("WorDuel")
        try:
            root.state('zoomed')
        except Exception:
            pass

        self.frame = tk.Frame(root, bg=THEME["bg"])
        self.frame.pack(fill="both", expand=True)

        header = tk.Frame(self.frame, bg=THEME["bg"])
        header.pack(pady=(12, 8))
        tk.Label(header, text="WorDuel", bg=THEME["bg"], fg=THEME["muted"], font=("Helvetica", 28, "bold")).pack()

        icons_frame = tk.Frame(self.frame, bg=THEME["bg"])
        icons_frame.pack(pady=(10, 10))
        tk.Button(icons_frame, text="🎯\nStandard", font=("Helvetica", 14), width=12, height=4, command=self.start_standard_flow, bg="white").grid(row=0, column=0, padx=12)
        tk.Button(icons_frame, text="⚔️\nDuel", font=("Helvetica", 14), width=12, height=4, command=self.open_duel_options, bg="white").grid(row=0, column=1, padx=12)

        self.center_frame = tk.Frame(self.frame, bg=THEME["bg"])
        self.center_frame.pack(fill="both", expand=True, padx=12, pady=12)
        tk.Label(self.center_frame, text="Choose a mode above or paste a duel link below and press Join.", bg=THEME["bg"], fg=THEME["muted"]).pack()

        bottom = tk.Frame(self.frame, bg=THEME["bg"])
        bottom.pack(side="bottom", fill="x", pady=8)
        tk.Label(bottom, text="Join / Load link:", bg=THEME["bg"], fg=THEME["muted"]).pack(side="left", padx=(8,4))
        self.link_entry = tk.Entry(bottom, width=70)
        self.link_entry.pack(side="left", padx=(0,8))
        tk.Button(bottom, text="Join", command=self._join_from_box, bg=THEME["primary"], fg="white").pack(side="left", padx=(0,8))

        self.waiting_for_return = False
        self.my_initial_secret = None
        self.my_length = None

        # keep reference for avatar to avoid GC
        self._main_avatar_tk = None

        # show creator popup inline in the same window before the main menu
        self.show_character_creator_popup()

    def show_character_creator_popup(self):
        InlinePopupCharacterCreator(self.center_frame, on_done=self.on_profile_created)

    def on_profile_created(self, profile):
        if profile is None:
            profile = {}
        # unify keys to lowercase names used by loader
        newprof = {
            "username": profile.get("username", profile.get("name", "Player")),
            "color": profile.get("base", profile.get("color", "")).lower() if isinstance(profile.get("base", ""), str) else "",
            "expression": profile.get("expression", profile.get("expr", "")).lower() if isinstance(profile.get("expression", ""), str) else "",
            "outfit": profile.get("outfit", profile.get("outfit", "")).lower() if isinstance(profile.get("outfit", ""), str) else ""
        }
        self.profile = newprof
        self.setup_main_menu()

    def start_standard_flow(self):
        for w in self.center_frame.winfo_children(): w.destroy()
        tk.Label(self.center_frame, text="Standard — pick word length:", bg=THEME["bg"], fg=THEME["muted"]).pack(pady=8)
        len_var = tk.IntVar(value=5)
        tk.Spinbox(self.center_frame, from_=3, to=7, textvariable=len_var, width=5).pack(pady=8)
        tk.Button(self.center_frame, text="Start Standard Game", command=lambda: self._start_standard(len_var.get()), bg=THEME["primary"], fg="white").pack(pady=8)

    def _start_standard(self, length):
        if length not in WORDS_BY_LENGTH:
            messagebox.showerror("Invalid", "Choose between 3 and 7.")
            return
        secret = random.choice(WORDS_BY_LENGTH[length])
        SingleGameWindow(self.root, secret_word=secret, word_length=length, title="WorDuel — Single")

    def open_duel_options(self):
        for w in self.center_frame.winfo_children(): w.destroy()
        tk.Label(self.center_frame, text="Duel — Choose mode:", bg=THEME["bg"], fg=THEME["muted"]).pack(pady=8)
        tk.Button(self.center_frame, text="Same Device (both on this computer)", width=40, command=self.duel_same_device_setup).pack(pady=6)
        tk.Button(self.center_frame, text="Share Link (send link to friend)", width=40, command=self.duel_share_link_setup).pack(pady=6)

    def duel_same_device_setup(self):
        for w in self.center_frame.winfo_children(): w.destroy()
        tk.Label(self.center_frame, text="Same-device duel — enter both players' length & secret (inline)", bg=THEME["bg"], fg=THEME["muted"]).pack(pady=8)

        p1_frame = tk.Frame(self.center_frame, bg=THEME["bg"])
        p1_frame.pack(pady=6)
        tk.Label(p1_frame, text="Player 1 length:", bg=THEME["bg"]).grid(row=0, column=0, padx=6)
        p1_len = tk.IntVar(value=5)
        tk.Spinbox(p1_frame, from_=3, to=7, textvariable=p1_len, width=5).grid(row=0, column=1, padx=6)
        tk.Label(p1_frame, text="Player 1 secret:", bg=THEME["bg"]).grid(row=1, column=0, padx=6)
        p1_word_var = tk.StringVar()
        tk.Entry(p1_frame, textvariable=p1_word_var, show="*").grid(row=1, column=1, padx=6)

        p2_frame = tk.Frame(self.center_frame, bg=THEME["bg"])
        p2_frame.pack(pady=6)
        tk.Label(p2_frame, text="Player 2 length:", bg=THEME["bg"]).grid(row=0, column=0, padx=6)
        p2_len = tk.IntVar(value=5)
        tk.Spinbox(p2_frame, from_=3, to=7, textvariable=p2_len, width=5).grid(row=0, column=1, padx=6)
        tk.Label(p2_frame, text="Player 2 secret:", bg=THEME["bg"]).grid(row=1, column=0, padx=6)
        p2_word_var = tk.StringVar()
        tk.Entry(p2_frame, textvariable=p2_word_var, show="*").grid(row=1, column=1, padx=6)

        tk.Button(self.center_frame, text="Start Same-device Duel", bg=THEME["primary"], fg="white",
                  command=lambda: self._start_same_device_duel(p1_word_var.get().strip(), p1_len.get(), p2_word_var.get().strip(), p2_len.get())).pack(pady=10)

    def _start_same_device_duel(self, p1_word, p1_len, p2_word, p2_len):
        if not (p1_word.isalpha() and len(p1_word) == p1_len and p2_word.isalpha() and len(p2_word) == p2_len):
            messagebox.showerror("Invalid", "Each player's secret must be alphabetic and match their chosen length.")
            return
        if VALID_WORDS:
            if p1_word.lower() not in VALID_WORDS:
                messagebox.showerror("Invalid", "Player 1's secret is not in the dictionary.")
                return
            if p2_word.lower() not in VALID_WORDS:
                messagebox.showerror("Invalid", "Player 2's secret is not in the dictionary.")
                return

        for w in self.center_frame.winfo_children(): w.destroy()
        container = tk.Frame(self.center_frame, bg=THEME["bg"])
        container.pack(fill="both", expand=True)
        left_col = tk.Frame(container, bg=THEME["bg"], padx=12, pady=12)
        right_col = tk.Frame(container, bg=THEME["bg"], padx=12, pady=12)
        left_col.pack(side="left", fill="both", expand=True)
        right_col.pack(side="right", fill="both", expand=True)

        self.results = {"P1": None, "P2": None}
        self.finished = {"P1": False, "P2": False}

        self.panel_p1 = PlayerPanel(left_col, "P1", "Player 1 (guess P2)", p2_len, p2_word, self._player_finished, self._player_made_guess)
        self.panel_p1.pack(fill="both", expand=True)
        self.panel_p2 = PlayerPanel(right_col, "P2", "Player 2 (guess P1)", p1_len, p1_word, self._player_finished, self._player_made_guess)
        self.panel_p2.pack(fill="both", expand=True)

        ctrl_frame = tk.Frame(container, bg=THEME["bg"], pady=8)
        ctrl_frame.pack(fill="x")
        self.turn_label = tk.Label(ctrl_frame, text="Turn: Player 1", font=("Helvetica", 12, "bold"), bg=THEME["bg"])
        self.turn_label.pack(side="left", padx=12)
        tk.Button(ctrl_frame, text="Back to menu", command=self.setup_main_menu).pack(side="right")

        self.active = "P1"
        self._apply_turn_state()

    def _apply_turn_state(self):
        if self.active == "P1":
            self.panel_p1.enable(not self.finished["P1"])
            self.panel_p2.enable(False)
            self.turn_label.config(text="Turn: Player 1")
            if not self.finished["P1"]:
                self.panel_p1.guess_entry.focus_set()
        else:
            self.panel_p1.enable(False)
            self.panel_p2.enable(not self.finished["P2"])
            self.turn_label.config(text="Turn: Player 2")
            if not self.finished["P2"]:
                self.panel_p2.guess_entry.focus_set()

    def _player_made_guess(self, player_id):
        other = "P2" if player_id == "P1" else "P1"
        if not self.finished[other]:
            self.active = other
        else:
            if self.finished[player_id]:
                pass
            else:
                self.active = player_id
        self._apply_turn_state()

    def _player_finished(self, player_id, attempts_used, guessed_bool):
        self.results[player_id] = (attempts_used, guessed_bool)
        self.finished[player_id] = True
        if player_id == "P1":
            self.panel_p1.enable(False)
        else:
            self.panel_p2.enable(False)

        if self.active == player_id:
            other = "P2" if player_id == "P1" else "P1"
            if not self.finished[other]:
                self.active = other

        self._apply_turn_state()

        if self.results["P1"] is not None and self.results["P2"] is not None:
            self._announce_winner()

    def _announce_winner(self):
        a_attempts, a_guessed = self.results["P1"]
        b_attempts, b_guessed = self.results["P2"]
        if a_attempts < b_attempts:
            winner = "Player 1"
        elif b_attempts < a_attempts:
            winner = "Player 2"
        else:
            winner = "Tie"
        msg = f"Results:\nPlayer 1: {'guessed' if a_guessed else 'failed'} in {a_attempts if a_guessed else '—'} attempts\n" \
              f"Player 2: {'guessed' if b_guessed else 'failed'} in {b_attempts if b_guessed else '—'} attempts\n\nWinner: {winner}"
        messagebox.showinfo("Duel finished", msg)
        self.panel_p1.enable(False)
        self.panel_p2.enable(False)

    def duel_share_link_setup(self):
        for w in self.center_frame.winfo_children(): w.destroy()
        tk.Label(self.center_frame, text="Share Link Duel — Host (Player A) prepare the link", bg=THEME["bg"], fg=THEME["muted"]).pack(pady=8)

        f = tk.Frame(self.center_frame, bg=THEME["bg"])
        f.pack(pady=6)
        tk.Label(f, text="Your word length (3-7):", bg=THEME["bg"]).grid(row=0, column=0, padx=6, pady=4)
        host_len = tk.IntVar(value=5)
        tk.Spinbox(f, from_=3, to=7, textvariable=host_len, width=5).grid(row=0, column=1, padx=6, pady=4)
        tk.Label(f, text="Your secret word:", bg=THEME["bg"]).grid(row=1, column=0, padx=6, pady=4)
        host_word_var = tk.StringVar()
        tk.Entry(f, textvariable=host_word_var, show="*").grid(row=1, column=1, padx=6, pady=4)

        def make_link():
            w = host_word_var.get().strip().lower()
            l = host_len.get()
            if not (w.isalpha() and len(w) == l):
                messagebox.showerror("Invalid", "Secret invalid or does not match chosen length.")
                return
            if VALID_WORDS and w not in VALID_WORDS:
                messagebox.showerror("Invalid", "Secret word is not in the dictionary.")
                return
            link = DuelLinkFlow.create_initial_link(l, w)
            self.waiting_for_return = True
            self.my_initial_secret = w
            self.my_length = l
            top = tk.Toplevel(self.root)
            top.title("Share this link with your friend")
            top.geometry("760x120")
            tk.Label(top, text="Copy this link and send to your friend (they will paste it into the Join box):").pack(pady=(8,6))
            e = tk.Entry(top, width=100)
            e.pack(padx=8)
            e.insert(0, link)
            def copy_clip():
                try:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(link)
                    messagebox.showinfo("Copied", "Link copied to clipboard")
                except Exception as ex:
                    messagebox.showerror("Clipboard", f"Could not copy: {ex}")
            tk.Button(top, text="Copy link", command=copy_clip).pack(pady=(6,8))

        tk.Button(self.center_frame, text="Generate Share Link", bg=THEME["primary"], fg="white", command=make_link).pack(pady=10)
        tk.Button(self.center_frame, text="Back to menu", command=self.setup_main_menu).pack(pady=6)

    def _join_from_box(self):
        txt = self.link_entry.get().strip()
        if not txt:
            messagebox.showerror("No link", "Paste a link or payload into the box first.")
            return
        self.join_or_load_link(txt)

    def join_or_load_link(self, txt):
        txt = txt.strip()
        try:
            length_r, secretB, attemptsB, guessedB = DuelLinkFlow.decode_return_link(txt)
            def on_finish_host(attemptsA, guessedA):
                a = attemptsA
                b = attemptsB
                if a < b:
                    winner = "You (Host, Player A)"
                elif b < a:
                    winner = "Friend (Player B)"
                else:
                    winner = "Tie"
                messagebox.showinfo("Duel result", f"Player A attempts: {a if guessedA else 'failed'}\n"
                                                   f"Player B attempts: {b if guessedB else 'failed'}\n\nWinner: {winner}")
            SingleGameWindow(self.root, secret_word=secretB, word_length=length_r, title="WorDuel — Guess Friend's word (return)", on_finish=on_finish_host)
            self.waiting_for_return = False
            self.my_initial_secret = None
            self.my_length = None
            return
        except Exception:
            pass

        try:
            length, secretA = DuelLinkFlow.decode_initial_link(txt)
        except Exception as e:
            messagebox.showerror("Invalid", f"Could not decode link/payload: {e}")
            return

        results = {"attempts": None, "guessed": None}
        def on_finish_b(attempts_b, guessed_b):
            results["attempts"] = attempts_b
            results["guessed"] = guessed_b
            ret_top = tk.Toplevel(self.root)
            ret_top.title("Create return link for host (Player A)")
            ret_top.geometry("560x200")
            tk.Label(ret_top, text="You finished guessing. Now enter your secret for Player A to guess:", wraplength=520).pack(pady=(8,6))
            frm = tk.Frame(ret_top)
            frm.pack(pady=6)
            tk.Label(frm, text="Your word length (3-7):").grid(row=0, column=0, padx=6, pady=6)
            p_len_var = tk.IntVar(value=length)
            tk.Spinbox(frm, from_=3, to=7, textvariable=p_len_var, width=5).grid(row=0, column=1, padx=6, pady=6)
            tk.Label(frm, text="Your secret word:").grid(row=1, column=0, padx=6, pady=6)
            p_word_var = tk.StringVar()
            tk.Entry(frm, textvariable=p_word_var, show="*").grid(row=1, column=1, padx=6, pady=6)

            def make_return():
                p_len = p_len_var.get()
                p_word = p_word_var.get().strip().lower()
                if not (p_word.isalpha() and len(p_word) == p_len):
                    messagebox.showerror("Invalid", "Secret invalid or does not match chosen length.")
                    return
                if VALID_WORDS and p_word not in VALID_WORDS:
                    messagebox.showerror("Invalid", "Secret word is not in the dictionary.")
                    return
                ret_link = DuelLinkFlow.create_return_link(p_len, p_word, results["attempts"], results["guessed"])
                show_top = tk.Toplevel(self.root)
                show_top.title("Return link — send back to host")
                show_top.geometry("760x120")
                tk.Label(show_top, text="Copy this return link and send it back to the original sender:").pack(pady=(8,6))
                e = tk.Entry(show_top, width=100)
                e.pack(padx=8)
                e.insert(0, ret_link)
                def copy_ret():
                    try:
                        self.root.clipboard_clear()
                        self.root.clipboard_append(ret_link)
                        messagebox.showinfo("Copied", "Return link copied to clipboard")
                    except Exception as ex:
                        messagebox.showerror("Clipboard", f"Could not copy: {ex}")
                tk.Button(show_top, text="Copy return link", command=copy_ret).pack(pady=(6,8))
                ret_top.destroy()

            tk.Button(ret_top, text="Create Return Link", command=make_return, bg=THEME["primary"], fg="white").pack(pady=6)

        SingleGameWindow(self.root, secret_word=secretA, word_length=length, title="WorDuel — Guess Player A's word (from link)", on_finish=on_finish_b)

    def _draw_avatar_on_canvas(self, canvas, prof, w, h):
        bases, exprs, outfits = find_layer_files()
        base_key = (prof.get("color") or "").lower()
        expr_key = (prof.get("expression") or "").lower()
        outfit_key = (prof.get("outfit") or "").lower()

        base_path = bases.get(base_key) if base_key else None
        expr_path = exprs.get(expr_key) if expr_key else None
        outfit_path = outfits.get(outfit_key) if outfit_key else None

        if PIL_AVAILABLE and (base_path or expr_path or outfit_path):
            base_im = load_and_prepare_image(base_path, target_size=DISPLAY_SIZE) if base_path else None
            expr_im = load_and_prepare_image(expr_path, target_size=DISPLAY_SIZE) if expr_path else None
            outfit_im = load_and_prepare_image(outfit_path, target_size=DISPLAY_SIZE) if outfit_path else None
            composed = compose_layers(base_im, outfit_im, expr_im)
            if composed is not None:
                comp_small = composed.resize((w, h), resample=Image.NEAREST)
                tkimg = ImageTk.PhotoImage(comp_small)
                self._main_avatar_tk = tkimg
                canvas.delete("all")
                canvas.create_image(w//2, h//2, image=tkimg)
                return

        # fallback drawing
        canvas.delete("all")
        canvas.create_rectangle(0,0,w,h, fill=THEME["bg"], outline="")
        canvas.create_oval(w*0.15, h*0.05, w*0.85, h*0.65, fill="#ffd27f", outline="#000", width=3)
        canvas.create_rectangle(w*0.22, h*0.55, w*0.78, h*0.95, fill="#2b6cb0", outline="#123")
        canvas.create_rectangle(w*0.33, h*0.28, w*0.37, h*0.32, fill="#0f172a")
        canvas.create_rectangle(w*0.63, h*0.28, w*0.67, h*0.32, fill="#0f172a")

    def setup_main_menu(self):
        for w in self.center_frame.winfo_children():
            w.destroy()
        if self.profile:
            prof = tk.Frame(self.center_frame, bg=THEME["bg"])
            prof.pack(pady=(6,8))
            name = self.profile.get("username", "Player")
            tk.Label(prof, text=f"Username: {name}", bg=THEME["bg"], fg=THEME["muted"]).pack()

            avatar_holder = tk.Frame(self.center_frame, bg=THEME["bg"])
            avatar_holder.pack(pady=6)
            canvas_w = 260
            canvas_h = 260
            avatar_canvas = tk.Canvas(avatar_holder, width=canvas_w, height=canvas_h, bg=THEME["bg"], highlightthickness=0)
            avatar_canvas.pack()
            self._draw_avatar_on_canvas(avatar_canvas, self.profile, canvas_w, canvas_h)

        tk.Label(self.center_frame, text="Choose a mode above or paste a duel link below and press Join.", bg=THEME["bg"], fg=THEME["muted"]).pack()

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()
