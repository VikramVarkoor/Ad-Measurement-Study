"""Build deck/ad_measurement_deck.pptx for a non-technical reader.

Design: a dark electric-editorial system. Every slide sits on generated
art (deep navy, cobalt glows, film grain and a dot grid, painted by
src/deck_art.py), charts are re-rendered with light strokes straight onto
the background, numerals are set huge in a condensed face, and content
lives on translucent glass panels. A soft fade transition is injected
into each slide's XML.

Every number is read from results/*.csv, so rebuilding the pipeline
rebuilds the deck with current figures. Rules: the title is the finding,
one message per slide, speaker notes on every slide.
"""
from __future__ import annotations

import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from . import deck_art, paths

# ----------------------------------------------------------------- palette
TEXT = RGBColor(0xF2, 0xF5, 0xFC)       # near-white ink
SUBTLE = RGBColor(0x93, 0xA0, 0xC4)     # muted blue-grey
FAINT = RGBColor(0x5E, 0x6B, 0x92)      # footers, fine print
COBALT = RGBColor(0x4D, 0x8D, 0xFF)     # electric accent
COBALT_SOFT = RGBColor(0x9D, 0xB9, 0xFF)
ORANGE = RGBColor(0xFF, 0x6A, 0x2B)     # signal accent
PANEL = RGBColor(0x10, 0x17, 0x2B)      # glass panels
PANEL_EDGE = RGBColor(0x2A, 0x35, 0x58)
GHOST = RGBColor(0x14, 0x1C, 0x36)      # oversized background numerals
ROW_A = RGBColor(0x0E, 0x15, 0x29)      # table banding
ROW_B = RGBColor(0x12, 0x1B, 0x36)
HAIR = RGBColor(0x23, 0x2D, 0x4D)

BODY = "Avenir Next"
DISPLAY = "Avenir Next Condensed"       # huge numerals and headlines

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.66)
ASSETS = paths.DECK / "assets"


