from hw01.dfa import dfa_from_csv
from hw01.tokenizer import LexError, tokenize

dfa = dfa_from_csv("dfa.csv")
SKIP = {"WS"}


def check(text, expected):
    result = tokenize(dfa, text, skip=SKIP)
    if result != expected:
        print(f"FAIL: {text!r} -> expected {expected}, got {result}")
        exit(1)
    else:
        print(f"SUCCESS: {text!r} -> {result}")


check("", [])
check("   \t\r\n", [])

check("0", [("INT", "0", 0)])
check("00", [("INT", "0", 0), ("INT", "0", 1)])
check("01", [("INT", "0", 0), ("INT", "1", 1)])
check("10", [("INT", "10", 0)])
check("123", [("INT", "123", 0)])

check("_foo", [("IDENT", "_foo", 0)])
check("foo_bar123", [("IDENT", "foo_bar123", 0)])
check("_", [("IDENT", "_", 0)])
check("__init__", [("IDENT", "__init__", 0)])

for kw in [
    "function",
    "returns",
    "uses",
    "while",
    "if",
    "else",
    "assert",
    "assume",
    "invariant",
    "length",
    "true",
    "false",
]:
    check(kw, [("KEYWORD", kw, 0)])
check("ifx", [("IDENT", "ifx", 0)])
check("iffalse", [("IDENT", "iffalse", 0)])

for op in [
    "(",
    ")",
    "[",
    "]",
    "{",
    "}",
    ",",
    ";",
    "+",
    "-",
    "*",
    "/",
    "==",
    "!=",
    "<=",
    ">=",
    "<",
    ">",
    "=",
]:
    check(op, [("OP", op, 0)])

check("// comment until eol", [("COMMENT", "// comment until eol", 0)])
check("//c\n", [("COMMENT", "//c", 0)])
check("//", [("COMMENT", "//", 0)])
check("// a\n// b", [("COMMENT", "// a", 0), ("COMMENT", "// b", 5)])

check(
    "if x == 10 { return x; }",
    [
        ("KEYWORD", "if", 0),
        ("IDENT", "x", 3),
        ("OP", "==", 5),
        ("INT", "10", 8),
        ("OP", "{", 11),
        ("IDENT", "return", 13),
        ("IDENT", "x", 20),
        ("OP", ";", 21),
        ("OP", "}", 23),
    ],
)

check(
    "function foo(a, b) returns c {\n  c = a + b;\n}",
    [
        ("KEYWORD", "function", 0),
        ("IDENT", "foo", 9),
        ("OP", "(", 12),
        ("IDENT", "a", 13),
        ("OP", ",", 14),
        ("IDENT", "b", 16),
        ("OP", ")", 17),
        ("KEYWORD", "returns", 19),
        ("IDENT", "c", 27),
        ("OP", "{", 29),
        ("IDENT", "c", 33),
        ("OP", "=", 35),
        ("IDENT", "a", 37),
        ("OP", "+", 39),
        ("IDENT", "b", 41),
        ("OP", ";", 42),
        ("OP", "}", 44),
    ],
)

check("  10   +   5  ", [("INT", "10", 2), ("OP", "+", 7), ("INT", "5", 11)])
try:
    tokenize(dfa, "хихихи", skip=SKIP)
except LexError:
    pass
else:
    raise AssertionError("expected LexError on non-ascii input")

try:
    tokenize(dfa, "x = 5 # bad", skip=SKIP)
except LexError as e:
    if e.pos != 6:
        raise AssertionError(f"expected LexError at pos 6, got {e.pos}")
else:
    raise AssertionError("expected LexError on '#'")

print("all tests passed")
