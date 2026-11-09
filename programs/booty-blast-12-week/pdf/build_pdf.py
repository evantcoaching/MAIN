"""Build the printable client PDF from the Trainerize text files.

Usage: python3 build_pdf.py
Writes Booty_Blast_2.0_Client_Program.html next to this script, then prints it
to ../Booty_Blast_2.0_Client_Program.pdf with headless Chromium.
"""
import html
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
TXT = HERE.parent / "trainerize"
OUT_HTML = HERE / "Booty_Blast_2.0_Client_Program.html"
OUT_PDF = HERE.parent / "Booty_Blast_2.0_Client_Program.pdf"
CHROME = "/opt/pw-browsers/chromium"

SECTION_HEADS = ("FOCUS", "TODAY'S INTENT", "EFFORT THIS WEEK", "WARM UP", "SESSION TYPE",
                 "TEMPO STRUCTURE", "OBJECTIVE", "RECOVERY", "COOL DOWN", "SESSION COMPLETE")
EX_RE = re.compile(r"^(\d+|[A-F]\d)\.\s+(.*)$")
STAT_RE = re.compile(r"^(Sets|Reps|Tempo|Rest|Duration):\s*(.*)$")
SXR_RE = re.compile(r"^(\d+) x (.+)$")
INLINE_STAT_RE = re.compile(r"^(Tempo|Rest) (.+)$")


def esc(s):
    return html.escape(s, quote=False)


def is_section(line):
    return any(line.startswith(h) for h in SECTION_HEADS)


def parse(path):
    lines = path.read_text().rstrip().split("\n")
    i = 0
    head = []
    while lines[i].strip():
        head.append(lines[i].strip())
        i += 1
    blocks = []
    cur = None  # current exercise dict
    section = None
    link_next = False

    def close():
        nonlocal cur, section
        if cur:
            blocks.append(("ex", cur))
        if section:
            blocks.append(("section", section))
        cur = section = None

    for raw in lines[i:]:
        line = raw.strip()
        if not line:
            if cur and cur.get("open_cues"):
                cur["open_cues"] = False
            if section:
                blocks.append(("section", section))
                section = None
            continue
        if line == "Coach Ev":
            close()
            continue
        if line.startswith("TOTAL ="):
            close()
            blocks.append(("total", line))
            continue
        if line.startswith("REFUEL") or line.startswith("Week 9 RELOAD?"):
            close()
            blocks.append(("note", line))
            continue
        if line.startswith("BLOCK "):
            close()
            blocks.append(("group", line.split("|", 1)[1].strip() if "|" in line else line,
                           line.split("|")[0].replace("BLOCK", "Block").strip()))
            continue
        if is_section(line):
            close()
            section = {"title": line, "lines": []}
            continue
        m = EX_RE.match(line)
        if m and not section:
            close()
            label, name = m.groups()
            if name.upper() == "SUPERSET":
                blocks.append(("group", "Superset", label))
                continue
            cur = {"label": label, "name": name, "stats": [], "cues": [], "notes": [],
                   "bullets": [], "linked": link_next, "open_cues": False}
            link_next = False
            continue
        if section:
            section["lines"].append(line)
            continue
        if line.startswith("↓"):
            if cur:
                rest = line[1:].strip()
                if rest:
                    cur["notes"].append(rest)
                blocks.append(("ex", cur))
                cur = None
            link_next = True
            continue
        if cur is None:
            blocks.append(("note", line))
            continue
        sm = STAT_RE.match(line)
        if sm:
            k, v = sm.groups()
            if k == "Sets" and "(" in v:
                v, extra = v.split("(", 1)
                cur["notes"].append(extra.rstrip(")").strip().capitalize())
            cur["stats"].append((k, v.strip()))
            continue
        sm = SXR_RE.match(line)
        if sm and not cur["stats"]:
            cur["stats"] += [("Sets", sm.group(1)), ("Reps", sm.group(2))]
            continue
        sm = INLINE_STAT_RE.match(line)
        if sm:
            cur["stats"].append(sm.groups())
            continue
        if line in ("Cues", "Cue"):
            cur["open_cues"] = True
            continue
        if line.startswith("• "):
            cur["bullets"].append(line[2:])
            continue
        (cur["cues"] if cur["open_cues"] else cur["notes"]).append(line)
    close()
    return head, blocks


def weeks_for(phase_line):
    m = re.search(r"Weeks? (\d+)-(\d+)", phase_line)
    if m:
        return list(range(int(m.group(1)), int(m.group(2)) + 1))
    m = re.search(r"Weeks (\d+) & (\d+)", phase_line)
    if m:
        return [int(m.group(1)), int(m.group(2))]
    m = re.search(r"Week (\d+)", phase_line)
    return [int(m.group(1))] if m else []


