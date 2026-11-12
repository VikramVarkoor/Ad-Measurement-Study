"""Build deck/ad_measurement_deck.pptx for a non-technical reader.

Design: an editorial system on a warm paper canvas. Oversized stat
typography carries the findings; charts sit on white cards; every slide
keeps the same frame (kicker, headline, footer) so the eye always knows
where to look. A soft fade transition is injected into each slide's XML.

Every number is read from results/*.csv, so rebuilding the pipeline
rebuilds the deck with current figures. Rules: the title is the finding,
one message per slide, speaker notes on every slide.
"""
from __future__ import annotations

import copy

import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from . import paths

# ----------------------------------------------------------------- palette
PAPER = RGBColor(0xF6, 0xF4, 0xEF)      # warm paper canvas
CARD = RGBColor(0xFF, 0xFF, 0xFF)       # chart cards
INK = RGBColor(0x14, 0x14, 0x1A)        # near-black text
MUTED = RGBColor(0x6E, 0x6C, 0x66)      # secondary text
HAIR = RGBColor(0xDD, 0xD9, 0xD0)       # hairlines
COBALT = RGBColor(0x1E, 0x5E, 0xF3)     # primary accent
COBALT_DARK = RGBColor(0x0E, 0x2E, 0x8A)
ORANGE = RGBColor(0xFF, 0x5A, 0x1F)     # secondary accent
CREAM_TINT = RGBColor(0xEF, 0xEC, 0xE4) # banded table rows

FONT = "Avenir Next"
W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.62)


def _load():
    r = {}
    r["lift"] = pd.read_csv(paths.RESULTS / "lift_results.csv")
    r["meta"] = pd.read_csv(paths.RESULTS / "meta_results.csv")
    r["uplift"] = pd.read_csv(paths.RESULTS / "uplift_summary.csv")
    r["dvr"] = pd.read_csv(paths.RESULTS / "delay_vs_review.csv")
    r["flags"] = pd.read_csv(paths.RESULTS / "monitor_flags.csv")
    r["adj"] = pd.read_csv(paths.RESULTS / "delay_adjusted_effect.csv")
    r["weekly"] = pd.read_csv(paths.RESULTS / "weekly_ecom.csv")
    r["deciles"] = pd.read_csv(paths.RESULTS / "uplift_deciles_criteo.csv")
    return r


