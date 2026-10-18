from hw01.dfa import dfa_from_csv
from hw03.checker import analyze, format_error

dfa = dfa_from_csv("dfa.csv")
HEAD = "f() returns r: int { "


def fail(src, expected, got):
    print(f"FAIL: {src!r} -> expected {expected}, got {got}")
    exit(1)


def find(src, m, nth=0):
    p = -1
    for _ in range(nth + 1):
        p = src.index(m, p + 1)
    return p


def ok(src):
    ast, errs = analyze(src, dfa)
    if errs:
        fail(src, "no errors", errs)
    print(f"SUCCESS: {src!r} -> ok")
    return ast


def bad(src, marker, part, nth=0):
    pos = find(src, marker, nth)
    ast, errs = analyze(src, dfa)
    if not errs or errs[0][0] != pos or part not in errs[0][1]:
        fail(src, f"first error at {pos} with {part!r}", errs)
    print(f"SUCCESS: {src!r} -> {errs[0]}")


def multi(src, positions):
    ast, errs = analyze(src, dfa)
    got = [p for p, _ in errs]
    if got != positions:
        fail(src, f"errors at {positions}", errs)
    print(f"SUCCESS: {src!r} -> {errs}")


def eq(src, got, expected):
    if got != expected:
        fail(src, expected, got)
    print(f"SUCCESS: {src!r} -> {expected!r}")


def stmt(ast, i=0, f=0):
    return ast["items"][f]["body"]["body"][i]


for src in [
    "f(a: int, b: int) returns r: int { r = a + b; }",
    "f(a: int[]) returns r: int { r = a[0] + length(a); }",
    "f(a: int, b: int) requires b != 0 returns q: int, r: int { q = a / b; r = a - q * b; }",
    "f(n: int) returns r: int { r = f(n - 1); }",
    "g() returns a: int, b: int { a = 1; b = 2; } f() returns r: int uses x, y { x, y = g(); r = x + y; }",
    "p(x: int) => x > 0 f(a: int) requires p(a) returns r: int { r = a; }",
    "f(a: int[]) requires forall (i: int | a[i] >= 0) returns r: int { r = 0; }",
    "f(a: int[]) requires a[0] > 0 returns r: int ensures r >= 0 { r = a[0]; }",
    "f(a: int[]) returns r: int uses i { i = 0; while (i < length(a)) invariant i >= 0 { i = i + 1; } r = i; }",
    "f() returns r: int uses x { x = 5; r = x; }",
    "f() returns r: int uses a { a[1] = 42; r = a[1]; }",
    "f() returns r: int uses a: int[], i { i = 0; r = a[i]; }",
    "f() returns r: int uses m: int[][] { m[1][2] = 5; r = m[0][1]; }",
    "f(a: int[]) returns r: int { if (r > 0) r = 1; else { r = a[0]; } assert r >= 0; assume not r == 3; }",
    "p(x: int) => x > 0 and (x < 10 or not x == 5)",
    "p(a: int[], n: int) => exists (i: int | a[i] == n)",
    "p(x: int) => x > 0 q(x: int) => p(x) and not p(x + 1)",
]:
    ok(src)

src = "f(a: int[]) requires a[0] > 0 returns r: int { r = a[0] + 1; }"
ast = ok(src)
fn = ast["items"][0]
eq(src, ast["ty"], "module")
eq(src, fn["ty"], {"params": ["int[]"], "returns": ["int"]})
eq(src, fn["params"][0]["ty"], "int[]")
eq(src, fn["requires"]["ty"], "bool")
eq(src, fn["requires"]["left"]["ty"], "int")
eq(src, fn["requires"]["left"]["array"]["ty"], "int[]")
eq(src, stmt(ast)["value"]["ty"], "int")
eq(src, stmt(ast)["value"]["left"]["array"]["ty"], "int[]")

src = "p(x: int) => x > 0"
ast = ok(src)
eq(src, ast["items"][0]["ty"], {"params": ["int"], "returns": ["bool"]})
eq(src, ast["items"][0]["body"]["ty"], "bool")

src = "g() returns a: int, b: int { a = 1; b = 2; } f() returns r: int uses x, y { x, y = g(); r = x + y; }"
ast = ok(src)
eq(src, ast["items"][1]["ty"], {"params": [], "returns": ["int"]})
eq(src, stmt(ast, 0, 1)["value"]["ty"], ["int", "int"])
eq(src, stmt(ast, 1, 1)["value"]["left"]["ty"], "int")

