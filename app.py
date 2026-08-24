import streamlit as st
import fitz
import zipfile
import random
import string
from collections import deque
from datetime import date
from fpdf import FPDF
from io import BytesIO
from PIL import Image

st.set_page_config(page_title="KDPEasy Activity Creator", page_icon="🧩", layout="centered")

# Password -> expiry date, or None for permanent access (paying customers).
PASSWORD_EXPIRY = {
    "KDPACT2026": None,
}

MARGIN = 0.5
TITLE_H = 0.5
GAP = 0.15

PAGE_SIZES = {
    "Letter (8.5 x 11 in)": (8.5, 11.0),
    "Square (8.5 x 8.5 in)": (8.5, 8.5),
    "8 x 10 in": (8.0, 10.0),
    "6 x 9 in": (6.0, 9.0),
    "A4": (8.27, 11.69),
    "A5": (5.83, 8.27),
}

THEMES = {
    "Indigo Classic": {"primary": (79, 70, 229), "weekend": (238, 242, 255), "grid": (209, 213, 219), "text": (31, 41, 55)},
    "Emerald Fresh":  {"primary": (16, 185, 129), "weekend": (209, 250, 229), "grid": (209, 213, 219), "text": (31, 41, 55)},
    "Sunset Warm":    {"primary": (234, 88, 12),  "weekend": (255, 237, 213), "grid": (209, 213, 219), "text": (31, 41, 55)},
    "Mono Minimal":   {"primary": (31, 41, 55),   "weekend": (243, 244, 246), "grid": (209, 213, 219), "text": (31, 41, 55)},
}

