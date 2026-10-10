from .dfa import ascii_alphabet, dfa_to_csv, nfa_to_dfa
from .minimizer import minimize_dfa, reachable_states
from .nfa import combine_nfas
from .parser import parse_regular

tokens = [
    (
        "KEYWORD",
        "function|returns|requires|ensures|uses|while|if|else|assert|assume|invariant|length|true|false|int|not|and|or|forall|exists",
    ),
    ("IDENT", "[A-Za-z_][A-Za-z0-9_]*"),
    ("INT", "0|[1-9][0-9]*"),
    ("WS", "[ \\t\\r\\n]+"),
    ("COMMENT", "//[^\\n]*"),
    ("OP", "\\(|\\)|\\[|\\]|\\{|\\}|,|;|\\+|-|\\*|/|==|!=|<=|>=|<|>|=|:|->|=>|\\|"),
]

print("Tokens:")
for k, v in tokens:
    print(f"  {k} <- {v}")

named_asts = [(name, parse_regular(pattern)) for name, pattern in tokens]
nfa = combine_nfas(named_asts)
dfa = nfa_to_dfa(nfa, ascii_alphabet())

print()

print(f"DFA state count before min: {len(reachable_states(dfa))}")
print(f"DFA transition count before min: {len(dfa.transitions)}")

min_dfa = minimize_dfa(dfa)

print(f"DFA state count after min: {len(reachable_states(min_dfa))}")
print(f"DFA transition count after min: {len(min_dfa.transitions)}")
print(f"Trap state: {min_dfa.trap_state}")

dfa_to_csv(min_dfa, "dfa.csv")
