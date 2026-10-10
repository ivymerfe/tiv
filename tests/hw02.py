import json

from hw01.dfa import dfa_from_csv
from hw02.parser import parse

dfa = dfa_from_csv("dfa.csv")
HEAD = "f() returns r: int { "


def fail(src, expected, got):
    print(f"FAIL: {src!r} -> expected {expected}, got {got}")
    exit(1)


def node(kind, pos, **fields):
    return {"kind": kind, "pos": pos, **fields}


def ok(src):
    ast, errs = parse(src, dfa)
    if errs:
        fail(src, "no errors", errs)
    json.dumps(ast.to_dict())
    print(f"SUCCESS: {src!r} -> ok")


def bad(src, pos):
    ast, errs = parse(src, dfa)
    if not errs or errs[0][0] != pos:
        fail(src, f"first error at {pos}", errs)
    print(f"SUCCESS: {src!r} -> {errs[0]}")


def multi(src, positions):
    ast, errs = parse(src, dfa)
    got = [p for p, _ in errs]
    if got != positions:
        fail(src, f"errors at {positions}", errs)
    print(f"SUCCESS: {src!r} -> {errs}")


def snap_module(src, expected):
    ast, errs = parse(src, dfa)
    if errs:
        fail(src, "no errors", errs)
    got = ast.to_dict()
    if got != expected:
        fail(src, expected, got)
    print(f"SUCCESS: {src!r} -> ast matches")


def snap(stmt, expected):
    src = HEAD + stmt + " }"
    ast, errs = parse(src, dfa)
    if errs:
        fail(src, "no errors", errs)
    got = ast.to_dict()["items"][0]["body"]["body"][0]
    if got != expected:
        fail(src, expected, got)
    print(f"SUCCESS: {stmt!r} -> ast matches")


for src in [
    "f() returns r: int { r = 1; }",
    "f() returns r: int { }",
    "f() returns r: int r = 1;",
    "// c\nf() returns r: int r = 1;",
    "f() returns r: int { // c\n r = 1; // d\n }",
    "f(a: int, b: int) returns x: int, y: int { x = a; y = b; }",
    "f(n: int) requires n > 0 returns r: int ensures r >= n { r = n; }",
    "f() returns r: int uses i: int, a: int[], j { i = 0; }",
    "f(a: int[], n: int) requires n > 0 returns r: int ensures r >= 0 uses i { i = 0; while (i < n) invariant i >= 0 { a[i] = a[i] + 1; i = i + 1; } r = i; }",
    "f(a: int[]) requires forall (i: int | a[i] >= 0) returns r: int { if (r > 0) r = 1; else { r = 2; } assert r >= 0; assume not r == 3; }",
    "f(a: int[]) requires forall (i: int | i >= 0 -> a[i] >= 0) returns r: int { r = 0; }",
    "f(a: int) returns r: int { if (a > 0) if (a > 1) r = 2; else r = 1; else r = 0; }",
    "f(n: int) returns r: int { while (n > 0) r = r + 1; }",
    "f(n: int) returns r: int { r = f(n - 1); }",
    "f() returns a: int, b: int { a, b = g(); }",
    "f(a: int[]) returns r: int { r = length(a); }",
    "f(a: int[]) returns r: int { r = a[a[0] + 1] * 2; }",
    "f() returns r: int { r = -(-1); }",
    "f() returns r: int { r = 10 / 2 / 5 - 1 * 3; }",
    "f(a: int[]) returns r: int { a[1][2] = 5; }",
    "f() returns r: int { { { r = 1; } } }",
    "p() => true",
    "p() => false or true",
    "p(x: int) => x > 0 and (x < 10 or not x == 5)",
    "p(x: int) => (x + 1) * 2 > 3",
    "p(x: int) => not (x > 1) -> x <= 1",
    "p(a: int[], n: int) => exists (i: int | a[i] == n)",
    "q(x: int) => p(x) and not p(x + 1)",
    "p(x: int) => x > 0 f() returns r: int { r = 1; }",
    "g(a: int[]) returns r: int { a[1][2] = 5; r, q = h(length(a), -3 * (2 + 1)); }",
    "f(a: int[][]) returns r: int { r = a[0][1]; a[1][2] = r; }",
    "f() returns r: int uses m: int[][], v: int[] { r = 0; }",
]:
    ok(src)

