import streamlit as st
import fitz
import zipfile
import random
import string
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


# Fixed high-contrast look, optimized for black & white KDP interior printing
# (color themes were removed — a colored title band just turns into a gray
# block once printed in B&W, which is how nearly every word search book ships).
THEME = {"primary": (0, 0, 0), "grid": (209, 213, 219), "text": (31, 41, 55)}

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


# ---------- Assembler ----------

def build_activity_pdf(page_w, page_h, theme,
                        include_cover, cover_title, cover_photo, photo_fill,
                        ws_word_bank, ws_num_puzzles, ws_words_per_puzzle, ws_grid_size, ws_hard_mode,
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

    bank = [w.strip() for w in ws_word_bank.replace(",", "\n").splitlines() if w.strip()]
    ws_puzzles = []
    for i in range(ws_num_puzzles):
        pool = bank if len(bank) <= ws_words_per_puzzle else random.sample(bank, ws_words_per_puzzle)
        grid, placements, skipped = generate_word_search(pool, ws_grid_size, ws_hard_mode)
        used_words = sorted({w.strip().upper().replace(" ", "") for w in pool} & set(placements.keys()))
        ws_puzzles.append((grid, used_words, placements))
        draw_word_search_page(pdf, page_w, page_h, theme, f"Word Search #{i + 1}", grid, used_words, False, {})

    if show_answers and ws_puzzles:
        pdf.add_page()
        pdf.set_fill_color(*primary)
        pdf.rect(0, 0, page_w, page_h, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 28 if page_w < 7 else 34)
        pdf.set_xy(0.3, page_h / 2 - 0.3)
        pdf.cell(page_w - 0.6, 0.6, "ANSWER KEY", align="C")

        for i, (grid, used_words, placements) in enumerate(ws_puzzles):
            draw_word_search_page(pdf, page_w, page_h, theme, f"Word Search #{i + 1} - Answer", grid, used_words, True, placements)

    pdf_bytes = pdf.output()
    return BytesIO(bytes(pdf_bytes))


if check_password():
    st.markdown('<div class="kdp-card">', unsafe_allow_html=True)
    st.title("🧩 KDPEasy Activity Creator")
    st.caption("Create a print-ready Word Search activity book for KDP in seconds.")

    col1, col2 = st.columns(2)
    with col1:
        page_size_label = st.selectbox("Page size", list(PAGE_SIZES.keys()))
    with col2:
        orientation = st.radio("Orientation", ["Portrait", "Landscape"], index=0, horizontal=True)

    theme = THEME
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

    st.markdown("### Word Search settings")
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

    bank_preview = [w.strip() for w in ws_word_bank.replace(",", "\n").splitlines() if w.strip()]
    if not bank_preview:
        st.warning("Add at least one word to the word bank to generate a puzzle.")

    export_png = st.checkbox("Also export as PNG images (zipped, 300 DPI)", value=False)

    if bank_preview and st.button("Generate Activity Book PDF"):
        pdf_buf = build_activity_pdf(
            page_w, page_h, theme,
            include_cover, cover_title, cover_photo, photo_fill,
            ws_word_bank, int(ws_num_puzzles), int(ws_words_per_puzzle), int(ws_grid_size), ws_hard_mode,
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
            file_name="KDPEasy_Word_Search_Book.pdf",
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
                file_name="KDPEasy_Word_Search_Book_PNG.zip",
                mime="application/zip",
            )

        doc.close()
    st.markdown('</div>', unsafe_allow_html=True)
