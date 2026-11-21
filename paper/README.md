# Paper (IEEE conference format)

- `main.tex`, `refs.bib`: the paper. Figures are read from `../feedback/final/figures/`.
- `IEEEtran.cls`, `IEEEtran.bst`: the IEEE template (LaTeX Project Public License), copied here so the paper builds without extra packages.
- `main.pdf`: the compiled paper.

Build:

```
cd paper
latexmk -pdf main.tex
```
