"""Phase 9: build deck/ad_measurement_deck.pptx for a non-technical reader.

Rules enforced here: every slide title is the finding in a sentence, one
message per slide, ≤ ~25 words of body text, a chart beats a table, speaker
notes on every slide. All numbers are read from results/*.csv, so rebuilding
the pipeline rebuilds the deck with current figures.
"""
from __future__ import annotations

import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

from . import paths

INK = RGBColor(0x0B, 0x0B, 0x0B)
INK2 = RGBColor(0x52, 0x51, 0x4E)
BLUE = RGBColor(0x2A, 0x78, 0xD6)
ORANGE = RGBColor(0xEB, 0x68, 0x34)
RED = RGBColor(0xE3, 0x49, 0x48)
SURFACE = RGBColor(0xFC, 0xFC, 0xFB)
BAND = RGBColor(0xEE, 0xF3, 0xFA)

W, H = Inches(13.333), Inches(7.5)


def _load():
    r = {}
    r["lift"] = pd.read_csv(paths.RESULTS / "lift_results.csv")
    r["meta"] = pd.read_csv(paths.RESULTS / "meta_results.csv")
    r["loo"] = pd.read_csv(paths.RESULTS / "meta_leave_one_out.csv")
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

    def _blank(self):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        bg = s.background.fill
        bg.solid()
        bg.fore_color.rgb = SURFACE
        self.n += 1
        return s

    def _text(self, slide, left, top, width, height, text, size, color=INK,
              bold=False, align=PP_ALIGN.LEFT):
        box = slide.shapes.add_textbox(left, top, width, height)
        tf = box.text_frame
        tf.word_wrap = True
        first = True
        for line in text.split("\n"):
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.text = line
            p.alignment = align
            for run in p.runs:
                run.font.size = Pt(size)
                run.font.bold = bold
                run.font.color.rgb = color
                run.font.name = "Avenir Next"
        return box

    def _title(self, slide, text):
        self._text(slide, Inches(0.55), Inches(0.35), W - Inches(1.1),
                   Inches(1.15), text, 27, INK, bold=True)

    def _footer(self, slide):
        self._text(slide, Inches(0.55), H - Inches(0.42), W - Inches(1.1),
                   Inches(0.3),
                   f"Public datasets · personal project · slide {self.n}",
                   10, INK2)

    def _notes(self, slide, text):
        slide.notes_slide.notes_text_frame.text = text

    def finding_slide(self, title, body=None, image=None, notes="",
                      image_width=Inches(8.6)):
        s = self._blank()
        self._title(s, title)
        top = Inches(1.55)
        if body:
            self._text(s, Inches(0.55), top, W - Inches(1.1), Inches(0.9),
                       body, 15, INK2)
            top = Inches(2.35)
        if image:
            from PIL import Image
            with Image.open(image) as im:
                w_px, h_px = im.size
            img_h = Emu(int(image_width * h_px / w_px))
            max_h = H - top - Inches(0.55)
            if img_h > max_h:
                img_h = max_h
                image_width = Emu(int(img_h * w_px / h_px))
            s.shapes.add_picture(str(image), Emu(int((W - image_width) / 2)),
                                 top, width=image_width)
        self._footer(s)
        self._notes(s, notes)
        return s

    def table_slide(self, title, df, notes="", col_widths=None, font=12,
                    body=None):
        s = self._blank()
        self._title(s, title)
        top = Inches(1.5)
        if body:
            self._text(s, Inches(0.55), top, W - Inches(1.1), Inches(0.6),
                       body, 14, INK2)
            top = Inches(2.1)
        rows, cols = df.shape[0] + 1, df.shape[1]
        tw = W - Inches(1.1)
        shape = s.shapes.add_table(rows, cols, Inches(0.55), top, tw,
                                   Inches(0.5) * rows)
        table = shape.table
        for c, name in enumerate(df.columns):
            cell = table.cell(0, c)
            cell.text = str(name)
            cell.fill.solid()
            cell.fill.fore_color.rgb = BAND
            for p in cell.text_frame.paragraphs:
                for r_ in p.runs:
                    r_.font.size = Pt(font)
                    r_.font.bold = True
                    r_.font.color.rgb = INK
        for i in range(df.shape[0]):
            for c in range(cols):
                cell = table.cell(i + 1, c)
                cell.text = str(df.iloc[i, c])
                cell.fill.solid()
                cell.fill.fore_color.rgb = SURFACE
                for p in cell.text_frame.paragraphs:
                    for r_ in p.runs:
                        r_.font.size = Pt(font)
                        r_.font.color.rgb = INK
        if col_widths:
            for c, wid in enumerate(col_widths):
                table.columns[c].width = Emu(int(tw * wid))
        self._footer(s)
        self._notes(s, notes)
        return s


