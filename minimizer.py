from dfa import DFA


def reachable_states(dfa):
    seen = {dfa.start_state}
    stack = [dfa.start_state]
    adj = {}
    for (s, c), t in dfa.transitions.items():
        adj.setdefault(s, []).append(t)
    while stack:
        s = stack.pop()
        for t in adj.get(s, ()):
            if t not in seen:
                seen.add(t)
                stack.append(t)
    return seen


def minimize_dfa(dfa: DFA) -> DFA:
    alphabet = sorted(dfa.alphabet)
    states = reachable_states(dfa)
    dead = dfa.trap_state if dfa.trap_state is not None else max(states) + 1
    states.add(dead)

    trans = {}
    for s in states:
        for c in alphabet:
            trans[(s, c)] = dfa.transitions.get((s, c), dead)

    reverse = {}
    for (s, c), t in trans.items():
        reverse.setdefault((t, c), []).append(s)

    accept_states = dfa.accept_states & states

    groups = {}
    for s in states:
        key = ("accept", dfa.accept_tokens.get(s)) if s in accept_states else ("other",)
        groups.setdefault(key, set()).add(s)

    blocks = {}
    block_of = {}
    for i, members in enumerate(groups.values()):
        blocks[i] = members
        for s in members:
            block_of[s] = i
    next_id = len(blocks)

    worklist = set(blocks)

    while worklist:
        a_id = worklist.pop()
        splitter = list(blocks[a_id])
        for c in alphabet:
            touched = {}
            for t in splitter:
                for s in reverse.get((t, c), ()):
                    touched.setdefault(block_of[s], set()).add(s)

            for b_id, inter in touched.items():
                block = blocks[b_id]
                if len(inter) == len(block):
                    continue
                rest = block - inter
                if len(inter) <= len(rest):
                    small, large = inter, rest
                else:
                    small, large = rest, inter

                blocks[b_id] = large
                new_id = next_id
                next_id += 1
                blocks[new_id] = small
                for s in small:
                    block_of[s] = new_id

                if b_id in worklist:
                    worklist.add(new_id)
                else:
                    worklist.add(new_id)

    dead_block = block_of[dead]
    kept = [b for b in blocks if b != dead_block]
    new_id_of = {b: i for i, b in enumerate(kept)}
    trap = len(kept)

    new_start = new_id_of[block_of[dfa.start_state]]

    new_accept = set()
    new_accept_tokens = {}
    for b in kept:
        hit = blocks[b] & accept_states
        if hit:
            nb = new_id_of[b]
            new_accept.add(nb)
            token = dfa.accept_tokens.get(next(iter(hit)))
            if token is not None:
                new_accept_tokens[nb] = token

    new_transitions = {}
    for b in kept:
        rep = next(iter(blocks[b]))
        nb = new_id_of[b]
        for c in alphabet:
            tb = block_of[trans[(rep, c)]]
            new_transitions[(nb, c)] = trap if tb == dead_block else new_id_of[tb]
    for c in alphabet:
        new_transitions[(trap, c)] = trap

    return DFA(
        start_state=new_start,
        accept_states=new_accept,
        transitions=new_transitions,
        alphabet=set(alphabet),
        accept_tokens=new_accept_tokens,
        trap_state=trap,
    )
