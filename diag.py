# diag.py
import os, sys

# 1) PIL availability
try:
    from PIL import Image
    print("PIL available: yes")
except Exception as e:
    print("PIL available: NO -> install with: pip install pillow")
    Image = None

# 2) Where am I running?
cwd = os.getcwd()
print("Working dir:", cwd)

# 3) Where assets are read from in the game
ASSETS_DIR = "assets"
search_dirs = [cwd]
if os.path.isdir(ASSETS_DIR):
    search_dirs.append(os.path.join(cwd, ASSETS_DIR))
print("Search dirs:", search_dirs)

# 4) List png files found
pngs = []
for d in search_dirs:
    try:
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith(".png"):
                full = os.path.join(d, fn)
                pngs.append(full)
    except Exception as e:
        print("Could not list", d, ":", e)

print("PNG files discovered:")
for p in pngs:
    print(" -", p)

# 5) Show which files match prefixes the game expects
bases = [p for p in pngs if os.path.basename(p).lower().startswith("base_")]
exprs = [p for p in pngs if os.path.basename(p).lower().startswith("expr_")]
outfits = [p for p in pngs if os.path.basename(p).lower().startswith("outfit_")]
print("\nMatches by prefix:")
print(" base_ :", bases or "(none)")
print(" expr_ :", exprs or "(none)")
print(" outfit_:", outfits or "(none)")

# 6) If no prefix matches, print suggestions (show top PNG names)
if not (bases or exprs or outfits):
    print("\nNo prefix-matching PNGs found. Common causes:")
    print(" - Files still in a zip; unzip them into this folder or 'assets/'")
    print(" - Filenames need to start with base_, expr_, outfit_ (case-insensitive).")
    print("\nPNG filenames found (helpful hints):")
    for p in pngs[:40]:
        print("  ", os.path.basename(p))

# 7) If PIL available, attempt to open up to 10 files and show sizes
if Image:
    print("\nAttempting to open and read PNGs (first 10):")
    for p in pngs[:10]:
        try:
            im = Image.open(p)
            print(f"  {os.path.basename(p)} -> size={im.size}, mode={im.mode}")
            im.close()
        except Exception as e:
            print(f"  FAILED to open {p}: {e}")

print("\nIf you want I can update the game script to accept your exact filenames automatically.")
print("If you prefer that, paste the exact filenames (case-sensitive) shown above and I will adapt the loader.")
