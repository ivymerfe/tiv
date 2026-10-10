from hw01.dfa import dfa_from_csv
from .parser import parse, Node

import json
import sys

def dump(n, ind=0):
    pad = "  " * ind
    if not isinstance(n, Node):
        return f"{pad}{n!r}"
    scal = " ".join(
        f"{k}={v!r}" for k, v in n.fields.items() if not isinstance(v, (Node, list))
    )
    out = [f"{pad}{n.kind} {scal}".rstrip()]
    for k, v in n.fields.items():
        if isinstance(v, (Node, list)):
            out.append(f"{pad}  .{k}:")
            for x in v if isinstance(v, list) else [v]:
                out.append(dump(x, ind + 2))
    return "\n".join(out)


def fmt(text, pos):
    line = text.count("\n", 0, pos) + 1
    col = pos - (text.rfind("\n", 0, pos) + 1) + 1
    return f"{line}:{col}"

text = open(sys.argv[1], encoding="utf-8").read()
dfa = dfa_from_csv("dfa.csv")
ast, errs = parse(text, dfa)
for pos, msg in errs:
    print(f"{fmt(text, pos)}: {msg}", file=sys.stderr)

if errs or ast is None:
    sys.exit(1)

if "--json" in sys.argv:
    print(json.dumps(ast.to_dict(), ensure_ascii=False, indent=2))
else:
    print(dump(ast))
