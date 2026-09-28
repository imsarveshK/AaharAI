"""Render the manuscript, tables and figures into one self-contained reading page."""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "paper"
FIGURES = ROOT / "analysis/output/figures"
OUT = PAPER / "paper_page.html"

FIGURE_CAPTIONS = {
    "fig1_adoption": ("Figure 1",
        "Online purchasing by domain and sector (A), and adoption of online food "
        "buying across deciles of monthly per capita consumption expenditure (B). "
        "Bars and bands show 95% confidence intervals from design-based standard errors."),
    "fig2_category_mix": ("Figure 2",
        "Share of the 19,842 households that bought any food online who bought each "
        "category. Groceries was asked over 30 days and the rest over 7, so it is not "
        "directly comparable."),
    "fig3_budget_shares": ("Figure 3",
        "Adjusted difference in each food group's share of the household food budget "
        "between households that did and did not buy food online, in percentage points, "
        "with 95% confidence intervals."),
    "fig4_robustness": ("Figure 4",
        "The vegetable and packaged-processed contrasts across five specifications, all "
        "on a common percentage-point scale."),
}

# Where each figure is placed, keyed by the section heading it follows.
FIGURE_AFTER = {
    "3.2 How far online food buying reaches": ["fig1_adoption"],
    "3.4 The gradient is steeper for processed food": ["fig2_category_mix"],
    "3.5 Food budget composition": ["fig3_budget_shares"],
    "3.6 Robustness": ["fig4_robustness"],
}


def data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def figure_html(stem: str) -> str:
    path = FIGURES / f"{stem}.png"
    if not path.exists():
        return ""
    number, caption = FIGURE_CAPTIONS[stem]
    return (f'<figure class="fig">\n<img src="{data_uri(path)}" alt="{number}. {caption}">\n'
            f'<figcaption><span class="fignum">{number}</span> {caption}</figcaption>\n</figure>\n')


def md_to_html(text: str) -> str:
    return markdown.markdown(text, extensions=["tables", "attr_list"])


def build() -> str:
    manuscript = (PAPER / "manuscript.md").read_text()
    tables = (PAPER / "tables.md").read_text()
    supp = (PAPER / "supplementary.md").read_text()
    key = json.loads((ROOT / "analysis/output/key_numbers.json").read_text())

    title_line, body = manuscript.split("\n", 1)
    title = title_line.lstrip("# ").strip()

    # Split the abstract and highlights off the front matter.
    abstract = body.split("## Abstract", 1)[1].split("**Keywords:**")[0].strip()
    keywords = body.split("**Keywords:**", 1)[1].split("\n")[0].strip()
    highlights = [l.strip("- ").strip() for l in
                  body.split("## Highlights", 1)[1].split("---")[0].strip().split("\n")
                  if l.strip().startswith("-")]
    main = body.split("## Highlights", 1)[1].split("---", 2)[-1]

    # Insert figures after their sections.
    for heading, stems in FIGURE_AFTER.items():
        marker = f"### {heading}"
        if marker not in main:
            continue
        nxt = re.search(rf"{re.escape(marker)}(.*?)(?=\n### |\n## |\Z)", main, re.S)
        if not nxt:
            continue
        block = nxt.group(0)
        main = main.replace(block, block.rstrip() + "\n\n"
                            + "".join(f"@@FIG:{s}@@\n\n" for s in stems))

    html_main = md_to_html(main)
    for stem in FIGURE_CAPTIONS:
        html_main = html_main.replace(f"<p>@@FIG:{stem}@@</p>", figure_html(stem))

    rec = key["mpce_reconciliation"]["computed"]["headline_excl_imputed_rent"]
    stats = [
        ("7.10%", "of households bought any food online", "against 45.6% buying anything online"),
        ("70×", "gap between richest and poorest decile", "0.34% to 23.84% adoption"),
        ("+1.81 pp", "packaged processed food budget share", "adjusted, 95% CI 1.50 to 2.13"),
        ("−0.63 pp", "vegetable budget share", "adjusted, 95% CI −0.83 to −0.44"),
    ]
    stat_html = "\n".join(
        f'<div class="stat"><div class="stat-v">{v}</div>'
        f'<div class="stat-l">{l}</div><div class="stat-s">{s}</div></div>'
        for v, l, s in stats)

    checks = [
        ("MPCE, rural", f"₹{rec['rural']:,.2f}", "₹4,122"),
        ("MPCE, urban", f"₹{rec['urban']:,.2f}", "₹6,996"),
        ("Food share of MPCE, rural", "47.03%", "~47%"),
        ("Food share of MPCE, urban", "39.69%", "~40%"),
        ("Sample households", f"{key['sample']['households_total']:,}", "261,953"),
        ("First-stage units", f"{key['sample']['psus']:,}", "14,827"),
    ]
    check_html = "\n".join(
        f"<tr><td>{n}</td><td class='num'>{a}</td><td class='num'>{b}</td></tr>"
        for n, a, b in checks)

    hi_html = "\n".join(f"<li>{h}</li>" for h in highlights)

    return TEMPLATE.format(
        title=title, keywords=keywords,
        abstract=md_to_html(abstract), highlights=hi_html,
        stats=stat_html, checks=check_html,
        main=html_main, tables=md_to_html(tables.split("\n", 1)[1]),
        supp=md_to_html(supp.split("\n", 1)[1]),
        n=f"{key['sample']['households_analysis']:,}")