src = "f() returns r: int uses a { a[1] = 42; r = a[1]; }"
ast = ok(src)
eq(src, stmt(ast, 0)["value"]["ty"], "int[]")
eq(src, stmt(ast, 0)["value"]["args"][0]["ty"], "int[]")
eq(src, stmt(ast, 1)["value"]["array"]["ty"], "int[]")

src = "f() returns r: int uses m: int[][] { m[1][2] = 5; r = m[0][1]; }"
ast = ok(src)
eq(src, stmt(ast, 1)["value"]["ty"], "int")
eq(src, stmt(ast, 1)["value"]["array"]["ty"], "int[]")

bad(HEAD + "r = x; }", "x;", "unknown name")
bad(HEAD + "r = g(1); }", "g(", "unknown function")
bad(HEAD + "y = 1; }", "y = 1", "undeclared variable")
bad("f(a: int[]) returns r: int { r = a; }", "r = a", "cannot assign")
bad("f(a: int[]) returns r: int { r = a + 1; }", "+ 1", "must be int")
bad("f(n: int) returns r: int { r = n[0]; }", "[0]", "cannot index")
bad("f(n: int) returns r: int { r = length(n); }", "length(n)", "expects an array")
bad("f(n: int) returns r: int { r = -(-n) + n[0]; }", "[0]", "cannot index")
bad("g(a: int) returns b: int { b = a; } f() returns r: int { r = g(1, 2); }", "g(1, 2)", "expects 1 argument")
bad("g(a: int[]) returns b: int { b = 0; } f() returns r: int { r = g(1); }", "g(1)", "expected int[]")
bad("g() returns a: int { a = 1; } f() returns r: int, s: int { r, s = g(); }", "r, s", "returns 1")
bad("g() returns a: int, b: int { a = 1; b = 2; } f() returns r: int { r = g(); }", "g();", "single value")
bad("f(a: int[], b: int[]) returns r: int { if (a == b) r = 1; }", "==", "must be int")

bad("f() returns r: int { r = 1; } f() returns r: int { r = 2; }", "f()", "redeclaration", 1)
bad("f(a: int, a: int) returns r: int { r = 1; }", "a: int", "redeclaration", 1)
bad("f(a: int) returns r: int uses a { r = 1; }", "a {", "redeclaration")
bad("f(i: int) requires forall (i: int | i > 0) returns r: int { r = 1; }", "i: int |", "redeclaration")
bad("set() returns r: int { r = 1; }", "set()", "reserved")

bad("f(a: int) returns r: int { a = 1; r = a; }", "a = 1", "parameter")
bad("f(a: int[]) returns r: int { a[0] = 1; r = 0; }", "a[0]", "parameter")
bad("f() returns r: int uses a: int[] { a = set(a, 0, 1); r = 0; }", "set(", "not a public")
bad("f(a: int) requires r > 0 returns r: int { r = a; }", "r > 0", "unknown name")
bad("f() returns r: int ensures x > 0 uses x { x = 1; r = x; }", "x > 0", "unknown name")

bad("f() returns r: int uses x { r = 1; }", "x {", "cannot infer")
bad("f(a: int[]) returns r: int uses x { x = 1; x = a; r = x; }", "x = a", "cannot assign")

bad("p(x: int) => x > 0 f() returns r: int { r = p(1); }", "p(1)", "cannot be used as an expression")
bad("g() returns r: int { r = 1; } p() => g()", "g()", "used as a predicate", 1)
bad("f() requires q(1) returns r: int { r = 1; }", "q(1)", "unknown formula")
bad("p(x: int) => x > 0 f() returns r: int { assert p(1, 2); r = 1; }", "p(1, 2)", "expects 1 argument")
bad("f(a: int[]) returns r: int { if (forall (i: int | a[i] > 0)) r = 1; }", "forall", "not allowed in conditions")
bad("p(x: int) => x > 0 f() returns r: int { if (p(1)) r = 1; }", "p(1)", "not allowed in conditions")

bad("f() returns r: int { r = ; }", "; }", "expected")

multi(HEAD + "r = x; r = y; }", [find(HEAD + "r = x; r = y; }", "x;"), find(HEAD + "r = x; r = y; }", "y;")])

src = "f() returns r: int { r = x; } g() returns s: int { s = y; }"
multi(src, [find(src, "x;"), find(src, "y;")])

src = "f(a: int[]) returns r: int { r = a; r = b; }"
multi(src, [find(src, "r = a"), find(src, "b;")])

eq("format_error", format_error("a\nbc", 3, "m"), "2:2: m")
eq("format_error", format_error("abc", 0, "m"), "1:1: m")

print("all tests passed")
