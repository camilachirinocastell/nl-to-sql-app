"""Flow diagram PNG: clean, full detail, aligned with the current code."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon

OUT = "docs/request-flow.png"

fig, ax = plt.subplots(figsize=(18, 13))
ax.set_xlim(0, 125)
ax.set_ylim(0, 90)
ax.axis("off")
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

INK = "#1f2937"
BLUE = "#1e40af"
LBLUE = "#e0e7ff"
LGREEN = "#dcfce7"
RED = "#991b1b"
LRED = "#fee2e2"
GRAY = "#f3f4f6"
AMBER = "#fef3c7"


def box(x, y, w, h, text, fill="white", fs=10):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=1.2",
                                linewidth=1.8, edgecolor=INK, facecolor=fill))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center",
            color=INK, fontsize=fs, weight="bold")


def diamond(x, y, w, h, text, fs=9.5):
    ax.add_patch(Polygon([(x+w/2, y+h), (x+w, y+h/2), (x+w/2, y), (x, y+h/2)],
                         closed=True, facecolor=AMBER, edgecolor=INK, linewidth=1.8))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center",
            color=INK, fontsize=fs, weight="bold")


def arrow(x1, y1, x2, y2, rad=0.0, dashed=False):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=16, color=INK, lw=1.8,
                                 linestyle=(0, (4, 3)) if dashed else "solid",
                                 connectionstyle=f"arc3,rad={rad}"))


def title(x, y, text):
    ax.text(x, y, text, ha="center", fontsize=12.5, weight="bold", color=BLUE)


# ---- Title ----
ax.text(62, 86, "NL-to-SQL App — Request Flow", ha="center", fontsize=20, weight="bold", color=INK)
ax.text(62, 83, "From a natural-language question to a validated SQL result, 100% local",
        ha="center", fontsize=11, color="#6b7280")

# ---- Left: startup ----
title(25, 78, "1 · STARTUP (lifespan)")
box(10, 70, 30, 6, "docker compose up\napp + ollama · custom dns", fill=LBLUE, fs=9.5)
box(10, 62, 30, 6, "Load CSV → SQLite\n(db.load_csv_to_db)", fill=GRAY, fs=9.5)
box(10, 54, 30, 6, "Model warm-up\n60 retries × 5s backoff", fill=GRAY, fs=9.5)
box(10, 46, 30, 6, "Ollama unreachable?\n→ /ask returns 503", fill=LRED, fs=9.5)
arrow(25, 70, 25, 68)
arrow(25, 62, 25, 60)
arrow(25, 54, 25, 52)

# ---- Center: main flow ----
title(70, 78, "2 · MAIN FLOW (POST /ask)")
box(52, 70, 36, 6, "User question\n(static JS frontend)", fill=LGREEN)
box(52, 62, 36, 6, "POST /ask {question}\nglobal timeout 120s (504 on timeout)", fill=GRAY, fs=9.5)
box(52, 54, 36, 6, "build_prompt()\nschema + few-shot + instructions", fill=GRAY, fs=9.5)
box(52, 46, 36, 6, "Ollama /api/generate\n\"temperature\": 0", fill=LBLUE, fs=9.5)
box(52, 38, 36, 6, "_extract_sql()\nstrip markdown/extra text", fill=GRAY, fs=9.5)
box(52, 30, 36, 6, "validate_sql()\nSELECT-only · 1 statement · LIMIT ≤ 100", fill=AMBER, fs=9.5)
box(52, 22, 36, 6, "execute_query()\nSQLite read-only connection", fill=GRAY, fs=9.5)
diamond(58, 13, 24, 7, "Success?")
box(52, 4, 36, 7, "JSON {question, sql, columns,\nrows, attempts} → UI", fill=LGREEN, fs=9.5)

ysteps = [70, 62, 54, 46, 38, 30, 22]
for a, b in zip(ysteps, ysteps[1:]):
    arrow(70, a, 70, b + 6)
arrow(70, 22, 70, 20)
arrow(70, 13, 70, 11)

# security boundary: dashed rect around validate + execute
mpatches.FancyBboxPatch  # noqa
sec = mpatches.FancyBboxPatch((50.5, 20.5), 39, 17,
        boxstyle="square,pad=0.02", linewidth=1.6, edgecolor=RED,
        facecolor="none", linestyle=(0, (4, 3)))
ax.add_patch(sec)
ax.text(49, 29, "SECURITY\nBOUNDARY", ha="right", fontsize=8.5, color=RED, weight="bold")

# retry loop
box(93, 24, 24, 8, "Retry ≤ 3:\nreal error\nfed back to\nthe model", fill=LRED, fs=9)
arrow(82, 16.5, 93, 28)
arrow(105, 32, 105, 49)
arrow(105, 49, 88, 49)

ax.text(70, 0.5, "3 failed attempts → 422 · Ollama unreachable → 503 · global timeout → 504",
        ha="center", fontsize=9.5, color="#6b7280")

# ---- Right: aux ----
title(106, 78, "3 · AUX")
box(95, 70, 25, 6, "GET /health\n{status, database_connected}", fill=GRAY, fs=9)
box(95, 62, 25, 6, "POST /internal/query\nraw SQL (dev only)", fill=GRAY, fs=9)
box(95, 54, 25, 6, "SQLite: products\n16 cols from CSV", fill=LBLUE, fs=9)

# ---- Footer ----
ax.plot([5, 120], [-2, -2], color="#e5e7eb", lw=1.2)
ax.text(62, -5.5, "Camila Chirino Castell · github.com/camilachirinocastell · linkedin.com/in/camila-chirino-castell · camilachirinocastell-portfolio.netlify.app",
        ha="center", fontsize=9, color="#6b7280")

ax.set_ylim(-9, 90)
os.makedirs("docs", exist_ok=True)
plt.tight_layout()
plt.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
print("saved", OUT)
