"""Figures, tables and number macros for the paper, computed from the committed run.

Every number the paper prints from the v0.2 run comes from this script, which reads
runs/full-v02-20261108T0432Z/metrics.json (written by eval/report.py from progress.jsonl).
The statistics added here (Wilson intervals, exact McNemar tests, Holm adjustment) are
exploratory: they were not part of the preregistered verdict rules.

Run from paper/:  python scripts/make_figures.py
Needs matplotlib (not a dependency of the gate itself).
"""
import json
from math import comb, sqrt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
RUN = HERE.parent / "runs" / "full-v02-20261108T0432Z"
OUT_FIG = HERE / "figures"
OUT_GEN = HERE / "generated"
OUT_FIG.mkdir(exist_ok=True)
OUT_GEN.mkdir(exist_ok=True)

M = json.loads((RUN / "metrics.json").read_text())
PRIMARY = ["spotlight", "sandwich", "trust_hierarchy", "drift_full_guided"]
LABEL = {
    "none": "none",
    "spotlight": "spotlight",
    "sandwich": "sandwich",
    "trust_hierarchy": "trust hierarchy",
    "drift_full_guided": "DRIFT (guided)",
}


def wilson(k, n, z=1.959964):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj = [0.0] * len(ps)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return adj


# ---------------------------------------------------------------- collect rows
A = M["benchmark_part_a"]
rows = []  # (defense, asr_off(k,n), asr_on, task_off, task_on, paired)
rows.append(("none", A["table"]["ALL|off"]["asr"], A["table"]["ALL|on"]["asr"],
             A["table"]["ALL|off"]["task_injected"], A["table"]["ALL|on"]["task_injected"], A["paired"]))
for d in PRIMARY:
    h = M["h3_primary"][d]
    rows.append((d, h["table"]["ALL|off"]["asr"], h["table"]["ALL|on"]["asr"],
                 h["table"]["ALL|off"]["task"], h["table"]["ALL|on"]["task"], h["paired"]))
    assert h["unscored"] == {"off": 0, "on": 0}, d

p_raw = {r[0]: mcnemar_exact(r[5]["off_only"], r[5]["on_only"]) for r in rows}
p_holm_b = dict(zip(PRIMARY, holm([p_raw[d] for d in PRIMARY])))


def pct(kn):
    return 100.0 * kn[0] / kn[1]


# ---------------------------------------------------------------- figure: ASR + task completion
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 7.5, "ytick.labelsize": 8,
    "legend.fontsize": 7.5, "axes.linewidth": 0.6, "pdf.fonttype": 42,
})
C_ALONE, C_GATE = "#7a7a7a", "#1f5fa8"

fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.05), sharey=True)
ylab = [LABEL[r[0]] for r in rows][::-1]
ys = list(range(len(rows)))
for ax, (idx_off, idx_on, title) in zip(
    axes, [(1, 2, "Attack success rate (injected runs)"), (3, 4, "Task completion (injected runs)")]
):
    for y, r in zip(ys, rows[::-1]):
        off, on = r[idx_off], r[idx_on]
        lo0, hi0 = wilson(*off)
        lo1, hi1 = wilson(*on)
        ax.plot([100 * lo0, 100 * hi0], [y + 0.13] * 2, color=C_ALONE, lw=0.9, alpha=0.55)
        ax.plot([100 * lo1, 100 * hi1], [y - 0.13] * 2, color=C_GATE, lw=0.9, alpha=0.55)
        ax.annotate("", xy=(pct(on), y - 0.13), xytext=(pct(off), y + 0.13),
                    arrowprops=dict(arrowstyle="-|>", color="#444444", lw=0.6, mutation_scale=6,
                                    shrinkA=3, shrinkB=3))
        ax.plot(pct(off), y + 0.13, "o", ms=4.2, mfc="white", mec=C_ALONE, mew=1.1)
        ax.plot(pct(on), y - 0.13, "o", ms=4.2, color=C_GATE)
        ax.text(pct(off), y + 0.36, f"{off[0]}", ha="center", va="bottom", fontsize=6.3, color=C_ALONE)
        ax.text(pct(on), y - 0.36, f"{on[0]}", ha="center", va="top", fontsize=6.3, color=C_GATE)
    ax.set_title(title, fontsize=8)
    ax.set_xlim(0, 50 if idx_off == 1 else 55)
    ax.set_xlabel("percent of 90 cases (95% Wilson interval)")
    ax.grid(axis="x", color="#dddddd", lw=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.axhline(len(rows) - 1.5, color="#bbbbbb", lw=0.5, ls=":")
axes[0].set_yticks(ys)
axes[0].set_yticklabels(ylab)
axes[0].set_ylim(-0.7, len(rows) - 0.3)
h1, = axes[0].plot([], [], "o", ms=4.2, mfc="white", mec=C_ALONE, mew=1.1, label="defense alone")
h2, = axes[0].plot([], [], "o", ms=4.2, color=C_GATE, label="defense + gate")
axes[0].legend(handles=[h1, h2], loc="upper right", frameon=False)
fig.tight_layout(w_pad=1.2)
fig.savefig(OUT_FIG / "fig_benchmark.pdf", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- figure: harness
H = M["harness"]
agents = [("ollama:qwen3-4b-instruct-32k", "Qwen3-4B agent"), ("stub", "obey-all stub")]
fig, ax = plt.subplots(figsize=(3.4, 1.65))
labels, offv, onv = [], [], []
for key, name in agents:
    for ch in ("latent", "autonomous"):
        labels.append(ch)
        offv.append(H[key]["asr"][f"{ch}_off"])
        onv.append(H[key]["asr"][f"{ch}_on"])
x = range(len(labels))
w = 0.36
b1 = ax.bar([i - w / 2 for i in x], [pct(v) for v in offv], w, color="white", edgecolor=C_ALONE, lw=0.9, label="gate off")
b2 = ax.bar([i + w / 2 for i in x], [pct(v) for v in onv], w, color=C_GATE, label="gate on")
for i, (o, n) in enumerate(zip(offv, onv)):
    ax.text(i - w / 2, pct(o) + 2, f"{o[0]}/{o[1]}", ha="center", fontsize=5.8, color="#444444")
    ax.text(i + w / 2, pct(n) + 2, f"{n[0]}/{n[1]}", ha="center", fontsize=5.8, color=C_GATE)
ax.set_xticks(list(x))
ax.set_xticklabels(labels, fontsize=6.5)
for j, (_, name) in enumerate(agents):
    ax.text(2 * j + 0.5, -0.30, name, transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=7)
    if j:
        ax.axvline(2 * j - 0.5, color="#cccccc", lw=0.5, ls=":")
ax.set_ylabel("attack success (%)")
ax.set_ylim(0, 115)
ax.set_yticks([0, 50, 100])
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(frameon=False, fontsize=6.5, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.2))
fig.tight_layout()
fig.savefig(OUT_FIG / "fig_harness.pdf", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- table: benchmark
def fmt_p(p):
    return f"{p:.3f}" if p >= 0.001 else "$<$0.001"


lines = []
for r in rows:
    d, off, on, toff, ton, pr = r
    red = pct(off) - pct(on)
    hp = fmt_p(p_holm_b[d]) if d in p_holm_b else "--"
    name = LABEL[d] + (" (Part A)" if d == "none" else "")
    lines.append(
        f"{name} & {off[0]} ({pct(off):.1f}) & {on[0]} ({pct(on):.1f}) & {red:+.1f} & "
        f"{toff[0]} & {ton[0]} & {pr['off_only']}/{pr['on_only']}/{pr['both']} & {fmt_p(p_raw[d])} & {hp} \\\\"
    )
    if d == "none":
        lines.append(r"\midrule")
(OUT_GEN / "tab_benchmark_rows.tex").write_text("\n".join(lines) + "\n")

env_lines = []
envs = ["devops", "marketplace", "productivity"]
src = [("none", A["table"])] + [(d, M["h3_primary"][d]["table"]) for d in PRIMARY]
for d, t in src:
    cells = []
    for e in envs:
        o, n = t[f"{e}|off"]["asr"], t[f"{e}|on"]["asr"]
        mark = r"$^{\uparrow}$" if n[0] > o[0] else ""
        cells.append(f"{o[0]}$\\to${n[0]}{mark}")
    env_lines.append(f"{LABEL[d]} & " + " & ".join(cells) + r" \\")
(OUT_GEN / "tab_env_rows.tex").write_text("\n".join(env_lines) + "\n")

# ---------------------------------------------------------------- macros
q = H["ollama:qwen3-4b-instruct-32k"]
mac = {
    "nCases": 90,
    "pNoneRaw": fmt_p(p_raw["none"]),
    "pTrustRaw": fmt_p(p_raw["trust_hierarchy"]),
    "pTrustHolm": fmt_p(p_holm_b["trust_hierarchy"]),
    "harnessFPR": f"{q['fpr_combined'][0]}/{q['fpr_combined'][1]}",
    "harnessLatP": f"{q['latency_us'][0]:.1f}",
    "harnessLatQ": f"{q['latency_us'][1]:.1f}",
    "benchLatP": f"{A['latency_us'][0]:.0f}",
    "benchLatQ": f"{A['latency_us'][1]:.0f}",
    "withheldInj": f"{A['recall_injected']['malicious_leaves'][0]}/{A['recall_injected']['malicious_leaves'][1]}",
    "withheldOther": f"{A['recall_injected']['other_leaves'][0]}/{A['recall_injected']['other_leaves'][1]}",
    "cleanIntervene": f"{A['clean_samples_with_block'][0]}/{A['clean_samples_with_block'][1]}",
    "cleanTaskOff": f"{pct(A['table']['ALL|off']['task_clean']):.1f}",
    "cleanTaskOn": f"{pct(A['table']['ALL|on']['task_clean']):.1f}",
    "hFourBench": f"{A['h4_identical'][0]}/{A['h4_identical'][1]}",
    "quarPlanted": f"{q['quarantine']['planted'][0]}/{q['quarantine']['planted'][1]}",
    "quarBenign": f"{q['quarantine']['benign_untrusted'][0]}/{q['quarantine']['benign_untrusted'][1]}",
    "ctlDone": f"{q['control_completion']['on'][0]}/{q['control_completion']['on'][1]}",
}
(OUT_GEN / "numbers.tex").write_text(
    "% generated by scripts/make_figures.py from runs/full-v02-20261108T0432Z/metrics.json\n"
    + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in mac.items())
)

# a plain-text dump for checking prose numbers by eye
dump = {r[0]: {"asr_off": r[1], "asr_on": r[2], "task_off": r[3], "task_on": r[4], "paired": r[5],
               "p_exact": p_raw[r[0]], "p_holm": p_holm_b.get(r[0]),
               "wilson_off": wilson(*r[1]), "wilson_on": wilson(*r[2])} for r in rows}
(OUT_GEN / "numbers_check.json").write_text(json.dumps({"benchmark": dump, "macros": mac}, indent=1))
print(json.dumps(dump, indent=1))
print(mac)