CUSTOM_CSS = """
<style>
:root {
    color-scheme: light;
}
.stApp {
    background: linear-gradient(135deg, #eef2ff 0%, #ffffff 60%);
}
.kdp-card {
    background: white;
    border-radius: 16px;
    padding: 2rem 2rem 1.5rem;
    box-shadow: 0 4px 24px rgba(79, 70, 229, 0.08);
    margin-bottom: 1.5rem;
}
h1, h2, h3 { color: #4f46e5; }
.stButton>button, .stDownloadButton>button {
    background-color: #10b981;
    color: white;
    border-radius: 10px;
    border: none;
    padding: 0.6rem 1.4rem;
    font-weight: 600;
}
.stButton>button:hover, .stDownloadButton>button:hover {
    background-color: #059669;
    color: white;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def check_password() -> bool:
    if st.session_state.get("authed"):
        return True
    st.markdown('<div class="kdp-card">', unsafe_allow_html=True)
    st.title("🧩 KDPEasy Activity Creator")
    pw = st.text_input("Enter access password", type="password")
    if st.button("Unlock"):
        if pw in PASSWORD_EXPIRY:
            expiry = PASSWORD_EXPIRY[pw]
            if expiry is None or date.today() <= expiry:
                st.session_state["authed"] = True
                st.rerun()
            else:
                st.error("This trial password has expired. Please reach out to get full access.")
        else:
            st.error("Incorrect password.")
    st.markdown('</div>', unsafe_allow_html=True)
    return False


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def tint_toward_white(color, amount=0.85):
    r, g, b = color
    return (
        int(r + (255 - r) * amount),
        int(g + (255 - g) * amount),
        int(b + (255 - b) * amount),
    )


def prepare_photo(uploaded_file, box_w, box_h, fill_mode):
    uploaded_file.seek(0)
    img = Image.open(uploaded_file).convert("RGB")
    target_ratio = box_w / box_h
    img_ratio = img.width / img.height

    if fill_mode:
        if img_ratio > target_ratio:
            new_w = int(img.height * target_ratio)
            left = (img.width - new_w) // 2
            img = img.crop((left, 0, left + new_w, img.height))
        else:
            new_h = int(img.width / target_ratio)
            top = (img.height - new_h) // 2
            img = img.crop((0, top, img.width, top + new_h))
        return img, box_w, box_h
    else:
        if img_ratio > target_ratio:
            draw_w = box_w
            draw_h = box_w / img_ratio
        else:
            draw_h = box_h
            draw_w = box_h * img_ratio
        return img, draw_w, draw_h


# ---------- Word Search ----------

WS_DIRECTIONS_EASY = [(0, 1), (1, 0)]
WS_DIRECTIONS_HARD = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def generate_word_search(words, grid_size, hard_mode=False, max_attempts=300):
    words = [w.strip().upper().replace(" ", "") for w in words if w.strip()]
    words = [w for w in words if w.isalpha() and len(w) <= grid_size]
    words = sorted(set(words), key=len, reverse=True)
    grid = [[None] * grid_size for _ in range(grid_size)]
    placements = {}
    skipped = []
    directions = WS_DIRECTIONS_HARD if hard_mode else WS_DIRECTIONS_EASY

    for word in words:
        placed = False
        for _ in range(max_attempts):
            dr, dc = random.choice(directions)
            r0 = random.randint(0, grid_size - 1)
            c0 = random.randint(0, grid_size - 1)
            r1 = r0 + dr * (len(word) - 1)
            c1 = c0 + dc * (len(word) - 1)
            if not (0 <= r1 < grid_size and 0 <= c1 < grid_size):
                continue
            cells = [(r0 + dr * i, c0 + dc * i) for i in range(len(word))]
            if all(grid[r][c] in (None, ch) for (r, c), ch in zip(cells, word)):
                for (r, c), ch in zip(cells, word):
                    grid[r][c] = ch
                placements[word] = cells
                placed = True
                break
        if not placed:
            skipped.append(word)

    for r in range(grid_size):
        for c in range(grid_size):
            if grid[r][c] is None:
                grid[r][c] = random.choice(string.ascii_uppercase)

    return grid, placements, skipped


def draw_word_search_page(pdf, page_w, page_h, theme, title, grid, word_list, show_solution, placements):
    primary = theme["primary"]
    text_color = theme["text"]
    grid_color = theme["grid"]

    pdf.add_page()
    pdf.set_line_width(0.01)
    pdf.set_fill_color(*primary)
    pdf.rect(MARGIN, MARGIN, page_w - 2 * MARGIN, TITLE_H, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16 if page_w < 7 else 20)
    pdf.set_xy(MARGIN, MARGIN)
    pdf.cell(page_w - 2 * MARGIN, TITLE_H, title, align="C")

    grid_size = len(grid)
    content_w = page_w - 2 * MARGIN
    cell = content_w / grid_size
    grid_top = MARGIN + TITLE_H + GAP

    if show_solution:
        highlight = tint_toward_white(primary, 0.6)
        pdf.set_fill_color(*highlight)
        for cells in placements.values():
            for (r, c) in cells:
                x = MARGIN + c * cell
                y = grid_top + r * cell
                pdf.rect(x, y, cell, cell, "F")

    font_size = max(8, min(20, cell * 45))
    pdf.set_draw_color(*grid_color)
    pdf.set_font("Helvetica", "B", font_size)
    pdf.set_text_color(*text_color)
    for r in range(grid_size):
        for c in range(grid_size):
            x = MARGIN + c * cell
            y = grid_top + r * cell
            pdf.rect(x, y, cell, cell, "D")
            pdf.set_xy(x, y + cell * 0.2)
            pdf.cell(cell, cell * 0.6, grid[r][c], align="C")

    list_top = grid_top + grid_size * cell + 0.2
    pdf.set_text_color(*primary)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(MARGIN, list_top)
    pdf.cell(content_w, 0.25, "Find these words:", align="L")
    pdf.set_text_color(*text_color)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(MARGIN, list_top + 0.28)
    pdf.multi_cell(content_w, 0.22, "   ".join(word_list), align="L")


# ---------- Sudoku ----------

SUDOKU_REMOVE = {"Easy": 36, "Medium": 46, "Hard": 54}


def generate_full_sudoku():
    grid = [[0] * 9 for _ in range(9)]

    def is_valid(r, c, val):
        for i in range(9):
            if grid[r][i] == val or grid[i][c] == val:
                return False
        br, bc = 3 * (r // 3), 3 * (c // 3)
        for i in range(br, br + 3):
            for j in range(bc, bc + 3):
                if grid[i][j] == val:
                    return False
        return True

    def solve(pos=0):
        if pos == 81:
            return True
        r, c = divmod(pos, 9)
        nums = list(range(1, 10))
        random.shuffle(nums)
        for num in nums:
            if is_valid(r, c, num):
                grid[r][c] = num
                if solve(pos + 1):
                    return True
                grid[r][c] = 0
        return False

    solve()
    return grid


def make_sudoku_puzzle(full_grid, difficulty):
    puzzle = [row[:] for row in full_grid]
    cells = [(r, c) for r in range(9) for c in range(9)]
    random.shuffle(cells)
    for r, c in cells[:SUDOKU_REMOVE.get(difficulty, 46)]:
        puzzle[r][c] = 0
    return puzzle


def draw_sudoku_page(pdf, page_w, page_h, theme, title, grid):
    primary = theme["primary"]
    text_color = theme["text"]

    pdf.add_page()
    pdf.set_line_width(0.01)
    pdf.set_fill_color(*primary)
    pdf.rect(MARGIN, MARGIN, page_w - 2 * MARGIN, TITLE_H, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16 if page_w < 7 else 20)
    pdf.set_xy(MARGIN, MARGIN)
    pdf.cell(page_w - 2 * MARGIN, TITLE_H, title, align="C")

    content_w = page_w - 2 * MARGIN
    avail_h = page_h - MARGIN - (MARGIN + TITLE_H + GAP)
    size = min(content_w, avail_h)
    cell = size / 9
    x0 = MARGIN + (content_w - size) / 2
    y0 = MARGIN + TITLE_H + GAP

    pdf.set_text_color(*text_color)
    pdf.set_font("Helvetica", "", max(10, min(20, cell * 45)))
    for r in range(9):
        for c in range(9):
            x = x0 + c * cell
            y = y0 + r * cell
            pdf.set_draw_color(180, 180, 180)
            pdf.set_line_width(0.008)
            pdf.rect(x, y, cell, cell, "D")
            val = grid[r][c]
            if val:
                pdf.set_xy(x, y + cell * 0.18)
                pdf.cell(cell, cell * 0.6, str(val), align="C")

    pdf.set_draw_color(*primary)
    pdf.set_line_width(0.03)
    for i in range(0, 10, 3):
        pdf.line(x0 + i * cell, y0, x0 + i * cell, y0 + size)
        pdf.line(x0, y0 + i * cell, x0 + size, y0 + i * cell)
    pdf.set_line_width(0.01)


# ---------- Maze ----------

MAZE_DIRS = [("N", 0, -1), ("S", 0, 1), ("E", 1, 0), ("W", -1, 0)]
MAZE_OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
MAZE_SIZES = {"Small": (10, 10), "Medium": (15, 15), "Large": (20, 20)}


def generate_maze(width, height):
    walls = {(x, y): {"N": True, "S": True, "E": True, "W": True} for x in range(width) for y in range(height)}
    visited = {(0, 0)}
    stack = [(0, 0)]
    while stack:
        x, y = stack[-1]
        dirs = MAZE_DIRS[:]
        random.shuffle(dirs)
        moved = False
        for d, dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                walls[(x, y)][d] = False
                walls[(nx, ny)][MAZE_OPPOSITE[d]] = False
                visited.add((nx, ny))
                stack.append((nx, ny))
                moved = True
                break
        if not moved:
            stack.pop()
    walls[(0, 0)]["W"] = False
    walls[(width - 1, height - 1)]["E"] = False
    return walls


def solve_maze(walls, width, height):
    start, end = (0, 0), (width - 1, height - 1)
    queue = deque([start])
    came_from = {start: None}
    while queue:
        cur = queue.popleft()
        if cur == end:
            break
        x, y = cur
        for d, dx, dy in MAZE_DIRS:
            nxt = (x + dx, y + dy)
            if not walls[(x, y)][d] and 0 <= nxt[0] < width and 0 <= nxt[1] < height:
                if nxt not in came_from:
                    came_from[nxt] = cur
                    queue.append(nxt)
    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = came_from.get(cur)
    path.reverse()
    return path


def draw_maze_page(pdf, page_w, page_h, theme, title, walls, width, height, solution_path=None):
    primary = theme["primary"]

    pdf.add_page()
    pdf.set_line_width(0.02)
    pdf.set_fill_color(*primary)
    pdf.rect(MARGIN, MARGIN, page_w - 2 * MARGIN, TITLE_H, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16 if page_w < 7 else 20)
    pdf.set_xy(MARGIN, MARGIN)
    pdf.cell(page_w - 2 * MARGIN, TITLE_H, title, align="C")

    content_w = page_w - 2 * MARGIN
    avail_h = page_h - MARGIN - (MARGIN + TITLE_H + GAP)
    cell = min(content_w / width, avail_h / height)
    maze_w = cell * width
    maze_h = cell * height
    x0 = MARGIN + (content_w - maze_w) / 2
    y0 = MARGIN + TITLE_H + GAP

    pdf.set_draw_color(31, 41, 55)
    pdf.set_line_width(0.02)
    for x in range(width):
        for y in range(height):
            cx = x0 + x * cell
            cy = y0 + y * cell
            w = walls[(x, y)]
            if w["N"]:
                pdf.line(cx, cy, cx + cell, cy)
            if w["S"]:
                pdf.line(cx, cy + cell, cx + cell, cy + cell)
            if w["W"]:
                pdf.line(cx, cy, cx, cy + cell)
            if w["E"]:
                pdf.line(cx + cell, cy, cx + cell, cy + cell)

    if solution_path:
        pdf.set_draw_color(*primary)
        pdf.set_line_width(0.03)
        pts = [(x0 + (x + 0.5) * cell, y0 + (y + 0.5) * cell) for x, y in solution_path]
        for i in range(len(pts) - 1):
            pdf.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
    pdf.set_line_width(0.01)


# ---------- Assembler ----------

def build_activity_pdf(page_w, page_h, theme,
                        include_cover, cover_title, cover_photo, photo_fill,
                        ws_enabled, ws_word_bank, ws_num_puzzles, ws_words_per_puzzle, ws_grid_size, ws_hard_mode,
                        su_enabled, su_num_puzzles, su_difficulty,
                        mz_enabled, mz_num_mazes, mz_size,
                        show_answers):
    pdf = FPDF(unit="in", format=(page_w, page_h))
    pdf.set_auto_page_break(False)
    primary = theme["primary"]

    if include_cover:
        pdf.add_page()
        if cover_photo is not None:
            pil_img, draw_w, draw_h = prepare_photo(cover_photo, page_w, page_h, photo_fill)
            offset_x = (page_w - draw_w) / 2
            offset_y = (page_h - draw_h) / 2
            pdf.image(pil_img, x=offset_x, y=offset_y, w=draw_w, h=draw_h)
            if cover_title:
                band_h = 1.1 if page_h >= 8 else 0.85
                pdf.set_fill_color(*primary)
                pdf.rect(0, page_h - band_h, page_w, band_h, "F")
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Helvetica", "B", 26 if page_w < 7 else 30)
                pdf.set_xy(0.3, page_h - band_h + (band_h - 0.5) / 2)
                pdf.multi_cell(page_w - 0.6, 0.5, cover_title, align="C")
        elif cover_title:
            pdf.set_fill_color(*primary)
            pdf.rect(0, 0, page_w, page_h, "F")
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 28 if page_w < 7 else 34)
            pdf.set_xy(0.3, page_h / 2 - 0.5)
            pdf.multi_cell(page_w - 0.6, 0.55, cover_title, align="C")

    ws_puzzles = []
    if ws_enabled:
        bank = [w.strip() for w in ws_word_bank.replace(",", "\n").splitlines() if w.strip()]
        for i in range(ws_num_puzzles):
            pool = bank if len(bank) <= ws_words_per_puzzle else random.sample(bank, ws_words_per_puzzle)
            grid, placements, skipped = generate_word_search(pool, ws_grid_size, ws_hard_mode)
            used_words = sorted({w.strip().upper().replace(" ", "") for w in pool} & set(placements.keys()))
            ws_puzzles.append((grid, used_words, placements))
            draw_word_search_page(pdf, page_w, page_h, theme, f"Word Search #{i + 1}", grid, used_words, False, {})

    su_puzzles = []
    if su_enabled:
        for i in range(su_num_puzzles):
            full = generate_full_sudoku()
            puzzle = make_sudoku_puzzle(full, su_difficulty)
            su_puzzles.append((puzzle, full))
            draw_sudoku_page(pdf, page_w, page_h, theme, f"Sudoku #{i + 1} ({su_difficulty})", puzzle)

    mz_puzzles = []
    if mz_enabled:
        dims = MAZE_SIZES[mz_size]
        for i in range(mz_num_mazes):
            walls = generate_maze(*dims)
            path = solve_maze(walls, *dims)
            mz_puzzles.append((walls, path, dims))
            draw_maze_page(pdf, page_w, page_h, theme, f"Maze #{i + 1}", walls, *dims)

    if show_answers and (ws_puzzles or su_puzzles or mz_puzzles):
        pdf.add_page()
        pdf.set_fill_color(*primary)
        pdf.rect(0, 0, page_w, page_h, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 28 if page_w < 7 else 34)
        pdf.set_xy(0.3, page_h / 2 - 0.3)
        pdf.cell(page_w - 0.6, 0.6, "ANSWER KEY", align="C")

        for i, (grid, used_words, placements) in enumerate(ws_puzzles):
            draw_word_search_page(pdf, page_w, page_h, theme, f"Word Search #{i + 1} - Answer", grid, used_words, True, placements)
        for i, (puzzle, full) in enumerate(su_puzzles):
            draw_sudoku_page(pdf, page_w, page_h, theme, f"Sudoku #{i + 1} - Answer", full)
        for i, (walls, path, dims) in enumerate(mz_puzzles):
            draw_maze_page(pdf, page_w, page_h, theme, f"Maze #{i + 1} - Answer", walls, *dims, solution_path=path)

    pdf_bytes = pdf.output()
    return BytesIO(bytes(pdf_bytes))


if check_password():
    st.markdown('<div class="kdp-card">', unsafe_allow_html=True)
    st.title("🧩 KDPEasy Activity Creator")
    st.caption("Create a print-ready activity book (Word Search, Sudoku, Maze) for KDP in seconds.")

    col1, col2 = st.columns(2)
    with col1:
        page_size_label = st.selectbox("Page size", list(PAGE_SIZES.keys()))
        orientation = st.radio("Orientation", ["Portrait", "Landscape"], index=0, horizontal=True)
    with col2:
        theme_mode = st.radio("Color theme", ["Preset", "Custom color"], index=0, horizontal=True)
        if theme_mode == "Preset":
            theme_name = st.selectbox("Choose a preset", list(THEMES.keys()))
            theme = THEMES[theme_name]
        else:
            custom_hex = st.color_picker("Pick any color", "#4f46e5")
            primary_rgb = hex_to_rgb(custom_hex)
            theme = {
                "primary": primary_rgb,
                "weekend": tint_toward_white(primary_rgb, 0.85),
                "grid": (209, 213, 219),
                "text": (31, 41, 55),
            }

    page_w, page_h = PAGE_SIZES[page_size_label]
    if orientation == "Landscape":
        page_w, page_h = page_h, page_w

    include_cover = st.checkbox("Include a cover page", value=True)
    cover_title = ""
    cover_photo = None
    photo_fill = False
    if include_cover:
        cover_title = st.text_input("Cover page title", value="ACTIVITY BOOK")
        cover_photo = st.file_uploader("Cover photo (optional, fills the whole cover page)", type=["png", "jpg", "jpeg"], key="cover_photo")
        if cover_photo is not None:
            fit_choice = st.radio(
                "Cover photo style",
                ["Fit — show the full photo, may add white bars (recommended for portrait photos)",
                 "Fill — crop to fill the page, no white bars (best for landscape/square photos)"],
                index=0,
            )
            photo_fill = fit_choice.startswith("Fill")
            cover_prev_img, _, _ = prepare_photo(cover_photo, page_w, page_h, photo_fill)
            st.image(cover_prev_img, caption="Cover photo preview", width=220)

    show_answers = st.checkbox("Include an answer key section at the end", value=True)

    st.markdown("### Word Search")
    ws_enabled = st.checkbox("Include Word Search puzzles", value=True)
    ws_word_bank, ws_num_puzzles, ws_words_per_puzzle, ws_grid_size, ws_hard_mode = "", 0, 0, 15, False
    if ws_enabled:
        ws_word_bank = st.text_area("Word bank (one word per line, or comma-separated)", height=100,
                                     placeholder="LION\nTIGER\nELEPHANT\nGIRAFFE\nZEBRA")
        wc1, wc2, wc3 = st.columns(3)
        with wc1:
            ws_num_puzzles = st.number_input("Number of puzzles", min_value=1, max_value=20, value=3)
        with wc2:
            ws_words_per_puzzle = st.number_input("Words per puzzle", min_value=5, max_value=20, value=10)
        with wc3:
            ws_grid_size = st.selectbox("Grid size", [12, 15, 18], index=1)
        ws_hard_mode = st.checkbox("Harder mode (backwards + diagonal words)", value=False)

    st.markdown("### Sudoku")
    su_enabled = st.checkbox("Include Sudoku puzzles", value=True)
    su_num_puzzles, su_difficulty = 0, "Medium"
    if su_enabled:
        sc1, sc2 = st.columns(2)
        with sc1:
            su_num_puzzles = st.number_input("Number of Sudoku puzzles", min_value=1, max_value=30, value=5)
        with sc2:
            su_difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1)

    st.markdown("### Maze")
    mz_enabled = st.checkbox("Include Mazes", value=True)
    mz_num_mazes, mz_size = 0, "Medium"
    if mz_enabled:
        mc1, mc2 = st.columns(2)
        with mc1:
            mz_num_mazes = st.number_input("Number of mazes", min_value=1, max_value=20, value=3)
        with mc2:
            mz_size = st.selectbox("Maze size", list(MAZE_SIZES.keys()), index=1)

    if not (ws_enabled or su_enabled or mz_enabled):
        st.warning("Please enable at least one activity type (Word Search, Sudoku, or Maze).")

    export_png = st.checkbox("Also export as PNG images (zipped, 300 DPI)", value=False)

    if (ws_enabled or su_enabled or mz_enabled) and st.button("Generate Activity Book PDF"):
        pdf_buf = build_activity_pdf(
            page_w, page_h, theme,
            include_cover, cover_title, cover_photo, photo_fill,
            ws_enabled, ws_word_bank, int(ws_num_puzzles), int(ws_words_per_puzzle), int(ws_grid_size), ws_hard_mode,
            su_enabled, int(su_num_puzzles), su_difficulty,
            mz_enabled, int(mz_num_mazes), mz_size,
            show_answers,
        )
        pdf_bytes = pdf_buf.getvalue()
        st.success("Your activity book is ready! Here's a preview before you download:")

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        preview_count = min(2, doc.page_count)
        preview_cols = st.columns(preview_count)
        for i in range(preview_count):
            pix = doc[i].get_pixmap(dpi=110)
            preview_cols[i].image(pix.tobytes("png"), caption=f"Page {i + 1}", use_container_width=True)

        st.download_button(
            "⬇️ Download Activity Book PDF",
            data=pdf_bytes,
            file_name="KDPEasy_Activity_Book.pdf",
            mime="application/pdf",
        )

        if export_png:
            zip_buf = BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for i in range(doc.page_count):
                    pix = doc[i].get_pixmap(dpi=300)
                    zf.writestr(f"{i + 1:04d}.png", pix.tobytes("png"))
            zip_buf.seek(0)
            st.download_button(
                "⬇️ Download PNG Images (ZIP, 300 DPI)",
                data=zip_buf,
                file_name="KDPEasy_Activity_Book_PNG.zip",
                mime="application/zip",
            )

        doc.close()
    st.markdown('</div>', unsafe_allow_html=True)
