#!/usr/bin/env python3
"""Sum up 18 November 2026's world news in one image.

Draws a 1024x1024 newspaper front page ("THE WORLD TODAY") covering the
seven biggest stories of Wednesday 18 November 2026 and writes it to
/output/entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png).

Two renderers, one layout:
  * Pillow (PIL) when it is importable, with DejaVu fonts.
  * A pure-stdlib fallback (bitmap font + hand-rolled PNG encoder) for the
    make.fun judge sandbox, which runs Python 3.13 with no extra packages
    and no network. The fallback is the image the judge actually sees, so
    it is built to the same geometry as the Pillow version.

Both renderers are fully deterministic: no timestamps, no randomness, no
network, fixed compression. Two runs produce byte-identical files.
"""

import os
import struct
import sys
import zlib

# ---------------------------------------------------------------------------
# The news: Wednesday 18 November 2026 (verified against Reuters / AP /
# NYT / WSJ / BBC reporting via Just Security's Early Edition, 18 Nov 2026,
# plus same-day briefings). Seven stories, plus three "also today" items.
# ---------------------------------------------------------------------------

MASTHEAD = "THE WORLD TODAY"
DATE_LINE = "WEDNESDAY 18 NOVEMBER 2026"
SUB_LINE = "7 stories that defined the day"

STORIES = [
    {
        "num": "1",
        "kicker": "GULF ESCALATION  |  LEAD STORY",
        "headline": "Iran strikes Kuwait, Bahrain after U.S. Qeshm hit",
        "deck": (
            "Tehran says it hit Ali Al Salem Air Base, home to U.S. forces, "
            "after U.S. jets struck a missile site on Qeshm Island."
        ),
        "accent": (178, 34, 24),
        "icon": "burst",
        "lead": True,
    },
    {
        "num": "2",
        "kicker": "UKRAINE WAR",
        "headline": "Ukraine hits Kerch Bridge again",
        "deck": (
            "Drone and missile strikes partly collapse the bridge; road span falls."
        ),
        "accent": (29, 78, 137),
        "icon": "bridge",
    },
    {
        "num": "3",
        "kicker": "DIPLOMACY  |  SHENZHEN",
        "headline": "Xi, Putin meet before Trump talks",
        "deck": (
            "Xi resists protectionism; Putin hits sanctions. Trump joins Thursday."
        ),
        "accent": (192, 138, 30),
        "icon": "summit",
    },
    {
        "num": "4",
        "kicker": "U.S. POLITICS",
        "headline": "Peltola wins Alaska Senate race",
        "deck": (
            "Beats Sen. Dan Sullivan; Democrats take a 56-44 majority."
        ),
        "accent": (15, 118, 110),
        "icon": "ballot",
    },
    {
        "num": "5",
        "kicker": "GAZA CEASEFIRE",
        "headline": "Trump's Board of Peace faults Israel, Hamas",
        "deck": (
            "A U.N. report says both sides failed their commitments. Kahana is speaker."
        ),
        "accent": (90, 60, 140),
        "icon": "dove",
    },
    {
        "num": "6",
        "kicker": "HEALTH  |  DR CONGO",
        "headline": "Ebola in DR Congo passes 11,000 cases",
        "deck": (
            "Over 5,400 dead, the U.N. says; nearly 3 in 4 infected children under five die."
        ),
        "accent": (178, 34, 24),
        "icon": "virus",
    },
    {
        "num": "7",
        "kicker": "HEALTH  |  UNITED STATES",
        "headline": "U.S. loses measles-free status after 26 years",
        "deck": (
            "Over 5,400 cases and 10 deaths, the most since the early 1990s."
        ),
        "accent": (29, 78, 137),
        "icon": "syringe",
    },
]

ALSO_TODAY = (
    "ALSO:  Russian plane crash in Siberia kills 19  |  "
    "Cyclone Xavier hits the Cook Islands  |  "
    "Ethiopia, Eritrea mass troops on border"
)

SOURCE_LINE = (
    "Sources: Reuters, AP, NYT, WSJ, BBC  |  Events of Wednesday 18 November 2026"
)

W, H = 1024, 1024
PAPER = (248, 244, 236)
INK = (20, 32, 46)
MUTED = (74, 84, 96)
RED = (178, 34, 24)
RULE = (20, 32, 46)
HAIRLINE = (190, 182, 168)


