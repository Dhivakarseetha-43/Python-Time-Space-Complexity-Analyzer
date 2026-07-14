

import ast


class CodeParseError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def parse_code(code: str) -> ast.AST:
    
    if not code or not code.strip():
        raise CodeParseError("No code was submitted.")

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise CodeParseError(
            f"Syntax error on line {exc.lineno}: {exc.msg}"
        ) from exc

    return tree
