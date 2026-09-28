from dataclasses import dataclass


@dataclass
class Literal:
    char: str

    def __str__(self, indent=0):
        return f"{'  ' * indent}Literal({self.char!s})"


@dataclass
class CharClass:
    ranges: list[tuple[str, str]]
    chars: list[str]
    negated: bool = False

    def __str__(self, indent=0):
        prefix = "!" if self.negated else ""
        return f"{'  ' * indent}CharClass({prefix}ranges={self.ranges}, chars={self.chars})"


@dataclass
class Concat:
    left: "RegNode"
    right: "RegNode"

    def __str__(self, indent=0):
        res = f"{'  ' * indent}Concat(\n"
        res += self.left.__str__(indent + 1) + ",\n"
        res += self.right.__str__(indent + 1) + "\n"
        res += f"{'  ' * indent})"
        return res


@dataclass
class Alt:
    left: "RegNode"
    right: "RegNode"

    def __str__(self, indent=0):
        res = f"{'  ' * indent}Alt(\n"
        res += self.left.__str__(indent + 1) + ",\n"
        res += self.right.__str__(indent + 1) + "\n"
        res += f"{'  ' * indent})"
        return res


@dataclass
class Star:
    node: "RegNode"

    def __str__(self, indent=0):
        res = f"{'  ' * indent}Star(\n"
        res += self.node.__str__(indent + 1) + "\n"
        res += f"{'  ' * indent})"
        return res


@dataclass
class Plus:
    node: "RegNode"

    def __str__(self, indent=0):
        res = f"{'  ' * indent}Plus(\n"
        res += self.node.__str__(indent + 1) + "\n"
        res += f"{'  ' * indent})"
        return res


type RegNode = Literal | CharClass | Concat | Alt | Star | Plus


class RegexParser:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    def peek(self) -> str | None:
        if self.pos < len(self.text):
            return self.text[self.pos]
        return None

    def consume(self) -> str:
        ch = self.peek()
        self.pos += 1
        return ch

    def parse(self) -> RegNode:
        node = self.parse_alt()
        if self.pos < len(self.text):
            raise ValueError(f"Unexpected character at pos {self.pos}: {self.peek()}")
        return node

    def parse_alt(self) -> RegNode:
        left = self.parse_concat()
        while self.peek() == "|":
            self.consume()
            right = self.parse_concat()
            left = Alt(left, right)
        return left

    def parse_concat(self) -> RegNode:
        nodes = []
        while True:
            ch = self.peek()
            if ch is None or ch == ")" or ch == "|":
                break
            nodes.append(self.parse_postfix())

        if not nodes:
            return Literal("")

        result = nodes[0]
        for n in nodes[1:]:
            result = Concat(result, n)
        return result

    def parse_postfix(self) -> RegNode:
        node = self.parse_atom()
        while True:
            ch = self.peek()
            if ch == "*":
                self.consume()
                node = Star(node)
            elif ch == "+":
                self.consume()
                node = Plus(node)
            else:
                break
        return node

    def parse_atom(self) -> RegNode:
        ch = self.peek()
        if ch is None:
            raise ValueError("Unexpected end of expression")

        if ch == "(":
            self.consume()
            node = self.parse_alt()
            if self.peek() != ")":
                raise ValueError("Expected ')'")
            self.consume()
            return node

        elif ch == "[":
            return self.parse_char_class()

        elif ch == "\\":
            self.consume()
            escaped = self.consume()
            escape_map = {"n": "\n", "t": "\t", "r": "\r", " ": " "}
            val = escape_map.get(escaped, escaped)
            return Literal(val)

        else:
            self.consume()
            return Literal(ch)

    def parse_char_class(self) -> CharClass:
        self.consume()  # '['
        negated = False
        if self.peek() == "^":
            negated = True
            self.consume()

        ranges = []
        chars = []

        while self.peek() != "]" and self.peek() is not None:
            start_ch = self.consume()
            if start_ch == "\\":
                escaped = self.consume()
                escape_map = {"n": "\n", "t": "\t", "r": "\r"}
                start_ch = escape_map.get(escaped, escaped)

            if self.peek() == "-":
                self.consume()  # '-'
                if self.peek() == "]":
                    chars.append(start_ch)
                    chars.append("-")
                    break
                end_ch = self.consume()
                if end_ch == "\\":
                    escaped = self.consume()
                    escape_map = {"n": "\n", "t": "\t", "r": "\r"}
                    end_ch = escape_map.get(escaped, escaped)
                ranges.append((start_ch, end_ch))
            else:
                chars.append(start_ch)

        if self.peek() == "]":
            self.consume()
        else:
            raise ValueError("Unterminated character class")

        return CharClass(ranges=ranges, chars=chars, negated=negated)


def parse_regular(reg: str) -> RegNode:
    parser = RegexParser(reg)
    return parser.parse()