def wrap_words(text, max_width, measure):
    """Greedy word wrap. measure(s) -> pixel width. Returns list of lines."""
    words = text.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if measure(trial) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------------------
# Pure-stdlib renderer: bitmap font, raster canvas, PNG encoder.
# ---------------------------------------------------------------------------

# 5x7 bitmap font, 7 rows of 5 bits per glyph ("#" = on, "." = off).
_FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "a": ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    "b": ("10000", "10000", "11110", "10001", "10001", "10001", "11110"),
    "c": ("00000", "00000", "01110", "10001", "10000", "10001", "01110"),
    "d": ("00001", "00001", "01111", "10001", "10001", "10001", "01111"),
    "e": ("00000", "00000", "01110", "10001", "11111", "10000", "01110"),
    "f": ("00110", "01001", "01000", "11110", "01000", "01000", "01000"),
    "g": ("00000", "01111", "10001", "10001", "01111", "00001", "01110"),
    "h": ("10000", "10000", "11110", "10001", "10001", "10001", "10001"),
    "i": ("00100", "00000", "01100", "00100", "00100", "00100", "01110"),
    "j": ("00010", "00000", "00110", "00010", "00010", "10010", "01100"),
    "k": ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    "l": ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    "m": ("00000", "00000", "11010", "10101", "10101", "10101", "10101"),
    "n": ("00000", "00000", "11110", "10001", "10001", "10001", "10001"),
    "o": ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    "p": ("00000", "00000", "11110", "10001", "11110", "10000", "10000"),
    "q": ("00000", "00000", "01111", "10001", "01111", "00001", "00001"),
    "r": ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    "s": ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    "t": ("01000", "01000", "11110", "01000", "01000", "01001", "00110"),
    "u": ("00000", "00000", "10001", "10001", "10001", "10011", "01101"),
    "v": ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    "w": ("00000", "00000", "10001", "10101", "10101", "10101", "01010"),
    "x": ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    "y": ("00000", "00000", "10001", "10001", "01111", "00001", "01110"),
    "z": ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ";": ("00000", "01100", "00000", "01100", "01100", "00100", "01000"),
    ":": ("00000", "01100", "00000", "01100", "01100", "00000", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "\u2013": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "\u2014": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    "#": ("01010", "01010", "11111", "01010", "11111", "01010", "01010"),
    "@": ("01110", "10001", "10111", "10101", "10110", "10000", "01110"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "*": ("00000", "00100", "10101", "01110", "10101", "00100", "00000"),
    "\u2022": ("00000", "00000", "01100", "01100", "01100", "00000", "00000"),
    "\u00b7": ("00000", "00000", "00000", "01100", "01100", "00000", "00000"),
    "|": ("00100", "00100", "00100", "00100", "00100", "00100", "00100"),
    "[": ("01110", "01000", "01000", "01000", "01000", "01000", "01110"),
    "]": ("01110", "00010", "00010", "00010", "00010", "00010", "01110"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "<": ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    ">": ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    "\\": ("10000", "01000", "01000", "00100", "00010", "00010", "00001"),
    "~": ("00000", "00000", "01001", "10110", "00000", "00000", "00000"),
    "^": ("00100", "01010", "10001", "00000", "00000", "00000", "00000"),
    "`": ("01000", "00100", "00000", "00000", "00000", "00000", "00000"),
    "\u00b0": ("01100", "10010", "10010", "01100", "00000", "00000", "00000"),
}

_BLANK = ("00000", "00000", "00000", "00000", "00000", "00000", "00000")


def _font_width(text, scale):
    return len(text) * 6 * scale - scale if text else 0


class StdCanvas:
    """RGB raster canvas with a bitmap-font text renderer."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def _set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = color

    def fill_rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        r, g, b = color
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.px[i], self.px[i + 1], self.px[i + 2] = r, g, b

    def hline(self, x, y, w, color, thick=1):
        self.fill_rect(x, y, w, thick, color)

    def vline(self, x, y, h, color, thick=1):
        self.fill_rect(x, y, thick, h, color)

    def line(self, x0, y0, x1, y1, color, thick=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            self.fill_rect(x - thick // 2, y - thick // 2, thick, thick, color)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def circle(self, cx, cy, r, color, fill=True):
        if fill:
            for yy in range(-r, r + 1):
                half = int((r * r - yy * yy) ** 0.5)
                self.hline(cx - half, cy + yy, 2 * half + 1, color)
        else:
            import math

            steps = max(24, r * 6)
            for k in range(steps):
                a = 2 * math.pi * k / steps
                self._set(int(cx + r * math.cos(a)), int(cy + r * math.sin(a)), color)

    def disc(self, cx, cy, r, color):
        self.circle(cx, cy, r, color, fill=True)

    def text(self, x, y, s, scale, color):
        """Draw text at top-left (x, y); glyph is 5x7 scaled by `scale`."""
        cx = x
        for ch in s:
            glyph = _FONT.get(ch, _BLANK)
            for row in range(7):
                bits = glyph[row]
                for col in range(5):
                    if bits[col] == "1":
                        self.fill_rect(
                            cx + col * scale, y + row * scale, scale, scale, color
                        )
            cx += 6 * scale
        return cx

    def text_center(self, cx, y, s, scale, color):
        self.text(cx - _font_width(s, scale) // 2, y, s, scale, color)

    def text_wrapped(self, x, y, s, scale, color, max_w, line_h):
        lines = wrap_words(s, max_w, lambda t: _font_width(t, scale))
        for i, ln in enumerate(lines):
            self.text(x, y + i * line_h, ln, scale, color)
        return len(lines)


def _png_chunk(kind, data):
    import binascii

    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
    return out


def encode_png(canvas):
    """Encode an StdCanvas as a deterministic PNG (RGB, no ancillaries)."""
    raw = bytearray()
    stride = canvas.w * 3
    for yy in range(canvas.h):
        raw.append(0)
        raw += canvas.px[yy * stride : (yy + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", canvas.w, canvas.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", ihdr)
    png += _png_chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += _png_chunk(b"IEND", b"")
    return png


# --- stdlib icons (simple geometric motifs, same spots as the PIL icons) ---

def _icon_std(canvas, kind, cx, cy, s, color):
    """Draw a small icon centred at (cx, cy); s ~ half-size in px."""
    if kind == "burst":
        for k in range(8):
            import math

            a = math.pi * k / 4
            x1 = int(cx + s * 0.45 * math.cos(a))
            y1 = int(cy + s * 0.45 * math.sin(a))
            x2 = int(cx + s * math.cos(a))
            y2 = int(cy + s * math.sin(a))
            canvas.line(x1, y1, x2, y2, color, 5)
        canvas.disc(cx, cy, s // 3, color)
    elif kind == "bridge":
        canvas.line(cx - s, cy + s // 2, cx + s, cy + s // 2, color, 5)
        for dx in (-s * 3 // 4, -s // 4, s // 4, s * 3 // 4):
            canvas.line(cx + dx, cy - s // 2, cx + dx, cy + s // 2, color, 4)
        canvas.line(cx - s, cy - s // 2, cx, cy - s, color, 4)
        canvas.line(cx, cy - s, cx + s, cy - s // 2, color, 4)
    elif kind == "summit":
        for dx in (-s // 2, 0, s // 2):
            canvas.disc(cx + dx, cy - s // 4, s // 3, color)
        canvas.line(cx - s, cy + s // 2, cx + s, cy + s // 2, color, 5)
    elif kind == "ballot":
        canvas.fill_rect(cx - s // 2, cy - s // 3, s, s * 2 // 3, color)
        canvas.line(cx - s // 2, cy, cx - s // 6, cy + s // 3, (255, 255, 255), 5)
        canvas.line(cx - s // 6, cy + s // 3, cx + s // 2, cy - s // 3, (255, 255, 255), 5)
    elif kind == "dove":
        canvas.disc(cx, cy, s // 2, color)
        canvas.line(cx - s, cy - s // 3, cx + s, cy - s // 3, color, 5)
        canvas.line(cx, cy + s // 2, cx + s // 2, cy + s, color, 5)
        canvas.line(cx, cy + s // 2, cx - s // 2, cy + s, color, 5)
    elif kind == "virus":
        canvas.disc(cx, cy, s // 2, color)
        for k in range(8):
            import math

            a = math.pi * k / 4
            x1 = int(cx + s * 0.5 * math.cos(a))
            y1 = int(cy + s * 0.5 * math.sin(a))
            x2 = int(cx + s * math.cos(a))
            y2 = int(cy + s * math.sin(a))
            canvas.line(x1, y1, x2, y2, color, 5)
    elif kind == "syringe":
        canvas.line(cx - s // 2, cy + s // 2, cx + s // 2, cy - s // 2, color, 7)
        canvas.line(cx + s // 2, cy - s // 2, cx + s, cy - s, color, 3)
        canvas.line(cx - s // 2, cy + s // 2, cx - s, cy + s, color, 5)


def render_stdlib():
    c = StdCanvas(W, H, PAPER)
    mx = 36
    cw = W - 2 * mx

    # Top strip.
    c.text(mx, 26, "THE WORLD IN ONE IMAGE", 2, MUTED)
    right = "WEDNESDAY  |  MAKE.FUN"
    c.text(W - mx - _font_width(right, 2), 26, right, 2, MUTED)
    c.hline(mx, 52, cw, RULE, 3)

    # Masthead.
    c.text_center(W // 2, 58, MASTHEAD, 10, INK)
    c.text_center(W // 2, 140, SUB_LINE, 2, MUTED)

    # Date band.
    c.fill_rect(mx, 160, cw, 40, RED)
    c.text(mx + 18, 169, DATE_LINE, 3, (255, 255, 255))
    tag = "7 STORIES - ONE DAY"
    c.text(W - mx - 18 - _font_width(tag, 3), 169, tag, 3, (255, 255, 255))

    # Lead story.
    lead = STORIES[0]
    ly = 214
    c.fill_rect(mx, ly, cw, 170, (255, 255, 255))
    c.fill_rect(mx, ly, 10, 170, lead["accent"])
    c.hline(mx, ly + 169, cw, HAIRLINE, 1)
    c.text(mx + 28, ly + 12, lead["kicker"], 2, lead["accent"])
    nlines = c.text_wrapped(
        mx + 28, ly + 36, lead["headline"], 4, INK, 700, 34
    )
    deck_y = ly + 36 + nlines * 34 + 6
    c.text_wrapped(mx + 28, deck_y, lead["deck"], 2, MUTED, 700, 18)
    _icon_std(c, lead["icon"], W - mx - 92, ly + 85, 52, lead["accent"])

    # Divider.
    c.hline(mx, 396, cw, RULE, 2)

    # Grid: 2 columns x 3 rows.
    col_w = (cw - 24) // 2
    row_h = 168
    gy = 410
    for idx, st in enumerate(STORIES[1:]):
        col = idx % 2
        row = idx // 2
        x = mx + col * (col_w + 24)
        y = gy + row * (row_h + 12)
        c.fill_rect(x, y, col_w, row_h, (255, 255, 255))
        c.hline(x, y + row_h - 1, col_w, HAIRLINE, 1)
        # Number badge.
        c.disc(x + 24, y + 24, 15, st["accent"])
        c.text_center(x + 24, y + 17, st["num"], 2, (255, 255, 255))
        c.text(x + 48, y + 17, st["kicker"], 2, st["accent"])
        n = c.text_wrapped(x + 24, y + 48, st["headline"], 3, INK, col_w - 48, 27)
        c.text_wrapped(
            x + 24, y + 48 + n * 27 + 6, st["deck"], 2, MUTED, col_w - 48, 18
        )
        _icon_std(c, st["icon"], x + col_w - 34, y + 26, 22, st["accent"])

    # Footer.
    fy = 944
    c.hline(mx, fy, cw, RULE, 2)
    c.text_wrapped(mx, fy + 10, ALSO_TODAY, 2, INK, cw, 18)
    c.text(mx, fy + 56, SOURCE_LINE, 2, MUTED)

    return encode_png(c)


# ---------------------------------------------------------------------------
# Pillow renderer (same layout, nicer fonts). Used only when PIL is present.
# ---------------------------------------------------------------------------

def _pil_fonts():
    from PIL import ImageFont

    base = "/usr/share/fonts/truetype/dejavu/"
    return {
        "masthead": ImageFont.truetype(base + "DejaVuSans-Bold.ttf", 76),
        "date": ImageFont.truetype(base + "DejaVuSans-Bold.ttf", 27),
        "kicker": ImageFont.truetype(base + "DejaVuSans-Bold.ttf", 17),
        "lead_head": ImageFont.truetype(base + "DejaVuSans-Bold.ttf", 37),
        "head": ImageFont.truetype(base + "DejaVuSans-Bold.ttf", 25),
        "deck": ImageFont.truetype(base + "DejaVuSans.ttf", 19),
        "lead_deck": ImageFont.truetype(base + "DejaVuSans.ttf", 21),
        "small": ImageFont.truetype(base + "DejaVuSans.ttf", 16),
        "small_b": ImageFont.truetype(base + "DejaVuSans-Bold.ttf", 16),
        "foot": ImageFont.truetype(base + "DejaVuSans.ttf", 15),
        "badge": ImageFont.truetype(base + "DejaVuSans-Bold.ttf", 20),
    }


def _pil_wrap(draw, text, font, max_w):
    words = text.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _icon_pil(draw, kind, cx, cy, s, color):
    if kind == "burst":
        import math

        for k in range(8):
            a = math.pi * k / 4
            x1 = cx + s * 0.45 * math.cos(a)
            y1 = cy + s * 0.45 * math.sin(a)
            x2 = cx + s * math.cos(a)
            y2 = cy + s * math.sin(a)
            draw.line([x1, y1, x2, y2], fill=color, width=7)
        draw.ellipse([cx - s // 3, cy - s // 3, cx + s // 3, cy + s // 3], fill=color)
    elif kind == "bridge":
        draw.line([cx - s, cy + s // 2, cx + s, cy + s // 2], fill=color, width=6)
        for dx in (-s * 3 // 4, -s // 4, s // 4, s * 3 // 4):
            draw.line([cx + dx, cy - s // 2, cx + dx, cy + s // 2], fill=color, width=5)
        draw.line([cx - s, cy - s // 2, cx, cy - s, cx + s, cy - s // 2], fill=color, width=5)
    elif kind == "summit":
        for dx in (-s // 2, 0, s // 2):
            draw.ellipse(
                [cx + dx - s // 3, cy - s // 2, cx + dx + s // 3, cy + s // 6],
                fill=color,
            )
        draw.line([cx - s, cy + s // 2, cx + s, cy + s // 2], fill=color, width=6)
    elif kind == "ballot":
        draw.rectangle([cx - s // 2, cy - s // 3, cx + s // 2, cy + s // 3], fill=color)
        draw.line(
            [cx - s // 2, cy, cx - s // 6, cy + s // 3, cx + s // 2, cy - s // 3],
            fill=(255, 255, 255),
            width=6,
            joint="curve",
        )
    elif kind == "dove":
        draw.ellipse([cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2], fill=color)
        draw.line([cx - s, cy - s // 3, cx + s, cy - s // 3], fill=color, width=6)
        draw.line([cx, cy + s // 2, cx + s // 2, cy + s], fill=color, width=5)
        draw.line([cx, cy + s // 2, cx - s // 2, cy + s], fill=color, width=5)
    elif kind == "virus":
        draw.ellipse([cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2], fill=color)
        for k in range(8):
            import math

            a = math.pi * k / 4
            x1 = cx + s * 0.5 * math.cos(a)
            y1 = cy + s * 0.5 * math.sin(a)
            x2 = cx + s * math.cos(a)
            y2 = cy + s * math.sin(a)
            draw.line([x1, y1, x2, y2], fill=color, width=6)
    elif kind == "syringe":
        draw.line([cx - s // 2, cy + s // 2, cx + s // 2, cy - s // 2], fill=color, width=9)
        draw.line([cx + s // 2, cy - s // 2, cx + s, cy - s], fill=color, width=4)
        draw.line([cx - s // 2, cy + s // 2, cx - s, cy + s], fill=color, width=6)


def render_pil():
    from PIL import Image, ImageDraw
    import io

    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    f = _pil_fonts()
    mx = 36
    cw = W - 2 * mx

    # Top strip.
    d.text((mx, 24), "THE WORLD IN ONE IMAGE", font=f["small_b"], fill=MUTED)
    right = "WEDNESDAY  |  MAKE.FUN"
    d.text((W - mx - d.textlength(right, font=f["small_b"]), 24), right, font=f["small_b"], fill=MUTED)
    d.rectangle([mx, 52, mx + cw, 55], fill=RULE)

    # Masthead.
    mw = d.textlength(MASTHEAD, font=f["masthead"])
    d.text(((W - mw) / 2, 58), MASTHEAD, font=f["masthead"], fill=INK)
    sw = d.textlength(SUB_LINE, font=f["small"])
    d.text(((W - sw) / 2, 140), SUB_LINE, font=f["small"], fill=MUTED)

    # Date band.
    d.rectangle([mx, 160, mx + cw, 200], fill=RED)
    d.text((mx + 18, 168), DATE_LINE, font=f["date"], fill=(255, 255, 255))
    tag = "7 STORIES - ONE DAY"
    d.text((W - mx - 18 - d.textlength(tag, font=f["date"]), 168), tag, font=f["date"], fill=(255, 255, 255))

    # Lead story.
    lead = STORIES[0]
    ly = 214
    d.rectangle([mx, ly, mx + cw, ly + 170], fill=(255, 255, 255))
    d.rectangle([mx, ly, mx + 10, ly + 170], fill=lead["accent"])
    d.line([mx, ly + 169, mx + cw, ly + 169], fill=HAIRLINE, width=1)
    d.text((mx + 28, ly + 12), lead["kicker"], font=f["kicker"], fill=lead["accent"])
    lines = _pil_wrap(d, lead["headline"], f["lead_head"], 700)
    y = ly + 36
    for ln in lines:
        d.text((mx + 28, y), ln, font=f["lead_head"], fill=INK)
        y += 40
    deck_lines = _pil_wrap(d, lead["deck"], f["lead_deck"], 700)
    y += 4
    for ln in deck_lines:
        d.text((mx + 28, y), ln, font=f["lead_deck"], fill=MUTED)
        y += 24
    _icon_pil(d, lead["icon"], W - mx - 92, ly + 85, 52, lead["accent"])

    # Divider.
    d.rectangle([mx, 396, mx + cw, 398], fill=RULE)

    # Grid: 2 columns x 3 rows.
    col_w = (cw - 24) // 2
    row_h = 168
    gy = 410
    for idx, st in enumerate(STORIES[1:]):
        col = idx % 2
        row = idx // 2
        x = mx + col * (col_w + 24)
        y = gy + row * (row_h + 12)
        d.rectangle([x, y, x + col_w, y + row_h], fill=(255, 255, 255))
        d.line([x, y + row_h - 1, x + col_w, y + row_h - 1], fill=HAIRLINE, width=1)
        d.ellipse([x + 9, y + 9, x + 39, y + 39], fill=st["accent"])
        nw = d.textlength(st["num"], font=f["badge"])
        d.text((x + 24 - nw / 2, y + 12), st["num"], font=f["badge"], fill=(255, 255, 255))
        d.text((x + 48, y + 14), st["kicker"], font=f["kicker"], fill=st["accent"])
        lines = _pil_wrap(d, st["headline"], f["head"], col_w - 48)
        yy = y + 50
        for ln in lines:
            d.text((x + 24, yy), ln, font=f["head"], fill=INK)
            yy += 30
        deck_lines = _pil_wrap(d, st["deck"], f["deck"], col_w - 48)
        yy += 4
        for ln in deck_lines:
            d.text((x + 24, yy), ln, font=f["deck"], fill=MUTED)
            yy += 24
        _icon_pil(d, st["icon"], x + col_w - 34, y + 26, 22, st["accent"])

    # Footer.
    fy = 944
    d.rectangle([mx, fy, mx + cw, fy + 2], fill=RULE)
    lines = _pil_wrap(d, ALSO_TODAY, f["foot"], cw)
    yy = fy + 10
    for ln in lines:
        d.text((mx, yy), ln, font=f["foot"], fill=INK)
        yy += 19
    d.text((mx, fy + 56), SOURCE_LINE, font=f["foot"], fill=MUTED)

    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=6, optimize=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Entry point.
# ---------------------------------------------------------------------------

def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "entry.png")

    force_stdlib = os.environ.get("MAKEFUN_FORCE_STDLIB") == "1"
    data = None
    if not force_stdlib:
        try:
            from PIL import Image  # noqa: F401

            data = render_pil()
        except Exception as exc:  # pragma: no cover - sandbox path
            print("Pillow render failed (%s); using stdlib fallback" % exc, file=sys.stderr)
            data = None
    if data is None:
        data = render_stdlib()

    with open(out_path, "wb") as fh:
        fh.write(data)
    print("wrote %s (%d bytes)" % (out_path, len(data)))


if __name__ == "__main__":
    main()