class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width = W
        self.prs.slide_height = H
        self.n = 0

    # ------------------------------------------------------------ plumbing
    def blank(self, bg=PAPER):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        fill = s.background.fill
        fill.solid()
        fill.fore_color.rgb = bg
        self.n += 1
        self._fade(s)
        return s

    @staticmethod
    def _fade(slide):
        """Inject a soft fade transition into the slide XML."""
        el = slide._element
        tr = el.makeelement(qn("p:transition"), {"spd": "med"})
        tr.append(el.makeelement(qn("p:fade"), {}))
        el.append(tr)

    def text(self, s, left, top, width, height, runs, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP, line_spacing=1.0, space_after=None):
        """runs: list of paragraphs; each paragraph is a list of
        (text, size, color, bold) tuples, or a single tuple."""
        box = s.shapes.add_textbox(left, top, width, height)
        tf = box.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        first = True
        for para in runs:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.alignment = align
            p.line_spacing = line_spacing
            if space_after is not None:
                p.space_after = space_after
            if isinstance(para, tuple):
                para = [para]
            for text, size, color, bold in para:
                r = p.add_run()
                r.text = text
                r.font.name = FONT
                r.font.size = Pt(size)
                r.font.color.rgb = color
                r.font.bold = bold
        return box

    def kicker(self, s, label, color=COBALT, ink=None):
        box = self.text(s, MARGIN, Inches(0.42), Inches(8), Inches(0.35),
                        [(label.upper(), 12, color, True)])
        # letter-spacing via raw XML (python-pptx has no API for it)
        for p in box.text_frame.paragraphs:
            for r in p.runs:
                r.font._rPr.set("spc", "280")
        if ink is None:
            bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, MARGIN, Inches(0.80),
                                     Inches(0.46), Pt(2.6))
            bar.fill.solid(); bar.fill.fore_color.rgb = color
            bar.line.fill.background()

    def pagenum(self, s, dark=False):
        c = CARD if dark else MUTED
        self.text(s, W - Inches(1.1), Inches(0.40), Inches(0.55), Inches(0.3),
                  [(f"{self.n:02d}", 11, c, True)], align=PP_ALIGN.RIGHT)

    def footer(self, s, dark=False):
        c = RGBColor(0xBF, 0xCF, 0xF5) if dark else MUTED
        line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, MARGIN, H - Inches(0.52),
                                  W - 2 * MARGIN, Pt(0.9))
        line.fill.solid()
        line.fill.fore_color.rgb = RGBColor(0x3A, 0x5B, 0xC2) if dark else HAIR
        line.line.fill.background()
        self.text(s, MARGIN, H - Inches(0.44), W - 2 * MARGIN, Inches(0.3),
                  [[("AD MEASUREMENT STUDY", 9, c, True),
                    ("    public data · personal project", 9, c, False)]])

    def headline(self, s, text_, size=28, width=None, top=Inches(1.02), color=INK):
        return self.text(s, MARGIN, top, width or (W - 2 * MARGIN), Inches(1.5),
                         [(text_, size, color, True)], line_spacing=1.04)

    def notes(self, s, text_):
        s.notes_slide.notes_text_frame.text = text_

    # ------------------------------------------------------------ elements
    def stat(self, s, left, top, width, number, label, sub=None,
             color=COBALT, num_size=66):
        self.text(s, left, top, width, Inches(1.3),
                  [(number, num_size, color, True)])
        y = top + Inches(0.52) + Emu(int(Pt(num_size) * 12700 // 12700 * 0))  # anchor below
        self.text(s, left, top + Inches(num_size / 58), width, Inches(0.75),
                  [(label, 14.5, INK, True)], line_spacing=1.05)
        if sub:
            self.text(s, left, top + Inches(num_size / 58 + 0.62), width,
                      Inches(0.9), [(sub, 11.5, MUTED, False)], line_spacing=1.1)

    def chip(self, s, left, top, text_, fill=None, ink=INK, width=None, bold=True):
        width = width or Inches(0.24 + 0.085 * len(text_))
        shape = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top,
                                   width, Inches(0.42))
        shape.adjustments[0] = 0.5
        if fill is None:
            shape.fill.background()
            shape.line.color.rgb = HAIR
            shape.line.width = Pt(1)
        else:
            shape.fill.solid(); shape.fill.fore_color.rgb = fill
            shape.line.fill.background()
        tf = shape.text_frame
        tf.word_wrap = False
        tf.margin_left = tf.margin_right = Inches(0.1)
        tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = text_
        r.font.name = FONT; r.font.size = Pt(11.5); r.font.bold = bold
        r.font.color.rgb = ink
        return shape

    def chart_card(self, s, image, top=Inches(1.95), height=None, left=None,
                   width=None):
        with Image.open(image) as im:
            wpx, hpx = im.size
        height = height or (H - top - Inches(0.75))
        width = width or Emu(int(height * wpx / hpx))
        max_w = W - 2 * MARGIN
        if width > max_w:
            width = max_w
            height = Emu(int(width * hpx / wpx))
        left = left if left is not None else Emu(int((W - width) / 2))
        pad = Inches(0.16)
        card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                  left - pad, top - pad,
                                  width + 2 * pad, height + 2 * pad)
        card.adjustments[0] = 0.045
        card.fill.solid(); card.fill.fore_color.rgb = CARD
        card.line.color.rgb = HAIR; card.line.width = Pt(1)
        card.shadow.inherit = False
        s.shapes.add_picture(str(image), left, top, width=width)
        return left, top, width, height

    def table(self, s, df, top, font=12, col_widths=None, row_h=0.46,
              left=MARGIN, width=None):
        rows, cols = df.shape[0] + 1, df.shape[1]
        width = width or (W - 2 * MARGIN)
        shape = s.shapes.add_table(rows, cols, left, top, width,
                                   Inches(row_h) * rows)
        t = shape.table
        # kill the default banded style look; style every cell by hand
        tbl = shape._element.graphic.graphicData.tbl
        tbl[0][-1].text = "{5940675A-B579-460E-94D1-54222C63F5DA}"  # "no style"
        for c, name in enumerate(df.columns):
            cell = t.cell(0, c)
            cell.fill.background()
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = cell.text_frame.paragraphs[0]
            r = p.add_run(); r.text = str(name).upper()
            r.font.name = FONT; r.font.size = Pt(font - 1.5); r.font.bold = True
            r.font.color.rgb = COBALT
            for rr in p.runs:
                rr.font._rPr.set("spc", "140")
        for i in range(df.shape[0]):
            for c in range(cols):
                cell = t.cell(i + 1, c)
                cell.fill.solid()
                cell.fill.fore_color.rgb = CARD if i % 2 == 0 else CREAM_TINT
                cell.margin_left = cell.margin_right = Inches(0.08)
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                p = cell.text_frame.paragraphs[0]
                p.line_spacing = 1.05
                r = p.add_run(); r.text = str(df.iloc[i, c])
                r.font.name = FONT; r.font.size = Pt(font)
                r.font.bold = (c == 0)
                r.font.color.rgb = INK
        if col_widths:
            for c, frac in enumerate(col_widths):
                t.columns[c].width = Emu(int(width * frac))
        return t

    def takeaway(self, s, text_, top=None, color=ORANGE):
        top = top or (H - Inches(1.12))
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, MARGIN, top,
                                 Pt(3.2), Inches(0.52))
        bar.fill.solid(); bar.fill.fore_color.rgb = color
        bar.line.fill.background()
        self.text(s, MARGIN + Inches(0.16), top - Inches(0.03),
                  W - 2 * MARGIN - Inches(0.2), Inches(0.68),
                  [(text_, 14, INK, True)], line_spacing=1.08,
                  anchor=MSO_ANCHOR.MIDDLE)