def render_section(sec):
    t = sec["title"]
    lines = sec["lines"]
    title = t.title().replace("'S", "'s").replace("(2 Rounds)", "· 2 rounds")
    if t.startswith("TODAY'S INTENT"):
        return f'<div class="intent">{esc(" ".join(lines))}</div>'
    if t.startswith("EFFORT"):
        chips = "".join(
            f'<div class="effort-row"><b>{esc(l.split("=")[0].strip())}</b>'
            f'<span>{esc(l.split("=", 1)[1].strip())}</span></div>' for l in lines)
        return f'<div class="box effort"><h4>Effort this phase</h4>{chips}</div>'
    if t.startswith("WARM UP"):
        items = "".join(f"<li>{esc(l[2:] if l.startswith('• ') else l)}</li>" for l in lines)
        return f'<div class="box warm"><h4>{esc(title)}</h4><ul>{items}</ul></div>'
    if t.startswith("SESSION COMPLETE"):
        return f'<div class="complete">{"<br>".join(esc(l) for l in lines)}</div>'
    if len(lines) > 2 and all(len(l) < 30 and not l.startswith("• ") for l in lines[:-1]):
        tail = lines[-1] if len(lines[-1]) >= 30 else None
        short = lines[:-1] if tail else lines
        out = f'<p class="tags">{" · ".join(esc(l) for l in short)}</p>'
        if tail:
            out += f"<p>{esc(tail)}</p>"
        return f'<div class="sec"><h4>{esc(title)}</h4>{out}</div>'
    body = "".join(f"<li>{esc(l[2:])}</li>" if l.startswith("• ") else f"<p>{esc(l)}</p>" for l in lines)
    if "<li>" in body:
        body = "<ul>" + body.replace("<p>", "</ul><p>").replace("</p>", "</p><ul>") + "</ul>"
        body = body.replace("<ul></ul>", "")
    return f'<div class="sec"><h4>{esc(title)}</h4>{body}</div>'


def render_ex(ex, weeks):
    stats = "".join(f'<span class="stat"><i>{esc(k)}</i>{esc(v)}</span>' for k, v in ex["stats"])
    cues = "".join(f"<li>{esc(c)}</li>" for c in ex["cues"])
    notes = "".join(f'<p class="exnote">{esc(n)}</p>' for n in ex["notes"])
    bullets = "".join(f"<li>{esc(b)}</li>" for b in ex["bullets"])
    name = ex["name"].replace("★ PR LIFT", "").strip()
    pr = '<span class="pr">★ PR LIFT</span>' if "★" in ex["name"] else ""
    has_sets = any(k == "Sets" for k, _ in ex["stats"])
    log = ""
    if has_sets and weeks:
        cells = "".join(f'<div class="logcell"><span>Wk {w}</span></div>' for w in weeks)
        log = f'<div class="log n{len(weeks)}"><div class="loglabel">LOG · kg × reps</div>{cells}</div>'
    link = '<div class="link">↓ straight into</div>' if ex["linked"] else ""
    return (f'<div class="keep">{link}<div class="ex{" linked" if ex["linked"] else ""}">'
            f'<div class="exlabel">{esc(ex["label"])}</div><div class="exbody">'
            f'<div class="exhead"><h3>{esc(name)}</h3>{pr}</div>'
            f'<div class="stats">{stats}</div>{notes}'
            f'{"<ul class=bul>" + bullets + "</ul>" if bullets else ""}'
            f'{"<ul class=cues>" + cues + "</ul>" if cues else ""}</div>{log}</div></div>')


def render_workout(path, kicker, accent="var(--berry)"):
    head, blocks = parse(path)
    weeks = weeks_for(head[1])
    title, phase_line, subs = head[0], head[1], head[2:]
    top, body = [], []
    for kind, *rest in blocks:
        if kind == "section":
            sec = rest[0]
            target = body if sec["title"].startswith(("SESSION COMPLETE", "RECOVERY", "COOL DOWN")) else top
            target.append(render_section(sec))
        elif kind == "ex":
            body.append(render_ex(rest[0], weeks))
        elif kind == "group":
            name, label = rest
            body.append(f'<div class="group"><span>{esc(label)}</span>{esc(name)}</div>')
        elif kind == "total":
            body.append(f'<div class="total">{esc(rest[0])}</div>')
        elif kind == "note":
            body.append(f'<div class="note">{esc(rest[0])}</div>')
    # keep each group heading with the card that follows it
    merged = []
    for item in body:
        if merged and merged[-1].startswith('<div class="group"') and not item.startswith('<div class="group"'):
            merged[-1] = f'<div class="keep">{merged[-1]}{item}</div>'
        else:
            merged.append(item)
    body = merged
    # split top: text sections left, warm-up/effort boxes right
    left = [t for t in top if 'class="box' not in t]
    right = [t for t in top if 'class="box' in t]
    subtitle = " · ".join(esc(s) for s in subs)
    return f'''
<section class="page workout" style="--accent:{accent}">
  <header class="whead">
    <div class="kicker">{esc(kicker)}</div>
    <h2>{esc(title)}</h2>
    <div class="phase">{esc(phase_line)}</div>
    <div class="subs">{subtitle}</div>
  </header>
  <div class="intro"><div>{"".join(left)}</div><div>{"".join(right)}</div></div>
  <div class="exlist">{"".join(body)}</div>
</section>'''


