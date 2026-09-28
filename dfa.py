import csv
from dataclasses import dataclass, field

from nfa import NFA


def symbol_matches(symbol, char):
    if isinstance(symbol, str):
        return symbol == char
    in_ranges = any(a <= char <= b for a, b in symbol.ranges)
    in_chars = char in symbol.chars
    result = in_ranges or in_chars
    return not result if symbol.negated else result


def ascii_alphabet() -> set[str]:
    return {chr(i) for i in range(128)}


def _index_nfa(nfa):
    eps_adj = {}
    sym_adj = {}
    for t in nfa.transitions:
        if t.symbol is None:
            eps_adj.setdefault(t.from_state, []).append(t.to_state)
        else:
            sym_adj.setdefault(t.from_state, []).append((t.symbol, t.to_state))
    return eps_adj, sym_adj


def _alphabet_classes(nfa, alphabet):
    labels = []
    seen = set()
    for t in nfa.transitions:
        if t.symbol is None:
            continue
        key = t.symbol if isinstance(t.symbol, str) else id(t.symbol)
        if key in seen:
            continue
        seen.add(key)
        labels.append(t.symbol)

    signature_to_class = {}
    for ch in sorted(alphabet):
        sig = tuple(symbol_matches(label, ch) for label in labels)
        signature_to_class.setdefault(sig, []).append(ch)
    return list(signature_to_class.values())


def eps_closure(eps_adj, states):
    stack = list(states)
    closure = set(states)
    while stack:
        s = stack.pop()
        for to in eps_adj.get(s, ()):
            if to not in closure:
                closure.add(to)
                stack.append(to)
    return frozenset(closure)


def move(sym_adj, states, char):
    result = set()
    for s in states:
        for symbol, to in sym_adj.get(s, ()):
            if symbol_matches(symbol, char):
                result.add(to)
    return result


def _resolve_token(priority, accept_tokens, states):
    best = None
    best_rank = None
    for s in states:
        if s in accept_tokens:
            rank = priority[s]
            if best_rank is None or rank < best_rank:
                best_rank = rank
                best = accept_tokens[s]
    return best


@dataclass
class DFA:
    start_state: int
    accept_states: set[int]
    transitions: dict[tuple[int, str], int] = field(default_factory=dict)
    alphabet: set[str] = field(default_factory=set)
    accept_tokens: dict[int, str] = field(default_factory=dict)
    trap_state: int | None = None

    def __str__(self):
        res = f"DFA(start={self.start_state}, accept={self.accept_states}, trap={self.trap_state})"
        for s, tok in sorted(self.accept_tokens.items()):
            res += f"\n  accept {s} -> {tok}"
        for (s, c), t in sorted(self.transitions.items()):
            if s == self.trap_state or t == self.trap_state:
                continue
            res += f"\n  {s} --({c!r})--> {t}"
        return res


def nfa_to_dfa(nfa: NFA, alphabet: set[str] | None = None) -> DFA:
    if alphabet is None:
        alphabet = ascii_alphabet()

    eps_adj, sym_adj = _index_nfa(nfa)
    classes = _alphabet_classes(nfa, alphabet)
    priority = {s: i for i, s in enumerate(nfa.accept_tokens)}

    start = eps_closure(eps_adj, {nfa.start_state})
    state_ids = {start: 0}
    unprocessed = [start]
    class_transitions = {}

    while unprocessed:
        current = unprocessed.pop()
        current_id = state_ids[current]
        for idx, members in enumerate(classes):
            moved = move(sym_adj, current, members[0])
            if not moved:
                continue
            target = eps_closure(eps_adj, moved)
            if target not in state_ids:
                state_ids[target] = len(state_ids)
                unprocessed.append(target)
            class_transitions[(current_id, idx)] = state_ids[target]

    accept_states = set()
    accept_tokens = {}
    for nfa_states, sid in state_ids.items():
        if nfa_states & nfa.accept_states:
            accept_states.add(sid)
            token = _resolve_token(priority, nfa.accept_tokens, nfa_states)
            if token is not None:
                accept_tokens[sid] = token

    trap = len(state_ids)
    transitions = {}
    for sid in range(trap):
        for idx, members in enumerate(classes):
            target = class_transitions.get((sid, idx), trap)
            for ch in members:
                transitions[(sid, ch)] = target
    for ch in alphabet:
        transitions[(trap, ch)] = trap

    return DFA(
        start_state=0,
        accept_states=accept_states,
        transitions=transitions,
        alphabet=alphabet,
        accept_tokens=accept_tokens,
        trap_state=trap,
    )


def dfa_to_csv(dfa: DFA, path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["type", "state", "char", "target"])
        writer.writerow(["start", dfa.start_state, "", ""])
        if dfa.trap_state is not None:
            writer.writerow(["trap", dfa.trap_state, "", ""])
        for s in sorted(dfa.accept_states):
            writer.writerow(["accept", s, dfa.accept_tokens.get(s, ""), ""])
        for (s, c), t in sorted(dfa.transitions.items()):
            writer.writerow(["trans", s, c, t])


def dfa_from_csv(path: str) -> DFA:
    start_state = None
    trap_state = None
    accept_states = set()
    accept_tokens = {}
    transitions = {}
    alphabet = set()

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            kind, state, char, target = row
            if kind == "start":
                start_state = int(state)
            elif kind == "trap":
                trap_state = int(state)
            elif kind == "accept":
                s = int(state)
                accept_states.add(s)
                if char:
                    accept_tokens[s] = char
            elif kind == "trans":
                transitions[(int(state), char)] = int(target)
                alphabet.add(char)

    return DFA(
        start_state=start_state,
        accept_states=accept_states,
        transitions=transitions,
        alphabet=alphabet,
        accept_tokens=accept_tokens,
        trap_state=trap_state,
    )
