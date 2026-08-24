# KDPEasy Activity Creator

Part of the KDPEasy Suite — free/paid tools for KDP creators.

Generate a print-ready activity book (Word Search, Sudoku, Maze) in seconds, complete with an answer key section.

## Features (v1)
- Any KDP trim size preset: Letter, Square (8.5x8.5), 8x10, 6x9, A4, A5 — portrait or landscape
- 4 preset color themes, or any custom color
- **Word Search**: type your own word bank (any theme/niche), choose number of puzzles, words per puzzle, grid size (12/15/18), and an optional "harder mode" (backwards + diagonal words)
- **Sudoku**: choose number of puzzles and difficulty (Easy/Medium/Hard), each a freshly generated valid puzzle
- **Maze**: choose number of mazes and size (Small 10x10 / Medium 15x15 / Large 20x20), each solvable start-to-finish
- Mix and match any combination of the three activity types in one book
- Optional answer key section at the end (word search solutions highlighted, sudoku full solution, maze solution path traced)
- Cover page with optional photo (Fit/Fill style, same pattern as Calendar/Journal Creator)
- On-screen preview before downloading, rendered from the actual PDF via PyMuPDF
- Optional PNG export: each page as a separate 300 DPI PNG, packaged into one ZIP

## Planned for v2
- Crossword puzzles (needs a word-placement + clue algorithm)
- Hidden Objects (needs AI image generation or sprite compositing)
- Rebus puzzles
- Themed decorative borders per activity type

## Stack
Streamlit + fpdf2 + PyMuPDF + Pillow (pure Python, no system dependencies, no paid API — runs free on Streamlit Cloud). All puzzle generation (word search placement, sudoku backtracking solver, maze DFS + BFS solver) is pure algorithmic Python, no AI involved.

Password-protected, same pattern as the rest of the KDPEasy Suite. Passwords are checked against `PASSWORD_EXPIRY` in `app.py` — a value of `None` means permanent access, a date means the password stops working after that day (used for time-limited trials).