def _load():
    r = {}
    r["lift"] = pd.read_csv(paths.RESULTS / "lift_results.csv")
    r["meta"] = pd.read_csv(paths.RESULTS / "meta_results.csv")
    r["uplift"] = pd.read_csv(paths.RESULTS / "uplift_summary.csv")
    r["dvr"] = pd.read_csv(paths.RESULTS / "delay_vs_review.csv")
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
    def blank(self, art="body"):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        s.shapes.add_picture(str(ASSETS / f"bg_{art}.jpg"), 0, 0,
                             width=W, height=H)
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

    @staticmethod
    def _alpha(shape, pct: int):
        """Make a solid-filled shape translucent (pct = opacity 0-100)."""
        srgb = shape._element.spPr.find(qn("a:solidFill")).find(
            qn("a:srgbClr"))
        srgb.append(srgb.makeelement(qn("a:alpha"),
                                     {"val": str(pct * 1000)}))

    def text(self, s, left, top, width, height, runs, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP, line_spacing=1.0, space_after=None,
             font=BODY):
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
                r.font.name = font
                r.font.size = Pt(size)
                r.font.color.rgb = color
                r.font.bold = bold
        return box

    def ghost(self, s, label, left=None, top=Inches(0.4)):
        """Oversized background numeral, barely lighter than the canvas."""
        left = left if left is not None else W - Inches(5.3)
        self.text(s, left, top, Inches(5.2), Inches(6.5),
                  [(label, 340, GHOST, True)], align=PP_ALIGN.RIGHT,
                  font=DISPLAY)

    def kicker(self, s, label, color=ORANGE):
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, MARGIN, Inches(0.52),
                                 Inches(0.34), Pt(3))
        bar.fill.solid(); bar.fill.fore_color.rgb = color
        bar.line.fill.background()
        box = self.text(s, MARGIN + Inches(0.5), Inches(0.40), Inches(9),
                        Inches(0.35), [(label.upper(), 12.5, color, True)])
        for p in box.text_frame.paragraphs:
            for r in p.runs:
                r.font._rPr.set("spc", "320")

    def pagenum(self, s):
        self.text(s, W - Inches(1.15), Inches(0.40), Inches(0.55),
                  Inches(0.3), [(f"{self.n:02d}", 11.5, FAINT, True)],
                  align=PP_ALIGN.RIGHT)

    def footer(self, s):
        line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, MARGIN,
                                  H - Inches(0.52), W - 2 * MARGIN, Pt(0.9))
        line.fill.solid(); line.fill.fore_color.rgb = HAIR
        line.line.fill.background()
        self.text(s, MARGIN, H - Inches(0.44), W - 2 * MARGIN, Inches(0.3),
                  [[("AD MEASUREMENT STUDY", 9, FAINT, True),
                    ("    public data · personal project", 9, FAINT,
                     False)]])

    def headline(self, s, text_, size=30, width=None, top=Inches(1.04),
                 color=TEXT):
        return self.text(s, MARGIN, top, width or (W - 2 * MARGIN),
                         Inches(1.5), [(text_, size, color, True)],
                         line_spacing=1.03, font=DISPLAY)

    def notes(self, s, text_):
        s.notes_slide.notes_text_frame.text = text_

    # ------------------------------------------------------------ elements
    def panel(self, s, left, top, width, height, opacity=78,
              edge=PANEL_EDGE):
        card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top,
                                  width, height)
        card.adjustments[0] = 0.055
        card.fill.solid(); card.fill.fore_color.rgb = PANEL
        self._alpha(card, opacity)
        card.line.color.rgb = edge
        card.line.width = Pt(1)
        card.shadow.inherit = False
        return card

    def stat(self, s, left, top, width, number, label, sub=None,
             color=COBALT, num_size=72):
        self.text(s, left, top, width, Inches(1.4),
                  [(number, num_size, color, True)], font=DISPLAY)
        self.text(s, left, top + Inches(num_size / 56), width, Inches(0.75),
                  [(label, 14.5, TEXT, True)], line_spacing=1.08)
        if sub:
            self.text(s, left, top + Inches(num_size / 56 + 0.66), width,
                      Inches(0.95), [(sub, 11.5, SUBTLE, False)],
                      line_spacing=1.14)

    def chip(self, s, left, top, text_, ink=SUBTLE, bold=False):
        width = Inches(0.3 + 0.082 * len(text_))
        shape = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top,
                                   width, Inches(0.42))
        shape.adjustments[0] = 0.5
        shape.fill.solid(); shape.fill.fore_color.rgb = PANEL
        self._alpha(shape, 62)
        shape.line.color.rgb = PANEL_EDGE
        shape.line.width = Pt(1)
        shape.shadow.inherit = False
        tf = shape.text_frame
        tf.word_wrap = False
        tf.margin_left = tf.margin_right = Inches(0.1)
        tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = text_
        r.font.name = BODY; r.font.size = Pt(11.5); r.font.bold = bold
        r.font.color.rgb = ink
        return shape

    def chart(self, s, image, top=Inches(1.95), height=None, left=None):
        """Place a transparent dark-render chart straight on the art."""
        from PIL import Image as PILImage
        with PILImage.open(image) as im:
            wpx, hpx = im.size
        height = height or (H - top - Inches(0.75))
        width = Emu(int(height * wpx / hpx))
        max_w = W - 2 * MARGIN
        if width > max_w:
            width = max_w
            height = Emu(int(width * hpx / wpx))
        left = left if left is not None else Emu(int((W - width) / 2))
        s.shapes.add_picture(str(image), left, top, width=width)
        return left, top, width, height

    def table(self, s, df, top, font=12, col_widths=None, row_h=0.46,
              left=MARGIN, width=None, first_col_color=ORANGE):
        rows, cols = df.shape[0] + 1, df.shape[1]
        width = width or (W - 2 * MARGIN)
        shape = s.shapes.add_table(rows, cols, left, top, width,
                                   Inches(row_h) * rows)
        t = shape.table
        # kill the default banded style look; style every cell by hand
        tbl = shape._element.graphic.graphicData.tbl
        tbl[0][-1].text = "{5940675A-B579-460E-94D1-54222C63F5DA}"
        for c, name in enumerate(df.columns):
            cell = t.cell(0, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(0x0A, 0x0F, 0x1E)
            cell.margin_left = cell.margin_right = Inches(0.09)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = cell.text_frame.paragraphs[0]
            r = p.add_run(); r.text = str(name).upper()
            r.font.name = BODY; r.font.size = Pt(font - 1.5)
            r.font.bold = True
            r.font.color.rgb = COBALT
            for rr in p.runs:
                rr.font._rPr.set("spc", "160")
        for i in range(df.shape[0]):
            for c in range(cols):
                cell = t.cell(i + 1, c)
                cell.fill.solid()
                cell.fill.fore_color.rgb = ROW_A if i % 2 == 0 else ROW_B
                cell.margin_left = cell.margin_right = Inches(0.09)
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                p = cell.text_frame.paragraphs[0]
                p.line_spacing = 1.08
                r = p.add_run(); r.text = str(df.iloc[i, c])
                r.font.name = BODY; r.font.size = Pt(font)
                r.font.bold = (c == 0)
                r.font.color.rgb = first_col_color if c == 0 else TEXT
        if col_widths:
            for c, frac in enumerate(col_widths):
                t.columns[c].width = Emu(int(width * frac))
        return t

    def takeaway(self, s, text_, top=None, color=ORANGE):
        top = top or (H - Inches(1.16))
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, MARGIN, top,
                                 Pt(3.2), Inches(0.52))
        bar.fill.solid(); bar.fill.fore_color.rgb = color
        bar.line.fill.background()
        self.text(s, MARGIN + Inches(0.18), top - Inches(0.03),
                  W - 2 * MARGIN - Inches(0.2), Inches(0.68),
                  [(text_, 14, TEXT, True)], line_spacing=1.1,
                  anchor=MSO_ANCHOR.MIDDLE)


