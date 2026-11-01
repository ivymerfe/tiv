import argparse
import sys

from hw01.dfa import dfa_from_csv
from hw02.parser import parse
from hw03.checker import Checker, format_error
from .ir import gen_module, build_cfg, fmt_func, cfg_dot_all
from .opt import optimize, interference, color, ig_text, ig_dot_all

ap = argparse.ArgumentParser()
ap.add_argument("file")
ap.add_argument("-O0", dest="o0", action="store_true")
ap.add_argument("--no-cprop", action="store_true")
ap.add_argument("--no-algebra", action="store_true")
ap.add_argument("--no-dce", action="store_true")
ap.add_argument("--cse", action="store_true")
ap.add_argument("--no-ig", action="store_true")
ap.add_argument("--cfg-dot")
ap.add_argument("--ig-dot")
ap.add_argument("--ig-all", action="store_true")
a = ap.parse_args()

text = open(a.file, encoding="utf-8").read()
dfa = dfa_from_csv("dfa.csv")
ast, errs = parse(text, dfa)

if ast is not None and not errs:
    c = Checker()
    c.check(ast)
    errs = sorted(set(c.errors))

for pos, msg in errs:
    print(format_error(text, pos, msg), file=sys.stderr)

if errs or ast is None:
    sys.exit(1)

funcs = gen_module(ast)
for f in funcs:
    build_cfg(f)
before = [fmt_func(f) for f in funcs]

passes = set()
if not a.o0:
    if not a.no_cprop:
        passes.add("cprop")
    if not a.no_algebra:
        passes.add("algebra")
    if not a.no_dce:
        passes.add("dce")
    if a.cse:
        passes.add("cse")

for f in funcs:
    optimize(f, passes)

print("# IR before")
print("\n\n".join(before))
print(f"\n# IR after (passes: {', '.join(sorted(passes)) or 'none'})")
print("\n\n".join(fmt_func(f) for f in funcs))

graphs = [(f.name, interference(f, a.ig_all)) for f in funcs]
colors = [color(g) for _, g in graphs]

if not a.no_ig:
    for (name, g), col in zip(graphs, colors):
        print()
        print(ig_text(name, g, col))

if a.cfg_dot:
    with open(a.cfg_dot, "w", encoding="utf-8") as fh:
        fh.write(cfg_dot_all(funcs) + "\n")

if a.ig_dot:
    items = [(n, g, c) for (n, g), c in zip(graphs, colors)]
    with open(a.ig_dot, "w", encoding="utf-8") as fh:
        fh.write(ig_dot_all(items) + "\n")
