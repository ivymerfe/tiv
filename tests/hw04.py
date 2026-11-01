from hw01.dfa import dfa_from_csv
from hw02.parser import parse
from hw03.checker import Checker
from hw04.ir import gen_module, build_cfg, fmt_func
from hw04.opt import optimize, interference, color

dfa = dfa_from_csv("dfa.csv")
ALL = {"cprop", "algebra", "dce"}


def fail(src, expected, got):
    print(f"FAIL: {src!r} -> expected {expected}, got {got}")
    exit(1)


def L(*lines):
    return "\n".join(lines)


def build(src, passes=()):
    ast, errs = parse(src, dfa)
    if errs:
        fail(src, "no parse errors", errs)
    c = Checker()
    c.check(ast)
    if c.errors:
        fail(src, "no check errors", c.errors)
    funcs = gen_module(ast)
    for f in funcs:
        build_cfg(f)
    for f in funcs:
        optimize(f, set(passes))
    return funcs


def check(src, expected, passes=(), i=0):
    got = fmt_func(build(src, passes)[i])
    if got != expected:
        fail(src, expected, got)
    print(f"SUCCESS: {src!r} {sorted(passes)} -> ok")


def eq(src, got, expected):
    if got != expected:
        fail(src, expected, got)
    print(f"SUCCESS: {src!r} -> {expected!r}")


def proper(g, col):
    return all(col[v] != col[u] for v in g for u in g[v])


check(
    "f(a: int, b: int) returns r: int { r = a + b; }",
    L("func f(a: int, b: int) -> (r: int)", "entry:", "  r = add a, b", "  ret r"),
)

src = "f() returns r: int { r = 1 + 2 * 3; }"
check(
    src,
    L(
        "func f() -> (r: int)",
        "entry:",
        "  %t1 = mul 2, 3",
        "  r = add 1, %t1",
        "  ret r",
    ),
)
check(
    src,
    L("func f() -> (r: int)", "entry:", "  %t1 = 6", "  r = 7", "  ret 7"),
    {"cprop"},
)
check(src, L("func f() -> (r: int)", "entry:", "  ret 7"), {"cprop", "dce"})

check(
    "f() returns r: int { r = 2147483647 + 1; }",
    L("func f() -> (r: int)", "entry:", "  ret -2147483648"),
    {"cprop", "dce"},
)
check(
    "f() returns r: int { r = 1 / 0; }",
    L("func f() -> (r: int)", "entry:", "  r = div 1, 0", "  ret r"),
    ALL,
)
check(
    "f() returns r: int { r = -7 / 2; }",
    L("func f() -> (r: int)", "entry:", "  ret -3"),
    ALL,
)

check(
    "f(a: int) returns r: int { r = a * 1 + 0; }",
    L("func f(a: int) -> (r: int)", "entry:", "  %t1 = a", "  r = %t1", "  ret r"),
    {"algebra"},
)
check(
    "f(a: int) returns r: int { r = a * 1 + 0; }",
    L("func f(a: int) -> (r: int)", "entry:", "  ret a"),
    ALL,
)
check(
    "f(a: int) returns r: int { r = a - a; }",
    L("func f(a: int) -> (r: int)", "entry:", "  ret 0"),
    ALL,
)
check(
    "f(a: int) returns r: int { r = a * 2; }",
    L("func f(a: int) -> (r: int)", "entry:", "  r = add a, a", "  ret r"),
    ALL,
)
check(
    "f(a: int) returns r: int { r = a + 2; }",
    L("func f(a: int) -> (r: int)", "entry:", "  r = add a, 2", "  ret r"),
    ALL,
)

src = "f(a: int, b: int) returns r: int { r = (a + b) * (b + a); }"
check(
    src,
    L(
        "func f(a: int, b: int) -> (r: int)",
        "entry:",
        "  %t1 = add a, b",
        "  %t2 = %t1",
        "  r = mul %t1, %t2",
        "  ret r",
    ),
    {"cse"},
)
check(
    src,
    L(
        "func f(a: int, b: int) -> (r: int)",
        "entry:",
        "  %t1 = add a, b",
        "  r = mul %t1, %t1",
        "  ret r",
    ),
    {"cse", "cprop", "dce"},
)
check(
    src,
    L(
        "func f(a: int, b: int) -> (r: int)",
        "entry:",
        "  %t1 = add a, b",
        "  %t2 = add b, a",
        "  r = mul %t1, %t2",
        "  ret r",
    ),
    ALL,
)

check(
    "f(a: int) returns r: int uses x { x = a + 1; r = a; }",
    L("func f(a: int) -> (r: int)", "entry:", "  r = a", "  ret r"),
    {"dce"},
)
check(
    "g() returns a: int { a = 1; } f() returns r: int uses x { x = g(); r = 0; }",
    L("func f() -> (r: int)", "entry:", "  x = call g()", "  r = 0", "  ret r"),
    {"dce"},
    1,
)
check(
    "f(a: int, b: int) returns r: int uses x { x = a / b; r = 0; }",
    L(
        "func f(a: int, b: int) -> (r: int)",
        "entry:",
        "  x = div a, b",
        "  r = 0",
        "  ret r",
    ),
    {"dce"},
)
check(
    "f(a: int[]) returns r: int uses x { x = a[0]; r = 0; }",
    L(
        "func f(a: int[]) -> (r: int)",
        "entry:",
        "  x = load a, 0",
        "  r = 0",
        "  ret r",
    ),
    {"dce"},
)