def static_pages():
    cover = '''
<section class="page cover">
  <div class="cover-top">12-WEEK GLUTE SPECIALISATION</div>
  <h1>BOOTY<br>BLAST<span>2.0</span></h1>
  <p class="cover-sub">3 glute days · 1 upper body sculpt day · abs every session</p>
  <div class="cover-grid">
    <div><b>40</b><span>glute working sets a week</span></div>
    <div><b>5</b><span>movement patterns every session</span></div>
    <div><b>3</b><span>PR weeks to prove your progress</span></div>
  </div>
  <div class="cover-name">Name: <span></span> Start date: <span></span></div>
  <div class="cover-coach">Coach Ev</div>
</section>'''

    welcome = '''
<section class="page info">
  <h2 class="ptitle">How your week works</h2>
  <p class="lede">A science-backed training system designed to maximise glute growth, strength and shape through
  smart exercise selection, progressive overload and a plan for every week. Each session has a specific purpose.</p>
  <div class="days">
    <div class="day"><div class="dname">MON</div><h3>Lengthened</h3><p>Load the glutes in the <b>stretched</b> position. Slow lowering, own the bottom. Stretch under load is one of the strongest drivers of growth.</p><div class="dsets">13 glute sets</div></div>
    <div class="day up"><div class="dname">TUE</div><h3>Upper Sculpt</h3><p>Shoulders, back, triceps and posture. <b>A</b> (push priority) on odd weeks, <b>B</b> (pull priority) on even weeks. Thursday works too.</p><div class="dsets">+ abs</div></div>
    <div class="day"><div class="dname">WED</div><h3>Squeeze</h3><p><b>Horizontal</b> hip extension. Thrusts, bridges and back extensions for peak contraction and mind-muscle connection.</p><div class="dsets">13 glute sets</div></div>
    <div class="day"><div class="dname">FRI</div><h3>Power</h3><p>Heavy <b>vertical</b> hip extension. Your hardest session of the week, with two recovery days to follow.</p><div class="dsets">14 glute sets</div></div>
    <div class="day rest"><div class="dname">SAT · SUN</div><h3>Recover</h3><p>8–10k steps, 7–9 hours sleep, protein at every meal. Glutes grow between sessions, not during them.</p></div>
  </div>
  <h3 class="h3">Every glute session trains 5 patterns</h3>
  <div class="patterns">
    <div><b>Thrust &amp; Bridge</b><span>peak contraction</span></div>
    <div><b>Squat</b><span>deep, full range</span></div>
    <div><b>Lunge</b><span>single-leg strength</span></div>
    <div><b>Hinge</b><span>stretch + posterior chain</span></div>
    <div><b>Abduction</b><span>side glute, shape</span></div>
  </div>
  <div class="two">
    <div class="box"><h4>Tempo key</h4>
      <p>Four numbers, in seconds: <b>Lower – Bottom pause – Lift – Top pause</b>.</p>
      <p class="tempo"><span>3</span><span>1</span><span>1</span><span>0</span></p>
      <p>= 3 sec down, 1 sec pause, 1 sec up, no pause at the top.</p></div>
    <div class="box"><h4>RIR — reps in reserve</h4>
      <p><b>RIR 2</b> = you could have done 2 more good reps.</p>
      <p><b>Technical failure</b> = the next rep would break your form. Stop there.</p>
      <p>Each workout tells you how close to failure to train that week.</p></div>
  </div>
</section>'''

    timeline_rows = [
        ("1–3", "Phase 1 · BUILD", "Learn the movements, find your weights, build the base.", "build"),
        ("4", "PR WEEK #1", "Test your three big lifts + pull-ups.", "pr"),
        ("5–7", "Phase 2 · DEVELOP", "New exercises, heavier loads, first intensity techniques.", "dev"),
        ("8", "PR WEEK #2", "Beat your Week 4 numbers.", "pr"),
        ("9", "RELOAD or REMIX", "Your readiness check decides: recover, or try something new.", "reload"),
        ("10–11", "Phase 3 · PEAK", "Heaviest loads of the program. Leave nothing in the tank.", "peak"),
        ("12", "FINAL PR WEEK", "Show off 12 weeks of work.", "pr"),
    ]
    tl = "".join(f'<div class="tl {c}"><div class="tlw">Week{"s" if "–" in w else ""} {w}</div>'
                 f'<div><b>{n}</b><span>{d}</span></div></div>' for w, n, d, c in timeline_rows)
    plan = f'''
<section class="page info">
  <h2 class="ptitle">Your 12 weeks</h2>
  <div class="timeline">{tl}</div>
  <h3 class="h3">How to progress</h3>
  <div class="two">
    <div class="box"><h4>Add weight when you earn it</h4>
      <p>When you hit the <b>top of the rep range on every set</b> with good form, add weight next session:</p>
      <ul><li>Barbell &amp; belt squat: <b>+2.5–5 kg</b></li><li>Dumbbells: <b>+1–2 kg</b> each hand</li><li>Machines &amp; cables: <b>+1 pin or plate</b></li></ul>
      <p>Then build the reps back up. Can't add weight? Add a rep, slow the lowering or go a little deeper. Better than last time = progress.</p></div>
    <div class="box"><h4>Log every session</h4>
      <p>Every exercise has <b>log boxes</b> for each week. Write the weight and reps of your best set, e.g. <b>60 × 10</b>.</p>
      <p>No log = no overload. Your log is how you know you're getting stronger.</p>
      <h4 style="margin-top:10px">Intensity techniques</h4>
      <ul><li><b>Rest-pause:</b> rest 15 sec, max reps, rest 15 sec, max reps</li><li><b>Drop set:</b> drop ~25% and go again</li><li><b>Lengthened partials:</b> half reps in the stretch after your last full rep</li></ul></div>
  </div>
  <div class="quote">Train with purpose. Focus on quality movement. Embrace progressive overload. Consistency is what builds stronger, fuller, more resilient glutes.</div>
</section>'''
    return cover, welcome, plan