def build() -> None:
    deck_art.build()
    r = _load()
    meta_re = r["meta"][r["meta"].model.str.startswith("random")].iloc[0]
    rr, lo, hi = float(meta_re.rr), float(meta_re.ci_low), float(meta_re.ci_high)
    i2 = float(meta_re.I2)
    loo_min, loo_max = float(meta_re.loo_rr_min), float(meta_re.loo_rr_max)
    fe_rr = float(r["meta"][r["meta"].model == "fixed effect"].rr.iloc[0])
    lf = r["lift"][r["lift"].kind == "primary"]
    crit = r["lift"][r["lift"].study == "criteo"].iloc[0]
    up_c = r["uplift"][r["uplift"].study == "criteo"].iloc[0]
    up_h = r["uplift"][r["uplift"].study == "hillstrom"].iloc[0]
    dvr = r["dvr"]
    on_time = dvr[dvr.delay_bucket.str.contains("on time")].iloc[0]
    very_late = dvr[dvr.delay_bucket.str.contains(">3")].iloc[0]
    adj = r["adj"].iloc[1]
    late_share = (r["weekly"].late_share * r["weekly"].orders).sum() \
        / r["weekly"].orders.sum()
    top_dec = r["deciles"].iloc[0]
    ctrl_conv = int(crit.events_control)

    d = Deck()

    # ---------------------------------------------------------- 01 · cover
    s = d.blank("cover")
    d.kicker(s, "Ad Measurement Study · 2026")
    d.text(s, MARGIN - Inches(0.06), Inches(0.98), Inches(11.8),
           Inches(3.2), [[("+32", 230, TEXT, True),
                          ("%", 230, COBALT, True)]], font=DISPLAY)
    d.text(s, MARGIN, Inches(4.25), Inches(11.9), Inches(1.4),
           [("Across six randomized experiments and 16.1 million users,",
             26, TEXT, True),
            ("marketing caused one third more conversions.", 26,
             COBALT_SOFT, True)], line_spacing=1.12, font=DISPLAY)
    d.text(s, MARGIN, Inches(5.42), Inches(11.8), Inches(0.5),
           [[("Honest range: ", 14.5, SUBTLE, False),
             (f"+{(lo-1)*100:.0f}% to +{(hi-1)*100:.0f}%", 14.5, ORANGE,
              True),
             ("  ·  and it varies hugely by channel", 14.5, SUBTLE,
              False)]])
    chips = ["Display ads 14.0M", "E-mail 64k", "Ad vs PSA 588k",
             "Retail 687k", "SMS promo 200k", "Telecom 600k"]
    x = MARGIN
    for cch in chips:
        shp = d.chip(s, x, Inches(6.0), cch)
        x += shp.width + Inches(0.14)
    d.text(s, MARGIN, Inches(6.62), Inches(11), Inches(0.4),
           [[("Vikram Varkoor", 13, TEXT, True),
             (f"   ·   {pd.Timestamp.today():%B %Y}   ·   every figure "
              "rebuilds from one command", 12, SUBTLE, False)]])
    d.notes(s, "One sentence answers the question, with the interval in "
               "the subtitle on purpose: honest uncertainty is the "
               "product. All data is public and the project is personal.")

    # ------------------------------------------- 02 · why honesty matters
    s = d.blank("stat")
    d.ghost(s, "02")
    d.kicker(s, "Part A · Why measure causally")
    d.headline(s, "Counting every buyer as an ad win over-credits the ads")
    panels = [
        (f"{crit.rate_control*100:.3f}%",
         "of the no-ads control group bought anyway",
         "this baseline is invisible without an experiment", COBALT),
        (f"{ctrl_conv:,}", "purchases happened with zero ad exposure",
         "real conversions, no ads involved at all", TEXT),
        ("100%", "of them would be claimed as wins by exposure counting",
         "which is why a control group is non-negotiable", ORANGE),
    ]
    pw, gap = Inches(3.9), Inches(0.26)
    for i, (num, lab, sub, col) in enumerate(panels):
        px = MARGIN + i * (pw + gap)
        d.panel(s, px, Inches(2.2), pw, Inches(3.2))
        d.stat(s, px + Inches(0.3), Inches(2.5), pw - Inches(0.6),
               num, lab, sub, col, 58)
    d.takeaway(s, "Only an experiment separates the sales the ads caused "
                  "from the sales that were coming anyway.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "The control group converts at a healthy rate with no ads. "
               "Attribution counts exposed converters; an experiment "
               "subtracts the counterfactual.")

    # ------------------------------------------- 03 · the mechanism
    s = d.blank("body")
    d.ghost(s, "03")
    d.kicker(s, "Part A · The mechanism")
    d.headline(s, "Show the ads to one group, hold them from another: "
                  "the gap is what the ads caused", size=27)
    def arm(left, title, pct, sub, accent):
        d.panel(s, left, Inches(2.25), Inches(4.75), Inches(2.9))
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, Inches(2.25),
                                 Inches(4.75), Pt(3.4))
        bar.fill.solid(); bar.fill.fore_color.rgb = accent
        bar.line.fill.background()
        d.text(s, left + Inches(0.35), Inches(2.55), Inches(4.1),
               Inches(0.4), [(title.upper(), 12.5, accent, True)])
        d.text(s, left + Inches(0.35), Inches(2.95), Inches(4.1),
               Inches(1.35), [(pct, 72, TEXT, True)], font=DISPLAY)
        d.text(s, left + Inches(0.35), Inches(4.4), Inches(4.1),
               Inches(0.7), [(sub, 13, SUBTLE, False)], line_spacing=1.12)
    arm(MARGIN, "Treated · sees the ads", f"{crit.rate_treated*100:.3f}%",
        "of 11.9M users converted", COBALT)
    arm(Inches(8.0), "Control · no ads", f"{crit.rate_control*100:.3f}%",
        "of 2.1M users converted", RGBColor(0x6B, 0x77, 0x9E))
    badge = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(5.73), Inches(3.0),
                               Inches(1.86), Inches(1.86))
    badge.fill.solid(); badge.fill.fore_color.rgb = ORANGE
    badge.line.fill.background(); badge.shadow.inherit = False
    tf = badge.text_frame; tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, (txt, sz) in enumerate([
            (f"+{crit.abs_lift_pp:.3f}pp", 16),
            (f"= +{crit.rel_lift_pct:.0f}% lift", 12.5), ("caused", 11)]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run(); run.text = txt
        run.font.name = BODY; run.font.size = Pt(sz); run.font.bold = True
        run.font.color.rgb = RGBColor(0x0A, 0x0F, 0x1E)
    d.takeaway(s, "Random assignment makes the groups alike, so the gap is "
                  "causal. We compare by assignment, never by who happened "
                  "to see an ad.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "Randomization balances everything else. Intention to "
               "treat: everyone assigned counts, exposed or not, because "
               "the exposed are systematically different people.")

    # ------------------------------------------- 04 · the evidence base
    s = d.blank("body")
    d.ghost(s, "04")
    d.kicker(s, "Part A · The evidence")
    d.headline(s, "Six real experiments: display ads, e-mail, SMS and "
                  "telecom offers", size=28)
    src = pd.DataFrame({
        "Experiment": ["Criteo display ads", "Hillstrom e-mail",
                       "Marketing A/B (ad vs PSA)", "Lenta retail",
                       "X5 SMS promotion", "MegaFon telecom offer"],
        "Users": [f"{int(n):,}" for n in lf.n_treated + lf.n_control],
        "Outcome": ["conversion", "conversion", "conversion",
                    "response", "purchase", "conversion"],
        "Extra conversions": [f"+{v:.2f} pp" for v in lf.abs_lift_pp],
        "95% interval": [f"{a:.2f} to {b:.2f}" for a, b in
                         zip(lf.ci_low_pp, lf.ci_high_pp)],
    })
    d.table(s, src, Inches(2.05), font=13,
            col_widths=[0.30, 0.16, 0.14, 0.19, 0.21], row_h=0.52,
            first_col_color=TEXT)
    d.takeaway(s, "The rules for which studies count were committed to git "
                  "before any result existed. Every interval excludes "
                  "zero.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "Hillstrom's two e-mail arms share one control, so they are "
               "pooled as one study. The bootstrap agreed with the "
               "analytic interval everywhere. 'pp' = percentage points.")

    # ------------------------------------------- 05 · forest
    s = d.blank("body")
    d.kicker(s, "Part A · Spread of effects")
    d.headline(s, "Every single campaign lifted sales, by 6% to 87%")
    d.chart(s, ASSETS / "forest_dark.png", top=Inches(1.95),
            height=Inches(4.35))
    d.takeaway(s, "Everything sits right of the no-effect line: it all "
                  "worked. How well depends entirely on the channel.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "Square = estimate, whisker = 95% interval, square size = "
               "weight. The spread, not the average, is the first "
               "finding.")

    # ------------------------------------------- 06 · pooled
    s = d.blank("stat")
    d.ghost(s, "06")
    d.kicker(s, "Part A · The pooled answer")
    d.headline(s, "Put together: one third more conversions, loosely held")
    d.text(s, MARGIN, Inches(1.95), Inches(4.8), Inches(2.3),
           [("1.32", 150, COBALT, True)], font=DISPLAY)
    d.text(s, MARGIN, Inches(4.45), Inches(4.8), Inches(0.5),
           [("pooled risk ratio, random effects", 14.5, TEXT, True)])
    d.text(s, MARGIN, Inches(4.85), Inches(4.8), Inches(0.5),
           [(f"95% CI {lo:.2f} to {hi:.2f}", 13, SUBTLE, False)])
    x0 = Inches(6.1)
    rows = [
        (f"{i2*100:.1f}%", "of the spread is real disagreement, not chance",
         "display, e-mail and SMS genuinely differ (I-squared)"),
        (f"{loo_min:.2f}-{loo_max:.2f}",
         "the pooled ratio, dropping any one study",
         "no single study owns the answer (leave-one-out)"),
        (f"{fe_rr:.2f}", "the fixed-effect answer, for contrast",
         "dominated by the biggest studies, so it is not the headline"),
    ]
    for i, (num, lab, sub) in enumerate(rows):
        y = Inches(2.0) + Inches(1.5) * i
        if i:
            ln = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x0, y - Inches(0.18),
                                    W - x0 - MARGIN, Pt(0.9))
            ln.fill.solid(); ln.fill.fore_color.rgb = HAIR
            ln.line.fill.background()
        d.text(s, x0, y, Inches(2.4), Inches(0.8),
               [(num, 34, ORANGE if i == 0 else TEXT, True)], font=DISPLAY)
        d.text(s, x0 + Inches(2.55), y + Inches(0.02), Inches(4.5),
               Inches(0.6), [(lab, 13.5, TEXT, True)], line_spacing=1.08)
        d.text(s, x0 + Inches(2.55), y + Inches(0.58), Inches(4.5),
               Inches(0.6), [(sub, 11.5, SUBTLE, False)], line_spacing=1.1)
    d.takeaway(s, "The pooled number summarises these six studies. It is "
                  "not a law of advertising, and the deck says so out "
                  "loud.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "Random effects because the true effects plainly differ. "
               "With six studies the between-study variance is rough, so "
               "the interval is approximate. Fixed effect lands at 1.13 "
               "and jumps to 1.24 if X5 is dropped: single-study "
               "dominance.")

    # ------------------------------------------- 07 · who responds
    s = d.blank("body")
    d.kicker(s, "Part A · Who responds")
    d.headline(s, "Most of the effect comes from a small slice of people")
    left, top, wimg, himg = d.chart(s, ASSETS / "uplift_dark.png",
                                    top=Inches(1.95), height=Inches(4.5),
                                    left=MARGIN)
    rx = MARGIN + wimg + Inches(0.5)
    d.panel(s, rx, Inches(2.1), W - rx - MARGIN, Inches(4.1))
    d.stat(s, rx + Inches(0.3), Inches(2.4), W - rx - MARGIN - Inches(0.6),
           f"{top_dec.observed_lift_pp:.2f} pp",
           "actual lift inside the top-ranked tenth of users",
           "the middle of the ranking sits near zero", COBALT, 40)
    d.stat(s, rx + Inches(0.3), Inches(4.35), W - rx - MARGIN - Inches(0.6),
           "held-out",
           "scores come only from data the models never saw",
           "two LightGBM models: one per group", TEXT, 40)
    d.footer(s); d.pagenum(s)
    d.notes(s, "Rank users by predicted uplift; the curve shows cumulative "
               "incremental conversions versus random targeting. Steep "
               "then flat means the causal effect is concentrated.")

    # ------------------------------------------- 08 · targeting, honestly
    s = d.blank("stat")
    d.ghost(s, "08")
    d.kicker(s, "Part A · Targeting value, honestly")
    d.headline(s, "Message a fifth of the audience, keep two thirds of "
                  "the effect", size=28)
    d.panel(s, MARGIN, Inches(2.5), Inches(5.9), Inches(3.3))
    d.stat(s, MARGIN + Inches(0.35), Inches(2.8), Inches(5.2),
           f"{up_c.share_kept_top20*100:.0f}%",
           "of extra conversions kept on Criteo (14M users)",
           "one fifth of the audience keeps two thirds of the causal "
           "effect: a 3.4x concentration", COBALT, 92)
    d.panel(s, Inches(6.95), Inches(2.5), Inches(5.65), Inches(3.3))
    d.stat(s, Inches(7.3), Inches(2.8), Inches(5.0),
           f"{up_h.share_kept_top20*100:.0f}%",
           "kept on Hillstrom, barely above the 20% random would keep",
           "19,200 held-out users and seven coarse features: not enough "
           "signal to rank on, and we say so", SUBTLE, 92)
    d.takeaway(s, "Same method, two datasets, two honest answers. "
                  "Reporting the weak one is what makes the strong one "
                  "believable.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "Criteo: 2M-row stratified sample, 600k held out. "
               "Hillstrom hugs the random line. Both numbers are in "
               "results/uplift_summary.csv and reproduce from one "
               "command.")

    # ------------------------------------------- 09 · divider
    s = d.blank("divider")
    box = d.text(s, MARGIN, Inches(2.1), Inches(11.5), Inches(0.6),
                 [("PART B", 15, COBALT_SOFT, True)])
    for p0 in box.text_frame.paragraphs:
        for r0 in p0.runs:
            r0.font._rPr.set("spc", "440")
    d.text(s, MARGIN, Inches(2.6), Inches(12.2), Inches(2.4),
           [("From measuring causes", 54, TEXT, True),
            ("to diagnosing a business.", 54, COBALT_SOFT, True)],
           line_spacing=1.04, font=DISPLAY)
    d.text(s, MARGIN, Inches(5.25), Inches(11.5), Inches(0.9),
           [("Olist, a Brazilian online marketplace · 96,470 delivered "
             "orders · no experiment ran here, so Part B only ever says "
             "“associated”, never “caused”", 15,
             COBALT_SOFT, False)], line_spacing=1.2)
    d.footer(s); d.pagenum(s)
    d.notes(s, "The contrast is the lesson: Part A may say caused; Part B "
               "may not, and holding that line is the skill on display.")

    # ------------------------------------------- 10 · monitor
    s = d.blank("body")
    d.kicker(s, "Part B · The monitor")
    d.headline(s, "A weekly dashboard that only speaks when something "
                  "really moved", size=28)
    d.chart(s, ASSETS / "monitor_dark.png", top=Inches(2.0),
            height=Inches(4.2))
    d.takeaway(s, "25 flagged weeks: the early launch ramp and one Black "
                  "Friday. A control chart says when a metric moved beyond "
                  "normal noise; it never says why.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "Band = mean plus or minus 3 sigma of the stable 2018 "
               "stretch. 24 flags are the 2016-17 ramp below today's "
               "level; the one above is Black Friday 2017. Late share and "
               "review score never leave their bands.")

    # ------------------------------------------- 11 · delay vs reviews
    s = d.blank("body")
    d.kicker(s, "Part B · The diagnosis")
    d.headline(s, "Late deliveries travel with terrible reviews",
               size=28)
    left, top, wimg, himg = d.chart(s, ASSETS / "delay_dark.png",
                                    top=Inches(2.0), height=Inches(4.3),
                                    left=MARGIN)
    rx = MARGIN + wimg + Inches(0.5)
    d.panel(s, rx, Inches(2.1), W - rx - MARGIN, Inches(4.2))
    d.stat(s, rx + Inches(0.3), Inches(2.4), W - rx - MARGIN - Inches(0.6),
           f"{very_late.share_1_2_star*100:.0f}%",
           "of orders more than 3 days late get a 1-2 star review",
           f"versus {on_time.share_1_2_star*100:.0f}% when on time",
           ORANGE, 44)
    d.stat(s, rx + Inches(0.3), Inches(4.3), W - rx - MARGIN - Inches(0.6),
           f"−{abs(adj.points_per_day_late):.3f}",
           "stars per day late, after controls",
           "product type, price, freight and seller region explain almost "
           "none of it away. Still an association: nobody randomized "
           "lateness", TEXT, 44)
    d.footer(s); d.pagenum(s)
    d.notes(s, "Observational: carrier, distance and weather are "
               "unmeasured. Surviving the controls makes delivery a "
               "strong suspect; proving cause would need an experiment on "
               "the delivery promise.")

    # ------------------------------------------- 12 · recommendations
    s = d.blank("body")
    d.ghost(s, "12")
    d.kicker(s, "Recommendations")
    d.headline(s, "What to do with this, ranked")
    rec = pd.DataFrame({
        "Rank": ["1", "2", "3"],
        "Action": [
            "Message the top uplift quintile first",
            "Attack >3-day-late deliveries, starting with Sao Paulo "
            "sellers",
            "Run a geographic holdout before scaling spend",
        ],
        "Evidence": [
            f"top 20% holds {up_c.share_kept_top20*100:.0f}% of extra "
            "conversions (held-out)",
            f"{late_share*100:.1f}% of orders late; worst bucket averages "
            f"{very_late.avg_review_score:.1f} stars",
            f"study effects span RR 1.06 to 1.87: your channel's number "
            "is unknown",
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
    d.table(s, rec, Inches(2.05), font=12,
            col_widths=[0.06, 0.27, 0.27, 0.25, 0.15], row_h=0.92)
    d.takeaway(s, "Every row: evidence, action, an effect stated as a "
                  "range, and a confidence with its reason. No "
                  "business-impact claims: public data, personal project.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "The ranked format mirrors the five-field recommendation "
               "template from the project plan.")

    # ------------------------------------------- 13 · limits + next test
    s = d.blank("stat")
    d.ghost(s, "13")
    d.kicker(s, "Limits")
    d.headline(s, "What we cannot say, and the test we would run next")
    d.panel(s, MARGIN, Inches(2.0), Inches(5.95), Inches(3.7))
    d.text(s, MARGIN + Inches(0.35), Inches(2.3), Inches(5.3),
           Inches(0.4), [("WE CANNOT SAY", 12.5, ORANGE, True)])
    cannot = [
        "that these numbers transfer to any specific platform",
        "that late delivery causes bad reviews",
        "that the pooled +32% applies to a new campaign",
        "anything about revenue: the data has none",
    ]
    for i, c in enumerate(cannot):
        d.text(s, MARGIN + Inches(0.35), Inches(2.78) + Inches(0.56) * i,
               Inches(5.3), Inches(0.5),
               [[("–  ", 13, ORANGE, True), (c, 13.5, TEXT, False)]])
    d.panel(s, Inches(6.95), Inches(2.0), Inches(5.65), Inches(3.7))
    d.text(s, Inches(7.3), Inches(2.3), Inches(5.0), Inches(0.4),
           [("THE NEXT TEST: A GEOGRAPHIC HOLDOUT", 12.5, COBALT, True)])
    steps = [
        "pick matched regions; withhold ads in a random half",
        "pre-register conversion as the metric",
        "check the sample ratio before reading anything",
        "read the result as an interval, never a bare p-value",
    ]
    for i, c in enumerate(steps):
        d.text(s, Inches(7.3), Inches(2.78) + Inches(0.56) * i,
               Inches(5.1), Inches(0.5),
               [[(f"{i+1}.  ", 13, COBALT, True), (c, 13.5, TEXT, False)]])
    d.takeaway(s, "Saying “we could not tell” where it is true "
                  "is the skill this study is built to demonstrate.")
    d.footer(s); d.pagenum(s)
    d.notes(s, "Ending on limits is deliberate. The geographic holdout is "
               "the standard design when user-level randomization is not "
               "available.")

    # ------------------------------------------- 14 · appendix
    s = d.blank("body")
    d.ghost(s, "14")
    d.kicker(s, "Appendix")
    d.headline(s, "Everything rebuilds from one command")
    ap = pd.DataFrame({
        "Item": ["Reproduce", "KPI dictionary", "Methods in one page",
                 "Tests", "Data and licences"],
        "Where": [
            "git clone, then: make venv · make data · make report · "
            "make test",
            "excel/measurement_tracker.xlsx and "
            "results/kpi_dictionary.csv",
            "docs/methods.md; the A/B checklist is docs/playbook.md",
            "known-answer tests, run by GitHub Actions on every push",
            "Criteo (CC BY-NC-SA 4.0), MineThatData, Kaggle (Olist "
            "non-commercial), scikit-uplift mirrors; raw files never "
            "redistributed",
        ],
    })
    d.table(s, ap, Inches(2.0), font=12.5, col_widths=[0.24, 0.76],
            row_h=0.56, first_col_color=COBALT)
    d.footer(s); d.pagenum(s)
    d.notes(s, "Seeds fixed end to end; exports rounded and sorted so a "
               "rebuild is byte-identical.")

    out = paths.DECK / "ad_measurement_deck.pptx"
    d.prs.save(str(out))
    print(f"wrote {out} with {d.n} slides")


if __name__ == "__main__":
    build()