snap_module(
    "f() returns r: int { r = 1; }",
    node(
        "Module",
        0,
        items=[
            node(
                "Function",
                0,
                name="f",
                params=[],
                requires=None,
                returns=[node("VarDef", 12, name="r", type="int")],
                ensures=None,
                locals=[],
                body=node(
                    "Block",
                    19,
                    body=[
                        node(
                            "Assign",
                            21,
                            targets=["r"],
                            value=node("Int", 25, value=1),
                        )
                    ],
                ),
            )
        ],
    ),
)

snap_module(
    "p(x: int) => x > 0",
    node(
        "Module",
        0,
        items=[
            node(
                "Formula",
                0,
                name="p",
                params=[node("VarDef", 2, name="x", type="int")],
                body=node(
                    "Cmp",
                    15,
                    op=">",
                    left=node("Ref", 13, name="x"),
                    right=node("Int", 17, value=0),
                ),
            )
        ],
    ),
)

snap(
    "a[0] = 5;",
    node(
        "Assign",
        21,
        targets=["a"],
        value=node(
            "Call",
            21,
            name="set",
            args=[
                node("Ref", 21, name="a"),
                node("Int", 23, value=0),
                node("Int", 28, value=5),
            ],
        ),
    ),
)

snap(
    "a[1][2] = 5;",
    node(
        "Seq",
        21,
        body=[
            node(
                "Assign",
                21,
                targets=["_t1"],
                value=node(
                    "Index",
                    21,
                    array=node("Ref", 21, name="a"),
                    index=node("Int", 23, value=1),
                ),
            ),
            node(
                "Assign",
                21,
                targets=["_t1"],
                value=node(
                    "Call",
                    21,
                    name="set",
                    args=[
                        node("Ref", 21, name="_t1"),
                        node("Int", 26, value=2),
                        node("Int", 31, value=5),
                    ],
                ),
            ),
            node(
                "Assign",
                21,
                targets=["a"],
                value=node(
                    "Call",
                    21,
                    name="set",
                    args=[
                        node("Ref", 21, name="a"),
                        node("Int", 23, value=1),
                        node("Ref", 21, name="_t1"),
                    ],
                ),
            ),
        ],
    ),
)

snap(
    "r = 1 + 2 * 3;",
    node(
        "Assign",
        21,
        targets=["r"],
        value=node(
            "Bin",
            27,
            op="+",
            left=node("Int", 25, value=1),
            right=node(
                "Bin",
                31,
                op="*",
                left=node("Int", 29, value=2),
                right=node("Int", 33, value=3),
            ),
        ),
    ),
)

snap(
    "r = 1 - 2 - 3;",
    node(
        "Assign",
        21,
        targets=["r"],
        value=node(
            "Bin",
            31,
            op="-",
            left=node(
                "Bin",
                27,
                op="-",
                left=node("Int", 25, value=1),
                right=node("Int", 29, value=2),
            ),
            right=node("Int", 33, value=3),
        ),
    ),
)

snap(
    "r = -a[1];",
    node(
        "Assign",
        21,
        targets=["r"],
        value=node(
            "Neg",
            25,
            operand=node(
                "Index",
                27,
                array=node("Ref", 26, name="a"),
                index=node("Int", 28, value=1),
            ),
        ),
    ),
)

snap(
    "r, q = h(1);",
    node(
        "Assign",
        21,
        targets=["r", "q"],
        value=node("Call", 28, name="h", args=[node("Int", 30, value=1)]),
    ),
)

snap(
    "assert true -> false -> true;",
    node(
        "Assert",
        21,
        pred=node(
            "Implies",
            33,
            left=node("Bool", 28, value=True),
            right=node(
                "Implies",
                42,
                left=node("Bool", 36, value=False),
                right=node("Bool", 45, value=True),
            ),
        ),
    ),
)