def divider(num, name, weeks, blurb, cls):
    return f'''
<section class="page divider {cls}">
  <div class="dnum">{"PHASE " + num if num.isdigit() else num}</div>
  <h2>{name}</h2>
  <div class="dweeks">{weeks}</div>
  <p>{blurb}</p>
</section>'''


def pr_page(weeks_label):
    lifts = [
        ("Monday", "Barbell RDL", "8-rep max", "Bar to mid-shin or lower, neutral spine, 3 sec lowering, hips fully locked out."),
        ("Wednesday", "Barbell Hip Thrust", "5-rep max", "Shins vertical at the top, pelvis tucked, 1 sec pause at lockout."),
        ("Friday", "Belt Squat (wide sumo)", "5-rep max", "Hip crease to knee height or lower, controlled descent, full lockout."),
        ("Upper B", "Pull-Up", "Max reps", "Full hang to chin over bar, no kipping. Not there yet? Least assistance for 5 clean reps."),
    ]
    cards = "".join(f'<div class="prcard"><div class="prday">{d}</div><h3>{l}</h3><div class="prtest">{t}</div><p>{v}</p></div>'
                    for d, l, t, v in lifts)
    return f'''
<section class="page info prpage">
  <div class="kicker">{weeks_label}</div>
  <h2 class="ptitle">★ PR WEEK</h2>
  <p class="lede">Run that week's normal workouts, with one change: each day has <b>one PR lift</b> that replaces its working sets. Every other exercise with 3 sets drops to 2 sets, so you're fresh to perform.</p>
  <div class="prgrid">{cards}</div>
  <div class="two">
    <div class="box"><h4>How to run your PR lift</h4>
      <ol><li><b>Ramp up:</b> 10 reps light → 6 @ ~50% → 4 @ ~70% → 2 @ ~85% of your target. Rest 90 sec–2 min.</li>
      <li><b>PR attempt:</b> up to 3 attempts at the target reps, 3–4 min rest. Stop as soon as a rep breaks form.</li>
      <li><b>Back-off set:</b> drop 15–20%, one set to RIR 1. Log it.</li></ol></div>
    <div class="box"><h4>Make it count</h4>
      <p>Ring the PR bell. Write it on the board. Record it on your PR sheet at the back of this book.</p>
      <p><b>Hip Thrust Club:</b> 60 kg · 80 kg · 100 kg · 1× bodyweight · 1.5× bodyweight · 2× bodyweight.</p>
      <p><b>Week 12 bonus:</b> bodyweight single-leg glute bridge, max reps each leg.</p></div>
  </div>
</section>'''