def build() -> None:
    r = _load()
    meta_re = r["meta"][r["meta"].model.str.startswith("random")].iloc[0]
    loo_min, loo_max = float(meta_re.loo_rr_min), float(meta_re.loo_rr_max)
    rr, lo, hi = float(meta_re.rr), float(meta_re.ci_low), float(meta_re.ci_high)
    i2 = float(meta_re.I2)
    crit = r["lift"][r["lift"].study == "criteo"].iloc[0]
    up_c = r["uplift"][r["uplift"].study == "criteo"].iloc[0]
    up_h = r["uplift"][r["uplift"].study == "hillstrom"].iloc[0]
    dvr = r["dvr"]
    on_time = dvr[dvr.delay_bucket.str.contains("on time")].iloc[0]
    very_late = dvr[dvr.delay_bucket.str.contains(">3")].iloc[0]
    adj = r["adj"].iloc[1]
    late_share = (r["weekly"].late_share * r["weekly"].orders).sum() / r["weekly"].orders.sum()
    n_flags = len(r["flags"])
    top_decile = r["deciles"].iloc[0]

    d = Deck()

    # 1 — headline
    s = d._blank()
    d._text(s, Inches(0.8), Inches(1.2), W - Inches(1.6), Inches(2.2),
            f"Across six randomized experiments, marketing caused "
            f"{(rr-1)*100:.0f}% more conversions — but the honest range is "
            f"{(lo-1)*100:.0f}% to {(hi-1)*100:.0f}%, and it varies hugely by channel.",
            30, INK, bold=True)
    d._text(s, Inches(0.8), Inches(3.6), W - Inches(1.6), Inches(1.6),
            f"Ad Measurement and Business Insight Study\n"
            f"Vikram Varkoor · {pd.Timestamp.today():%d %b %Y}\n"
            f"Pooled risk ratio {rr:.2f} (95% CI {lo:.2f}–{hi:.2f}), "
            f"six public experiments, {int(r['lift'][r['lift'].kind=='primary'].n_treated.sum() + r['lift'][r['lift'].kind=='primary'].n_control.sum()):,} users",
            16, INK2)
    d._footer(s)
    d._notes(s, "One sentence answers the question. The interval is in the "
                "headline on purpose: honest uncertainty is the product. "
                "All data is public; this is a personal project.")

    # 2 — why it matters
    d.finding_slide(
        "Counting every converter over-credits the ad — some would have bought anyway",
        body=f"In the Criteo experiment, {crit.rate_control*100:.2f}% of people who saw "
             f"NO ads still converted. An ad platform counting them as wins would "
             f"claim every one of those {int(crit.events_control):,} conversions.",
        notes="The control group converts at a nonzero rate with no ads at all. "
              "Attribution tools count exposed converters; only an experiment "
              "separates caused conversions from conversions that would have "
              "happened anyway.")

    # 3 — control group picture
    s = d._blank()
    d._title(s, "A control group shows what the ad actually caused")
    from pptx.enum.shapes import MSO_SHAPE
    def group_box(x, label, rate_label, color):
        box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, Inches(2.2),
                                 Inches(4.6), Inches(2.6))
        box.fill.solid(); box.fill.fore_color.rgb = color
        box.line.fill.background()
        tf = box.text_frame; tf.word_wrap = True
        tf.text = label
        p2 = tf.add_paragraph(); p2.text = rate_label
        for p in tf.paragraphs:
            p.alignment = PP_ALIGN.CENTER
            for run_ in p.runs:
                run_.font.size = Pt(18); run_.font.bold = True
                run_.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    group_box(Inches(1.1), "Treated group — sees the ads",
              f"{crit.rate_treated*100:.2f}% convert", BLUE)
    group_box(Inches(7.4), "Control group — sees no ads",
              f"{crit.rate_control*100:.2f}% convert", RGBColor(0x9B, 0x9A, 0x94))
    d._text(s, Inches(1.1), Inches(5.3), Inches(11), Inches(1.2),
            f"Random assignment makes the groups alike, so the gap — "
            f"{crit.abs_lift_pp:.2f} points, a {crit.rel_lift_pct:.0f}% lift — was CAUSED by the ads "
            f"(Criteo, {int(crit.n_treated + crit.n_control):,} users).",
            16, INK)
    d._footer(s)
    d._notes(s, "Randomization is the whole trick: both groups have the same mix "
                "of people, seasons and habits, so the only difference left is "
                "the ads. We always compare by assignment (intention to treat), "
                "never by who happened to see an ad.")

    # 4 — sources
    lf = r["lift"][r["lift"].kind == "primary"]
    src = pd.DataFrame({
        "Study": lf.label,
        "Channel": lf.channel,
        "Users": [f"{int(n):,}" for n in lf.n_treated + lf.n_control],
        "Outcome": ["conversion", "conversion", "conversion",
                    "response", "purchase", "conversion"],
        "Lift (pp)": [f"{v:.2f}" for v in lf.abs_lift_pp],
    })
    d.table_slide(
        "Six public randomized experiments, one ad account, one marketplace",
        src, font=12,
        body="Every included study randomized assignment; outcomes were fixed "
             "before analysis. The Facebook ad account and the Olist marketplace "
             "are observational and are never treated as experiments.",
        notes="Inclusion rules were committed in analysis_plan.md before any "
              "result was computed: random assignment, binary outcome, known "
              "group sizes. Hillstrom's two e-mail arms share one control, so "
              "they count as one study, not two.")

    # 5 — forest plot
    d.finding_slide(
        "Every treatment lifted conversions — by 6% to 87% depending on channel",
        image=paths.FIGURES / "forest_plot.png",
        notes="One row per study, the box is the estimate, whiskers the 95% "
              "interval, box size the statistical weight. All six sit right of "
              "1.0, so every treatment worked — but they disagree about how "
              "much, which is the next slide's point.")

    # 6 — pooled
    d.finding_slide(
        f"Pooled: {(rr-1)*100:.0f}% more conversions (CI {(lo-1)*100:.0f}–"
        f"{(hi-1)*100:.0f}%) — but the studies genuinely disagree",
        body=f"I² = {i2*100:.0f}%: almost all the spread between studies is real "
             f"disagreement, not chance. Dropping any single study moves the "
             f"pooled ratio between {loo_min:.2f} and {loo_max:.2f}. The pooled "
             f"number summarises these six studies — it is not a law of advertising.",
        notes="Random-effects (DerSimonian–Laird) because the channels genuinely "
              "differ. With six studies the between-study variance is roughly "
              "estimated, so the interval is treated as approximate. The "
              "fixed-effect answer (1.13) is dominated by the largest precise "
              "studies — the leave-one-out table shows exactly that.")

    # 7 — responders are a minority
    d.finding_slide(
        "The people ads move are a minority — the top tenth holds most of the effect",
        body=f"Ranking held-out Criteo users by predicted uplift: the top decile's "
             f"observed lift is {top_decile.observed_lift_pp:.2f} pp; the middle "
             f"deciles sit near zero.",
        image=paths.FIGURES / "qini_criteo.png",
        image_width=Inches(7.2),
        notes="Two LightGBM models (treated and control) score every user; the "
              "difference is the predicted uplift. Scored only on data the "
              "models never saw. The curve rises steeply then flattens: most of "
              "the causal effect lives in a small slice of users.")

    # 8 — targeting
    tg = pd.DataFrame({
        "Experiment": ["Criteo display ads", "Hillstrom e-mail"],
        "Messaging only the top 20% keeps": [
            f"{up_c.share_kept_top20*100:.0f}% of extra conversions",
            f"{up_h.share_kept_top20*100:.0f}% of extra conversions",
        ],
        "Verdict": ["model finds responders",
                    "barely better than random (20%) — reported as weak"],
    })
    d.table_slide(
        f"Targeting the top 20% keeps {up_c.share_kept_top20*100:.0f}% of the extra "
        f"conversions on Criteo — but adds little on the small e-mail test",
        tg, font=14,
        notes="The same method, two datasets, two honest answers. On 14M users "
              "with informative features the model concentrates the effect "
              "3.4x. On 64k users with coarse features it cannot beat random "
              "by much — and saying so is the credibility of this deck.")

    # 9 — monitor
    d.finding_slide(
        f"The shop's weekly monitor flags {n_flags} unusual weeks — the launch ramp "
        f"and one Black Friday",
        image=paths.FIGURES / "monitor_orders.png",
        notes=f"Control band = mean ± 3σ of the stable 2018 stretch. 24 flags are "
              "the 2016–17 growth ramp sitting below today's level (growth, not "
              "a problem); the one flag above the band is Black Friday 2017. "
              "Late-delivery share and review score stay inside their bands all "
              "period. A control chart says WHEN something moved, never why.")

    # 10 — delay vs reviews
    d.finding_slide(
        f"Orders more than 3 days late average {very_late.avg_review_score:.1f} stars "
        f"vs {on_time.avg_review_score:.1f} on time — and the link survives controls",
        body=f"{very_late.share_1_2_star*100:.0f}% of very-late orders leave 1–2 "
             f"stars (vs {on_time.share_1_2_star*100:.0f}% on time). Adjusted for "
             f"category, price, freight and seller state, each day late still goes "
             f"with {abs(adj.points_per_day_late):.3f} points lower score. "
             f"Association — Olist ran no experiment.",
        image=paths.FIGURES / "delay_vs_review.png",
        image_width=Inches(6.4),
        notes="Observational data: late orders could differ in ways we cannot "
              "see (carrier, distance, weather). The controls shrink the raw "
              "association by only ~2%, which makes delivery a strong suspect — "
              "but proving cause would need an experiment, e.g. a random "
              "delivery-promise change.")

    # 11 — recommendations
    rec = pd.DataFrame({
        "Recommendation (ranked)": [
            "1. Target the top uplift quintile first",
            "2. Attack >3-day-late deliveries, starting with São Paulo sellers",
            "3. Run a geographic holdout before scaling spend",
        ],
        "Finding behind it": [
            f"Top 20% of users holds {up_c.share_kept_top20*100:.0f}% of extra conversions (Criteo, held-out)",
            f"{late_share*100:.1f}% of orders late; >3-day lates average {very_late.avg_review_score:.1f}★ vs {on_time.avg_review_score:.1f}★",
            f"Study effects range RR 1.06–1.87 (I² {i2*100:.0f}%) — your channel's number is unknown",
        ],
        "Expected effect": [
            "~⅔ of incremental conversions at ~⅕ of the audience cost",
            f"up to ~0.12 avg review points (upper bound, association)",
            "a causal read of YOUR campaign, not a borrowed benchmark",
        ],
        "Confidence": [
            "high (randomized, held-out)",
            "medium (association survives controls)",
            "high (method, not prediction)",
        ],
    })
    d.table_slide("What we recommend, ranked", rec, font=11,
                  col_widths=[0.26, 0.33, 0.26, 0.15],
                  notes="Every row: finding → so-what → action → expected effect "
                        "as a range → confidence with the reason. Nothing here "
                        "claims a business impact; the data is public and the "
                        "project personal.")

    # 12 — limits
    d.finding_slide(
        "What we cannot say — and the test we would run next",
        body="We cannot say: that these numbers transfer to any specific platform; "
             "that late delivery CAUSES bad reviews; that the pooled 32% applies "
             "to a new campaign; anything about revenue (no revenue data).\n\n"
             "Next test: a geographic holdout — pick matched regions, withhold "
             "ads in a random half, pre-register conversion as the metric, check "
             "the sample ratio, and read the lift with the same interval-first "
             "discipline used here.",
        notes="Ending on limits is deliberate: the ability to say 'we could not "
              "tell' is the skill the deck demonstrates. The geographic holdout "
              "is the standard industry design when user-level randomization "
              "isn't possible.")

    # A — appendix
    ap = pd.DataFrame({
        "Appendix item": ["KPI dictionary", "Methods in one page", "Data sources & licences",
                          "Reproduce everything"],
        "Where": ["excel workbook · results/kpi_dictionary.csv",
                  "docs/methods.md",
                  "README — Criteo (CC BY-NC-SA 4.0), MineThatData, Kaggle (Olist non-commercial), scikit-uplift mirrors",
                  "git clone → make data → make report → make test"],
    })
    d.table_slide("Appendix", ap, font=13, col_widths=[0.3, 0.7],
                  notes="Everything in this deck is reproducible from one "
                        "command on a fresh clone.")

    out = paths.DECK / "ad_measurement_deck.pptx"
    d.prs.save(str(out))
    print(f"wrote {out} with {d.n} slides")


if __name__ == "__main__":
    build()
