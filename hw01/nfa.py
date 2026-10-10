from dataclasses import dataclass, field

from .parser import Alt, CharClass, Concat, Literal, Plus, RegNode, Star


@dataclass
class Transition:
    from_state: int
    to_state: int
    symbol: str | CharClass | None = None


@dataclass
class NFA:
    start_state: int
    accept_states: set[int]
    transitions: list[Transition] = field(default_factory=list)
    accept_tokens: dict[int, str] = field(default_factory=dict)

    def __str__(self):
        res = f"NFA(start={self.start_state}, accept={self.accept_states})"
        for t in self.transitions:
            if t.symbol is None:
                sym = "ε"
            elif isinstance(t.symbol, CharClass):
                sym = str(t.symbol).replace("\n", "\\n")
            else:
                sym = repr(t.symbol)
            res += f"\n  {t.from_state} --({sym})--> {t.to_state}"
        return res


class NFABuilder:
    def __init__(self):
        self.state_counter = 0
        self.transitions: list[Transition] = []

    def new_state(self) -> int:
        s = self.state_counter
        self.state_counter += 1
        return s

    def build(self, node: RegNode) -> NFA:
        start, accept = self._build_node(node)
        return NFA(
            start_state=start,
            accept_states={accept},
            transitions=self.transitions,
        )

    def _build_node(self, node: RegNode) -> tuple[int, int]:
        match node:
            case Literal(char):
                start = self.new_state()
                accept = self.new_state()
                self.transitions.append(Transition(start, accept, char))
                return start, accept

            case CharClass():
                start = self.new_state()
                accept = self.new_state()
                self.transitions.append(Transition(start, accept, node))
                return start, accept

            case Concat(left, right):
                left_start, left_accept = self._build_node(left)
                right_start, right_accept = self._build_node(right)
                self.transitions.append(Transition(left_accept, right_start, None))
                return left_start, right_accept

            case Alt(left, right):
                start = self.new_state()
                accept = self.new_state()
                l_start, l_accept = self._build_node(left)
                r_start, r_accept = self._build_node(right)

                self.transitions.append(Transition(start, l_start, None))
                self.transitions.append(Transition(start, r_start, None))
                self.transitions.append(Transition(l_accept, accept, None))
                self.transitions.append(Transition(r_accept, accept, None))
                return start, accept

            case Star(sub):
                start = self.new_state()
                accept = self.new_state()
                sub_start, sub_accept = self._build_node(sub)

                self.transitions.append(Transition(start, sub_start, None))
                self.transitions.append(Transition(start, accept, None))
                self.transitions.append(Transition(sub_accept, sub_start, None))
                self.transitions.append(Transition(sub_accept, accept, None))
                return start, accept

            case Plus(sub):
                start = self.new_state()
                accept = self.new_state()
                sub_start, sub_accept = self._build_node(sub)

                self.transitions.append(Transition(start, sub_start, None))
                self.transitions.append(Transition(sub_accept, sub_start, None))
                self.transitions.append(Transition(sub_accept, accept, None))
                return start, accept

            case _:
                raise TypeError(f"Unknown node type: {type(node)}")


def ast_to_nfa(node: RegNode) -> NFA:
    builder = NFABuilder()
    return builder.build(node)


def combine_nfas(token_patterns: list[tuple[str, RegNode]]) -> NFA:
    builder = NFABuilder()
    start = builder.new_state()
    accept_states = set()
    accept_tokens = {}

    for name, node in token_patterns:
        sub_start, sub_accept = builder._build_node(node)
        builder.transitions.append(Transition(start, sub_start, None))
        accept_states.add(sub_accept)
        accept_tokens[sub_accept] = name

    return NFA(
        start_state=start,
        accept_states=accept_states,
        transitions=builder.transitions,
        accept_tokens=accept_tokens,
    )