check(
    "f(a: int) returns r: int { if (a > 0) r = 1; else r = 2; }",
    L(
        "func f(a: int) -> (r: int)",
        "entry:",
        "  %t1 = gt a, 0",
        "  br %t1, then1, else2",
        "then1:",
        "  r = 1",
        "  jmp endif3",
        "else2:",
        "  r = 2",
        "  jmp endif3",
        "endif3:",
        "  ret r",
    ),
)
check(
    "f() returns r: int { if (1 < 2) r = 1; else r = 2; }",
    L(
        "func f() -> (r: int)",
        "entry:",
        "  jmp then1",
        "then1:",
        "  r = 1",
        "  jmp endif3",
        "endif3:",
        "  ret r",
    ),
    ALL,
)
fn = build("f() returns r: int { if (1 < 2) r = 1; else r = 2; }", ALL)[0]
eq("unreachable", [b.name for b in fn.blocks], ["entry", "then1", "endif3"])

check(
    "f(a: int, b: int) returns r: int { if (a > 0 and b > 0) r = 1; }",
    L(
        "func f(a: int, b: int) -> (r: int)",
        "entry:",
        "  %t1 = gt a, 0",
        "  br %t1, and4, endif3",
        "and4:",
        "  %t2 = gt b, 0",
        "  br %t2, then1, endif3",
        "then1:",
        "  r = 1",
        "  jmp endif3",
        "endif3:",
        "  ret r",
    ),
)

loop = "f(n: int) returns r: int uses i { i = 0; r = 0; while (i < n) { r = r + i; i = i + 1; } }"
loop_ir = L(
    "func f(n: int) -> (r: int)",
    "entry:",
    "  i = 0",
    "  r = 0",
    "  jmp while1",
    "while1:",
    "  %t1 = lt i, n",
    "  br %t1, body2, endwhile3",
    "body2:",
    "  r = add r, i",
    "  i = add i, 1",
    "  jmp while1",
    "endwhile3:",
    "  ret r",
)
check(loop, loop_ir)
check(loop, loop_ir, ALL)
fn = build(loop)[0]
eq(
    loop,
    {b.name: b.succs for b in fn.blocks},
    {
        "entry": ["while1"],
        "while1": ["body2", "endwhile3"],
        "body2": ["while1"],
        "endwhile3": [],
    },
)
eq(
    loop,
    {b.name: b.preds for b in fn.blocks},
    {
        "entry": [],
        "while1": ["entry", "body2"],
        "body2": ["while1"],
        "endwhile3": ["while1"],
    },
)

check(
    "f(a: int) returns r: int { assert a > 0; r = a; }",
    L(
        "func f(a: int) -> (r: int)",
        "entry:",
        "  %t1 = gt a, 0",
        "  br %t1, ok1, fail2",
        "fail2:",
        "  trap",
        "ok1:",
        "  r = a",
        "  ret r",
    ),
)
check(
    "f(a: int[]) returns r: int { assert forall (i: int | i >= 0 -> i >= 0); r = 0; }",
    L("func f(a: int[]) -> (r: int)", "entry:", "  r = 0", "  ret r"),
)
check(
    "f(a: int) returns r: int { assume a > 0; r = a; }",
    L("func f(a: int) -> (r: int)", "entry:", "  r = a", "  ret r"),
)

src = "g() returns a: int, b: int { a = 1; b = 2; } f() returns r: int uses x, y { x, y = g(); r = x + y; }"
check(
    src,
    L(
        "func f() -> (r: int)",
        "entry:",
        "  x, y = call g()",
        "  r = add x, y",
        "  ret r",
    ),
    (),
    1,
)
check(
    src,
    L("func g() -> (a: int, b: int)", "entry:", "  ret 1, 2"),
    {"cprop", "dce"},
    0,
)

check(
    "f(a: int[], i: int) returns b: int[] { b = a; b[i] = 5; }",
    L(
        "func f(a: int[], i: int) -> (b: int[])",
        "entry:",
        "  b = a",
        "  b = aset b, i, 5",
        "  ret b",
    ),
)
check(
    "f(a: int[], i: int) returns b: int[] { b = a; b[i] = 5; }",
    L(
        "func f(a: int[], i: int) -> (b: int[])",
        "entry:",
        "  b = aset a, i, 5",
        "  ret b",
    ),
    {"cprop", "dce"},
)
check(
    "f() returns r: int uses m: int[][] { m[1][2] = 5; r = m[0][1]; }",
    L(
        "func f() -> (r: int)",
        "entry:",
        "  _t1 = load m, 1",
        "  _t1 = aset _t1, 2, 5",
        "  m = aset m, 1, _t1",
        "  %t1 = load m, 0",
        "  r = load %t1, 1",
        "  ret r",
    ),
)

fn = build("f(a: int, b: int) returns r: int { r = (a + b) * (a - b); }")[0]
g = interference(fn)
col = color(g)
eq("two live temps", g, {"%t1": {"%t2"}, "%t2": {"%t1"}})
eq("two live temps", col, {"%t1": 0, "%t2": 1})

fn = build("f(a: int, b: int) returns r: int { r = ((a + b) + a) + b; }")[0]
g = interference(fn)
col = color(g)
eq("chain", g, {"%t1": set(), "%t2": set()})
eq("chain", col, {"%t1": 0, "%t2": 0})

fn = build("f(a: int, b: int) returns r: int { r = (a + b) * ((a - b) * (a * b)); }")[0]
g = interference(fn)
col = color(g)
eq(
    "clique",
    g,
    {
        "%t1": {"%t2", "%t3", "%t4"},
        "%t2": {"%t1", "%t3"},
        "%t3": {"%t1", "%t2"},
        "%t4": {"%t1"},
    },
)
eq("clique", col, {"%t1": 0, "%t2": 1, "%t3": 2, "%t4": 1})
eq("clique", proper(g, col), True)

print("all tests passed")
