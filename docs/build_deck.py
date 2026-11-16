"""Build the viva presentation (docs/presentation.pptx) from the measured results.

    python docs/build_deck.py

Numbers are read from results/**/summary.json where possible, so the deck matches the report.
"""
import json
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "presentation.pptx"

# Palette: deep navy dominates; red = failure, teal = resilience, amber = caution.
NAVY = RGBColor(0x14, 0x21, 0x3D)
NAVY_2 = RGBColor(0x22, 0x33, 0x5A)
RED = RGBColor(0xD6, 0x28, 0x39)
TEAL = RGBColor(0x1F, 0x8A, 0x7E)
AMBER = RGBColor(0xE0, 0x9F, 0x1F)
INK = RGBColor(0x1B, 0x1F, 0x2A)
MUTED = RGBColor(0x5B, 0x63, 0x73)
LIGHT = RGBColor(0xF3, 0xF5, 0xF9)
CARD = RGBColor(0xE8, 0xEC, 0xF3)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
HEAD = "Cambria"
BODY = "Calibri"


def summary(path):
    return json.loads((ROOT / "results" / path / "summary.json").read_text(encoding="utf-8"))


S1E1 = summary("s1/e1/run1")
S2E1 = summary("s2/e1/run1")
S2E2 = summary("s2/e2/run1")
E4_ON = [summary(f"local-s2/e4-breaker-on/run{i}") for i in (1, 2, 3)]
E4_OFF = [summary(f"local-s2/e4-breaker-off/run{i}") for i in (1, 2, 3)]
E3_ON = summary("local-s2/e3-breaker-on/run1")
E3_OFF = summary("local-s2/e3-breaker-off/run1")


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2]


prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
W, H = 13.333, 7.5
slide_no = [0]


# ---------- helpers ----------
def bg(slide, color):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = color


