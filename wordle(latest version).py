import tkinter as tk
from tkinter import messagebox
import random
import base64
import urllib.parse
import urllib.request
import ssl
import os

# ---------------------------------------------------------
# DEPENDENCIES & ASSETS
# ---------------------------------------------------------
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# ---------------------------------------------------------
# THEME & CONFIG
# ---------------------------------------------------------
MAX_ATTEMPTS = 6

THEME = {
    "bg": "#f8f5ff",           # Very light lavender background
    "card_bg": "#ffffff",      # White cards
    "text_main": "#4a4a6a",    # Dark purplish grey text
    "muted": "#8d8d9e",        # Muted text
    "primary": "#b088ff",      # Cute purple button
    "primary_hover": "#9e70f7",
    "secondary": "#eaddff",    # Light purple accent
    "success": "#9bf6c2",      # Mint green (Win)
    "warning": "#ffeebb",      # Pastel Yellow (Present)
    "error": "#ffb3b3",        # Pastel Red (Lose)
    "grey": "#e0e0e0",         # Absent
    "tile_text": "#5c5c70",
    "white": "#ffffff"
}

WORDS_BY_LENGTH = {
    3: ["cat", "dog", "sun", "car", "map", "bag", "hot", "cup", "key", "ice", "pen", "jam", "egg", "owl", "fox"],
    4: ["moon", "book", "code", "play", "fish", "tree", "lamp", "road", "star", "home", "milk", "cake", "ship", "rain", "cute", "love"],
    5: ["apple", "house", "light", "plant", "table", "chair", "spark", "brand", "until", "ghost", "brown", "water", "mouse", "heart", "smile", "dream"],
    6: ["planet", "garden", "silver", "random", "buffer", "friend", "castle", "bridge", "flight", "flower", "summer"],
    7: ["marbles", "monster", "picture", "charger", "balance", "battery", "journey", "vintage", "rainbow", "unicorn"],
}

DEFAULT_WORDLIST_URL = "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt"

# ---------------------------------------------------------
# HELPERS: WORD LOADING & ENCODING
# ---------------------------------------------------------
def load_valid_words(local_path="wordlist.txt", fallback_url=DEFAULT_WORDLIST_URL):
    words = set()
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                for line in f:
                    w = line.strip().lower()
                    if w: words.add(w)
            if words: return words
        except Exception: pass
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(fallback_url, context=ctx, timeout=5) as resp:
            for raw in resp:
                try: w = raw.decode("utf-8").strip().lower()
                except: continue
                if w: words.add(w)
        if words:
            try:
                with open(local_path, "w", encoding="utf-8") as f:
                    for w in sorted(words): f.write(w + "\n")
            except: pass
            return words
    except: pass
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
            b64 = q["w"][0] if "w" in q else link_text[link_text.find("w=") + 2:]
        else: b64 = link_text
        decoded = DuelLinkFlow._b64_decode(b64)
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
            b64 = q["w"][0] if "w" in q else link_text[link_text.find("w=") + 2:]
        else: b64 = link_text
        decoded = DuelLinkFlow._b64_decode(b64)
        parts = decoded.split(":", 4)
        return int(parts[1]), parts[2], int(parts[3]), parts[4] == "1"

    @staticmethod
    def _b64_encode(s: str) -> str:
        return base64.urlsafe_b64encode(s.encode("utf-8")).decode("ascii").rstrip("=")

    @staticmethod
    def _b64_decode(s: str) -> str:
        padding = "=" * (-len(s) % 4)
        return base64.urlsafe_b64decode((s + padding).encode("ascii")).decode("utf-8")

class WordleEngine:
    @staticmethod
    def check_guess(guess: str, secret: str):
        n = len(secret)
        result = ["grey"] * n
        counts = {}
        for i in range(n):
            if guess[i] == secret[i]: result[i] = "green"
            else: counts[secret[i]] = counts.get(secret[i], 0) + 1
        for i in range(n):
            if result[i] == "green": continue
            g = guess[i]
            if counts.get(g, 0) > 0:
                result[i] = "yellow"
                counts[g] -= 1
        return result

# ---------------------------------------------------------
# ASSET & AVATAR DRAWING SYSTEM
# ---------------------------------------------------------
ASSETS_DIR = "assets"
DISPLAY_SIZE = 160

def find_layer_files():
    """Returns dictionaries of available assets"""
    candidates = []
    places = [os.getcwd()]
    if os.path.isdir(ASSETS_DIR): places.append(os.path.join(os.getcwd(), ASSETS_DIR))
    for p in places:
        try:
            for fn in os.listdir(p):
                if fn.lower().endswith(".png"): candidates.append(os.path.join(p, fn))
        except: pass
    bases, exprs, outfits = {}, {}, {}
    for full in candidates:
        fn = os.path.basename(full)
        lfn = fn.lower()
        if lfn.startswith("base_"): bases[fn[5:].rsplit(".", 1)[0].lower()] = full
        elif lfn.startswith("expr_"): exprs[fn[5:].rsplit(".", 1)[0].lower()] = full
        elif lfn.startswith("outfit_"): outfits[fn[7:].rsplit(".", 1)[0].lower()] = full
    return bases, exprs, outfits

def load_and_prepare_image(path, target_size=DISPLAY_SIZE):
    if not PIL_AVAILABLE or not path: return None
    try:
        im = Image.open(path).convert("RGBA")
        if im.width != target_size or im.height != target_size:
            im = im.resize((target_size, target_size), resample=Image.NEAREST)
        return im
    except: return None

def compose_layers(base_im, outfit_im, expr_im):
    """Stacks avatar layers: Base -> Outfit -> Expression."""
    if not PIL_AVAILABLE: return None
    size = None
    for im in (base_im, outfit_im, expr_im):
        if im is not None:
            size = im.size
            break
    if size is None: return None
    out = Image.new("RGBA", size, (0,0,0,0))
    if base_im: out = Image.alpha_composite(out, base_im)
    if outfit_im: out = Image.alpha_composite(out, outfit_im)
    if expr_im: out = Image.alpha_composite(out, expr_im)
    return out