def week9_page():
    checks = ["Joints or tendons aching (hips, knees, low back)",
              "My main lifts went backwards two sessions in a row",
              "Soreness hanging around longer than 72 hours",
              "Sleep is worse than usual or life stress is high",
              "Motivation is flat, sessions feel like a grind"]
    cl = "".join(f'<li><span class="cb"></span>{c}</li>' for c in checks)
    return f'''
<section class="page info">
  <div class="kicker">WEEK 9</div>
  <h2 class="ptitle">Reload or Remix?</h2>
  <p class="lede">You've just finished 8 big weeks. At the end of Week 8, run this readiness check and tick each one that applies to you.</p>
  <div class="box check"><ul>{cl}</ul></div>
  <div class="two">
    <div class="box choice"><div class="ctag">2 or more ticks</div><h3>RELOAD WEEK</h3>
      <ul><li>Run your <b>Phase 2</b> workouts (Mon / Wed / Fri / Upper A)</li><li><b>Halve the sets</b> on every exercise (3 → 2, 2 → 1)</li><li>Use about <b>70%</b> of your Week 8 weights</li><li><b>RIR 4</b>: leave feeling better than when you arrived</li><li>Skip finishers: 10 min easy walk + mobility instead</li></ul>
      <p class="small">A reload isn't going backwards. It's how you come back stronger for the Peak phase.</p></div>
    <div class="box choice"><div class="ctag">0–1 ticks</div><h3>REMIX WEEK</h3>
      <ul><li>Run the <b>Remix</b> workouts on the next pages: new exercises for one week</li><li>Upper day = <b>Upper A, Phase 3</b> as normal</li><li><b>RIR 2</b>: no failure, no PR attempts</li><li>Have fun with it</li></ul></div>
  </div>
</section>'''


def record_page():
    rows = [("Barbell RDL", "8RM"), ("Barbell Hip Thrust", "5RM"), ("Belt Squat", "5RM"),
            ("Pull-Up", "max reps / assistance"), ("Single-leg glute bridge (L / R)", "max reps, Wk 12")]
    tr = "".join(f"<tr><td><b>{l}</b><small>{t}</small></td><td></td><td></td><td></td><td></td></tr>" for l, t in rows)
    clubs = "".join(f'<div class="club"><span class="cb"></span>{c}</div>' for c in
                    ["60 kg", "80 kg", "100 kg", "1× bodyweight", "1.5× bodyweight", "2× bodyweight"])
    return f'''
<section class="page info">
  <h2 class="ptitle">My PR Sheet</h2>
  <table class="rec"><thead><tr><th>Lift</th><th>Week 1<br><small>starting weight</small></th><th>Week 4</th><th>Week 8</th><th>Week 12</th></tr></thead><tbody>{tr}</tbody></table>
  <h3 class="h3">Hip Thrust Club</h3>
  <div class="clubs">{clubs}</div>
  <div class="two" style="margin-top:18px">
    <div class="box"><h4>Bodyweight</h4><div class="lines"><span>Week 1</span><span>Week 12</span></div></div>
    <div class="box"><h4>My goal for these 12 weeks</h4><div class="writeline"></div><div class="writeline"></div></div>
  </div>
  <div class="quote">Great physiques aren't built from random workouts. They're built through consistent execution, technical mastery and relentless effort. Stay patient. Stay disciplined. The results will follow.<br><b>Coach Ev</b></div>
</section>'''