snap(
    "assert true or false and true;",
    node(
        "Assert",
        21,
        pred=node(
            "Or",
            33,
            left=node("Bool", 28, value=True),
            right=node(
                "And",
                42,
                left=node("Bool", 36, value=False),
                right=node("Bool", 46, value=True),
            ),
        ),
    ),
)

snap(
    "if (r > 0) r = 1; else r = 2;",
    node(
        "If",
        21,
        cond=node(
            "Cmp",
            27,
            op=">",
            left=node("Ref", 25, name="r"),
            right=node("Int", 29, value=0),
        ),
        then=node(
            "Assign", 32, targets=["r"], value=node("Int", 36, value=1)
        ),
        else_=node(
            "Assign", 44, targets=["r"], value=node("Int", 48, value=2)
        ),
    ),
)

snap(
    "while (r < 3) invariant r >= 0 r = r + 1;",
    node(
        "While",
        21,
        cond=node(
            "Cmp",
            30,
            op="<",
            left=node("Ref", 28, name="r"),
            right=node("Int", 32, value=3),
        ),
        invariant=node(
            "Cmp",
            47,
            op=">=",
            left=node("Ref", 45, name="r"),
            right=node("Int", 50, value=0),
        ),
        body=node(
            "Assign",
            52,
            targets=["r"],
            value=node(
                "Bin",
                58,
                op="+",
                left=node("Ref", 56, name="r"),
                right=node("Int", 60, value=1),
            ),
        ),
    ),
)

for src, pos in [
    ("", 0),
    ("   \n", 0),
    ("// just a comment", 0),
    ("f(a: int returns r: int { r = 1; }", 9),
    ("f(a) returns r: int { r = 1; }", 3),
    ("f(a: int,) returns r: int { r = 1; }", 9),
    ("f() r: int { r = 1; }", 4),
    ("f() returns if: int { }", 12),
    ("f() returns r: int { r = 1; ", 28),
    ("f() returns r: int { if (r > 0) { r = 1; }", 42),
    ("f() returns r: int { { { r = 1; }", 33),
    ("f() returns r: int { r = ; }", 25),
    ("f() returns r: int { r = 1 }", 27),
    ("f() returns r: int { r = 1 = 2; }", 27),
    ("f() returns r: int { r = (1 + 2; }", 31),
    ("f() returns r: int { r = g(1, 2; }", 31),
    ("f() returns r: int { r = 1 +* 2; }", 28),
    ("f() returns r: int { r = 1 ** 2; }", 28),
    ("f() returns r: int { r = 1 % 2; }", 27),
    ("f() returns r: int { r = 1 # 2; }", 27),
    ("f() returns r: int { r = 1 @ 2; }", 27),
    ("f() returns r: int { r, q = 1; }", 21),
    ("f() returns r: int { if (r > ) r = 1; }", 29),
    ("f() returns r: int { if (r > 0 r = 1; }", 31),
    ("f() returns r: int { if (r = 1) r = 2; }", 27),
    ("f() returns r: int { if (r > 0) }", 32),
    ("f() returns r: int { else r = 1; }", 21),
    ("f() returns r: int { while r < 3 r = 1; }", 27),
    ("f() returns r: int { assert r > 0 }", 34),
    ("f() returns r: int { ) ) ) }", 21),
    ("f() returns r: int { r = 1; } }", 30),
    ("f() returns r: int r = 1; x", 27),
    ("p(x: int) =>", 12),
    ("p(x: int) => forall (i | x > 0)", 23),
    ("f(a: int[]]) returns r: int { r = 1; }", 10),
    ("f(a: int[ []) returns r: int { r = 1; }", 10),
]:
    bad(src, pos)

multi("f() returns r: int { r = ; r = ; r = ; }", [25, 31, 37])
multi("f() returns r: int { r = ; } g() returns s: int { s = 1; }", [25])
multi("f( returns r: int { r = 1; } g() returns s: int { s = 1; }", [3])
multi("f() returns r: int { r = ; } g( returns s: int { s = 1; }", [25, 32])
multi("}}}}", [0, 1, 2, 3])

print("all tests passed")