def draw_profile_avatar(canvas, profile, w, h):
    """Global helper to draw a profile's avatar onto a tkinter Canvas."""
    bases, exprs, outfits = find_layer_files()
    base_key = (profile.get("color") or "").lower()
    expr_key = (profile.get("expression") or "").lower()
    outfit_key = (profile.get("outfit") or "").lower()

    base_path = bases.get(base_key)
    expr_path = exprs.get(expr_key)
    outfit_path = outfits.get(outfit_key)

    if PIL_AVAILABLE and (base_path or expr_path or outfit_path):
        base_im = load_and_prepare_image(base_path, target_size=DISPLAY_SIZE)
        expr_im = load_and_prepare_image(expr_path, target_size=DISPLAY_SIZE)
        outfit_im = load_and_prepare_image(outfit_path, target_size=DISPLAY_SIZE)
        composed = compose_layers(base_im, outfit_im, expr_im)
        if composed:
            comp_small = composed.resize((w, h), resample=Image.NEAREST)
            canvas.image = ImageTk.PhotoImage(comp_small) # Keep ref
            canvas.delete("all")
            canvas.create_image(w//2, h//2, image=canvas.image)
            return

    # Fallback "Cute" Placeholder
    canvas.delete("all")
    canvas.create_oval(w*0.1, h*0.1, w*0.9, h*0.9, fill="#ffd27f", outline=THEME["text_main"], width=2)
    # Eyes
    canvas.create_oval(w*0.3, h*0.4, w*0.4, h*0.5, fill=THEME["text_main"])
    canvas.create_oval(w*0.6, h*0.4, w*0.7, h*0.5, fill=THEME["text_main"])
    # Smile
    canvas.create_arc(w*0.3, h*0.5, w*0.7, h*0.8, start=0, extent=-180, style="arc", outline=THEME["text_main"], width=2)

# ---------------------------------------------------------
# CUSTOM RESULT OVERLAY (Replaces MessageBox)
# ---------------------------------------------------------
class GameResultOverlay(tk.Frame):
    def __init__(self, parent, is_win, secret_word, profile, on_close_callback):
        super().__init__(parent, bg="white", bd=0)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Center Container (The Card)
        card = tk.Frame(self, bg=THEME["bg"], padx=40, pady=40)
        card.place(relx=0.5, rely=0.5, anchor="center")
        
        # Title
        title_text = "YOU WON!" if is_win else "YOU LOST"
        title_color = "#76c893" if is_win else "#ff8fab"
        
        tk.Label(card, text=title_text, font=("Helvetica", 24, "bold"), 
                 bg=THEME["bg"], fg=title_color).pack(pady=(0, 10))

        # Avatar Display (Always show avatar for the current player)
        av_frame = tk.Frame(card, bg=THEME["bg"])
        av_frame.pack(pady=10)
        canv = tk.Canvas(av_frame, width=140, height=140, bg=THEME["bg"], highlightthickness=0)
        canv.pack()
        draw_profile_avatar(canv, profile, 140, 140)
        
        tk.Label(card, text=f"Great job, {profile.get('username','Player')}!", 
                 bg=THEME["bg"], fg=THEME["muted"], font=("Helvetica", 10)).pack(pady=(5,0))

        # Secret Word Reveal
        tk.Label(card, text=f"The word was:", bg=THEME["bg"], fg=THEME["muted"]).pack(pady=(15, 5))
        tk.Label(card, text=secret_word.upper(), font=("Helvetica", 18, "bold"), 
                 bg=THEME["white"], fg=THEME["text_main"], width=15, relief="flat", padx=10, pady=5).pack()

        # Close Button
        btn = tk.Button(card, text="Continue", font=("Helvetica", 12, "bold"),
                        bg=THEME["primary"], fg="white", relief="flat",
                        activebackground=THEME["primary_hover"], activeforeground="white",
                        width=12, command=on_close_callback)
        btn.pack(pady=(25, 0))

# ---------------------------------------------------------
# SINGLE GAME WINDOW
# ---------------------------------------------------------
class SingleGameWindow:
    def __init__(self, master, secret_word, word_length, player_profile, title="WorDuel", on_finish=None):
        self.master = master
        self.secret = secret_word.lower()
        self.word_length = word_length
        self.profile = player_profile
        self.attempt = 0
        self.attempts_used = None
        self.on_finish = on_finish
        self.guessed = False
        self.key_buttons = {}

        self.win = tk.Toplevel(master)
        self.win.title(title)
        self.win.protocol("WM_DELETE_WINDOW", self._on_force_close)
        self.win.configure(bg=THEME["bg"])
        self.win.geometry("900x700")
        self.win.minsize(700, 600)

        # Main Layout
        container = tk.Frame(self.win, bg=THEME["bg"], padx=20, pady=20)
        container.pack(fill="both", expand=True)

        # START CHANGE 2: Apply Duel Name style to Single Player
        username = self.profile.get("username", "Player")
        tk.Label(container, text=f"{username}'s Game", bg=THEME["bg"], fg=THEME["text_main"],
                 font=("Helvetica", 14, "bold")).pack(pady=(5, 10))
        # END CHANGE 2

        # Grid
        self.grid_frame = tk.Frame(container, bg=THEME["bg"])
        self.grid_frame.pack(pady=10)

        self.cells = []
        for r in range(MAX_ATTEMPTS):
            row = []
            for c in range(word_length):
                # Flatter, cleaner tiles
                lbl = tk.Label(self.grid_frame, text="", width=4, height=2,
                               bg="white", fg=THEME["tile_text"],
                               relief="flat", font=("Helvetica", 14, "bold"))
                # Use a frame to simulate a border if needed, or just padding
                lbl.grid(row=r, column=c, padx=3, pady=3)
                row.append(lbl)
            self.cells.append(row)

        # Entry Area
        entry_frame = tk.Frame(container, bg=THEME["bg"])
        entry_frame.pack(pady=20)
        
        self.guess_var = tk.StringVar()
        self.guess_entry = tk.Entry(entry_frame, textvariable=self.guess_var, 
                                    width=15, font=("Helvetica", 16), 
                                    relief="flat", bg="white", fg=THEME["text_main"],
                                    justify="center")
        self.guess_entry.pack(side="left", ipady=5, padx=10)
        self.guess_entry.bind("<Return>", lambda e: self.submit_guess())
        
        self.submit_btn = tk.Button(entry_frame, text="GUESS", command=self.submit_guess, 
                                    bg=THEME["primary"], fg="white", font=("Helvetica", 11, "bold"),
                                    relief="flat", activebackground=THEME["primary_hover"], width=10)
        self.submit_btn.pack(side="left", padx=10, ipady=5)

        # Keyboard
        self._build_keyboard(container)
        
        self.status_lbl = tk.Label(container, text=f"Attempts left: {MAX_ATTEMPTS}", 
                                   bg=THEME["bg"], fg=THEME["muted"], font=("Helvetica", 10))
        self.status_lbl.pack(side="bottom", pady=10)

        self.enable(True)
        self.win.lift()
        self.guess_entry.focus_set()

    def _build_keyboard(self, parent):
        kb_frame = tk.Frame(parent, bg=THEME["bg"])
        kb_frame.pack(pady=10)
        rows = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
        for r in rows:
            rframe = tk.Frame(kb_frame, bg=THEME["bg"])
            rframe.pack(pady=2)
            for ch in r:
                btn = tk.Button(rframe, text=ch, width=4, height=1, 
                                bg="white", fg=THEME["text_main"], relief="flat",
                                activebackground="#eee",
                                command=lambda c=ch: self._on_key_click(c))
                btn.pack(side="left", padx=2)
                self.key_buttons[ch.lower()] = btn
        
        # Tools row
        tools = tk.Frame(kb_frame, bg=THEME["bg"])
        tools.pack(pady=4)
        tk.Button(tools, text="⌫", command=self._on_backspace, bg=THEME["secondary"], relief="flat", width=6).pack(side="left", padx=5)

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
        # Visual feedback for error
        base_bg = row_widgets[0].cget("bg")
        # Ensure base_bg is set to a solid color for the flash cycle, usually 'white'
        if base_bg not in [THEME["success"], THEME["warning"], THEME["grey"]]:
            base_bg = 'white'
        
        def color_flash(c, count):
            if count > 4: 
                for w in row_widgets: w.config(bg=base_bg)
                return
            col = THEME["error"] if count % 2 == 0 else base_bg
            for w in row_widgets: w.config(bg=col)
            self.win.after(100, lambda: color_flash(c, count+1))
        color_flash(base_bg, 0)

    def submit_guess(self):
        guess = self.guess_var.get().strip().lower()
        if len(guess) != self.word_length or not guess.isalpha():
            if self.attempt < MAX_ATTEMPTS: self._shake_row(self.cells[self.attempt])
            return
        if VALID_WORDS and guess not in VALID_WORDS:
            if self.attempt < MAX_ATTEMPTS: self._shake_row(self.cells[self.attempt])
            return

        colors = WordleEngine.check_guess(guess, self.secret)
        row_labels = self.cells[self.attempt]
        
        for i, ch in enumerate(guess):
            lbl = row_labels[i]
            lbl.config(text=ch.upper())
            if colors[i] == "green": lbl.config(bg=THEME["success"], fg=THEME["tile_text"])
            elif colors[i] == "yellow": lbl.config(bg=THEME["warning"], fg=THEME["tile_text"])
            else: lbl.config(bg=THEME["grey"], fg="#999")
            
        self._update_keyboard(colors, guess)
        self.attempt += 1
        self.status_lbl.config(text=f"Attempts left: {MAX_ATTEMPTS - self.attempt}")
        self.guess_var.set("")

        if guess == self.secret:
            self.guessed = True
            self.attempts_used = self.attempt
            self.show_result(True)
        elif self.attempt >= MAX_ATTEMPTS:
            self.guessed = False
            self.attempts_used = MAX_ATTEMPTS + 1
            self.show_result(False)

    def show_result(self, is_win):
        self.enable(False)
        # Call the cute overlay instead of closing
        GameResultOverlay(self.win, is_win, self.secret, self.profile, self.finish)

    def _update_keyboard(self, colors, guess):
        rank_map = {"green": 3, "yellow": 2, "grey": 1}
        for c, col in zip(guess, colors):
            btn = self.key_buttons.get(c)
            if not btn: continue
            
            cur_bg = btn.cget("bg")
            cur_rank = 0
            if cur_bg == THEME["success"]: cur_rank = 3
            elif cur_bg == THEME["warning"]: cur_rank = 2
            elif cur_bg == THEME["grey"]: cur_rank = 1
            
            new_rank = rank_map.get(col, 0)
            if new_rank > cur_rank:
                if col == "green": btn.config(bg=THEME["success"])
                elif col == "yellow": btn.config(bg=THEME["warning"])
                else: btn.config(bg=THEME["grey"])

    def enable(self, flag: bool):
        state = "normal" if flag else "disabled"
        self.guess_entry.config(state=state)
        self.submit_btn.config(state=state)
        for b in self.key_buttons.values(): b.config(state=state)

    def finish(self):
        # Actual cleanup
        if self.attempts_used is None:
            self.attempts_used = MAX_ATTEMPTS + 1
            self.guessed = False
        if self.on_finish:
            self.on_finish(self.attempts_used, self.guessed)
        self.win.destroy()

    def _on_force_close(self):
        self.finish()

# ---------------------------------------------------------
# DUEL PLAYER PANEL
# ---------------------------------------------------------
class PlayerPanel(tk.Frame):
    def __init__(self, parent, player_id, title, word_length, secret_word, on_finish, on_guess):
        super().__init__(parent, bg=THEME["bg"])
        self.player_id = player_id
        self.word_length = word_length
        self.secret = secret_word.lower()
        self.on_finish = on_finish
        self.on_guess = on_guess
        self.attempt = 0
        self.attempts_used = None
        self.guessed = False
        self.key_buttons = {}

        tk.Label(self, text=title, font=("Helvetica", 14, "bold"), bg=THEME["bg"], fg=THEME["text_main"]).pack(pady=(5, 5))
        
        # Grid
        grid = tk.Frame(self, bg=THEME["bg"])
        grid.pack()
        self.cells = []
        for r in range(MAX_ATTEMPTS):
            row = []
            for c in range(word_length):
                lbl = tk.Label(grid, text="", width=3, height=1, bg="white", 
                               relief="flat", font=("Helvetica", 12, "bold"))
                lbl.grid(row=r, column=c, padx=2, pady=2)
                row.append(lbl)
            self.cells.append(row)

        # Input
        inp = tk.Frame(self, bg=THEME["bg"])
        inp.pack(pady=8)
        self.guess_var = tk.StringVar()
        self.guess_entry = tk.Entry(inp, textvariable=self.guess_var, width=12, relief="flat", font=("Helvetica", 12))
        self.guess_entry.pack(side="left", padx=5, ipady=3)
        self.guess_entry.bind("<Return>", lambda e: self.submit_guess())
        
        self.submit_btn = tk.Button(inp, text="GO", command=self.submit_guess, 
                                    bg=THEME["primary"], fg="white", relief="flat", width=4)
        self.submit_btn.pack(side="left")

        # Tiny Keyboard
        kb_frame = tk.Frame(self, bg=THEME["bg"])
        kb_frame.pack(pady=5)
        rows = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
        for r in rows:
            rf = tk.Frame(kb_frame, bg=THEME["bg"])
            rf.pack(pady=1)
            for ch in r:
                b = tk.Button(rf, text=ch, width=2, relief="flat", font=("Arial", 7),
                              command=lambda c=ch: self._on_key(c))
                b.pack(side="left", padx=1)
                self.key_buttons[ch.lower()] = b
        
        tk.Button(kb_frame, text="⌫", command=self._backspace, bg=THEME["secondary"], relief="flat", font=("Arial", 8)).pack(pady=2)

        self.status_lbl = tk.Label(self, text=f"Left: {MAX_ATTEMPTS}", bg=THEME["bg"], fg=THEME["muted"], font=("Arial", 9))
        self.status_lbl.pack(pady=2)

    def _on_key(self, ch):
        cur = self.guess_var.get()
        if len(cur) < self.word_length:
            self.guess_var.set(cur + ch.lower())
            self.guess_entry.icursor(tk.END)

    def _backspace(self):
        cur = self.guess_var.get()
        self.guess_var.set(cur[:-1])
        self.guess_entry.icursor(tk.END)
    
    # NEW: Added shake logic for invalid guesses
    def _shake_row(self, row_widgets):
        # Visual feedback for error
        base_bg = row_widgets[0].cget("bg")
        # Ensure base_bg is set to a solid color for the flash cycle
        if base_bg not in [THEME["success"], THEME["warning"], THEME["grey"]]:
            base_bg = 'white'
        
        # We need the top-level window (usually the MainApp's root or the duel setup Toplevel) 
        # to call .after for time-based animation.
        top_level = self.master.winfo_toplevel()
        
        def color_flash(c, count):
            if count > 4: 
                for w in row_widgets: w.config(bg=base_bg)
                return
            col = THEME["error"] if count % 2 == 0 else base_bg
            for w in row_widgets: w.config(bg=col)
            top_level.after(100, lambda: color_flash(c, count+1))
        
        color_flash(base_bg, 0)

    def submit_guess(self):
        guess = self.guess_var.get().strip().lower()
        
        # 1. Validation Check: Length/Alpha
        if len(guess) != self.word_length or not guess.isalpha(): 
            if self.attempt < MAX_ATTEMPTS: self._shake_row(self.cells[self.attempt])
            return
            
        # 2. Validation Check: Valid Word (Added this check and shake)
        if VALID_WORDS and guess not in VALID_WORDS: 
            if self.attempt < MAX_ATTEMPTS: self._shake_row(self.cells[self.attempt])
            return
        
        colors = WordleEngine.check_guess(guess, self.secret)
        row_labels = self.cells[self.attempt]
        for i, ch in enumerate(guess):
            row_labels[i].config(text=ch.upper())
            if colors[i] == "green": row_labels[i].config(bg=THEME["success"])
            elif colors[i] == "yellow": row_labels[i].config(bg=THEME["warning"])
            else: row_labels[i].config(bg=THEME["grey"])
        
        self._update_keyboard(colors, guess)
        self.attempt += 1
        self.status_lbl.config(text=f"Left: {MAX_ATTEMPTS - self.attempt}")
        self.guess_var.set("")
        
        if self.on_guess: self.on_guess(self.player_id)
        
        if guess == self.secret:
            self.guessed = True
            self.attempts_used = self.attempt
            self.finish()
        elif self.attempt >= MAX_ATTEMPTS:
            self.guessed = False
            self.attempts_used = MAX_ATTEMPTS + 1
            self.finish()

    def _update_keyboard(self, colors, guess):
        rank_map = {"green": 3, "yellow": 2, "grey": 1}
        for c, col in zip(guess, colors):
            btn = self.key_buttons.get(c)
            if not btn: continue
            cur_bg = btn.cget("bg")
            cur_rank = 0
            if cur_bg == THEME["success"]: cur_rank = 3
            elif cur_bg == THEME["warning"]: cur_rank = 2
            elif cur_bg == THEME["grey"]: cur_rank = 1
            
            new_rank = rank_map.get(col, 0)
            if new_rank > cur_rank:
                if col == "green": btn.config(bg=THEME["success"])
                elif col == "yellow": btn.config(bg=THEME["warning"])
                else: btn.config(bg=THEME["grey"])

    def enable(self, flag: bool):
        state = "normal" if flag else "disabled"
        self.guess_entry.config(state=state)
        self.submit_btn.config(state=state)
        for b in self.key_buttons.values(): b.config(state=state)

    def finish(self):
        if self.attempts_used is None:
            self.attempts_used = MAX_ATTEMPTS + 1
            self.guessed = False
        if self.on_finish:
            self.on_finish(self.player_id, self.attempts_used, self.guessed)

# ---------------------------------------------------------
# CHARACTER CREATOR (Cuter)
# ---------------------------------------------------------
class InlinePopupCharacterCreator:
    def __init__(self, parent_frame, on_done):
        self.parent = parent_frame
        self.on_done = on_done
        self.available_bases, self.available_exprs, self.available_outfits = find_layer_files()
        
        self.username_var = tk.StringVar(value="Player")
        # Ensure initial keys exist in their respective lists if they are found
        self.color_key = next(iter(self.available_bases.keys()), "default")
        self.expr_key = next(iter(self.available_exprs.keys()), "smile")
        self.outfit_key = next(iter(self.available_outfits.keys()), "casual")
        self.active_category = "base"
        self.tk_cache = {}

        self.popup = tk.Frame(self.parent, bg=THEME["grey"], bd=0)
        # MODIFICATION: Keeps the reduced size from the previous step.
        self.popup.place(relx=0.5, rely=0.5, anchor="center", width=450, height=470)
        
        self.card = tk.Frame(self.popup, bg="white")
        self.card.pack(fill="both", expand=True, padx=2, pady=2)

        tk.Label(self.card, text="Design Your Character", bg="white", fg=THEME["primary"], font=("Helvetica", 16, "bold")).pack(pady=(20,10))

        content = tk.Frame(self.card, bg="white")
        content.pack(fill="both", expand=True, padx=20, pady=5)

        # Name
        uname_frame = tk.Frame(content, bg="white")
        uname_frame.pack(pady=(5, 15))
        tk.Label(uname_frame, text="Name:", bg="white", font=("Helvetica", 11), fg=THEME["muted"]).pack(side="left", padx=(0,8))
        tk.Entry(uname_frame, textvariable=self.username_var, width=18, font=("Helvetica", 12), 
                 relief="flat", bg=THEME["bg"]).pack(side="left", ipady=4)

        # Toggles
        toggles = tk.Frame(content, bg="white")
        toggles.pack(pady=(0,10))
        self.toggle_buttons = {}
        for cat in ("base", "expr", "outfit"):
            b = tk.Button(toggles, text=cat.capitalize(), width=8, font=("Helvetica", 10, "bold"),
                          relief="flat", command=lambda c=cat: self._set_active_category(c))
            b.pack(side="left", padx=5)
            self.toggle_buttons[cat] = b
        self._highlight_active_toggle()

        # Preview
        pv = tk.Frame(content, bg="white")
        pv.pack()
        
        tk.Button(pv, text="❮", font=("Arial", 14), width=3, bg="white", relief="flat", 
                  command=lambda: self._cycle_active(-1)).grid(row=0, column=0, padx=10)
        
        self.preview_label_img = tk.Label(pv, bg="white")
        self.preview_label_img.grid(row=0, column=1)
        self.preview_canvas = tk.Canvas(pv, width=DISPLAY_SIZE, height=DISPLAY_SIZE, bg="white", highlightthickness=0)
        # Use label if PIL available, else canvas
        if not PIL_AVAILABLE: self.preview_canvas.grid(row=0, column=1)
            
        tk.Button(pv, text="❯", font=("Arial", 14), width=3, bg="white", relief="flat", 
                  command=lambda: self._cycle_active(1)).grid(row=0, column=2, padx=10)

        # Actions
        action_row = tk.Frame(content, bg="white")
        action_row.pack(side="bottom", pady=(10, 20))
        tk.Button(action_row, text="Save & Play", font=("Helvetica", 12, "bold"), 
                  bg=THEME["primary"], fg="white", relief="flat", padx=20, pady=6, 
                  command=self._submit).pack(side="left", padx=10)

        self._redraw_preview()

    def _get_list(self, cat):
        if cat == "base": return list(self.available_bases.keys()) if self.available_bases else ["amber", "blue"]
        if cat == "expr": return list(self.available_exprs.keys()) if self.available_exprs else ["smile", "wink"]
        return list(self.available_outfits.keys()) if self.available_outfits else ["casual", "armor"]

    def _set_active_category(self, cat):
        self.active_category = cat
        self._highlight_active_toggle()
        self._redraw_preview() # Redraw when category changes to reflect current state

    def _highlight_active_toggle(self):
        for c, b in self.toggle_buttons.items():
            if c == self.active_category: b.config(bg=THEME["primary"], fg="white")
            else: b.config(bg=THEME["bg"], fg=THEME["muted"])

    def _cycle_active(self, delta):
        lst = self._get_list(self.active_category)
        if not lst: 
            # If the list is empty, default to a fallback key so the logic doesn't crash, 
            # and set the key to the fallback if it's currently empty.
            if self.active_category == "base": self.color_key = "default"
            elif self.active_category == "expr": self.expr_key = "smile"
            else: self.outfit_key = "casual"
            self._redraw_preview()
            return
            
        cur = getattr(self, f"{self.active_category}_key", "")
        try: i = lst.index(cur)
        except: i = 0
        i = (i + delta) % len(lst)
        new_val = lst[i]
        
        if self.active_category == "base": self.color_key = new_val
        elif self.active_category == "expr": self.expr_key = new_val
        else: self.outfit_key = new_val
        self._redraw_preview()

    def _submit(self):
        name = self.username_var.get().strip() or "Player"
        self.popup.destroy()
        if self.on_done:
            self.on_done({
                "username": name,
                "color": self.color_key, # Changed from 'base' to 'color' to match draw_profile_avatar expectations
                "expression": self.expr_key,
                "outfit": self.outfit_key
            })

    def _redraw_preview(self):
        # Temp profile for drawing
        prof = {"color": self.color_key, "expression": self.expr_key, "outfit": self.outfit_key}
        if PIL_AVAILABLE:
            # Replicate drawing:
            base_p = self.available_bases.get(self.color_key)
            expr_p = self.available_exprs.get(self.expr_key)
            outfit_p = self.available_outfits.get(self.outfit_key)
            
            base_im = load_and_prepare_image(base_p)
            expr_im = load_and_prepare_image(expr_p)
            outfit_im = load_and_prepare_image(outfit_p)
            # Use the global compose_layers which is designed to stack Base -> Outfit -> Expression
            comp = compose_layers(base_im, outfit_im, expr_im)
            
            if comp:
                tkimg = ImageTk.PhotoImage(comp)
                self.tk_cache["prev"] = tkimg
                self.preview_label_img.config(image=tkimg)
                self.preview_canvas.grid_remove()
                self.preview_label_img.grid()
                return

        # Fallback
        self.preview_label_img.grid_remove()
        self.preview_canvas.grid()
        draw_profile_avatar(self.preview_canvas, prof, DISPLAY_SIZE, DISPLAY_SIZE)

# ---------------------------------------------------------
# MAIN APP
# ---------------------------------------------------------
class MainApp:
    def __init__(self, root, profile=None):
        self.root = root
        self.profile = profile or {}
        self.root.title("WorDuel")
        self.root.configure(bg=THEME["bg"])
        try: root.state('zoomed')
        except: pass

        self.frame = tk.Frame(root, bg=THEME["bg"])
        self.frame.pack(fill="both", expand=True)

        # Header
        header = tk.Frame(self.frame, bg=THEME["bg"])
        header.pack(pady=(20, 10))
        tk.Label(header, text="WorDuel", bg=THEME["bg"], fg=THEME["primary"], font=("Helvetica", 32, "bold")).pack()

        # Nav
        nav = tk.Frame(self.frame, bg=THEME["bg"])
        nav.pack(pady=10)
        self.btn_std = tk.Button(nav, text="Single Player", font=("Helvetica", 12, "bold"), width=15, height=2,
                  bg="white", relief="flat", command=self.start_standard_flow)
        self.btn_std.grid(row=0, column=0, padx=10)
        
        self.btn_duel = tk.Button(nav, text="Duel Mode", font=("Helvetica", 12, "bold"), width=15, height=2,
                  bg="white", relief="flat", command=self.open_duel_options)
        self.btn_duel.grid(row=0, column=1, padx=10)

        # Main Content
        self.center_frame = tk.Frame(self.frame, bg=THEME["bg"])
        self.center_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.link_entry = None
        self._main_avatar_tk = None # Keep ref

        # Show creator first
        InlinePopupCharacterCreator(self.center_frame, on_done=self.on_profile_created)

    def on_profile_created(self, profile):
        self.profile = profile
        # MODIFICATION: Removed temporary greeting and call setup_main_menu directly
        self.setup_main_menu()

    def setup_main_menu(self):
        for w in self.center_frame.winfo_children(): w.destroy()
        
        # Link Input
        link_frame = tk.Frame(self.center_frame, bg=THEME["bg"])
        link_frame.pack(pady=(10, 20))
        tk.Label(link_frame, text="Have a duel link?", bg=THEME["bg"], fg=THEME["muted"]).pack(anchor="w", padx=5)
        
        inp_box = tk.Frame(link_frame, bg="white", padx=5, pady=5)
        inp_box.pack()
        self.link_entry = tk.Entry(inp_box, width=50, relief="flat", font=("Helvetica", 10))
        self.link_entry.pack(side="left", padx=5)
        tk.Button(inp_box, text="JOIN", bg=THEME["primary"], fg="white", font=("Helvetica", 9, "bold"), 
                  relief="flat", command=self._join_from_box).pack(side="left")

        # Avatar Display
        if self.profile:
            prof_frame = tk.Frame(self.center_frame, bg=THEME["bg"])
            prof_frame.pack(pady=10)
            
            canv = tk.Canvas(prof_frame, width=200, height=200, bg=THEME["bg"], highlightthickness=0)
            canv.pack()
            draw_profile_avatar(canv, self.profile, 200, 200)
            
            # MODIFICATION: Display "Haii <username>" here.
            username = self.profile.get("username", "Player")
            tk.Label(prof_frame, text=f"Haii {username}", 
                     bg=THEME["bg"], fg=THEME["text_main"], font=("Helvetica", 14, "bold")).pack(pady=5)

    def start_standard_flow(self):
        for w in self.center_frame.winfo_children(): w.destroy()
        tk.Label(self.center_frame, text="How many letters?", bg=THEME["bg"], fg=THEME["muted"], font=("Helvetica", 14)).pack(pady=15)
        
        len_var = tk.IntVar(value=5)
        spin = tk.Spinbox(self.center_frame, from_=3, to=7, textvariable=len_var, width=5, font=("Helvetica", 16), relief="flat", justify="center")
        spin.pack(pady=10, ipady=5)
        
        tk.Button(self.center_frame, text="START GAME", bg=THEME["primary"], fg="white", 
                  font=("Helvetica", 12, "bold"), relief="flat", padx=20, pady=10,
                  command=lambda: self._start_standard(len_var.get())).pack(pady=20)
        
        tk.Button(self.center_frame, text="Back", bg=THEME["bg"], fg=THEME["muted"], relief="flat", 
                  command=self.setup_main_menu).pack()

    def _start_standard(self, length):
        secret = random.choice(WORDS_BY_LENGTH.get(length, WORDS_BY_LENGTH[5]))
        # Pass profile so standard game can show avatar on win
        SingleGameWindow(self.root, secret, length, self.profile)

    def open_duel_options(self):
        for w in self.center_frame.winfo_children(): w.destroy()
        
        opt_frame = tk.Frame(self.center_frame, bg=THEME["bg"])
        opt_frame.pack(pady=20)
        
        tk.Button(opt_frame, text="Local Duel (Same PC)", width=30, height=2, bg="white", relief="flat", font=("Helvetica", 11),
                  command=self.duel_same_device_setup).pack(pady=10)
        
        tk.Button(opt_frame, text="Create Link (Send to Friend)", width=30, height=2, bg="white", relief="flat", font=("Helvetica", 11),
                  command=self.duel_share_link_setup).pack(pady=10)
        
        tk.Button(self.center_frame, text="Back", bg=THEME["bg"], fg=THEME["muted"], relief="flat", 
                  command=self.setup_main_menu).pack()

    # ---------------------------
    # SAME DEVICE DUEL LOGIC
    # ---------------------------
    def duel_same_device_setup(self):
        # ... setup UI same as before, simplified ...
        for w in self.center_frame.winfo_children(): w.destroy()
        tk.Label(self.center_frame, text="Local Duel Setup", bg=THEME["bg"], font=("Helvetica", 14, "bold")).pack(pady=10)
        
        # Simple inputs container
        f = tk.Frame(self.center_frame, bg=THEME["bg"])
        f.pack(pady=10)
        
        # P1
        tk.Label(f, text="Player 1 Secret:", bg=THEME["bg"]).grid(row=0, column=0, padx=10, pady=5)
        p1_word = tk.Entry(f, show="*")
        p1_word.grid(row=0, column=1, padx=10, pady=5)
        
        # P2
        tk.Label(f, text="Player 2 Secret:", bg=THEME["bg"]).grid(row=1, column=0, padx=10, pady=5)
        p2_word = tk.Entry(f, show="*")
        p2_word.grid(row=1, column=1, padx=10, pady=5)

        tk.Button(self.center_frame, text="FIGHT!", bg=THEME["primary"], fg="white", font=("Helvetica", 12, "bold"), relief="flat",
                  command=lambda: self._start_same_device_duel(p1_word.get().strip(), p2_word.get().strip())).pack(pady=20)

    def _start_same_device_duel(self, p1_w, p2_w):
        p1_w = p1_w.lower()
        p2_w = p2_w.lower()
        
        if not p1_w.isalpha() or not p2_w.isalpha(): 
            messagebox.showerror("Oops", "Words must be letters only")
            return
            
        # Validate secret words against the dictionary
        if VALID_WORDS and (p1_w not in VALID_WORDS or p2_w not in VALID_WORDS):
            messagebox.showerror("Oops", "Both secret words must be valid words from the dictionary.")
            return

        # Basic validation passed
        for w in self.center_frame.winfo_children(): w.destroy()
        
        # Containers
        container = tk.Frame(self.center_frame, bg=THEME["bg"])
        container.pack(fill="both", expand=True)
        
        self.results = {"P1": None, "P2": None}
        self.finished = {"P1": False, "P2": False}
        self.p1_secret = p1_w
        self.p2_secret = p2_w

        # Panels
        left = tk.Frame(container, bg=THEME["bg"], padx=10); left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(container, bg=THEME["bg"], padx=10); right.pack(side="right", fill="both", expand=True)
        
        # P1 tries to guess P2's word
        p1_name = self.profile.get("username", "Player 1")
        self.panel_p1 = PlayerPanel(left, "P1", p1_name, len(p2_w), p2_w, self._player_finished, self._player_made_guess)
        self.panel_p1.pack()
        # P2 tries to guess P1's word
        self.panel_p2 = PlayerPanel(right, "P2", "Player 2 (Opponent)", len(p1_w), p1_w, self._player_finished, self._player_made_guess)
        self.panel_p2.pack()
        
        self.active = "P1"
        self._apply_turn_state()

    def _apply_turn_state(self):
        # Manage turns
        if self.active == "P1":
            self.panel_p1.enable(not self.finished["P1"])
            self.panel_p2.enable(False)
        else:
            self.panel_p1.enable(False)
            self.panel_p2.enable(not self.finished["P2"])

    def _player_made_guess(self, pid):
        other = "P2" if pid == "P1" else "P1"
        if not self.finished[other]: self.active = other
        self._apply_turn_state()

    def _player_finished(self, pid, attempts, guessed):
        self.results[pid] = (attempts, guessed)
        self.finished[pid] = True
        self.panel_p1.enable(False)
        self.panel_p2.enable(False)
        
        other = "P2" if pid == "P1" else "P1"
        if not self.finished[other]:
            self.active = other
            self._apply_turn_state()
        else:
            # Both finished
            self._show_duel_winner_overlay()

    def _show_duel_winner_overlay(self):
        # Determine winner
        p1_a, p1_g = self.results["P1"]
        p2_a, p2_g = self.results["P2"]
        
        winner_name = "Nobody"
        
        # Logic: Lowest attempts wins, providing they guessed it.
        if p1_g and not p2_g: winner_name = "Player 1"
        elif p2_g and not p1_g: winner_name = "Player 2"
        elif p1_g and p2_g:
            if p1_a < p2_a: winner_name = "Player 1"
            elif p2_a < p1_a: winner_name = "Player 2"
            else: winner_name = "Tie"
        
        # Overlay
        overlay = tk.Frame(self.center_frame, bg="white")
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        card = tk.Frame(overlay, bg=THEME["bg"], padx=40, pady=40)
        card.place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(card, text="DUEL OVER", font=("Helvetica", 24, "bold"), bg=THEME["bg"], fg=THEME["muted"]).pack(pady=10)
        
        # START CHANGE 1: Display Winner Avatar
        if winner_name == "Tie":
            tk.Label(card, text="It's a Tie!", font=("Helvetica", 18), bg=THEME["bg"], fg=THEME["primary"]).pack()
            tk.Label(card, text="🤝", font=("Helvetica", 60), bg=THEME["bg"]).pack(pady=10)
        elif winner_name == "Nobody":
             tk.Label(card, text="Nobody won...", font=("Helvetica", 18), bg=THEME["bg"], fg=THEME["error"]).pack()
             tk.Label(card, text="😭", font=("Helvetica", 60), bg=THEME["bg"]).pack(pady=10)
        else:
            tk.Label(card, text=f"{winner_name} Wins!", font=("Helvetica", 20, "bold"), bg=THEME["bg"], fg=THEME["success"]).pack(pady=10)
            
            # Display Avatar if P1 (local user) won
            if winner_name == "Player 1":
                canv = tk.Canvas(card, width=120, height=120, bg=THEME["bg"], highlightthickness=0)
                canv.pack(pady=10)
                draw_profile_avatar(canv, self.profile, 120, 120)
                self.tk_cache["duel_win_avatar"] = canv # Cache to prevent GC
            # Display a generic placeholder for Player 2
            elif winner_name == "Player 2":
                 tk.Label(card, text="👤", font=("Helvetica", 60), bg=THEME["bg"]).pack(pady=10)
        # END CHANGE 1

        tk.Button(card, text="Back to Menu", bg=THEME["primary"], fg="white", font=("Helvetica", 12), relief="flat",
                  command=self.setup_main_menu).pack(pady=20)

    # ---------------------------
    # LINK DUEL LOGIC
    # ---------------------------
    def duel_share_link_setup(self):
        for w in self.center_frame.winfo_children(): w.destroy()
        tk.Label(self.center_frame, text="Create Challenge Link", bg=THEME["bg"], font=("Helvetica", 14, "bold")).pack(pady=15)
        
        f = tk.Frame(self.center_frame, bg=THEME["bg"])
        f.pack()
        tk.Label(f, text="Your Secret Word:", bg=THEME["bg"]).grid(row=0, column=0, padx=10)
        w_entry = tk.Entry(f, show="*"); w_entry.grid(row=0, column=1)
        
        def generate():
            secret = w_entry.get().strip().lower()
            if not secret.isalpha():
                messagebox.showerror("Error", "Secret must be letters only.")
                return
            
            # Validate secret word against dictionary
            if VALID_WORDS and secret not in VALID_WORDS:
                messagebox.showerror("Error", "Secret word must be a valid word from the dictionary.")
                return
            
            link = DuelLinkFlow.create_initial_link(len(secret), secret)
            
            # Show link
            top = tk.Toplevel(self.root)
            top.title("Copy Link")
            top.geometry("600x150")
            tk.Label(top, text="Send this link to your friend:").pack(pady=10)
            e = tk.Entry(top, width=80); e.pack(padx=10); e.insert(0, link)
            tk.Button(top, text="Done", command=lambda: [top.destroy(), self.setup_main_menu()]).pack(pady=10)

        tk.Button(self.center_frame, text="Generate Link", bg=THEME["primary"], fg="white", font=("Helvetica", 11, "bold"),
                  relief="flat", command=generate).pack(pady=20)
        tk.Button(self.center_frame, text="Back", command=self.setup_main_menu, relief="flat", bg=THEME["bg"]).pack()

    def _join_from_box(self):
        txt = self.link_entry.get().strip()
        if not txt: return
        
        # 1. Check if Return Payload (Friend played, now telling Host result)
        if "ret:" in txt or "ret%3A" in txt:
             try:
                lr, secB, attB, guessB = DuelLinkFlow.decode_return_link(txt)
                # Host plays now
                
                # Check 1: Validate length of the decoded word
                if len(secB) != lr: 
                    messagebox.showerror("Error", "Link corrupted: Word length mismatch.")
                    return
                # Check 2: Validate the secret word itself
                if VALID_WORDS and secB not in VALID_WORDS:
                    messagebox.showerror("Error", "Link contains an invalid secret word. Cannot proceed.")
                    return
                
                def on_host_finish(attA, guessA):
                    # Compare
                    winner = "Tie"
                    if guessA and not guessB: winner = "You"
                    elif guessB and not guessA: winner = "Friend"
                    elif guessA and guessB:
                        if attA < attB: winner = "You"
                        elif attB < attA: winner = "Friend"
                    
                    # Show result overlay
                    msg = f"Winner: {winner}\n(You: {attA if guessA else 'X'}, Friend: {attB if guessB else 'X'})"
                    messagebox.showinfo("Duel Result", msg)
                
                SingleGameWindow(self.root, secB, lr, self.profile, title="Duel: Your Turn", on_finish=on_host_finish)
                return
             except Exception as e:
                 messagebox.showerror("Error", f"Invalid Return Link: {e}")
                 return

        # 2. Check if Initial Load (Friend joining Host)
        try:
            length, secretA = DuelLinkFlow.decode_initial_link(txt)
            
            # Check 1: Validate the secret word itself
            if VALID_WORDS and secretA not in VALID_WORDS:
                messagebox.showerror("Error", "Link contains an invalid secret word. Cannot proceed.")
                return
            
            def on_friend_finish(attB, guessB):
                # Friend finished guessing Host's word.
                # Now Friend creates return link with their stats + their secret
                
                # Popup to ask for secret
                pop = tk.Toplevel(self.root)
                pop.title("Round 2 Setup")
                pop.geometry("400x200")
                tk.Label(pop, text="You finished! Now enter a secret for your friend:").pack(pady=10)
                e_sec = tk.Entry(pop); e_sec.pack(pady=5)
                
                def make_ret():
                    s = e_sec.get().strip().lower()
                    if not s.isalpha() or len(s) != length: 
                        messagebox.showerror("Error", f"Word must be {length} letters."); return
                    
                    # Validate return secret word against dictionary
                    if VALID_WORDS and s not in VALID_WORDS:
                        messagebox.showerror("Error", "Secret word must be a valid word from the dictionary.")
                        return
                    
                    ret_link = DuelLinkFlow.create_return_link(length, s, attB, guessB)
                    
                    # Show return link
                    top2 = tk.Toplevel(self.root)
                    top2.title("Send Back")
                    top2.geometry("600x150")
                    tk.Label(top2, text="Send this back to the Host:").pack(pady=10)
                    e2 = tk.Entry(top2, width=80); e2.pack(padx=10); e2.insert(0, ret_link)
                    pop.destroy()
                    
                tk.Button(pop, text="Create Return Link", command=make_ret).pack(pady=10)

            SingleGameWindow(self.root, secretA, length, self.profile, title="Duel: Guess Host's Word", on_finish=on_friend_finish)
        except Exception as e:
            messagebox.showerror("Error", "Invalid Link")

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()