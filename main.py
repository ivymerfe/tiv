from parser import parse_regular
from nfa import ast_to_nfa
from dfa import nfa_to_dfa
from minimizer import minimize_dfa

expr = "a(b|c)d*"

ast = parse_regular(expr)
print(ast)
nfa = ast_to_nfa(ast)
print(nfa)
dfa = nfa_to_dfa(nfa, "abcde")
print(dfa)
dfa_min = minimize_dfa(dfa)
print(dfa_min)
