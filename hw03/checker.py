from hw02.parser import parse

def format_error(text, pos, msg):
    line = text.count("\n", 0, pos) + 1
    col = pos - (text.rfind("\n", 0, pos) + 1) + 1
    return f"{line}:{col}: {msg}"


def analyze(text, dfa):
    ast, errs = parse(text, dfa)
    if ast is None or errs:
        return (ast.to_dict() if ast is not None else None), list(errs)
    c = Checker()
    c.check(ast)
    return ast.to_dict(), sorted(set(c.errors))


class Checker:
    def __init__(self):
        self.errors = []
        self.funcs = {}
        self.formulas = {}
        self.scope = {}
        self.pending = {}
        self.params = set()
        self.in_cond = False
        self.stmt_pos = None


    def err(self, pos, msg):
        self.errors.append((pos, msg))

    def check(self, ast):
        items = ast.fields["items"]
        for n in items:
            name = n.fields["name"]
            if name in ("set", "length"):
                self.err(n.pos, f"{name!r} is a reserved builtin name")
            elif name in self.funcs or name in self.formulas:
                self.err(n.pos, f"redeclaration of {name!r}")
            elif n.kind == "Function":
                self.funcs[name] = n
            else:
                self.formulas[name] = n
        for n in items:
            self.top(n)
        ast.fields["ty"] = "module"
        return ast

    def declare(self, v):
        name = v.fields["name"]
        ty = v.fields["type"]
        if name in self.scope:
            self.err(v.pos, f"redeclaration of {name!r}")
        else:
            self.scope[name] = ty
        v.fields["ty"] = ty

    def top(self, n):
        f = n.fields
        self.scope = {}
        self.pending = {}
        self.params = {p.fields["name"] for p in f["params"]}
        for p in f["params"]:
            self.declare(p)
        ptypes = [p.fields["type"] for p in f["params"]]
        if n.kind == "Formula":
            self.pred(f["body"])
            f["ty"] = {"params": ptypes, "returns": ["bool"]}
            return
        if f["requires"] is not None:
            self.pred(f["requires"])
        for r in f["returns"]:
            self.declare(r)
        if f["ensures"] is not None:
            self.pred(f["ensures"])
        for l in f["locals"]:
            self.declare(l)
        self.stmt(f["body"])
        for l in f["locals"]:
            name = l.fields["name"]
            t = self.scope.get(name)
            l.fields["ty"] = t
            if t is None:
                self.err(l.pos, f"cannot infer type of local variable {name!r}")
        f["ty"] = {
            "params": ptypes,
            "returns": [r.fields["type"] for r in f["returns"]],
        }

    def settype(self, name, t):
        self.scope[name] = t
        for r in self.pending.pop(name, []):
            r.fields["ty"] = t

    def cond(self, n):
        self.in_cond = True
        self.pred(n)
        self.in_cond = False

    def stmt(self, n):
        getattr(self, "s_" + n.kind)(n)

    def need_int(self, pos, t, what):
        if t is not None and t != "int":
            self.err(pos, f"{what} must be int, got {t}")
    
    def pred(self, n):
        getattr(self, "p_" + n.kind)(n)
        n.fields["ty"] = "bool"
    
    def expr(self, n, want=None):
        t = getattr(self, "e_" + n.kind)(n)
        if t is None and want is not None and n.kind == "Ref":
            name = n.fields["name"]
            if name in self.scope and self.scope[name] is None:
                self.settype(name, want)
                t = want
        n.fields["ty"] = t
        return t

    def assign_stmt(self, n):
        f = n.fields
        targets, val = f["targets"], f["value"]
        if len(targets) == 1:
            self.assign(n.pos, targets[0], self.expr(val, self.scope.get(targets[0])))
            return
        rets = self.call(val)
        if rets is None:
            return
        val.fields["ty"] = rets
        if len(rets) != len(targets):
            self.err(
                n.pos,
                f"function {val.fields['name']!r} returns {len(rets)} value(s), "
                f"but {len(targets)} target(s) given",
            )
            return
        for tg, t in zip(targets, rets):
            self.assign(n.pos, tg, t)

    def assign(self, pos, name, t):
        if name[:2] == "_t" and name[2:].isdigit():
            self.scope[name] = t
            return
        if name not in self.scope:
            self.err(pos, f"assignment to undeclared variable {name!r}")
            return
        if name in self.params:
            self.err(pos, f"cannot assign to parameter {name!r}")
            return
        cur = self.scope[name]
        if cur is None:
            if t is not None:
                self.settype(name, t)
        elif t is not None and cur != t:
            self.err(pos, f"cannot assign {t} to {name!r} of type {cur}")

    def match_args(self, pos, name, ptypes, ats):
        if len(ptypes) != len(ats):
            self.err(pos, f"{name!r} expects {len(ptypes)} argument(s), got {len(ats)}")
            return
        for k, (p, a) in enumerate(zip(ptypes, ats), 1):
            if a is not None and a != p:
                self.err(pos, f"argument {k} of {name!r}: expected {p}, got {a}")
    
    def args_of(self, args, ptypes=None):
        ws = ptypes if ptypes is not None and len(ptypes) == len(args) else [None] * len(args)
        return [self.expr(a, w) for a, w in zip(args, ws)]

    def call(self, n):
        f = n.fields
        name, args = f["name"], f["args"]
        if name == "length":
            ats = self.args_of(args, ["int[]"])
            if len(args) != 1:
                self.err(n.pos, f"'length' expects 1 argument, got {len(args)}")
            elif ats[0] is not None and not ats[0].endswith("[]"):
                self.err(n.pos, f"'length' expects an array, got {ats[0]}")
            return ["int"]
        if name == "set":
            if n.pos != self.stmt_pos:
                self.args_of(args)
                self.err(n.pos, "'set' is not a public function; use a[i] = v")
                return None
            a = self.expr(args[0], "int[]")
            self.need_int(n.pos, self.expr(args[1], "int"), "index argument of 'set'")
            elem = a[:-2] if a is not None and a.endswith("[]") else None
            x = self.expr(args[2], elem)
            if a is None:
                return None
            if elem is None:
                self.err(n.pos, f"first argument of 'set' must be an array, got {a}")
                return None
            if x is not None and x != elem:
                self.err(n.pos, f"'set' on {a} expects element of type {elem}, got {x}")
            return [a]
        if name in self.formulas:
            self.args_of(args)
            self.err(n.pos, f"formula {name!r} cannot be used as an expression")
            return None
        fn = self.funcs.get(name)
        if fn is None:
            self.args_of(args)
            self.err(n.pos, f"unknown function {name!r}")
            return None
        sig = fn.fields["ty"] if fn.fields.get("ty") else {
            "params": [p.fields["type"] for p in fn.fields["params"]],
            "returns": [r.fields["type"] for r in fn.fields["returns"]],
        }
        ats = self.args_of(args, sig["params"])
        self.match_args(n.pos, name, sig["params"], ats)
        return sig["returns"]
    
    def s_Block(self, n):
        for s in n.fields["body"]:
            self.stmt(s)

    s_Seq = s_Block

    def s_If(self, n):
        f = n.fields
        self.cond(f["cond"])
        self.stmt(f["then"])
        if f["else_"] is not None:
            self.stmt(f["else_"])

    def s_While(self, n):
        f = n.fields
        self.cond(f["cond"])
        if f["invariant"] is not None:
            self.pred(f["invariant"])
        self.stmt(f["body"])

    def s_Assert(self, n):
        self.pred(n.fields["pred"])

    s_Assume = s_Assert

    def s_Assign(self, n):
        self.stmt_pos = n.pos
        self.assign_stmt(n)
        self.stmt_pos = None

    def e_Int(self, n):
        return "int"
    
    def e_Ref(self, n):
        name = n.fields["name"]
        if name not in self.scope:
            self.err(n.pos, f"unknown name {name!r}")
            return None
        t = self.scope[name]
        if t is None:
            self.pending.setdefault(name, []).append(n)
        return t

    def e_Neg(self, n):
        self.need_int(n.pos, self.expr(n.fields["operand"], "int"), "operand of unary '-'")
        return "int"

    def e_Bin(self, n):
        f = n.fields
        self.need_int(n.pos, self.expr(f["left"], "int"), f"left operand of {f['op']!r}")
        self.need_int(n.pos, self.expr(f["right"], "int"), f"right operand of {f['op']!r}")
        return "int"

    def e_Index(self, n):
        f = n.fields
        a = self.expr(f["array"], "int[]")
        self.need_int(n.pos, self.expr(f["index"], "int"), "array index")
        if a is None:
            return None
        if not a.endswith("[]"):
            self.err(n.pos, f"cannot index value of type {a}")
            return None
        return a[:-2]

    def e_Call(self, n):
        rets = self.call(n)
        if rets is None:
            return None
        if len(rets) != 1:
            self.err(
                n.pos,
                f"function {n.fields['name']!r} returns {len(rets)} values, "
                "expected a single value",
            )
            return None
        return rets[0]
    
    def p_Bool(self, n):
        pass

    def p_Not(self, n):
        self.pred(n.fields["operand"])

    def p_And(self, n):
        self.pred(n.fields["left"])
        self.pred(n.fields["right"])

    p_Or = p_And
    p_Implies = p_And

    def p_Cmp(self, n):
        f = n.fields
        l = self.expr(f["left"], "int")
        r = self.expr(f["right"], "int")
        self.need_int(n.pos, l, f"left operand of {f['op']!r}")
        self.need_int(n.pos, r, f"right operand of {f['op']!r}")

    def p_Quantifier(self, n):
        f = n.fields
        name = f["var"].fields["name"]
        dup = name in self.scope
        if self.in_cond:
            self.err(n.pos, "quantifiers are not allowed in conditions")
        if dup:
            self.err(f["var"].pos, f"redeclaration of {name!r}")
        else:
            self.scope[name] = f["var"].fields["type"]
        self.pred(f["body"])
        if not dup:
            del self.scope[name]

    def p_FormulaRef(self, n):
        f = n.fields
        name = f["name"]
        if self.in_cond:
            self.err(n.pos, "formula references are not allowed in conditions")
        fm = self.formulas.get(name)
        if fm is None:
            self.args_of(f["args"])
            if name in self.funcs:
                self.err(n.pos, f"function {name!r} used as a predicate, expected comparison")
            else:
                self.err(n.pos, f"unknown formula {name!r}")
            return
        ptypes = [p.fields["type"] for p in fm.fields["params"]]
        self.match_args(n.pos, name, ptypes, self.args_of(f["args"], ptypes))
