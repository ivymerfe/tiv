from hw01.tokenizer import LexError, tokenize

SKIP = {"WS", "COMMENT"}
CMP = {"==", "!=", "<", ">", "<=", ">="}


class ParseError(Exception):
    def __init__(self, msg, pos):
        super().__init__(msg)
        self.msg = msg
        self.pos = pos


def conv(v):
    if isinstance(v, Node):
        return v.to_dict()
    if isinstance(v, list):
        return [conv(x) for x in v]
    return v


class Node:
    def __init__(self, kind, pos, **fields):
        self.kind = kind
        self.pos = pos
        self.fields = fields

    def to_dict(self):
        d = {"kind": self.kind, "pos": self.pos}
        for k, v in self.fields.items():
            d[k] = conv(v)
        return d


class Parser:
    def __init__(self, text, toks):
        self.text = text
        self.toks = toks + [("EOF", "", len(text))]
        self.i = 0
        self.errors = []

    def key(self, t=None):
        t = t or self.toks[self.i]
        return t[1] if t[0] in ("KEYWORD", "OP") else t[0]

    def cur(self):
        return self.toks[self.i]

    def at(self, *ks):
        return self.key() in ks

    def eat(self, k=None):
        if k is not None and self.key() != k:
            self.fail(f"expected {k!r}")
        t = self.toks[self.i]
        if t[0] != "EOF":
            self.i += 1
        return t

    def fail(self, msg):
        t = self.cur()
        got = "end of input" if t[0] == "EOF" else repr(t[1])
        raise ParseError(f"{msg}, got {got}", t[2])

    def comma_list(self, item, end):
        res = []
        if not self.at(end):
            res.append(item())
            while self.at(","):
                self.eat()
                res.append(item())
        return res

    def module(self):
        items = []
        while not self.at("EOF"):
            try:
                items.append(self.top())
            except ParseError as e:
                self.errors.append(e)
                self.sync_top()
        if not items and not self.errors:
            self.errors.append(
                ParseError("empty input: expected function or formula", 0)
            )
        return Node("Module", 0, items=items)

    def sync_top(self):
        depth = 0
        while not self.at("EOF"):
            k = self.key()
            self.i += 1
            if k == "{":
                depth += 1
            elif k == "}":
                depth = max(depth - 1, 0)
                if depth == 0:
                    return
            elif k == ";" and depth == 0:
                return

    def type(self):
        self.eat("int")
        ty = "int"
        while self.at("["):
            self.eat()
            self.eat("]")
            ty += "[]"
        return ty

    def var_def(self, typed=True):
        p = self.cur()[2]
        name = self.eat("IDENT")[1]
        ty = None
        if typed or self.at(":"):
            self.eat(":")
            ty = self.type()
        return Node("VarDef", p, name=name, type=ty)

    def local_def(self):
        return self.var_def(False)

    def top(self):
        p = self.cur()[2]
        name = self.eat("IDENT")[1]
        self.eat("(")
        params = self.comma_list(self.var_def, ")")
        self.eat(")")
        if self.at("=>"):
            self.eat()
            return Node("Formula", p, name=name, params=params, body=self.predicate())
        requires = None
        if self.at("requires"):
            self.eat()
            requires = self.predicate()
        self.eat("returns")
        rets = [self.var_def()]
        while self.at(","):
            self.eat()
            rets.append(self.var_def())
        ensures = None
        if self.at("ensures"):
            self.eat()
            ensures = self.predicate()
        locs = []
        if self.at("uses"):
            self.eat()
            locs = [self.local_def()]
            while self.at(","):
                self.eat()
                locs.append(self.local_def())
        body = self.statement()
        return Node(
            "Function",
            p,
            name=name,
            params=params,
            requires=requires,
            returns=rets,
            ensures=ensures,
            locals=locs,
            body=body,
        )

    def statement(self):
        k = self.key()
        p = self.cur()[2]
        if k == "{":
            return self.block()
        if k == "if":
            self.eat()
            self.eat("(")
            c = self.predicate()
            self.eat(")")
            then = self.statement()
            els = None
            if self.at("else"):
                self.eat()
                els = self.statement()
            return Node("If", p, cond=c, then=then, else_=els)
        if k == "while":
            self.eat()
            self.eat("(")
            c = self.predicate()
            self.eat(")")
            inv = None
            if self.at("invariant"):
                self.eat()
                inv = self.predicate()
            return Node("While", p, cond=c, invariant=inv, body=self.statement())
        if k in ("assert", "assume"):
            self.eat()
            pr = self.predicate()
            self.eat(";")
            return Node(k.capitalize(), p, pred=pr)
        if k == "IDENT":
            return self.assignment()
        self.fail("expected operator")

    def block(self):
        p = self.cur()[2]
        self.eat("{")
        body = []
        while not self.at("}", "EOF"):
            try:
                body.append(self.statement())
            except ParseError as e:
                self.errors.append(e)
                self.sync_stmt()
        self.eat("}")
        return Node("Block", p, body=body)

    def sync_stmt(self):
        start = self.i
        while not self.at("EOF", "}"):
            k = self.key()
            if k == ";":
                self.i += 1
                return
            if k in ("if", "while", "assert", "assume", "{") and self.i > start:
                return
            self.i += 1

    def assignment(self):
        p = self.cur()[2]
        first = self.eat("IDENT")[1]
        if self.at("["):
            idx = []
            while self.at("["):
                self.eat()
                idx.append(self.expr())
                self.eat("]")
            self.eat("=")
            v = self.expr()
            self.eat(";")
            return self.desugar(first, idx, v, p)
        targets = [first]
        while self.at(","):
            self.eat()
            targets.append(self.eat("IDENT")[1])
        self.eat("=")
        e = self.expr()
        self.eat(";")
        if len(targets) > 1 and e.kind != "Call":
            raise ParseError("присваивание кортежа требует вызова функции", p)
        return Node("Assign", p, targets=targets, value=e)

    def desugar(self, name, idx, v, p):
        def ref(n):
            return Node("Ref", p, name=n)

        def setc(a, i, x):
            return Node("Call", p, name="set", args=[a, i, x])

        def asg(t, e):
            return Node("Assign", p, targets=[t], value=e)

        k = len(idx)
        if k == 1:
            return asg(name, setc(ref(name), idx[0], v))
        tmp = [f"_t{j}" for j in range(1, k)]
        out = [asg(tmp[0], Node("Index", p, array=ref(name), index=idx[0]))]
        for j in range(1, k - 1):
            out.append(
                asg(tmp[j], Node("Index", p, array=ref(tmp[j - 1]), index=idx[j]))
            )
        out.append(asg(tmp[k - 2], setc(ref(tmp[k - 2]), idx[k - 1], v)))
        for j in range(k - 2, 0, -1):
            out.append(asg(tmp[j - 1], setc(ref(tmp[j - 1]), idx[j], ref(tmp[j]))))
        out.append(asg(name, setc(ref(name), idx[0], ref(tmp[0]))))
        return Node("Seq", p, body=out)

    def expr(self):
        l = self.term()
        while self.at("+", "-"):
            t = self.eat()
            l = Node("Bin", t[2], op=t[1], left=l, right=self.term())
        return l

    def term(self):
        l = self.unary()
        while self.at("*", "/"):
            t = self.eat()
            l = Node("Bin", t[2], op=t[1], left=l, right=self.unary())
        return l

    def unary(self):
        if self.at("-"):
            t = self.eat()
            return Node("Neg", t[2], operand=self.unary())
        return self.postfix()

    def postfix(self):
        e = self.primary()
        while self.at("["):
            t = self.eat()
            i = self.expr()
            self.eat("]")
            e = Node("Index", t[2], array=e, index=i)
        return e

    def primary(self):
        t = self.cur()
        k = self.key()
        if k == "INT":
            self.eat()
            return Node("Int", t[2], value=int(t[1]))
        if k == "(":
            self.eat()
            e = self.expr()
            self.eat(")")
            return e
        if k in ("IDENT", "length"):
            self.eat()
            if self.at("("):
                self.eat()
                args = self.comma_list(self.expr, ")")
                self.eat(")")
                return Node("Call", t[2], name=t[1], args=args)
            if k == "length":
                self.fail("expected '(' after length")
            return Node("Ref", t[2], name=t[1])
        self.fail("expected expression")

    def predicate(self):
        return self.implies()

    def implies(self):
        l = self.disj()
        if self.at("->"):
            t = self.eat()
            return Node("Implies", t[2], left=l, right=self.implies())
        return l

    def disj(self):
        l = self.conj()
        while self.at("or"):
            t = self.eat()
            l = Node("Or", t[2], left=l, right=self.conj())
        return l

    def conj(self):
        l = self.neg()
        while self.at("and"):
            t = self.eat()
            l = Node("And", t[2], left=l, right=self.neg())
        return l

    def neg(self):
        if self.at("not"):
            t = self.eat()
            return Node("Not", t[2], operand=self.neg())
        return self.patom()

    def comparison(self, left):
        t = self.eat()
        return Node("Cmp", t[2], op=t[1], left=left, right=self.expr())

    def patom(self):
        t = self.cur()
        k = self.key()
        if k in ("true", "false"):
            self.eat()
            return Node("Bool", t[2], value=(k == "true"))
        if k in ("forall", "exists"):
            self.eat()
            self.eat("(")
            v = self.var_def()
            self.eat("|")
            b = self.predicate()
            self.eat(")")
            return Node("Quantifier", t[2], quant=k, var=v, body=b)
        if k == "(":
            save = self.i
            e = None
            try:
                e = self.expr()
                ok = self.key() in CMP
            except ParseError:
                ok = False
            if ok:
                return self.comparison(e)
            self.i = save
            self.eat()
            p = self.predicate()
            self.eat(")")
            return p
        e = self.expr()
        if self.key() in CMP:
            return self.comparison(e)
        if e.kind == "Call":
            return Node("FormulaRef", e.pos, name=e.fields["name"], args=e.fields["args"])
        self.fail("expected comparison")


def parse(text, dfa):
    try:
        toks = tokenize(dfa, text, SKIP)
    except LexError as e:
        return None, [(e.pos, f"bad character {e.char!r}")]
    p = Parser(text, toks)
    ast = p.module()
    errs = {}
    for e in p.errors:
        errs.setdefault(e.pos, e.msg)
    return ast, sorted(errs.items())
