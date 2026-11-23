# Paper (IEEE conference format)

*Counting the Drops: Joint Admission and Site Selection for Computing-Aware Traffic Steering under Stale Shared Telemetry*, revised version of 23 Nov 2026 (tag `paper-submitted`).

- `main.tex`, `refs.bib`: the paper. Figures are read from `../feedback/final/figures/`.
- `IEEEtran.cls`, `IEEEtran.bst`: the IEEE template (LaTeX Project Public License), copied here so the paper builds without extra packages.
- `main.pdf`: the compiled paper.
- Needs the LaTeX packages `algorithm` and `algpseudocode` (TeX Live: `texlive-science`; Overleaf and MiKTeX have them).
- Numbers added in the revision come from `../feedback/revision/` (see its README).

Build:

```
cd paper
latexmk -pdf main.tex
```