def text(slide, x, y, w, h, runs, size=16, color=INK, font=BODY, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, italic=False, name=None):
    """runs: str, or list of paragraphs; a paragraph is a str or a list of (text, {opts})."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paras = runs if isinstance(runs, list) else [runs]
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        pieces = p if isinstance(p, list) else [(p, {})]
        for t, o in pieces:
            r = para.add_run()
            r.text = t
            f = r.font
            f.name = o.get("font", font)
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", italic)
            f.color.rgb = o.get("color", color)
    return tb


def bullets(slide, x, y, w, h, items, size=17, color=INK, gap=8):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, item in enumerate(items):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.space_after = Pt(gap)
        pieces = item if isinstance(item, list) else [(item, {})]
        first = True
        for t, o in pieces:
            r = para.add_run()
            r.text = ("•  " if first else "") + t
            first = False
            r.font.name = BODY
            r.font.size = Pt(o.get("size", size))
            r.font.bold = o.get("bold", False)
            r.font.color.rgb = o.get("color", color)
    return tb


def box(slide, x, y, w, h, fill=CARD, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line:
        s.line.color.rgb = line
        s.line.width = Pt(1.25)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    return s


def circle_num(slide, x, y, d, label, fill=NAVY, color=WHITE, size=16):
    c = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    c.fill.solid()
    c.fill.fore_color.rgb = fill
    c.line.fill.background()
    c.shadow.inherit = False
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size = Pt(size)
    r.font.bold = True
    r.font.name = BODY
    r.font.color.rgb = color
    return c


def footer(slide, dark=False):
    slide_no[0] += 1
    c = RGBColor(0xA9, 0xB4, 0xC8) if dark else MUTED
    text(slide, 0.6, 7.05, 8, 0.3, "IT457 Cloud Computing  ·  Netflix on AWS and Chaos Engineering", size=10, color=c)
    text(slide, W - 1.6, 7.05, 1.0, 0.3, str(slide_no[0]), size=10, color=c, align=PP_ALIGN.RIGHT)


def content(title, kicker=None, notes=""):
    s = prs.slides.add_slide(BLANK)
    bg(s, WHITE)
    if kicker:
        text(s, 0.6, 0.38, 10, 0.3, kicker.upper(), size=12, color=TEAL, bold=True)
    text(s, 0.6, 0.68, W - 1.2, 0.8, title, size=32, color=NAVY, font=HEAD, bold=True, name="Title")
    footer(s)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def divider(num, title, sub, notes=""):
    s = prs.slides.add_slide(BLANK)
    bg(s, NAVY)
    circle_num(s, 0.9, 2.55, 1.0, num, fill=TEAL, size=28)
    text(s, 2.25, 2.45, 10, 0.9, title, size=40, color=WHITE, font=HEAD, bold=True)
    text(s, 2.25, 3.4, 10, 0.8, sub, size=18, color=RGBColor(0xC9, 0xD3, 0xE6))
    footer(s, dark=True)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def stat(slide, x, y, w, value, label, color=NAVY, vsize=44, lsize=13):
    vh = vsize / 72 * 1.25
    text(slide, x, y, w, vh, value, size=vsize, color=color, font=HEAD, bold=True)
    text(slide, x, y + vh + 0.02, w, 0.7, label, size=lsize, color=MUTED)


def picture(slide, path, x, y, w=None, h=None):
    kw = {}
    if w:
        kw["width"] = Inches(w)
    if h:
        kw["height"] = Inches(h)
    return slide.shapes.add_picture(str(ROOT / path), Inches(x), Inches(y), **kw)


def fit_picture(slide, path, x, y, max_w, max_h):
    from PIL import Image
    iw, ih = Image.open(ROOT / path).size
    scale = min(max_w / iw, max_h / ih)
    w, h = iw * scale, ih * scale
    return picture(slide, path, x + (max_w - w) / 2, y + (max_h - h) / 2, w=w, h=h)


def bar_chart(slide, x, y, w, h, cats, vals, colors, title, fmt='0.0', vmax=None, unit=""):
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series(title, vals)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    ch.has_legend = False
    ch.has_title = True
    ch.chart_title.text_frame.text = title
    tp = ch.chart_title.text_frame.paragraphs[0]
    tp.runs[0].font.size = Pt(14)
    tp.runs[0].font.bold = True
    tp.runs[0].font.color.rgb = INK
    tp.runs[0].font.name = BODY
    plot = ch.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format = fmt + unit
    dl.number_format_is_linked = False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(14)
    dl.font.bold = True
    dl.font.color.rgb = INK
    dl.font.name = BODY
    for i, c in enumerate(colors):
        pt = plot.series[0].points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = c
    va = ch.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = RGBColor(0xDD, 0xE1, 0xE8)
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(11)
    va.tick_labels.font.color.rgb = MUTED
    va.tick_labels.font.name = BODY
    if vmax is not None:
        va.maximum_scale = vmax
        va.minimum_scale = 0
    ca = ch.category_axis
    ca.tick_labels.font.size = Pt(12)
    ca.tick_labels.font.color.rgb = INK
    ca.tick_labels.font.name = BODY
    ca.format.line.color.rgb = RGBColor(0xBB, 0xC2, 0xCE)
    return ch


def table(slide, x, y, w, rows, col_w, size=13, header_fill=NAVY, row_h=0.42, verdict_col=None):
    nr, nc = len(rows), len(rows[0])
    gt = slide.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(row_h * nr)).table
    for j, cw in enumerate(col_w):
        gt.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        gt.rows[i].height = Inches(row_h)
        for j, val in enumerate(row):
            cell = gt.cell(i, j)
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.margin_top = cell.margin_bottom = Inches(0.04)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = header_fill if i == 0 else (WHITE if i % 2 else LIGHT)
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            r = p.add_run()
            r.text = str(val)
            r.font.name = BODY
            r.font.size = Pt(size)
            r.font.bold = i == 0
            r.font.color.rgb = WHITE if i == 0 else INK
            if verdict_col is not None and j == verdict_col and i > 0:
                v = str(val).lower()
                r.font.bold = True
                r.font.color.rgb = TEAL if v.startswith("accepted") else (AMBER if v.startswith("partly") else MUTED)
    return gt


# =====================================================================
# 1. Title
s = prs.slides.add_slide(BLANK)
bg(s, NAVY)
text(s, 0.9, 1.5, 11.5, 0.4, "IT457 CLOUD COMPUTING  ·  CASE STUDY PROJECT", size=14, color=RGBColor(0x8F, 0xD3, 0xC8), bold=True)
text(s, 0.9, 2.05, 11.5, 1.9, "Migrate, then break it on purpose", size=50, color=WHITE, font=HEAD, bold=True)
text(s, 0.9, 3.25, 11.5, 0.9, "Netflix's move to AWS and chaos engineering, reproduced and measured in miniature",
     size=22, color=RGBColor(0xC9, 0xD3, 0xE6))
box(s, 0.9, 4.65, 7.6, 1.05, fill=NAVY_2)
text(s, 1.15, 4.8, 7.2, 0.8, [[("Claim we test:  ", {"bold": True, "color": RGBColor(0x8F, 0xD3, 0xC8)}),
                              ("moving to the cloud is not enough; the architecture is what makes a system survive failure.",
                               {"color": WHITE})]], size=17)
text(s, 0.9, 6.2, 11, 0.4, "Team: [names and roll numbers]   ·   November 2026", size=14, color=RGBColor(0xA9, 0xB4, 0xC8))
slide_no[0] += 1
s.notes_slide.notes_text_frame.text = (
    "Open with the one-sentence claim. Netflix is famous for 'moving to AWS', but what actually made it resilient was "
    "re-architecting and then deliberately breaking its own systems. We rebuilt that journey at small scale and measured it.")

# 2. Agenda / at a glance
s = content("The project at a glance", "Overview",
            "Three parts: the case, what we built, what we measured. Headline numbers are on the right so the audience "
            "knows where we are going.")
items = [("1", "The case", "Why Netflix left its data center, and how it rebuilt on AWS (2008–2016)"),
         ("2", "Our experiment", "Same app in four stages: laptop, one VM, refactored on AWS, plus chaos"),
         ("3", "Results", "Availability under failure, recovery, scale-out, circuit breaker, cost"),
         ("4", "Lessons", "What held, what did not, and the limits of a small simulation")]
for i, (n, h, d) in enumerate(items):
    yy = 1.75 + i * 1.2
    circle_num(s, 0.7, yy, 0.62, n, fill=NAVY)
    text(s, 1.6, yy - 0.02, 5.6, 0.4, h, size=20, bold=True, color=NAVY)
    text(s, 1.6, yy + 0.42, 5.6, 0.6, d, size=14, color=MUTED)
box(s, 7.75, 1.7, 4.95, 4.85, fill=LIGHT)
text(s, 8.1, 1.95, 4.3, 0.4, "HEADLINE RESULTS (MEASURED ON AWS)", size=12, bold=True, color=TEAL)
stat(s, 8.1, 2.4, 4.4, f"{S1E1['availability_pct']:.1f}%", "one rehosted VM loses its only instance", color=RED)
stat(s, 8.1, 3.75, 4.4, f"{S2E1['availability_pct']:.1f}–{S2E2['availability_pct']:.1f}%",
     "refactored design: random kills and a lost AZ", color=TEAL)
stat(s, 8.1, 5.1, 4.4, f"{min(e['time_to_restore_capacity_s'] for e in S2E1['events'] if e['time_to_restore_capacity_s']):.0f}–"
                       f"{max(e['time_to_restore_capacity_s'] for e in S2E1['events'] if e['time_to_restore_capacity_s']):.0f} s",
     "to self-heal, with no human action", color=NAVY)

# ---------------- Part 1: the case ----------------
divider("1", "The case", "Netflix, 2008–2016: from one data center to hundreds of services on AWS",
        "Part one is the case analysis. Keep this to about three minutes in the live talk.")

# 4. The incident
s = content("2008: one database failure stopped the business", "The problem",
            "Database corruption in Netflix's own data center stopped DVD shipping for about three days [R3]. "
            "The root cause was not bad luck but design: single points of failure at every layer, and capacity bought "
            "months ahead. Streaming was about to make availability matter far more.")
stat(s, 0.6, 1.75, 3.6, "3 days", "DVD shipping stopped by one database failure [R3]", color=RED, vsize=60)
stat(s, 0.6, 3.75, 3.6, "7 years", "to finish the move to AWS (2009 → Jan 2016) [R3]", color=NAVY, vsize=60)
cards = [("One site, one big database", "A vertically scaled relational database in one data center: lose it, lose everything."),
         ("A monolith", "One failure or one bad deploy could take down the whole application."),
         ("Slow capacity", "Hardware bought months ahead for peaks that were growing fast and hard to predict."),
         ("Undifferentiated work", "Running data centers consumed engineers without improving the product [R1].")]
for i, (h, d) in enumerate(cards):
    cx, cy = 4.75 + (i % 2) * 4.05, 1.75 + (i // 2) * 2.45
    box(s, cx, cy, 3.8, 2.15, fill=LIGHT)
    circle_num(s, cx + 0.25, cy + 0.25, 0.45, "!", fill=RED, size=16)
    text(s, cx + 0.85, cy + 0.27, 2.8, 0.5, h, size=16, bold=True, color=NAVY)
    text(s, cx + 0.25, cy + 0.9, 3.35, 1.2, d, size=14, color=INK)

# 5. Decision and timeline
s = content("They chose to rebuild, not just to move", "The decision",
            "Netflix chose AWS for elasticity and focus, not lower unit cost [R1]. It refactored almost everything into "
            "microservices rather than rehosting the monolith [R3], which is why it took seven years. Billing moved last.")
events = [("2008", "Database corruption; decision to leave the data center"),
          ("2009", "Migration begins with non-customer-facing work"),
          ("2010–11", "Streaming on AWS; Chaos Monkey; Simian Army"),
          ("2012", "Christmas Eve ELB outage in us-east-1 (~20 h impact)"),
          ("2013–15", "Multi-region active-active; Chaos Kong drills"),
          ("Jan 2016", "Last data center pieces (billing) shut down")]
line = s.shapes.add_connector(1, Inches(0.73), Inches(3.05), Inches(10.83), Inches(3.05))
line.line.color.rgb = RGBColor(0xBB, 0xC2, 0xCE)
line.line.width = Pt(2.5)
for i, (yr, d) in enumerate(events):
    cx = 0.73 + i * 2.02
    dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - 0.13), Inches(2.92), Inches(0.26), Inches(0.26))
    dot.fill.solid()
    dot.fill.fore_color.rgb = RED if i in (0, 3) else TEAL
    dot.line.fill.background()
    text(s, cx - 0.13, 2.2, 1.9, 0.5, yr, size=18, bold=True, color=NAVY)
    text(s, cx - 0.13, 3.4, 1.85, 1.4, d, size=13, color=INK)
box(s, 0.6, 5.1, 12.1, 1.55, fill=LIGHT)
text(s, 0.95, 5.3, 11.4, 1.2, [[("Rehost vs refactor.  ", {"bold": True, "color": NAVY}),
                                ("In the AWS \"6 Rs\" [R24], lifting the monolith onto VMs is rehost; Netflix refactored: "
                                 "\"rebuilding virtually all of our technology\" as cloud-native microservices [R3]. "
                                 "Our S1 and S2 stages reproduce exactly this choice.", {})]], size=16)

# 6. Architecture before/after
s = content("Each new layer removes a single point of failure", "Architecture",
            "Walk the figure left to right: monolith to microservices, Oracle to Cassandra, one data center to Auto Scaling "
            "Groups across zones and regions, plus Open Connect for video. Point out that each change removes one SPOF.")
fit_picture(s, "docs/diagrams/netflix-before-after.png", 0.6, 1.6, 12.1, 5.3)

# 7. Chaos engineering
s = content("Chaos engineering: break things on purpose", "Resilience practice",
            "Chaos Monkey kills instances, Gorilla an AZ, Kong a region. FIT and ChAP then narrowed the blast radius "
            "again by experimenting on a small slice of real traffic with automatic stop conditions [R4, R7, R8].")
steps = [("Chaos Monkey", "2010–11", "Terminates random instances in business hours"),
         ("Chaos Gorilla", "Simian Army", "Takes out a whole Availability Zone"),
         ("Chaos Kong", "2013+", "Evacuates an entire AWS region"),
         ("FIT", "2014", "Injects failures into chosen requests"),
         ("ChAP", "2017", "Automated experiment vs control on live traffic")]
for i, (n, yr, d) in enumerate(steps):
    cx = 0.6 + i * 2.48
    box(s, cx, 1.8, 2.25, 2.6, fill=LIGHT if i < 3 else CARD)
    circle_num(s, cx + 0.2, 2.0, 0.5, str(i + 1), fill=RED if i < 3 else TEAL, size=16)
    text(s, cx + 0.2, 2.65, 1.95, 0.45, n, size=17, bold=True, color=NAVY)
    text(s, cx + 0.2, 3.05, 1.95, 0.35, yr, size=12, color=MUTED, italic=True)
    text(s, cx + 0.2, 3.4, 1.9, 1.0, d, size=13, color=INK)
text(s, 0.6, 4.75, 12, 0.4, "Principles of chaos engineering [R8]", size=18, bold=True, color=NAVY)
bullets(s, 0.6, 5.2, 12.1, 1.6, [
    "Define a measurable steady state (Netflix: stream starts per second · ours: % of home pages answered 200 within 1 s)",
    "Hypothesise it continues, inject real-world failures, try to disprove the hypothesis",
    "Minimise the blast radius, and run continuously in production-like conditions"], size=15, gap=5)

# 8. Evidence
s = content("Did it work? Same regional failure, before and after", "Evidence",
            "Christmas Eve 2012: AWS ELB state deleted in us-east-1, Netflix TV streaming in the Americas disrupted about "
            "20 hours. September 2015: DynamoDB errors in us-east-1 for about 5 hours, many AWS customers hit, Netflix "
            "reported no significant impact [R26]. Caveat: Netflix did not credit a single tool.")
for i, (when, what, impact, col) in enumerate([
        ("24 Dec 2012", "ELB failure, us-east-1", "~20 hours of disrupted streaming in the Americas", RED),
        ("20 Sep 2015", "DynamoDB failure, us-east-1", "No significant impact: traffic moved to other regions", TEAL)]):
    cx = 0.6 + i * 6.2
    box(s, cx, 1.8, 5.9, 3.4, fill=LIGHT)
    text(s, cx + 0.35, 2.05, 5.2, 0.5, when, size=16, bold=True, color=MUTED)
    text(s, cx + 0.35, 2.5, 5.2, 0.6, what, size=24, bold=True, color=NAVY, font=HEAD)
    text(s, cx + 0.35, 3.4, 5.2, 1.4, impact, size=20, color=col, bold=True)
text(s, 0.6, 5.55, 12.1, 1.2, [[("Cost note.  ", {"bold": True, "color": NAVY}),
                               ("Netflix says cloud cost per streaming start ended up a fraction of the data center cost [R3], "
                                "yet it delivers video from its own Open Connect CDN [R5]: owning wins for huge, steady traffic. "
                                "Our cost model (S5) reproduces that split.", {})]], size=16)

# ---------------- Part 2: experiment ----------------
divider("2", "Our experiment", "One movie-catalogue app, four stages, hypotheses fixed before testing",
        "Part two: what we built. Emphasise that hypotheses and thresholds were fixed in Week 2, before any test.")

# 10. Stages
s = content("Same app, four stages: the Netflix journey in miniature", "What we built",
            "S0 laptop monolith; S1 the same container on one EC2 instance (rehost); S2 three services in an Auto Scaling "
            "Group across two AZs behind an ALB with RDS (refactor); S3 chaos tools; S5 cost model. All AWS built with Terraform.")
fit_picture(s, "docs/diagrams/mini-netflix-stages.png", 0.5, 1.55, 7.6, 5.35)
rows = [("S0", "Laptop Docker monolith + Postgres", "Pre-2009 data center"),
        ("S1", "Same container, 1 × EC2 t3.micro", "Rehost"),
        ("S2", "3 services, ASG 2–4 in 2 AZs, ALB, RDS", "Refactor"),
        ("S3/4", "boto3 Chaos Monkey, AZ kill, faults", "Simian Army"),
        ("S5", "AWS vs GCP vs on-prem cost model", "Open Connect choice")]
for i, (st, what, par) in enumerate(rows):
    yy = 1.65 + i * 1.03
    box(s, 8.35, yy, 4.4, 0.9, fill=LIGHT)
    text(s, 8.55, yy + 0.1, 0.9, 0.7, st, size=18, bold=True, color=TEAL, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 9.45, yy + 0.1, 3.2, 0.4, what, size=13, bold=True, color=NAVY)
    text(s, 9.45, yy + 0.48, 3.2, 0.35, par, size=12, color=MUTED)

# 11. Hypotheses
s = content("Six hypotheses, with pass criteria fixed in advance", "Method",
            "Fixing thresholds in advance stops us bending results afterwards. 99% / 2× / 500 ms act as a simple SLO [R18].")
table(s, 0.6, 1.7, 12.1, [
    ("ID", "Hypothesis", "Pass criterion"),
    ("H1", "Lift-and-shift (S1) gains nothing in resilience", "Availability clearly below 99%; outage ends only on manual action"),
    ("H2", "Refactored S2 survives loss of any single instance", "≥ 99% over 10 min with kills every 2–3 min; p95 ≤ 2× baseline"),
    ("H3", "S2 restores capacity automatically", "ASG restores desired count with no human action; time reported"),
    ("H4", "S2 scales out under load with acceptable latency", "p95 < 500 ms as instances rise from 2 toward 4"),
    ("H5", "Circuit breaker + fallback keeps the page up", "With recommendations down: HTTP 200 with breaker, errors without"),
    ("H6", "Cloud cheaper small/variable; owning cheaper large/steady", "Cost model shows a break-even point"),
], [0.8, 5.2, 6.1], size=14, row_h=0.62)

# 12. Experiments + measurement
s = content("Experiments: one failure at a time, measured every second", "Method",
            "Steady state is the share of home-page requests answered 200 within 1 s, computed per second from our own "
            "load generator, which logs every request with status, latency, the EC2 instance that served it and whether "
            "the fallback was used.")
exps = [("E0", "Steady load, no faults", "baseline"), ("E1", "Kill a random instance every 2–3 min", "H1–H3"),
        ("E2", "Kill every instance in one AZ", "H2, H3"), ("E3", "+300 ms latency on recommendations", "H5"),
        ("E4", "Stop the recommendations service", "H5"), ("E5", "Ramp load to force scale-out", "H4")]
for i, (e, d, h) in enumerate(exps):
    cx, cy = 0.6 + (i % 3) * 4.1, 1.75 + (i // 3) * 1.6
    box(s, cx, cy, 3.85, 1.35, fill=LIGHT)
    circle_num(s, cx + 0.22, cy + 0.33, 0.68, e, fill=NAVY if i < 3 else TEAL, size=15)
    text(s, cx + 1.1, cy + 0.25, 2.6, 0.7, d, size=14, bold=True, color=NAVY)
    text(s, cx + 1.1, cy + 0.88, 2.6, 0.35, "tests " + h, size=12, color=MUTED)
bullets(s, 0.6, 5.1, 12.1, 1.8, [
    [("Load: ", {"bold": True}), ("own Python generator, 20 virtual users (ramp for E5), 5–10 min per run", {})],
    [("Chaos: ", {"bold": True}), ("boto3 Chaos Monkey restricted to tagged instances, refuses if > 4 match, dry-run mode", {})],
    [("Evidence: ", {"bold": True}), ("requests.csv, events.csv, watch.csv (ASG and target health every 2 s), AWS activity log", {})]],
    size=15, gap=5)

# ---------------- Part 3: results ----------------
divider("3", "Results", "Local runs: 28 Oct and 4 Nov 2026  ·  AWS runs: 14 Nov 2026, us-east-1",
        "Part three: results. All numbers are measured; raw CSVs are in results/ and every number can be recomputed.")

# 14. Scoreboard
s = content("Scoreboard: four hypotheses accepted, two partly", "Results",
            "Read the verdicts first, then go into each one. Be upfront that H2 missed its threshold by 0.08 points and why, "
            "and that H4's latency criterion was masked by the load generator, not the servers.")
H4_RESULT = "ASG scaled 2 → 4 automatically; latency masked by our laptop's limit"
H4_VERDICT = "Partly tested"
table(s, 0.6, 1.7, 12.1, [
    ("", "Measured result", "Verdict"),
    ("H1  one VM", f"{S1E1['availability_pct']:.1f}% availability; {S1E1['longest_outage_s']} s outage never ended for clients", "Accepted"),
    ("H2  survive a kill", f"{S2E1['availability_pct']:.2f}% (3 kills), {S2E2['availability_pct']:.2f}% (AZ lost); longest gap 5 s", "Partly accepted"),
    ("H3  self-heal", "Every instance replaced automatically; capacity back in 114–176 s", "Accepted"),
    ("H4  scale out", H4_RESULT, H4_VERDICT),
    ("H5  circuit breaker", f"Recs down: {med([e['availability_pct'] for e in E4_ON]):.0f}% with vs {med([e['availability_pct'] for e in E4_OFF]):.1f}% without", "Accepted"),
    ("H6  cost", "Break-even ≈ 240–308 vCPU and ≈ 187 TB/month (estimate)", "Accepted"),
], [2.6, 7.2, 2.3], size=15, row_h=0.66, verdict_col=2)

# 15. S1 vs S2 headline chart
s = content("Same app, same kind of failure: the architecture decides", "AWS · H1, H2",
            "The core result. One rehosted VM: 37.5%. Refactored design under three random kills: 98.9%; losing a whole "
            "zone: 99.5%. Moving to the cloud did not make S1 resilient; the redundancy, the load balancer and automatic "
            "replacement did.")
bar_chart(s, 0.6, 1.55, 7.7, 5.3, ["S1: stop the only VM", "S2: 3 random kills", "S2: lose a whole AZ"],
          [S1E1["availability_pct"], S2E1["availability_pct"], S2E2["availability_pct"]], [RED, TEAL, TEAL],
          "Home-page availability during the failure run (%)", fmt="0.0", vmax=110)
stat(s, 8.75, 1.75, 4.0, f"{S1E1['longest_outage_s']} s", "longest outage on one VM", color=RED)
stat(s, 8.75, 3.3, 4.0, "5 s", "longest gap on the refactored design", color=TEAL)
stat(s, 8.75, 4.85, 4.0, "0", "human actions needed by S2 to recover", color=NAVY)

# 16. S1 story
s = content("S1: the server came back, the users did not", "AWS · S1 E1 · H1",
            "We stopped the only instance 63 s in; our 'operator' restarted it 60 s later. It was running again 73 s after "
            "the stop, but it came back with a new public IP, so every client pointing at the old address stayed down for "
            "the rest of the run. Rehosting kept the single point of failure and added a manual recovery step.")
fit_picture(s, "results/s1/e1/run1/timeline.png", 0.5, 1.55, 7.9, 5.35)
steps = [("1:03", "Chaos script stops the only instance", RED),
         ("2:03", "Operator restarts it (scripted, +60 s)", AMBER),
         ("~2:16", "Instance running again", NAVY),
         ("10:00", "Clients still failing: new IP 3.239.110.80, old 44.203.10.200 dead", RED)]
for i, (t, d, c) in enumerate(steps):
    yy = 1.75 + i * 1.22
    circle_num(s, 8.7, yy, 0.32, "", fill=c)
    text(s, 9.2, yy - 0.06, 3.5, 0.4, t, size=16, bold=True, color=NAVY)
    text(s, 9.2, yy + 0.32, 3.55, 0.8, d, size=13, color=INK)

# 17. S2 self-healing
s = content("S2: three instances killed, the service kept answering", "AWS · S2 E1 · H2, H3",
            "Three random terminations at 63, 244 and 421 s. The ASG launched each replacement within 2 s; full capacity was "
            "back in 114–176 s. The small loss is the ALB detection window: 10 s health checks, two failures needed, so "
            "requests reached a dying instance for up to about 20 s. That is why E1 missed 99% by 0.08 points.")
fit_picture(s, "results/s2/e1/run1/timeline.png", 0.5, 1.55, 7.9, 5.35)
stat(s, 8.75, 1.65, 4.0, f"{S2E1['availability_pct']:.2f}%", "availability over 10 min, 3 kills", color=TEAL, vsize=40)
stat(s, 8.75, 3.0, 4.0, "< 2 s", "from termination to replacement launch (AWS activity log)", color=NAVY, vsize=40)
stat(s, 8.75, 4.35, 4.0, "114–176 s", "until two healthy instances again", color=NAVY, vsize=40)
text(s, 8.75, 5.85, 4.0, 1.0, "Fix for the missing 0.08 points: shorter health-check interval or connection draining.",
     size=13, color=MUTED, italic=True)

# 18. AZ loss + evidence
s = content("Losing a whole AZ, and proof it ran on AWS", "AWS · S2 E2 · evidence",
            "Chaos Gorilla in miniature: every instance in us-east-1a terminated at once; the service stayed up from us-east-1b "
            "at 99.47%. Evidence: AWS's own Auto Scaling activity log pairs every termination with a launch two seconds later, "
            "and requests.csv records the EC2 instance ID that served every request.")
stat(s, 0.6, 1.7, 3.6, f"{S2E2['availability_pct']:.2f}%", "availability with a whole AZ lost (SLO met)", color=TEAL)
stat(s, 0.6, 3.2, 3.6, f"{S2E2['longest_outage_s']} s", "longest gap", color=NAVY)
stat(s, 0.6, 4.7, 3.6, f"{S2E2['mean_time_to_restore_capacity_s']:.0f} s", "to restore capacity from the other AZ", color=NAVY)
acts = [line.split("\t") for line in (ROOT / "results/aws-logs/s2-asg-activities.txt").read_text(encoding="utf-8").splitlines() if "\t" in line]
rows = [("Time (UTC)", "AWS Auto Scaling activity")]
for t, _st, d in reversed(acts[:8]):
    rows.append((t[11:19], d.replace("EC2 instance", "instance")))
table(s, 4.6, 1.7, 8.1, rows, [1.6, 6.5], size=13, row_h=0.5)
text(s, 4.6, 6.35, 8.1, 0.4, "Source: aws autoscaling describe-scaling-activities, saved in results/aws-logs/", size=11, color=MUTED, italic=True)

# 19. E5 scale-out (filled from E5 results)
E5 = {}
e5_path = ROOT / "results/aws-logs/s2-e5-findings.json"
if e5_path.exists():
    E5 = json.loads(e5_path.read_text(encoding="utf-8"))
s = content(E5.get("title", "Scale-out under load"), "AWS · S2 E5 · H4", E5.get("notes", ""))
if E5.get("image"):
    fit_picture(s, E5["image"], 0.5, 1.55, 7.9, 5.35)
for i, (v, l, c) in enumerate(E5.get("stats", [])):
    stat(s, 8.75, 1.65 + i * 1.4, 4.0, v, l, color={"teal": TEAL, "navy": NAVY, "red": RED, "amber": AMBER}[c], vsize=36)
if E5.get("footnote"):
    text(s, 8.75, 6.05, 4.0, 0.9, E5["footnote"], size=12, color=MUTED, italic=True)

# 20. Circuit breaker E4
s = content("Circuit breaker: one dead service, page stays up", "Local S2 · E4 · H5",
            "Recommendations stopped for 120 of 300 s. Without the breaker every home page failed with 502 for the whole "
            "fault (59.6%). With a 250 ms timeout, pybreaker and a popular-list fallback, the page stayed at 100% in all "
            "three runs, with 40.5% of pages served from the fallback. This is Netflix's Hystrix pattern.")
bar_chart(s, 0.6, 1.55, 6.3, 5.3, ["Breaker OFF", "Breaker ON"],
          [med([e['availability_pct'] for e in E4_OFF]), med([e['availability_pct'] for e in E4_ON])], [RED, TEAL],
          "Home-page availability, recommendations down (median of 3 runs, %)", fmt="0.0", vmax=110)
box(s, 7.3, 1.75, 5.4, 4.9, fill=LIGHT)
text(s, 7.65, 1.95, 4.8, 0.4, "HOW THE BREAKER WORKS", size=12, bold=True, color=TEAL)
flow = [("Call recommendations with a 250 ms timeout", NAVY), ("After 5 failures the breaker opens for 10 s", AMBER),
        ("Open: skip the call, serve a generic popular list", TEAL), ("After 10 s: one trial call; success closes it", NAVY)]
for i, (d, c) in enumerate(flow):
    yy = 2.5 + i * 0.95
    circle_num(s, 7.65, yy, 0.5, str(i + 1), fill=c, size=14)
    text(s, 8.35, yy + 0.02, 4.1, 0.8, d, size=15, color=INK)

# 21. E3 slow vs down
s = content("Slow is worse than down: the timeout fixes it", "Local S2 · E3 · H5",
            "Adding 300 ms to recommendations caused no errors, but without the breaker home-page p95 rose to 803 ms and "
            "throughput fell 30% as workers waited. With the 250 ms timeout the slow service was treated as failed: p95 21 ms.")
bar_chart(s, 0.6, 1.55, 6.3, 5.3, ["Breaker OFF", "Breaker ON"], [E3_OFF["home_p95_ms"], E3_ON["home_p95_ms"]], [RED, TEAL],
          "Home-page p95 latency with +300 ms on recommendations (ms)", fmt="0", vmax=950)
stat(s, 7.4, 1.75, 5.2, f"{E3_OFF['home_p95_ms'] / E3_ON['home_p95_ms']:.0f}×", "higher p95 latency without the breaker", color=RED)
E0L = summary("local-s2/e0/run1")
stat(s, 7.4, 3.3, 5.2, f"−{(1 - E3_OFF['throughput_rps'] / E0L['throughput_rps']) * 100:.0f}%",
     f"throughput vs no fault ({E0L['throughput_rps']:.0f} → {E3_OFF['throughput_rps']:.0f} req/s), breaker off", color=RED)
stat(s, 7.4, 4.85, 5.2, f"{E3_ON['fallback_pct_of_home']:.0f}%", "of pages used the fallback, with the breaker on", color=TEAL)

# 22. Cost
s = content("Cost: rent the brain, own the bytes", "S5 cost model · H6 · estimates",
            "All figures are estimates from cost/cost_model.py with on-demand list prices. Break-even for compute is around "
            "240–308 average vCPU; for video delivery around 187 TB/month. Netflix is far beyond both for video, which is "
            "why it built Open Connect while keeping the control plane on AWS.")
fit_picture(s, "results/charts/cost_breakeven.png", 0.5, 1.6, 8.3, 4.6)
stat(s, 9.1, 1.7, 3.6, "≈ 240–308", "average vCPU where owning compute breaks even", color=NAVY, vsize=36)
stat(s, 9.1, 3.2, 3.6, "≈ 187 TB", "per month where an own CDN breaks even", color=NAVY, vsize=36)
stat(s, 9.1, 4.7, 3.6, "$0.13M vs $2.1M", "per month at 100 PB: own CDN vs CloudFront", color=TEAL, vsize=28)
text(s, 0.6, 6.4, 8.2, 0.4, "Our stages: S1 ≈ $0.016/h; S2 ≈ $0.099/h at 2 instances, $0.137/h at 4. The AWS session cost under $1.",
     size=13, color=MUTED, italic=True)

# 23. Limitations
s = content("What our simulation cannot show", "Critical discussion",
            "Be honest and specific; graders value this. Each limitation says what it affects.")
lims = [("One run per AWS experiment", "No ranges for S1/S2; the 0.08-point H2 miss is within likely noise."),
        ("Load generated from India", "≈ 210 ms of every AWS latency is network; the laptop, not the servers, capped load."),
        ("Scripted operator in S1", "Restart came exactly 60 s after the stop; a real on-call response is usually slower."),
        ("Tiny scale", "3 services, ≤ 4 instances: no retry storms, deep dependency chains or replication lag."),
        ("No region failure", "Chaos Kong-style evacuation needs two regions; out of budget and time."),
        ("Cost model is approximate", "List prices not re-checked against calculators; on-prem costs are our estimates.")]
for i, (h, d) in enumerate(lims):
    cx, cy = 0.6 + (i % 2) * 6.15, 1.7 + (i // 2) * 1.68
    box(s, cx, cy, 5.9, 1.45, fill=LIGHT)
    text(s, cx + 0.3, cy + 0.2, 5.3, 0.4, h, size=17, bold=True, color=NAVY)
    text(s, cx + 0.3, cy + 0.65, 5.35, 0.75, d, size=14, color=INK)

# 24. Conclusion
s = prs.slides.add_slide(BLANK)
bg(s, NAVY)
text(s, 0.9, 0.9, 11.5, 0.4, "CONCLUSION", size=14, bold=True, color=RGBColor(0x8F, 0xD3, 0xC8))
text(s, 0.9, 1.35, 11.5, 1.2, "Rehosting moves the problem; refactoring removes it", size=40, color=WHITE, font=HEAD, bold=True)
lessons = [("Measured on AWS", f"One VM: {S1E1['availability_pct']:.1f}%. Refactored: {S2E1['availability_pct']:.1f}–{S2E2['availability_pct']:.1f}% "
                               "and self-healed in about 2.5 minutes with no human action."),
           ("Measured locally", "A circuit breaker kept the page at 100% when a dependency died, and stopped a slow one "
                                "from raising p95 forty-fold."),
           ("Estimated", "Cloud wins for small, variable workloads; owning wins for huge, steady ones, as with Open Connect."),
           ("Next", "Repeat AWS runs, scale-out from a cloud load generator, AWS FIS, and a two-region Chaos Kong test.")]
for i, (h, d) in enumerate(lessons):
    yy = 2.85 + i * 1.0
    circle_num(s, 0.9, yy + 0.05, 0.45, str(i + 1), fill=TEAL, size=14)
    text(s, 1.6, yy, 2.6, 0.5, h, size=17, bold=True, color=WHITE)
    text(s, 4.2, yy, 8.4, 0.9, d, size=16, color=RGBColor(0xDD, 0xE4, 0xF0))
footer(s, dark=True)
s.notes_slide.notes_text_frame.text = (
    "End on the main lesson, then go to the demo. Netflix's own lesson was that the move was the smaller part; "
    "designing for failure and proving it by breaking things was the real work.")

# 25. Demo + Q&A + references
s = content("Live demo, questions and sources", "Thank you",
            "Run bash demo/demo.sh (about 4 minutes): breaker on returns 200 with fallback; breaker off returns 502. "
            "If the demo fails, play the recorded backup and continue.")
box(s, 0.6, 1.7, 5.6, 4.9, fill=NAVY)
text(s, 0.95, 1.95, 5.0, 0.4, "LIVE DEMO  ·  bash demo/demo.sh", size=13, bold=True, color=RGBColor(0x8F, 0xD3, 0xC8))
demo = ["Start the 3 services with the breaker ON", "Stop recommendations: page still 200 (fallback)",
        "Restart: breaker closes after 10 s", "Same app with the breaker OFF", "Stop recommendations: page returns 502"]
for i, d in enumerate(demo):
    yy = 2.55 + i * 0.75
    circle_num(s, 0.95, yy, 0.42, str(i + 1), fill=TEAL, size=13)
    text(s, 1.55, yy + 0.04, 4.5, 0.6, d, size=15, color=WHITE)
text(s, 6.6, 1.7, 6.1, 0.4, "KEY SOURCES", size=13, bold=True, color=TEAL)
bullets(s, 6.6, 2.15, 6.1, 4.6, [
    "[R1] Netflix Tech Blog, Four Reasons We Choose Amazon's Cloud (2010)",
    "[R3] Izrailevsky et al., Completing the Netflix Cloud Migration (2016)",
    "[R4] Netflix Tech Blog, The Netflix Simian Army (2011)",
    "[R7] Netflix Tech Blog, FIT (2014) and ChAP (2017)",
    "[R8] principlesofchaos.org · [R20] Basiri et al., IEEE Software (2016)",
    "[R24] AWS Prescriptive Guidance, migration strategies (6 Rs)",
    "[R26] Press reports of the 2012 and 2015 us-east-1 outages",
    "Full list, code and raw data: final report and project repository"], size=13, gap=6)

prs.save(OUT)
print(f"wrote {OUT} ({len(prs.slides)} slides)")