CSS = r"""
@page { size: A4; margin: 13mm 14mm 14mm; }
@page bleed { margin: 0; }
.cover, .divider { page: bleed; }
:root { --berry:#A8325A; --ink:#1F1A22; --muted:#6E6570; --line:#E6DEE2; --soft:#F8F1F4; --gold:#C9932E; }
* { box-sizing:border-box; }
body { margin:0; font-family:Inter, 'DejaVu Sans', sans-serif; color:var(--ink); font-size:9.6pt; line-height:1.38;
  -webkit-print-color-adjust:exact; print-color-adjust:exact; background:#fff; }
.page { page-break-after:always; position:relative; }
.page:last-child { page-break-after:auto; }
h1,h2,h3,h4 { margin:0; }
b { font-weight:700; }
/* cover */
.cover { background:var(--ink); color:#fff; display:flex; flex-direction:column; padding:22mm 18mm; width:210mm; height:297mm; }
.cover-top { letter-spacing:.3em; font-size:10pt; color:#E9B7C8; font-weight:600; }
.cover h1 { font-family:'Inter Display',Inter,sans-serif; font-size:86pt; line-height:.9; font-weight:900; margin-top:28mm; letter-spacing:-.02em; }
.cover h1 span { display:inline-block; font-size:30pt; background:var(--berry); padding:4px 14px; border-radius:6px; margin-left:12px; vertical-align:middle; letter-spacing:0; }
.cover-sub { font-size:14pt; color:#D9CFD4; margin-top:10mm; }
.cover-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8mm; margin-top:auto; border-top:1px solid #4A3F4C; padding-top:8mm; }
.cover-grid b { display:block; font-size:34pt; font-weight:800; color:#F2C4D4; line-height:1; }
.cover-grid span { color:#D9CFD4; font-size:10pt; }
.cover-name { margin-top:12mm; font-size:11pt; color:#D9CFD4; }
.cover-name span { display:inline-block; width:62mm; border-bottom:1px solid #8A7E8C; margin:0 8mm 0 2mm; }
.cover-coach { margin-top:8mm; font-weight:700; letter-spacing:.2em; color:#fff; }
/* info pages */
.ptitle { font-family:'Inter Display',Inter,sans-serif; font-size:28pt; font-weight:800; letter-spacing:-.01em; margin-bottom:4mm; }
.kicker { font-size:8.5pt; letter-spacing:.22em; color:var(--berry); font-weight:700; margin-bottom:2mm; }
.lede { font-size:11pt; color:#3E3640; max-width:165mm; margin:0 0 6mm; }
.h3 { font-size:13pt; margin:7mm 0 3mm; font-weight:800; }
.days { display:grid; grid-template-columns:repeat(5,1fr); gap:3mm; }
.day { background:var(--soft); border-radius:8px; padding:4mm; border-top:4px solid var(--berry); display:flex; flex-direction:column; }
.day.up { border-top-color:var(--ink); } .day.rest { border-top-color:#B9AEB4; background:#F4F2F3; }
.dname { font-size:8pt; letter-spacing:.18em; font-weight:700; color:var(--muted); }
.day h3 { font-size:12pt; margin:1mm 0 2mm; }
.day p { margin:0; font-size:8.6pt; color:#3E3640; }
.dsets { margin-top:auto; padding-top:3mm; font-weight:700; color:var(--berry); font-size:9pt; }
.patterns { display:grid; grid-template-columns:repeat(5,1fr); gap:3mm; }
.patterns div { border:1.5px solid var(--line); border-radius:8px; padding:3mm; text-align:center; }
.patterns b { display:block; font-size:10.5pt; } .patterns span { color:var(--muted); font-size:8.5pt; }
.two { display:grid; grid-template-columns:1fr 1fr; gap:4mm; margin-top:6mm; }
.box { background:var(--soft); border-radius:8px; padding:4mm 5mm; }
.box h4 { font-size:8.5pt; letter-spacing:.16em; text-transform:uppercase; color:var(--berry); margin-bottom:2mm; }
.box p { margin:0 0 2mm; } .box ul, .box ol { margin:0 0 2mm; padding-left:5mm; } .box li { margin-bottom:1mm; }
.tempo { display:flex; gap:2mm; } .tempo span { width:10mm; height:10mm; background:var(--ink); color:#fff; border-radius:6px; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:13pt; }
.timeline { display:flex; flex-direction:column; gap:2mm; }
.tl { display:grid; grid-template-columns:28mm 1fr; align-items:center; border-radius:8px; padding:3mm 4mm; background:var(--soft); border-left:5px solid var(--berry); }
.tl b { display:block; font-size:11pt; } .tl span { color:#4A414C; }
.tlw { font-weight:800; font-size:10.5pt; }
.tl.pr { background:#FBF3E4; border-left-color:var(--gold); } .tl.reload { background:#EEF1F4; border-left-color:#6B7C8F; }
.tl.peak { border-left-color:var(--ink); }
.quote { margin-top:8mm; border-left:4px solid var(--berry); padding:3mm 0 3mm 5mm; font-size:11.5pt; font-weight:600; color:#3E3640; }
/* dividers */
.divider { background:var(--berry); color:#fff; display:flex; flex-direction:column; justify-content:center; padding:24mm; width:210mm; height:297mm; }
.divider.p2 { background:#7A2443; } .divider.p3 { background:var(--ink); } .divider.w9 { background:#4E5D6E; }
.dnum { letter-spacing:.3em; font-weight:700; color:rgba(255,255,255,.75); }
.divider h2 { font-family:'Inter Display',Inter,sans-serif; font-size:64pt; font-weight:900; line-height:1; margin:4mm 0; }
.dweeks { font-size:16pt; font-weight:600; }
.divider p { font-size:13pt; max-width:140mm; color:rgba(255,255,255,.88); margin-top:10mm; }
/* workouts */
.whead { border-bottom:3px solid var(--accent); padding-bottom:3mm; margin-bottom:4mm; }
.whead .kicker { color:var(--accent); }
.whead h2 { font-family:'Inter Display',Inter,sans-serif; font-size:21pt; font-weight:800; line-height:1.1; }
.phase { font-weight:700; margin-top:1mm; }
.subs { color:var(--muted); font-size:9pt; }
.intro { display:grid; grid-template-columns:1.25fr 1fr; gap:4mm; margin-bottom:4mm; }
.intro .box { margin-bottom:3mm; padding:3mm 4mm; font-size:8.8pt; }
.intro .box ul { padding-left:4mm; margin:0; }
.sec h4 { font-size:8pt; letter-spacing:.16em; color:var(--accent); margin:0 0 1mm; }
.sec p { margin:0 0 1.5mm; font-size:9pt; } .sec .tags { font-weight:600; } .sec ul { margin:0 0 1.5mm; padding-left:4mm; font-size:9pt; }
.intent { font-size:11pt; font-weight:700; border-left:3px solid var(--accent); padding:1mm 0 1mm 3mm; margin:2mm 0 3mm; }
.effort-row { display:flex; gap:2mm; font-size:8.6pt; } .effort-row b { min-width:15mm; }
.group { margin:4mm 0 2mm; font-weight:800; letter-spacing:.12em; text-transform:uppercase; font-size:8.5pt; color:var(--accent); display:flex; align-items:center; gap:2mm; }
.group span { background:var(--accent); color:#fff; border-radius:4px; padding:.5mm 2mm; letter-spacing:.05em; }
.group::after { content:""; flex:1; height:1px; background:var(--line); }
.ex { display:grid; grid-template-columns:9mm 1fr auto; gap:3mm; border:1px solid var(--line); border-radius:8px; padding:3mm 4mm 3mm 3mm; margin-bottom:2.5mm; break-inside:avoid; }
.ex.linked { margin-top:0; }
.keep { break-inside:avoid; }
.link { font-size:8pt; color:var(--muted); font-weight:600; margin:-1mm 0 1mm 12mm; }
.exlabel { width:9mm; height:9mm; border-radius:50%; background:var(--ink); color:#fff; font-weight:800; display:flex; align-items:center; justify-content:center; font-size:9pt; }
.exhead { display:flex; align-items:center; gap:2mm; flex-wrap:wrap; }
.exhead h3 { font-size:10.5pt; font-weight:800; text-transform:uppercase; letter-spacing:.01em; }
.pr { background:var(--gold); color:#fff; font-size:7.5pt; font-weight:800; border-radius:4px; padding:.5mm 1.8mm; letter-spacing:.06em; }
.stats { display:flex; flex-wrap:wrap; gap:1.5mm; margin:1.5mm 0 1mm; }
.stat { background:var(--soft); border-radius:5px; padding:.8mm 2.2mm; font-weight:600; font-size:8.8pt; }
.stat i { font-style:normal; color:var(--muted); font-weight:500; margin-right:1.2mm; font-size:7.6pt; text-transform:uppercase; letter-spacing:.06em; }
.exnote { margin:.5mm 0; color:#3E3640; font-size:8.8pt; }
ul.cues, ul.bul { margin:1mm 0 0; padding-left:4mm; font-size:8.8pt; color:#3E3640; }
ul.cues li::marker { color:var(--accent); }
.log { display:grid; grid-template-columns:repeat(2,25mm); gap:1.5mm; align-content:start; }
.log.n1 { grid-template-columns:25mm; }
.loglabel { grid-column:1/-1; font-size:6.5pt; font-weight:800; letter-spacing:.1em; color:var(--muted); }
.logcell { border:1px dashed #CFC4CA; border-radius:4px; height:9mm; position:relative; }
.logcell span { position:absolute; top:.6mm; left:1.4mm; font-size:6.5pt; color:#9A8F96; font-weight:600; }
.total { margin-top:3mm; background:var(--ink); color:#fff; border-radius:6px; padding:2mm 4mm; font-weight:800; letter-spacing:.08em; font-size:9pt; display:inline-block; }
.note { background:#FBF3E4; border-radius:6px; padding:2mm 4mm; margin:2mm 0; font-weight:600; font-size:9pt; }
.complete { margin-top:4mm; font-weight:600; color:#3E3640; border-left:3px solid var(--accent); padding-left:3mm; }
.workout .sec + .sec { margin-top:1mm; }
.sign { margin-top:4mm; font-weight:800; letter-spacing:.2em; font-size:8.5pt; color:var(--muted); }
/* PR page */
.prgrid { display:grid; grid-template-columns:1fr 1fr; gap:4mm; }
.prcard { border:2px solid var(--gold); border-radius:10px; padding:4mm 5mm; }
.prday { font-size:8pt; letter-spacing:.18em; font-weight:700; color:var(--gold); text-transform:uppercase; }
.prcard h3 { font-size:14pt; margin:1mm 0; } .prtest { font-weight:800; color:var(--berry); }
.prcard p { margin:1.5mm 0 0; font-size:9pt; color:#3E3640; }
/* week 9 */
.check ul { list-style:none; padding:0; margin:0; } .check li { display:flex; gap:3mm; align-items:center; padding:2mm 0; font-size:10.5pt; border-bottom:1px solid var(--line); }
.check li:last-child { border:0; }
.cb { width:5mm; height:5mm; border:1.8px solid var(--ink); border-radius:3px; flex:none; display:inline-block; }
.choice h3 { font-size:15pt; margin:1mm 0 2mm; } .ctag { font-weight:800; color:var(--berry); font-size:9pt; }
.small { font-size:8.8pt; color:var(--muted); }
/* record */
table.rec { width:100%; border-collapse:collapse; margin-top:2mm; }
.rec th { text-align:left; font-size:9pt; background:var(--ink); color:#fff; padding:2.5mm 3mm; }
.rec th small { font-weight:500; color:#D9CFD4; }
.rec td { border:1px solid var(--line); height:16mm; padding:2mm 3mm; vertical-align:top; width:17%; }
.rec td:first-child { width:32%; } .rec td small { display:block; color:var(--muted); font-size:8pt; }
.clubs { display:grid; grid-template-columns:repeat(3,1fr); gap:3mm; }
.club { display:flex; gap:3mm; align-items:center; border:1.5px solid var(--line); border-radius:8px; padding:3mm; font-weight:700; }
.lines { display:flex; gap:6mm; } .lines span { flex:1; border-bottom:1px solid #A99CA3; padding-top:6mm; font-size:8pt; color:var(--muted); }
.writeline { border-bottom:1px solid #A99CA3; height:9mm; }
"""


