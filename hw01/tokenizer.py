from .dfa import DFA


class LexError(Exception):
    def __init__(self, pos, char):
        super().__init__(f"unexpected character {char!r} at position {pos}")
        self.pos = pos
        self.char = char


def tokenize(dfa: DFA, text: str, skip: set[str]) -> list[tuple[str, str, int]]:
    tokens = []
    pos = 0
    n = len(text)

    while pos < n:
        state = dfa.start_state
        last_accept_pos = None
        last_accept_token = None
        i = pos

        while i < n:
            c = text[i]
            next_state = dfa.transitions.get((state, c), dfa.trap_state)
            if next_state == dfa.trap_state:
                break
            state = next_state
            i += 1
            if state in dfa.accept_states:
                last_accept_pos = i
                last_accept_token = dfa.accept_tokens.get(state)

        if last_accept_pos is None:
            raise LexError(pos, text[pos])

        if last_accept_token not in skip:
            tokens.append((last_accept_token, text[pos:last_accept_pos], pos))
        pos = last_accept_pos

    return tokens
