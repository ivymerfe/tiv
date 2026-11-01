from .ir import liveness, build_cfg, fmt_func

CMPS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "lt": lambda a, b: a < b,
    "le": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "ge": lambda a, b: a >= b,
}
ARITH = {"add", "sub", "mul", "div"}
COMM = {"add", "mul", "eq", "ne"}
EXPR = {"neg", "load", "len"} | ARITH | set(CMPS)
PURE = (EXPR | {"mov"}) - {"load"}
MAX_ROUNDS = 20


def idiv(a, b):
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def wrap(x):
    return (x + 2**31) % 2**32 - 2**31


def fold(op, a, b=None):
    if op == "neg":
        return wrap(-a)
    if op == "add":
        return wrap(a + b)
    if op == "sub":
        return wrap(a - b)
    if op == "mul":
        return wrap(a * b)
    if op == "div":
        return None if b == 0 else wrap(idiv(a, b))
    return int(CMPS[op](a, b))


def is_int(x):
    return isinstance(x, int)


def cprop(fn):
    for b in fn.blocks:
        env = {}
        for i in b.instrs:
            i.args = [env.get(a, a) if isinstance(a, str) else a for a in i.args]
            if i.op == "neg" and is_int(i.args[0]):
                i.op, i.args = "mov", [wrap(-i.args[0])]
            elif (i.op in ARITH or i.op in CMPS) and all(map(is_int, i.args)):
                v = fold(i.op, *i.args)
                if v is not None:
                    i.op, i.args = "mov", [v]
            elif i.op == "br":
                if is_int(i.args[0]):
                    i.op, i.aux, i.args = (
                        "jmp",
                        [i.aux[0] if i.args[0] else i.aux[1]],
                        [],
                    )
                elif i.aux[0] == i.aux[1]:
                    i.op, i.aux, i.args = "jmp", [i.aux[0]], []
            for d in i.dst:
                env.pop(d, None)
                for k in [k for k, v in env.items() if v == d]:
                    del env[k]
            if i.op == "mov" and i.dst[0] != i.args[0]:
                env[i.dst[0]] = i.args[0]
    build_cfg(fn)


def algebra(fn):
    for b in fn.blocks:
        for i in b.instrs:
            o = i.op
            if o not in ARITH and o not in CMPS:
                continue
            a, c = i.args
            r = None
            if o == "add":
                if c == 0:
                    r = a
                elif a == 0:
                    r = c
            elif o == "sub":
                if c == 0:
                    r = a
                elif a == c:
                    r = 0
            elif o == "mul":
                if a == 0 or c == 0:
                    r = 0
                elif c == 1:
                    r = a
                elif a == 1:
                    r = c
                elif c == 2 and isinstance(a, str):
                    i.op, i.args = "add", [a, a]
                elif a == 2 and isinstance(c, str):
                    i.op, i.args = "add", [c, c]
            elif o == "div":
                if c == 1:
                    r = a
            elif o in ("eq", "le", "ge") and a == c:
                r = 1
            elif o in ("ne", "lt", "gt") and a == c:
                r = 0
            if r is not None:
                i.op, i.args = "mov", [r]


def cse(fn):
    for b in fn.blocks:
        av = {}
        for i in b.instrs:
            key = None
            if i.op in EXPR:
                args = sorted(i.args, key=str) if i.op in COMM else i.args
                key = (i.op, tuple(args))
                if key in av:
                    i.op, i.args = "mov", [av[key]]
                    key = None
            for d in i.dst:
                for k in [k for k, v in av.items() if v == d or d in k[1]]:
                    del av[k]
            if key and i.dst[0] not in key[1]:
                av[key] = i.dst[0]


def dce(fn):
    _, lout = liveness(fn)
    for b in fn.blocks:
        live = set(lout[b.name])
        keep = []
        for i in reversed(b.instrs):
            rm = False
            if i.op in PURE:
                if i.op == "mov" and i.dst[0] == i.args[0]:
                    rm = True
                elif all(d not in live for d in i.dst):
                    rm = not (
                        i.op == "div" and not (is_int(i.args[1]) and i.args[1] != 0)
                    )
            if rm:
                continue
            live -= set(i.dst)
            live |= set(i.uses())
            keep.append(i)
        b.instrs = keep[::-1]


def optimize(fn, passes):
    for _ in range(MAX_ROUNDS):
        s = fmt_func(fn)
        if "cprop" in passes:
            cprop(fn)
        if "algebra" in passes:
            algebra(fn)
        if "cse" in passes:
            cse(fn)
        if "dce" in passes:
            dce(fn)
        if fmt_func(fn) == s:
            break


def interference(fn, all_vars=False):
    _, lout = liveness(fn)
    g = {}

    def isn(v):
        return all_vars or v.startswith("%")

    for b in fn.blocks:
        live = set(lout[b.name])
        for i in reversed(b.instrs):
            for d in i.dst:
                if isn(d):
                    g.setdefault(d, set())
            for d in i.dst:
                if not isn(d):
                    continue
                for v in live | set(i.dst):
                    if v == d or not isn(v):
                        continue
                    if i.op == "mov" and v == i.args[0]:
                        continue
                    g.setdefault(v, set()).add(d)
                    g[d].add(v)
            live -= set(i.dst)
            live |= set(i.uses())
    return g


def color(g):
    col = {}
    for v in sorted(g, key=lambda v: (-len(g[v]), v)):
        used = {col[u] for u in g[v] if u in col}
        c = 0
        while c in used:
            c += 1
        col[v] = c
    return col


def ig_text(name, g, col):
    out = [f"conflicts {name}:"]
    for v in sorted(g):
        out.append(f"  {v}: {' '.join(sorted(g[v]))}".rstrip())
    out.append("colors:")
    for v in sorted(col):
        out.append(f"  {v} -> r{col[v]}")
    out.append(f"registers used: {len(set(col.values()))}")
    return "\n".join(out)


def ig_dot_all(items):
    pal = [
        "lightblue",
        "lightgreen",
        "lightyellow",
        "lightpink",
        "orange",
        "lightgrey",
        "violet",
        "cyan",
    ]
    out = ["graph ig {", "  node [style=filled, fontname=monospace];"]
    for name, g, col in items:
        out.append(f'  subgraph "cluster_{name}" {{')
        out.append(f'    label="{name}";')
        for v in sorted(g):
            c = col[v]
            out.append(
                f'    "{name}.{v}" [label="{v}\\nr{c}", fillcolor={pal[c % len(pal)]}];'
            )
        for v in sorted(g):
            for u in sorted(g[v]):
                if v < u:
                    out.append(f'    "{name}.{v}" -- "{name}.{u}";')
        out.append("  }")
    out.append("}")
    return "\n".join(out)