def main():
    w = lambda name: TXT / f"{name}.txt"
    cover, welcome, plan = static_pages()
    parts = [cover, welcome, plan]
    phases = [
        ("1", "BUILD", "Weeks 1–4", "Learn the movements, find your working weights and build the base. Week 4 is your first PR Week.", "p1",
         ["01_P1_MONDAY_LENGTHENED", "02_P1_WEDNESDAY_SQUEEZE", "03_P1_FRIDAY_POWER", "04_P1_UPPER_A_PUSH", "05_P1_UPPER_B_PULL"], "PR WEEK #1 · WEEK 4"),
        ("2", "DEVELOP", "Weeks 5–8", "New exercises, lower reps on the big lifts and heavier loads. Week 8 is PR Week #2.", "p2",
         ["06_P2_MONDAY_LENGTHENED", "07_P2_WEDNESDAY_SQUEEZE", "08_P2_FRIDAY_POWER", "09_P2_UPPER_A_PUSH", "10_P2_UPPER_B_PULL"], "PR WEEK #2 · WEEK 8"),
    ]
    kick = {"MONDAY": "MONDAY", "WEDNESDAY": "WEDNESDAY", "FRIDAY": "FRIDAY", "UPPER_A": "UPPER DAY · A", "UPPER_B": "UPPER DAY · B"}

    def kicker(name):
        for k, v in kick.items():
            if k in name:
                return v
        return ""

    accents = {"p1": "var(--berry)", "p2": "#7A2443", "p3": "var(--ink)", "w9": "#4E5D6E"}
    for num, nm, wk, blurb, cls, files, prl in phases:
        parts.append(divider(num, nm, wk, blurb, cls))
        parts += [render_workout(w(f), kicker(f), accents[cls]) for f in files]
        parts.append(pr_page(prl))
    parts.append(divider("WEEK 9", "RELOAD / REMIX", "", "Recover or remix. Your readiness check decides.", "w9"))
    parts.append(week9_page())
    parts += [render_workout(w(f), "REMIX · " + kicker(f), accents["w9"])
              for f in ["12_WEEK9_REMIX_MONDAY", "13_WEEK9_REMIX_WEDNESDAY", "14_WEEK9_REMIX_FRIDAY"]]
    parts.append(divider("3", "PEAK", "Weeks 10–12", "The heaviest loads of the program, plus intensity techniques. Week 12 is your Final PR Week.", "p3"))
    parts += [render_workout(w(f), kicker(f), accents["p3"]) for f in
              ["15_P3_MONDAY_LENGTHENED", "16_P3_WEDNESDAY_SQUEEZE", "17_P3_FRIDAY_POWER", "18_P3_UPPER_A_PUSH", "19_P3_UPPER_B_PULL"]]
    parts.append(pr_page("FINAL PR WEEK · WEEK 12"))
    parts.append(record_page())
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Booty Blast 2.0</title>'
           f'<style>{CSS}</style></head><body>{"".join(parts)}</body></html>')
    OUT_HTML.write_text(doc)
    subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={OUT_PDF}", OUT_HTML.as_uri()], check=True, capture_output=True)
    print(OUT_PDF)


if __name__ == "__main__":
    main()
