"""Generated art for the deck: full-bleed backgrounds and dark chart renders.

Backgrounds are painted with numpy + Pillow (radial glows, a dot grid, thin
rings and film grain on a deep navy base) so the deck depends on no stock
imagery. Charts are re-rendered from results/*.csv on a transparent canvas
with light strokes, so they sit directly on the dark slides.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from . import paths

ASSETS = paths.DECK / "assets"
W, H = 2560, 1440

# dark-system palette (hex mirrored in make_deck.py)
BASE = (10, 15, 30)          # 0A0F1E deep navy
COBALT = (77, 141, 255)      # 4D8DFF electric accent
COBALT_DEEP = (24, 58, 180)
ORANGE = (255, 106, 43)      # FF6A2B signal accent
TEXT = "#F2F5FC"
SUBTLE = "#93A0C4"
GRID = "#1C2440"


# ------------------------------------------------------------- backgrounds
def _glow(img: np.ndarray, cx: float, cy: float, r: float,
          color: tuple, peak: float) -> None:
    ys, xs = np.ogrid[:H, :W]
    d2 = ((xs - cx) ** 2 + (ys - cy) ** 2) / (r * r)
    a = peak * np.exp(-d2)
    img += a[..., None] * np.asarray(color, np.float32)


def _grain(img: np.ndarray, seed: int, amp: float = 2.4) -> None:
    rng = np.random.default_rng(seed)
    img += rng.normal(0.0, amp, size=img.shape).astype(np.float32)


def _overlay(pil: Image.Image, draw_fn) -> Image.Image:
    layer = Image.new("RGBA", pil.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    return Image.alpha_composite(pil.convert("RGBA"), layer).convert("RGB")


def _dots(pil: Image.Image, alpha: int = 16, step: int = 56) -> Image.Image:
    def fn(d):
        for y in range(step, H, step):
            for x in range(step, W, step):
                d.ellipse([x - 1, y - 1, x + 1, y + 1],
                          fill=(147, 160, 196, alpha))
    return _overlay(pil, fn)


def _rings(pil: Image.Image, cx: int, cy: int, radii, alpha: int = 26,
           color=COBALT) -> Image.Image:
    def fn(d):
        for r in radii:
            d.ellipse([cx - r, cy - r, cx + r, cy + r],
                      outline=(*color, alpha), width=2)
    return _overlay(pil, fn)


def _finish(img: np.ndarray, seed: int) -> Image.Image:
    _grain(img, seed)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def bg_cover() -> Image.Image:
    img = np.tile(np.asarray(BASE, np.float32), (H, W, 1))
    _glow(img, -150, H + 250, 1500, (24, 62, 205), 0.62)
    _glow(img, W - 220, -140, 760, ORANGE, 0.16)
    _glow(img, W * 0.62, H * 0.95, 900, (16, 40, 130), 0.35)
    pil = _finish(img, 11)
    pil = _rings(pil, -150, H + 250, [820, 1020, 1220], alpha=30)
    return _dots(pil)


def bg_body() -> Image.Image:
    img = np.tile(np.asarray(BASE, np.float32), (H, W, 1))
    _glow(img, -260, -260, 1150, (22, 55, 180), 0.26)
    _glow(img, W + 260, H + 260, 1250, (14, 34, 110), 0.22)
    pil = _finish(img, 23)
    return _dots(pil, alpha=12)


def bg_stat() -> Image.Image:
    img = np.tile(np.asarray(BASE, np.float32), (H, W, 1))
    _glow(img, W * 0.5, H * 1.25, 1500, (22, 55, 185), 0.40)
    _glow(img, W * 0.08, -200, 800, (16, 40, 130), 0.25)
    pil = _finish(img, 37)
    return _dots(pil, alpha=12)


def bg_divider() -> Image.Image:
    img = np.tile(np.asarray(BASE, np.float32), (H, W, 1))
    _glow(img, W * 0.78, H * 0.35, 1250, (26, 66, 215), 0.78)
    _glow(img, W * 0.95, H * 0.1, 500, ORANGE, 0.22)
    _glow(img, -200, H + 200, 1100, (14, 34, 115), 0.5)
    pil = _finish(img, 51)
    pil = _rings(pil, int(W * 0.78), int(H * 0.35), [540, 700, 870, 1050],
                 alpha=42, color=(130, 175, 255))
    return _dots(pil)


# ------------------------------------------------------------- dark charts
def _style(ax):
    ax.set_facecolor("none")
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(colors=SUBTLE, labelsize=12, length=0)
    ax.grid(True, axis="x", color=GRID, linewidth=0.9)
    ax.grid(False, axis="y")


def forest_dark() -> None:
    studies = pd.read_csv(paths.RESULTS / "meta_studies.csv")
    meta = pd.read_csv(paths.RESULTS / "meta_results.csv")
    re_row = meta[meta.model.str.startswith("random")].iloc[0]
    fig, ax = plt.subplots(figsize=(11.8, 5.1), dpi=200)
    fig.patch.set_alpha(0)
    _style(ax)
    ax.grid(True, axis="x", color=GRID, linewidth=0.9)
    n = len(studies)
    ys = np.arange(n, 0, -1)
    w = 1.0 / studies["var"]
    sizes = 9 + 13 * (w - w.min()) / (w.max() - w.min())
    rr, lo, hi = re_row.rr, re_row.ci_low, re_row.ci_high
    for y, (_, row), s in zip(ys, studies.iterrows(), sizes):
        ax.plot([row.ci_low_rr, row.ci_high_rr], [y, y], color="#5F6F9E",
                lw=2.2, solid_capstyle="round", zorder=2)
        ax.plot(row.rr, y, "s", color="#4D8DFF", markersize=s, zorder=3)
    ax.fill([lo, rr, hi, rr], [0, 0.24, 0, -0.24], color="#FF6A2B", zorder=3)
    # labels left of the axis, values right of it, clear of the whiskers
    short = {"criteo": "Criteo display ads",
             "hillstrom": "Hillstrom e-mail",
             "marketing_ab": "Marketing A/B (ad vs PSA)",
             "lenta": "Lenta retail",
             "x5": "X5 SMS promotion",
             "megafon": "MegaFon telecom offer"}
    tf = ax.get_yaxis_transform()
    for y, (_, row) in zip(ys, studies.iterrows()):
        ax.text(-0.015, y, short.get(row.study, row.label), color=TEXT,
                fontsize=13, va="center", ha="right", fontweight="bold",
                transform=tf)
        ax.text(1.015, y, f"{row.rr:.2f}  ({row.ci_low_rr:.2f}-"
                f"{row.ci_high_rr:.2f})", color=SUBTLE, fontsize=12,
                va="center", ha="left", family="monospace", transform=tf)
    ax.text(-0.015, 0, "Pooled (random effects)", color="#FF6A2B",
            fontsize=13, va="center", ha="right", fontweight="bold",
            transform=tf)
    ax.text(1.015, 0, f"{rr:.2f}  ({lo:.2f}-{hi:.2f})", color="#FF6A2B",
            fontsize=12, va="center", ha="left", family="monospace",
            transform=tf)
    ax.axvline(1.0, color=SUBTLE, lw=1.1, ls=(0, (4, 3)))
    ax.text(1.0, n + 0.75, "no effect", color=SUBTLE, fontsize=11,
            ha="center")
    ax.set_xlim(0.95, 2.35)
    ax.set_ylim(-0.8, n + 0.9)
    ax.set_yticks([])
    ax.set_xticks([1.0, 1.25, 1.5, 1.75, 2.0, 2.25])
    ax.set_xlabel("risk ratio: conversions with treatment vs without",
                  color=SUBTLE, fontsize=11)
    fig.subplots_adjust(left=0.24, right=0.82, top=0.9, bottom=0.12)
    fig.savefig(ASSETS / "forest_dark.png", transparent=True)
    plt.close(fig)


def uplift_dark() -> None:
    pts = pd.read_csv(paths.RESULTS / "qini_points_criteo.csv")
    summ = pd.read_csv(paths.RESULTS / "uplift_summary.csv")
    summ = summ[summ.study == "criteo"].iloc[0]
    frac = pts.phi.to_numpy()
    cum = pts.qini.to_numpy()
    rand = pts.random_line.to_numpy()
    k20 = int(np.argmin(np.abs(frac - 0.20)))
    fig, ax = plt.subplots(figsize=(7.6, 5.6), dpi=200)
    fig.patch.set_alpha(0)
    _style(ax)
    ax.grid(True, axis="y", color=GRID, linewidth=0.9)
    ax.grid(False, axis="x")
    ax.fill_between(frac, rand, cum, where=cum >= rand,
                    color="#4D8DFF", alpha=0.16, zorder=1)
    ax.plot(frac, cum, color="#4D8DFF", lw=3.4, solid_capstyle="round",
            zorder=3)
    ax.plot(frac, rand, color=SUBTLE, lw=1.6, ls=(0, (5, 4)), zorder=2)
    ax.plot(frac[k20], cum[k20], "o", color="#FF6A2B", markersize=11,
            zorder=4)
    ax.annotate("top 20% already holds\n"
                f"{summ.share_kept_top20*100:.0f}% of the extra conversions",
                xy=(frac[k20], cum[k20]), xytext=(0.3, cum[k20] * 0.74),
                color=TEXT, fontsize=12.5, fontweight="bold",
                arrowprops=dict(arrowstyle="-", color=SUBTLE, lw=1.1))
    ax.text(0.72, rand[-3] * 0.82, "random targeting", color=SUBTLE,
            fontsize=11.5, rotation=18)
    ax.set_xlabel("share of users targeted, ranked by predicted uplift",
                  color=SUBTLE, fontsize=12)
    ax.set_ylabel("cumulative incremental conversions (held-out)",
                  color=SUBTLE, fontsize=12)
    ax.set_xlim(0, 1)
    fig.tight_layout()
    fig.savefig(ASSETS / "uplift_dark.png", transparent=True)
    plt.close(fig)


def monitor_dark() -> None:
    weekly = pd.read_csv(paths.RESULTS / "weekly_ecom.csv",
                         parse_dates=["purchase_week"])
    stable = weekly[(weekly.purchase_week >= "2018-01-01")
                    & (weekly.purchase_week <= "2018-07-31")]
    mu, sd = stable.orders.mean(), stable.orders.std()
    lo, hi = mu - 3 * sd, mu + 3 * sd
    out = (weekly.orders < lo) | (weekly.orders > hi)
    fig, ax = plt.subplots(figsize=(11.4, 4.9), dpi=200)
    fig.patch.set_alpha(0)
    _style(ax)
    ax.grid(True, axis="y", color=GRID, linewidth=0.9)
    ax.grid(False, axis="x")
    ax.axhspan(lo, hi, color="#4D8DFF", alpha=0.10, zorder=1)
    ax.axhline(mu, color="#4D8DFF", lw=1.2, ls=(0, (4, 3)), alpha=0.8)
    ax.plot(weekly.purchase_week, weekly.orders, color="#9DB9FF", lw=2.4,
            solid_capstyle="round", zorder=3)
    flagged = weekly[out]
    ax.plot(flagged.purchase_week, flagged.orders, "o", color="#FF6A2B",
            markersize=6.5, zorder=4)
    peak = weekly.loc[weekly.orders.idxmax()]
    ax.set_ylim(0, peak.orders * 1.22)
    ax.annotate("Black Friday 2017", xy=(peak.purchase_week, peak.orders),
                xytext=(peak.purchase_week, peak.orders * 1.09),
                color=TEXT, fontsize=12.5, fontweight="bold", ha="center")
    ax.text(weekly.purchase_week.iloc[4], hi * 0.9,
            "control band: stable-2018 mean ± 3σ", color=SUBTLE,
            fontsize=11.5)
    ax.set_ylabel("orders per week", color=SUBTLE, fontsize=12)
    fig.tight_layout()
    fig.savefig(ASSETS / "monitor_dark.png", transparent=True)
    plt.close(fig)


def delay_dark() -> None:
    dvr = pd.read_csv(paths.RESULTS / "delay_vs_review.csv")
    labels = [b.split(". ", 1)[1] for b in dvr.delay_bucket]
    colors = ["#4D8DFF", "#8F7BE8", "#FF6A2B"]
    fig, ax = plt.subplots(figsize=(7.2, 5.4), dpi=200)
    fig.patch.set_alpha(0)
    _style(ax)
    ax.grid(True, axis="y", color=GRID, linewidth=0.9)
    ax.grid(False, axis="x")
    bars = ax.bar(labels, dvr.avg_review_score, width=0.58, color=colors,
                  zorder=3)
    for b, v, n in zip(bars, dvr.avg_review_score, dvr.orders):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.09, f"{v:.2f}★",
                ha="center", color=TEXT, fontsize=17, fontweight="bold")
        ax.text(b.get_x() + b.get_width() / 2, 0.18, f"{n:,} orders",
                ha="center", color="#0A0F1E", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 5)
    ax.set_ylabel("average review score", color=SUBTLE, fontsize=12)
    ax.tick_params(axis="x", labelsize=13, colors=TEXT)
    fig.tight_layout()
    fig.savefig(ASSETS / "delay_dark.png", transparent=True)
    plt.close(fig)


def build() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    # JPEG: film grain makes PNG backgrounds ~6MB each; JPEG keeps them small
    bg_cover().save(ASSETS / "bg_cover.jpg", quality=86)
    bg_body().save(ASSETS / "bg_body.jpg", quality=86)
    bg_stat().save(ASSETS / "bg_stat.jpg", quality=86)
    bg_divider().save(ASSETS / "bg_divider.jpg", quality=86)
    forest_dark()
    uplift_dark()
    monitor_dark()
    delay_dark()
    print(f"wrote deck art to {ASSETS}")


if __name__ == "__main__":
    build()
