🎮 WorDuel: The Ultimate Word Challenge
WorDuel is a feature-rich, competitive Wordle-style game built entirely with Python and the Tkinter library. It features a fun character creator, standard single-player gameplay, and a unique Duel Mode that supports both local head-to-head play and link-based asynchronous challenges with friends!

✨ Features
Custom Character Creator: Personalize your profile with a name and a customizable avatar (color, expression, and outfit).

Single Player Mode: Traditional Wordle experience where you choose the word length (3 to 7 letters) and guess a randomly chosen secret word.

Local Duel Mode: Two players on the same PC enter secret words and race to see who can guess their opponent's word in the fewest attempts.

Link Duel Mode: Challenge friends remotely using shareable, encrypted links.
      1) Host: Creates a link containing their secret word.
      2) Friend: Clicks the link, plays the game, enters their own secret word, and generates a Return Link.
      3) Host: Clicks the Return Link to play the friend's word. The winner is determined based on the best score (lowest attempts).

Visual Feedback: Clear, color-coded grid tiles and a persistent on-screen keyboard to track letter status (Green, Yellow, Grey).

🚀 Setup & Dependencies
To run WorDuel, you need Python and the Pillow library for image handling, especially for the Character Creator and avatar display.
Install Python: Ensure you have Python 3 installed.
Install Pillow:
    Bash
    pip install Pillow
Run the Game: Save the code as a Python file (e.g., worduel.py) and run it from your terminal:
    Bash
    python worduel.py

🕹️ How to Play
1. Character Creation
On first launch, you will be prompted to create your character and enter your desired username.
Use the toggles (Base, Expr, Outfit) and the ❮ / ❯ buttons to cycle through available avatar options.
Click Save & Play to proceed to the main menu.

2. Single Player
From the main menu, click Single Player. Select the desired word length (3-7 letters). Click START GAME and begin guessing!
BASIC RULES:
Green: Correct letter, correct position.
Yellow: Correct letter, wrong position.
Grey: Letter is not in the word.

3. Duel Mode
Click Duel Mode on the main menu to choose between:
A. Local Duel (Same PC)
Player 1 and Player 2 enter a secret word for the other to guess.Click FIGHT!
The game alternates turns between Player 1 (you) and Player 2 (opponent).The first player to guess their opponent's word, or the player who uses fewer attempts, is the winner.

B. Link Duel (Async Challenge)
Create Link: Enter your secret word and click Generate Link. Copy the generated link and send it to your friend.
Join Link: If you receive a link from a friend, paste it into the "Have a duel link?" box on the main menu and click JOIN.

Hope ya have fun :D

If it's an Initial Link, you will guess your friend's word.

If it's a Return Link, you will guess your friend's word, and the game will immediately calculate and display the winner based on both players' scores.