TEMPLATE = """<title>The Indian Digital Food Basket</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,300;0,400;0,600;1,400&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{
  --ground:#f6f7f9; --panel:#fdfdfe; --ink:#141b24; --ink-2:#43505f; --ink-3:#77848f;
  --rule:#dde1e6; --rule-2:#eaedf0; --accent:#2a78d6; --warm:#c2521f;
  --shadow:0 1px 2px rgba(20,27,36,.05);
  --serif:"Spectral",Georgia,"Times New Roman",serif;
  --sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
  --col:min(68ch,100%);
}}
@media (prefers-color-scheme:dark) {{
  :root:not([data-theme="light"]) {{
    --ground:#101418; --panel:#161b21; --ink:#e7ebef; --ink-2:#b3bdc7; --ink-3:#8896a3;
    --rule:#28313a; --rule-2:#1e252c; --accent:#5c9ee8; --warm:#e08a5c;
    --shadow:0 1px 2px rgba(0,0,0,.3);
  }}
}}
:root[data-theme="dark"] {{
  --ground:#101418; --panel:#161b21; --ink:#e7ebef; --ink-2:#b3bdc7; --ink-3:#8896a3;
  --rule:#28313a; --rule-2:#1e252c; --accent:#5c9ee8; --warm:#e08a5c;
  --shadow:0 1px 2px rgba(0,0,0,.3);
}}
* {{ box-sizing:border-box; }}
body {{ background:var(--ground); color:var(--ink); font-family:var(--serif);
  font-size:17px; line-height:1.62; -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:0 24px 96px; }}
.col {{ width:var(--col); margin-inline:auto; }}

header.mast {{ padding:56px 0 34px; border-bottom:2px solid var(--ink); margin-bottom:34px; }}
.eyebrow {{ font-family:var(--sans); font-size:11.5px; font-weight:600; letter-spacing:.13em;
  text-transform:uppercase; color:var(--warm); margin-bottom:16px; }}
h1 {{ font-family:var(--serif); font-weight:600; font-size:clamp(29px,4.4vw,46px);
  line-height:1.14; letter-spacing:-.015em; margin:0 0 18px; text-wrap:balance; }}
.byline {{ font-family:var(--sans); font-size:13.5px; color:var(--ink-2); }}
.byline .sep {{ color:var(--ink-3); padding:0 8px; }}

.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:1px;
  background:var(--rule); border:1px solid var(--rule); margin:34px 0 8px; }}
.stat {{ background:var(--panel); padding:18px 18px 16px; }}
.stat-v {{ font-family:var(--mono); font-size:26px; font-weight:500; letter-spacing:-.02em;
  color:var(--accent); font-variant-numeric:tabular-nums; }}
.stat-l {{ font-family:var(--sans); font-size:12.5px; font-weight:500; margin-top:6px; line-height:1.36; }}
.stat-s {{ font-family:var(--sans); font-size:11.5px; color:var(--ink-3); margin-top:4px; line-height:1.36; }}

.abstract {{ background:var(--panel); border:1px solid var(--rule); padding:26px 30px;
  margin:34px 0; box-shadow:var(--shadow); }}
.abstract h2, .hl h2 {{ font-family:var(--sans); font-size:11.5px; font-weight:600;
  letter-spacing:.13em; text-transform:uppercase; color:var(--ink-3); margin:0 0 14px; }}
.abstract p {{ font-size:15.5px; line-height:1.6; margin:0 0 13px; }}
.abstract p:last-child {{ margin-bottom:0; }}
.abstract strong {{ font-family:var(--sans); font-size:12px; font-weight:600;
  letter-spacing:.04em; text-transform:uppercase; color:var(--warm); }}
.kw {{ font-family:var(--sans); font-size:12.5px; color:var(--ink-3); margin-top:16px;
  padding-top:14px; border-top:1px solid var(--rule-2); }}

.hl {{ margin:34px 0; }}
.hl ul {{ list-style:none; padding:0; margin:0; display:grid; gap:1px; background:var(--rule);
  border:1px solid var(--rule); }}
.hl li {{ background:var(--panel); font-family:var(--sans); font-size:14px; padding:12px 16px 12px 40px;
  position:relative; }}
.hl li::before {{ content:"→"; position:absolute; left:16px; color:var(--accent); }}

h2 {{ font-family:var(--serif); font-weight:600; font-size:25px; letter-spacing:-.01em;
  margin:52px 0 14px; padding-bottom:9px; border-bottom:1px solid var(--rule); text-wrap:balance; }}
h3 {{ font-family:var(--sans); font-weight:600; font-size:15px; letter-spacing:.005em;
  margin:34px 0 10px; color:var(--ink); text-wrap:balance; }}
p {{ margin:0 0 16px; }}
ul, ol {{ margin:0 0 16px; padding-left:22px; }}
li {{ margin-bottom:7px; }}
strong {{ font-weight:600; }}
code {{ font-family:var(--mono); font-size:.87em; background:var(--rule-2);
  padding:1px 5px; border-radius:2px; }}
a {{ color:var(--accent); text-decoration:none; border-bottom:1px solid color-mix(in oklab,var(--accent) 35%,transparent); }}
a:hover {{ border-bottom-color:var(--accent); }}
a:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}

figure.fig {{ margin:32px 0; width:min(940px,100%); margin-inline:auto; }}
figure.fig img {{ width:100%; display:block; background:#fff; border:1px solid var(--rule);
  box-shadow:var(--shadow); }}
figcaption {{ font-family:var(--sans); font-size:12.5px; line-height:1.5; color:var(--ink-2);
  margin-top:10px; }}
.fignum {{ font-weight:600; color:var(--ink); }}

.tablewrap {{ overflow-x:auto; margin:0 0 24px; border:1px solid var(--rule); background:var(--panel); }}
table {{ border-collapse:collapse; width:100%; font-family:var(--sans); font-size:12.8px; }}
th, td {{ padding:8px 12px; text-align:left; border-bottom:1px solid var(--rule-2); white-space:nowrap; }}
th {{ font-weight:600; font-size:11.5px; letter-spacing:.04em; text-transform:uppercase;
  color:var(--ink-3); background:var(--rule-2); position:sticky; top:0; }}
td {{ font-variant-numeric:tabular-nums; }}
td.num, td:nth-child(n+2) {{ text-align:right; }}
tbody tr:last-child td {{ border-bottom:none; }}

.checks {{ margin:24px 0 8px; }}
.checks table td:first-child {{ text-align:left; font-family:var(--sans); }}

.note {{ border-left:3px solid var(--warm); background:var(--panel); padding:16px 20px;
  margin:26px 0; font-size:15px; }}
.note p:last-child {{ margin-bottom:0; }}
.note .lbl {{ font-family:var(--sans); font-size:11.5px; font-weight:600; letter-spacing:.1em;
  text-transform:uppercase; color:var(--warm); display:block; margin-bottom:7px; }}

.refs p {{ font-family:var(--sans); font-size:13px; line-height:1.5; padding-left:24px;
  text-indent:-24px; margin-bottom:11px; color:var(--ink-2); }}
.refs a {{ word-break:break-word; }}

footer {{ margin-top:64px; padding-top:22px; border-top:1px solid var(--rule);
  font-family:var(--sans); font-size:12.5px; color:var(--ink-3); }}
@media (max-width:640px) {{ body {{ font-size:16px; }} .wrap {{ padding:0 16px 64px; }} }}
</style>

<div class="wrap">
<header class="mast">
  <div class="col">
    <div class="eyebrow">Household Consumption Expenditure Survey 2023-24 &middot; {n} households</div>
    <h1>{title}</h1>
    <div class="byline">Working manuscript<span class="sep">|</span>Analysis reproducible from the official microdata archive</div>
  </div>
</header>

<div class="col">
  <div class="stats">{stats}</div>

  <section class="abstract">
    <h2>Abstract</h2>
    {abstract}
    <div class="kw"><strong style="text-transform:none;letter-spacing:0;font-size:12.5px;color:var(--ink-3)">Keywords</strong> &nbsp;{keywords}</div>
  </section>

  <section class="hl">
    <h2>Highlights</h2>
    <ul>{highlights}</ul>
  </section>

  <div class="note">
    <span class="lbl">A note on the data</span>
    <p>The ministry's unit-level data note designates the online-purchase items auxiliary,
    gathered "to check internal consistency and validation of the data and not to compile
    estimates/indicators based on this information." Section 3.1 reports the reliability
    evidence for the module, and the findings are presented as provisional throughout.</p>
  </div>

  <section class="checks">
    <h2>Reconciliation against published statistics</h2>
    <div class="tablewrap"><table>
      <thead><tr><th>Quantity</th><th>This analysis</th><th>Published</th></tr></thead>
      <tbody>{checks}</tbody>
    </table></div>
  </section>

  <main>{main}</main>

  <section id="tables"><h2>Tables</h2>{tables}</section>
  <section id="supp"><h2>Supplementary material</h2>{supp}</section>

  <footer>
    Generated from <code>paper/manuscript.md</code> with figures and tables produced by
    <code>analysis/run_all.sh</code>. Every quoted figure is checked against the computed
    output by <code>analysis/tests/test_manuscript_numbers.py</code>.
  </footer>
</div>
</div>

<script>
// Tables arrive from Markdown as bare <table>; wrap each so wide ones scroll
// inside their own container instead of pushing the page sideways.
document.querySelectorAll("main table, #tables table, #supp table").forEach(t => {{
  if (t.parentElement.classList.contains("tablewrap")) return;
  const w = document.createElement("div");
  w.className = "tablewrap";
  t.replaceWith(w);
  w.appendChild(t);
}});
// The reference list is the last block of the manuscript; give it hanging indents.
const refs = [...document.querySelectorAll("main h2")].find(h => h.textContent.trim() === "References");
if (refs) {{
  let el = refs.nextElementSibling;
  const box = document.createElement("div");
  box.className = "refs";
  refs.after(box);
  while (el) {{ const next = el.nextElementSibling; box.appendChild(el); el = next; }}
}}
</script>
"""


def main() -> int:
    OUT.write_text(build())
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
