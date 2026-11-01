from hw02.parser import Node

TERM = {"jmp", "br", "ret", "trap"}
BIN = {"+": "add", "-": "sub", "*": "mul", "/": "div"}
CMPOP = {"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}


class Instr:
    def __init__(self, op, dst=(), args=(), aux=None):
        self.op = op
        self.dst = list(dst)
        self.args = list(args)
        self.aux = aux

    def uses(self):
        return [a for a in self.args if isinstance(a, str)]

    def is_term(self):
        return self.op in TERM


class Block:
    def __init__(self, name):
        self.name = name
        self.instrs = []
        self.succs = []
        self.preds = []

    def term(self):
        if self.instrs and self.instrs[-1].is_term():
            return self.instrs[-1]
        return None


class Func:
    def __init__(self, name, params, rets):
        self.name = name
        self.params = params
        self.rets = rets
        self.blocks = []


def fmt_instr(i):
    o = i.op
    a = ", ".join(map(str, i.args))
    if o == "mov":
        return f"{i.dst[0]} = {a}"
    if o == "call":
        return f"{', '.join(i.dst)} = call {i.aux}({a})"
    if o == "jmp":
        return f"jmp {i.aux[0]}"
    if o == "br":
        return f"br {a}, {i.aux[0]}, {i.aux[1]}"
    if o in ("ret", "trap"):
        return f"{o} {a}".rstrip()
    return f"{i.dst[0]} = {o} {a}"


def fmt_func(fn):
    ps = ", ".join(f"{n}: {t}" for n, t in fn.params)
    rs = ", ".join(f"{n}: {t}" for n, t in fn.rets)
    out = [f"func {fn.name}({ps}) -> ({rs})"]
    for b in fn.blocks:
        out.append(f"{b.name}:")
        out.extend("  " + fmt_instr(i) for i in b.instrs)
    return "\n".join(out)


def has_spec(n):
    if n.kind in ("Quantifier", "FormulaRef"):
        return True
    return any(has_spec(v) for v in n.fields.values() if isinstance(v, Node))


class Gen:
    def __init__(self, fn):
        f = fn.fields
        self.f = Func(
            fn.fields["name"],
            [(p.fields["name"], p.fields["type"]) for p in f["params"]],
            [(r.fields["name"], r.fields["type"]) for r in f["returns"]],
        )
        self.nt = 0
        self.nl = 0
        self.cur = None

    def tmp(self):
        self.nt += 1
        return f"%t{self.nt}"

    def label(self, hint):
        self.nl += 1
        return f"{hint}{self.nl}"

    def start(self, name):
        if self.cur is not None and self.cur.term() is None:
            self.cur.instrs.append(Instr("jmp", aux=[name]))
        b = Block(name)
        self.f.blocks.append(b)
        self.cur = b

    def emit(self, i):
        if self.cur.term() is not None:
            self.start(self.label("dead"))
        self.cur.instrs.append(i)

    def expr(self, n, dst=None):
        k, f = n.kind, n.fields
        if k in ("Int", "Ref"):
            v = f["value"] if k == "Int" else f["name"]
            if dst is None:
                return v
            self.emit(Instr("mov", [dst], [v]))
            return dst
        if k == "Call":
            return self.call(n, [dst] if dst else None)[0]
        if k == "Neg":
            a = self.expr(f["operand"])
            d = dst or self.tmp()
            self.emit(Instr("neg", [d], [a]))
            return d
        if k == "Bin":
            a = self.expr(f["left"])
            b = self.expr(f["right"])
            d = dst or self.tmp()
            self.emit(Instr(BIN[f["op"]], [d], [a, b]))
            return d
        if k == "Index":
            a = self.expr(f["array"])
            i = self.expr(f["index"])
            d = dst or self.tmp()
            self.emit(Instr("load", [d], [a, i]))
            return d
        raise ValueError(k)

    def call(self, n, dsts=None):
        name = n.fields["name"]
        args = [self.expr(a) for a in n.fields["args"]]
        d = dsts or [self.tmp()]
        if name == "length":
            self.emit(Instr("len", d, args))
        elif name == "set":
            self.emit(Instr("aset", d, args))
        else:
            self.emit(Instr("call", d, args, name))
        return d

    def cond(self, n, lt, lf):
        k, f = n.kind, n.fields
        if k == "Bool":
            self.emit(Instr("jmp", aux=[lt if f["value"] else lf]))
        elif k == "Not":
            self.cond(f["operand"], lf, lt)
        elif k == "And":
            m = self.label("and")
            self.cond(f["left"], m, lf)
            self.start(m)
            self.cond(f["right"], lt, lf)
        elif k == "Or":
            m = self.label("or")
            self.cond(f["left"], lt, m)
            self.start(m)
            self.cond(f["right"], lt, lf)
        elif k == "Implies":
            m = self.label("imp")
            self.cond(f["left"], m, lt)
            self.start(m)
            self.cond(f["right"], lt, lf)
        elif k == "Cmp":
            a = self.expr(f["left"])
            b = self.expr(f["right"])
            d = self.tmp()
            self.emit(Instr(CMPOP[f["op"]], [d], [a, b]))
            self.emit(Instr("br", [], [d], [lt, lf]))
        else:
            raise ValueError(k)

    def stmt(self, n):
        getattr(self, "s_" + n.kind)(n)

    def s_Block(self, n):
        for s in n.fields["body"]:
            self.stmt(s)

    s_Seq = s_Block

    def s_Assign(self, n):
        f = n.fields
        ts, v = f["targets"], f["value"]
        if len(ts) > 1:
            self.call(v, list(ts))
        else:
            self.expr(v, ts[0])

    def s_If(self, n):
        f = n.fields
        t, e, end = self.label("then"), self.label("else"), self.label("endif")
        has_else = f["else_"] is not None
        self.cond(f["cond"], t, e if has_else else end)
        self.start(t)
        self.stmt(f["then"])
        if has_else:
            self.start(e)
            self.stmt(f["else_"])
        self.start(end)

    def s_While(self, n):
        f = n.fields
        head, body, end = (
            self.label("while"),
            self.label("body"),
            self.label("endwhile"),
        )
        self.start(head)
        self.cond(f["cond"], body, end)
        self.start(body)
        self.stmt(f["body"])
        self.emit(Instr("jmp", aux=[head]))
        self.start(end)

    def s_Assert(self, n):
        p = n.fields["pred"]
        if has_spec(p):
            return
        ok, bad = self.label("ok"), self.label("fail")
        self.cond(p, ok, bad)
        self.start(bad)
        self.emit(Instr("trap"))
        self.start(ok)

    def s_Assume(self, n):
        pass


def gen_func(fn):
    g = Gen(fn)
    g.start("entry")
    g.stmt(fn.fields["body"])
    g.emit(Instr("ret", [], [n for n, _ in g.f.rets]))
    return g.f


def gen_module(ast):
    return [gen_func(n) for n in ast.fields["items"] if n.kind == "Function"]


def build_cfg(fn):
    m = {b.name: b for b in fn.blocks}
    for b in fn.blocks:
        t = b.term()
        if t is None or t.op in ("ret", "trap"):
            b.succs = []
        else:
            b.succs = list(dict.fromkeys(t.aux))
    seen = set()
    st = [fn.blocks[0].name]
    while st:
        x = st.pop()
        if x in seen:
            continue
        seen.add(x)
        st.extend(m[x].succs)
    fn.blocks = [b for b in fn.blocks if b.name in seen]
    for b in fn.blocks:
        b.preds = []
    for b in fn.blocks:
        for s in b.succs:
            m[s].preds.append(b.name)


def liveness(fn):
    use, dfn = {}, {}
    for b in fn.blocks:
        u, d = set(), set()
        for i in b.instrs:
            u |= {x for x in i.uses() if x not in d}
            d |= set(i.dst)
        use[b.name], dfn[b.name] = u, d
    lin = {b.name: set() for b in fn.blocks}
    lout = {b.name: set() for b in fn.blocks}
    ch = True
    while ch:
        ch = False
        for b in reversed(fn.blocks):
            o = set().union(*(lin[s] for s in b.succs))
            i = use[b.name] | (o - dfn[b.name])
            if o != lout[b.name] or i != lin[b.name]:
                lout[b.name], lin[b.name] = o, i
                ch = True
    return lin, lout


def cfg_dot_all(funcs):
    out = ["digraph cfg {", "  node [shape=box, fontname=monospace];"]
    for fn in funcs:
        out.append(f'  subgraph "cluster_{fn.name}" {{')
        out.append(f'    label="{fn.name}";')
        for b in fn.blocks:
            lab = b.name + ":\\l" + "".join(fmt_instr(i) + "\\l" for i in b.instrs)
            out.append(f'    "{fn.name}.{b.name}" [label="{lab}"];')
        for b in fn.blocks:
            for s in b.succs:
                out.append(f'    "{fn.name}.{b.name}" -> "{fn.name}.{s}";')
        out.append("  }")
    out.append("}")
    return "\n".join(out)