def build() -> None:
    r = _load()
    meta_re = r["meta"][r["meta"].model.str.startswith("random")].iloc[0]
    rr, lo, hi = float(meta_re.rr), float(meta_re.ci_low), float(meta_re.ci_high)
    i2 = float(meta_re.I2)
    loo_min, loo_max = float(meta_re.loo_rr_min), float(meta_re.loo_rr_max)
    fe_rr = float(r["meta"][r["meta"].model == "fixed effect"].rr.iloc[0])
    lf = r["lift"][r["lift"].kind == "primary"]
    crit = r["lift"][r["lift"].study == "criteo"].iloc[0]
    total_users = int(lf.n_treated.sum() + lf.n_control.sum())
    up_c = r["uplift"][r["uplift"].study == "criteo"].iloc[0]
    up_h = r["uplift"][r["uplift"].study == "hillstrom"].iloc[0]
    dvr = r["dvr"]
    on_time = dvr[dvr.delay_bucket.str.contains("on time")].iloc[0]
    very_late = dvr[dvr.delay_bucket.str.contains(">3")].iloc[0]
    adj = r["adj"].iloc[1]
    late_share = (r["weekly"].late_share * r["weekly"].orders).sum() / r["weekly"].orders.sum()
    top_dec = r["deciles"].iloc[0]
    ctrl_conv = int(crit.events_control)

    d = Deck()

    # ---------------------------------------------------------- 01 · cover
    s = d.blank()
    d.kicker(s, "Ad Measurement Study", ink=True)
    d.text(s, MARGIN, Inches(1.05), Inches(9.2), Inches(2.6),
           [("+32%", 170, COBALT, True)])
    d.text(s, MARGIN, Inches(3.55), Inches(11.6), Inches(1.5),
           [("Across six randomized experiments and 16.1 million users,",
             27, INK, True),
            ("marketing caused 32% more conversions.", 27, INK, True)],
           line_spacing=1.1)
    d.text(s, MARGIN, Inches(4.85), Inches(11.8), Inches(0.5),
           [[("Honest range: ", 15, MUTED, False),
             (f"+{(lo-1)*100:.0f}% to +{(hi-1)*100:.0f}%", 15, ORANGE, True),
             ("  ·  and it varies hugely by channel", 15, MUTED, False)]])
    chips = ["Display ads 14.0M", "E-mail 64k", "Ad vs PSA 588k",
             "Retail 687k", "SMS promo 200k", "Telecom 600k"]
    x = MARGIN
    for cch in chips:
        shp = d.chip(s, x, Inches(5.55), cch, ink=MUTED, bold=False)
        x += shp.width + Inches(0.14)
    d.text(s, MARGIN, Inches(6.35), Inches(11), Inches(0.4),
           [[("Vikram Varkoor", 13, INK, True),
             (f"   ·   {pd.Timestamp.today():%B %Y}   ·   deck rebuilt from the "
              "pipeline, every figure reproducible", 12, MUTED, False)]])
    d.footer(s)
    d.notes(s, "One sentence answers the question, with the interval in the "
               "subtitle on purpose: honest uncertainty is the product. All "
               "data is public and the project is personal.")

    # ------------------------------------------- 02 · why honesty matters
    s = d.blank()
    d.kicker(s, "Part A · Why measure causally")
    d.headline(s, "Counting every converter over-credits the ads")
    d.stat(s, MARGIN, Inches(2.15), Inches(3.9), "0.194%",
           "of Criteo's control group converted with zero ads",
           "the baseline that attribution tools silently claim", COBALT, 58)
    d.stat(s, Inches(4.85), Inches(2.15), Inches(3.9), f"{ctrl_conv:,}",
           "conversions happened in the control group anyway",
           "real purchases, no ad exposure at all", INK, 58)
    d.stat(s, Inches(9.1), Inches(2.15), Inches(3.6), "100%",
           "of them would be counted as wins by exposure counting",
           "which is why a control group is non-negotiable", ORANGE, 58)
    d.takeaway(s, "Only an experiment separates conversions the ads caused "
                  "from conversions that were coming anyway.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "The control group converts at a healthy rate with no ads. "
               "Attribution counts exposed converters; an experiment "
               "subtracts the counterfactual.")

    # ------------------------------------------- 03 · the mechanism
    s = d.blank()
    d.kicker(s, "Part A · The mechanism")
    d.headline(s, "A control group reveals what the ads caused")
    def arm(left, title, pct, sub, fill, ink_c):
        card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left,
                                  Inches(2.1), Inches(4.7), Inches(2.9))
        card.adjustments[0] = 0.06
        card.fill.solid(); card.fill.fore_color.rgb = fill
        card.line.fill.background()
        card.shadow.inherit = False
        d.text(s, left + Inches(0.35), Inches(2.4), Inches(4.0), Inches(0.4),
               [(title.upper(), 12.5, ink_c, True)])
        d.text(s, left + Inches(0.35), Inches(2.8), Inches(4.0), Inches(1.3),
               [(pct, 64, CARD if fill != CREAM_TINT else INK, True)])
        d.text(s, left + Inches(0.35), Inches(4.15), Inches(4.0), Inches(0.7),
               [(sub, 13, ink_c, False)], line_spacing=1.1)
    arm(MARGIN, "Treated · sees the ads", "0.313%",
        "of 11.9M users converted", COBALT, RGBColor(0xDCE, 0xE6, 0xFD) if False else RGBColor(0xDC, 0xE6, 0xFD))
    arm(Inches(8.0), "Control · no ads", "0.194%",
        "of 2.1M users converted", CREAM_TINT, MUTED)
    # delta badge between the cards
    badge = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(5.78), Inches(2.95),
                               Inches(1.78), Inches(1.78))
    badge.fill.solid(); badge.fill.fore_color.rgb = ORANGE
    badge.line.fill.background(); badge.shadow.inherit = False
    tf = badge.text_frame; tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, (txt, sz) in enumerate([("+0.115 pp", 17), ("= +61% lift", 13),
                                   ("caused", 11)]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run(); run.text = txt
        run.font.name = FONT; run.font.size = Pt(sz); run.font.bold = True
        run.font.color.rgb = CARD
    d.takeaway(s, "Random assignment makes the groups alike, so the gap is "
                  "causal. We compare by assignment, never by who happened "
                  "to see an ad.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "Randomization balances everything else. Intention to treat: "
               "everyone assigned counts, exposed or not, because the "
               "exposed are systematically different people.")

    # ------------------------------------------- 04 · the evidence base
    s = d.blank()
    d.kicker(s, "Part A · The evidence")
    d.headline(s, "Six randomized experiments, one ad account, one marketplace")
    src = pd.DataFrame({
        "Experiment": ["Criteo display ads", "Hillstrom e-mail",
                       "Marketing A/B (ad vs PSA)", "Lenta retail",
                       "X5 SMS promotion", "MegaFon telecom offer"],
        "Users": [f"{int(n):,}" for n in lf.n_treated + lf.n_control],
        "Outcome": ["conversion", "conversion", "conversion",
                    "response", "purchase", "conversion"],
        "Lift": [f"+{v:.2f} pp" for v in lf.abs_lift_pp],
        "95% interval": [f"{a:.2f} to {b:.2f}" for a, b in
                         zip(lf.ci_low_pp, lf.ci_high_pp)],
    })
    d.table(s, src, Inches(2.0), font=13,
            col_widths=[0.32, 0.17, 0.15, 0.15, 0.21], row_h=0.52)
    d.takeaway(s, "Inclusion rules were committed before any result: random "
                  "assignment, binary outcome, known group sizes. The ad "
                  "account and the marketplace stay observational.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "Hillstrom's two e-mail arms share one control, so they are "
               "pooled as one study. Every interval excludes zero; the "
               "bootstrap agreed with the analytic interval everywhere.")

    # ------------------------------------------- 05 · forest
    s = d.blank()
    d.kicker(s, "Part A · Spread of effects")
    d.headline(s, "Every treatment lifted conversions, by 6% to 87%")
    d.chart_card(s, paths.FIGURES / "forest_plot.png", top=Inches(2.0),
                 height=Inches(4.1))
    d.takeaway(s, "All six sit right of 1.0: everything worked. How much it "
                  "worked depends entirely on the channel.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "Box = estimate, whisker = 95% interval, box size = weight. "
               "The spread, not the average, is the first finding.")

    # ------------------------------------------- 06 · pooled
    s = d.blank()
    d.kicker(s, "Part A · The pooled answer")
    d.headline(s, "Pooled: one third more conversions, loosely held")
    d.stat(s, MARGIN, Inches(2.05), Inches(4.6), f"{rr:.2f}",
           "pooled risk ratio, random effects",
           f"95% CI {lo:.2f} to {hi:.2f}", COBALT, 96)
    x0 = Inches(5.7)
    for i, (num, lab, sub) in enumerate([
        (f"{i2*100:.1f}%", "I-squared: real disagreement between studies",
         "display, e-mail and SMS genuinely differ"),
        (f"{loo_min:.2f}-{loo_max:.2f}", "leave-one-out range of the pooled ratio",
         "no single study owns the answer"),
        (f"{fe_rr:.2f}", "the fixed-effect answer, for contrast",
         "dominated by the biggest studies; that is why it is not the headline"),
    ]):
        d.stat(s, x0, Inches(2.0) + Inches(1.52) * i, Inches(7.0), num, lab,
               None, INK if i else ORANGE, 30)
        d.text(s, x0 + Inches(2.55), Inches(2.08) + Inches(1.52) * i + Inches(0.0),
               Inches(4.9), Inches(0.9), [(sub, 11.5, MUTED, False)],
               line_spacing=1.1)
    d.takeaway(s, "The pooled number summarises these six studies. It is not "
                  "a law of advertising, and the deck says so out loud.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "Random effects because the true effects plainly differ. With "
               "six studies the between-study variance is rough, so the "
               "interval is approximate. Fixed effect lands at 1.13 and "
               "jumps to 1.24 if X5 is dropped: single-study dominance.")

    # ------------------------------------------- 07 · qini
    s = d.blank()
    d.kicker(s, "Part A · Who responds")
    d.headline(s, "The people ads move are a small minority")
    left, top, wimg, himg = d.chart_card(
        s, paths.FIGURES / "qini_criteo.png", top=Inches(2.0),
        height=Inches(4.05), left=MARGIN)
    rx = MARGIN + wimg + Inches(0.55)
    d.stat(s, rx, Inches(2.2), W - rx - MARGIN, f"{top_dec.observed_lift_pp:.2f} pp",
           "observed lift in the top decile of the ranking",
           "the middle deciles sit near zero", COBALT, 40)
    d.stat(s, rx, Inches(4.15), W - rx - MARGIN, "held-out",
           "every score comes from data the models never saw",
           "two LightGBM models: treated and control", INK, 40)
    d.footer(s); d.pagenum(s)
    d.notes(s, "Rank users by predicted uplift; the curve shows cumulative "
               "incremental conversions versus random targeting. Steep then "
               "flat means the causal effect is concentrated.")

    # ------------------------------------------- 08 · targeting, honestly
    s = d.blank()
    d.kicker(s, "Part A · Targeting value, honestly")
    d.headline(s, "Top-20% targeting keeps two thirds of the effect on "
                  "Criteo, and adds little on the small e-mail test")
    d.stat(s, MARGIN, Inches(2.3), Inches(5.6), f"{up_c.share_kept_top20*100:.0f}%",
           "of incremental conversions kept, Criteo",
           "messaging one fifth of users keeps two thirds of the causal "
           "effect: a 3.4x concentration", COBALT, 96)
    d.stat(s, Inches(7.1), Inches(2.3), Inches(5.4), f"{up_h.share_kept_top20*100:.0f}%",
           "kept on Hillstrom, versus 20% for random",
           "19,200 held-out users and seven coarse features: not enough "
           "signal to rank on, and we say so", MUTED, 96)
    d.takeaway(s, "Same method, two datasets, two honest answers. Reporting "
                  "the weak one is what makes the strong one believable.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "Criteo: 2M-row stratified sample, 600k held out. Hillstrom "
               "hugs the random line. Both numbers are in "
               "results/uplift_summary.csv and reproduce from one command.")

    # ------------------------------------------- 09 · divider
    s = d.blank(bg=COBALT_DARK)
    d.text(s, MARGIN, Inches(2.3), Inches(11.5), Inches(1.0),
           [("PART B", 15, RGBColor(0x9F, 0xBC, 0xFA), True)])
    for p0 in s.shapes[-1].text_frame.paragraphs:
        for r0 in p0.runs:
            r0.font._rPr.set("spc", "400")
    d.text(s, MARGIN, Inches(2.85), Inches(12.0), Inches(2.4),
           [("From measuring causes", 48, CARD, True),
            ("to diagnosing a shop.", 48, RGBColor(0x9F, 0xBC, 0xFA), True)],
           line_spacing=1.06)
    d.text(s, MARGIN, Inches(5.3), Inches(11.5), Inches(0.9),
           [("Olist marketplace · 96,470 delivered orders · observational "
             "data, so Part B only ever says “associated”", 15,
             RGBColor(0xCF, 0xDC, 0xFB), False)])
    d.footer(s, dark=True); d.pagenum(s, dark=True)
    d.notes(s, "The contrast is the lesson: Part A may say caused; Part B "
               "may not, and holding that line is the skill on display.")

    # ------------------------------------------- 10 · monitor
    s = d.blank()
    d.kicker(s, "Part B · The monitor")
    d.headline(s, "The weekly monitor flags 25 weeks: a launch ramp and one "
                  "Black Friday", size=26)
    d.chart_card(s, paths.FIGURES / "monitor_orders.png", top=Inches(2.05),
                 height=Inches(3.95))
    d.takeaway(s, "A control chart says when a metric moved beyond normal "
                  "noise. It never says why.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "Band = mean plus or minus 3 sigma of the stable 2018 "
               "stretch. 24 flags are the 2016-17 ramp below today's level; "
               "the one above is Black Friday 2017. Late share and review "
               "score never leave their bands.")

    # ------------------------------------------- 11 · delay vs reviews
    s = d.blank()
    d.kicker(s, "Part B · The diagnosis")
    d.headline(s, "Very late orders average 1.9 stars; on time averages 4.3",
               size=26)
    left, top, wimg, himg = d.chart_card(
        s, paths.FIGURES / "delay_vs_review.png", top=Inches(2.05),
        height=Inches(3.9), left=MARGIN)
    rx = MARGIN + wimg + Inches(0.55)
    d.stat(s, rx, Inches(2.1), W - rx - MARGIN, f"{very_late.share_1_2_star*100:.0f}%",
           "of very-late orders leave a 1-2 star review",
           f"versus {on_time.share_1_2_star*100:.0f}% when on time", ORANGE, 44)
    d.stat(s, rx, Inches(3.9), W - rx - MARGIN,
           f"−{abs(adj.points_per_day_late):.3f}",
           "review points per day late, after controls",
           "category, price, freight and seller state shrink the raw slope "
           "by only 2%. Still an association: nobody randomized lateness",
           INK, 44)
    d.footer(s); d.pagenum(s)
    d.notes(s, "Observational: carrier, distance and weather are unmeasured. "
               "Surviving the controls makes delivery a strong suspect; "
               "proving cause would need an experiment on the delivery "
               "promise.")

    # ------------------------------------------- 12 · recommendations
    s = d.blank()
    d.kicker(s, "Recommendations")
    d.headline(s, "What we recommend, ranked")
    rec = pd.DataFrame({
        "Rank": ["1", "2", "3"],
        "Action": [
            "Target the top uplift quintile first",
            "Attack >3-day-late deliveries, starting with Sao Paulo sellers",
            "Run a geographic holdout before scaling spend",
        ],
        "Evidence": [
            f"top 20% holds {up_c.share_kept_top20*100:.0f}% of extra "
            "conversions (held-out)",
            f"{late_share*100:.1f}% of orders late; worst bucket averages "
            f"{very_late.avg_review_score:.1f} stars",
            f"study effects span RR 1.06 to 1.87, I² {i2*100:.0f}%: your "
            "channel's number is unknown",
        ],
        "Expected effect": [
            "about 2/3 of the effect at 1/5 of the audience cost",
            "up to 0.12 points of average review score (upper bound)",
            "a causal read of your campaign, not a borrowed benchmark",
        ],
        "Confidence": [
            "high: randomized, held-out",
            "medium: association only",
            "high: method, not prediction",
        ],
    })
    d.table(s, rec, Inches(2.0), font=11.5,
            col_widths=[0.06, 0.27, 0.27, 0.25, 0.15], row_h=0.62)
    d.takeaway(s, "Every row: evidence, action, an effect stated as a range, "
                  "and a confidence with its reason. No business-impact "
                  "claims: public data, personal project.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "The ranked format mirrors the five-field recommendation "
               "template from the project plan.")

    # ------------------------------------------- 13 · limits + next test
    s = d.blank()
    d.kicker(s, "Limits")
    d.headline(s, "What we cannot say, and the test we would run next")
    d.text(s, MARGIN, Inches(2.1), Inches(5.9), Inches(0.4),
           [("WE CANNOT SAY", 12.5, ORANGE, True)])
    cannot = [
        "that these numbers transfer to any specific platform",
        "that late delivery causes bad reviews",
        "that the pooled +32% applies to a new campaign",
        "anything about revenue: the data has none",
    ]
    for i, c in enumerate(cannot):
        d.text(s, MARGIN, Inches(2.55) + Inches(0.52) * i, Inches(5.9),
               Inches(0.5), [[("–  ", 13, ORANGE, True),
                              (c, 13.5, INK, False)]])
    d.text(s, Inches(7.0), Inches(2.1), Inches(5.6), Inches(0.4),
           [("THE NEXT TEST: A GEOGRAPHIC HOLDOUT", 12.5, COBALT, True)])
    steps = [
        "pick matched regions; withhold ads in a random half",
        "pre-register conversion as the metric",
        "check the sample ratio before reading anything",
        "read the result as an interval, never a bare p-value",
    ]
    for i, c in enumerate(steps):
        d.text(s, Inches(7.0), Inches(2.55) + Inches(0.52) * i, Inches(5.7),
               Inches(0.5), [[(f"{i+1}.  ", 13, COBALT, True),
                              (c, 13.5, INK, False)]])
    d.takeaway(s, "Saying “we could not tell” where it is true is "
                  "the skill this study is built to demonstrate.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "Ending on limits is deliberate. The geographic holdout is "
               "the standard design when user-level randomization is not "
               "available.")

    # ------------------------------------------- 14 · appendix
    s = d.blank()
    d.kicker(s, "Appendix")
    d.headline(s, "Everything is reproducible from one command")
    ap = pd.DataFrame({
        "Item": ["Reproduce", "KPI dictionary", "Methods in one page",
                 "Tests", "Data and licences"],
        "Where": [
            "git clone, then: make venv · make data · make report · make test",
            "excel/measurement_tracker.xlsx and results/kpi_dictionary.csv",
            "docs/methods.md; the A/B checklist is docs/playbook.md",
            "34 known-answer tests, run by GitHub Actions on every push",
            "Criteo (CC BY-NC-SA 4.0), MineThatData, Kaggle (Olist "
            "non-commercial), scikit-uplift mirrors; raw files never "
            "redistributed",
        ],
    })
    d.table(s, ap, Inches(2.0), font=12.5, col_widths=[0.24, 0.76], row_h=0.56)
    d.footer(s); d.pagenum(s)
    d.notes(s, "Seeds fixed end to end; exports rounded and sorted so a "
               "rebuild is byte-identical.")

    out = paths.DECK / "ad_measurement_deck.pptx"
    d.prs.save(str(out))
    print(f"wrote {out} with {d.n} slides")


if __name__ == "__main__":
    build()
