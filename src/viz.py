"""Shared matplotlib style: one palette, light surface, recessive axes.

Palette and rules follow a validated colorblind-safe reference palette:
categorical hues are assigned in fixed order, never cycled; grids stay
recessive; text wears text colors, never series colors.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"

BLUE = "#2a78d6"     # series 1
ORANGE = "#eb6834"   # series 2
AQUA = "#1baf7a"     # series 3
YELLOW = "#eda100"   # series 4
GRAY = "#9b9a94"     # de-emphasis, never a series identity
RED = "#e34948"      # status: serious: reserved for flags

SERIES = [BLUE, ORANGE, AQUA, YELLOW]


def style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "text.color": TEXT,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT_2,
        "xtick.color": TEXT_2,
        "ytick.color": TEXT_2,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "figure.dpi": 150,
    })


def save(fig, path, title_note: str | None = None) -> None:
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
