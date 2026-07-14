"""
parser.py
---------
Thin wrapper around Python's built-in `ast` module.

Responsibility: turn raw source code (a string) into an AST we can
traverse, and turn syntax errors into a clean, catchable exception.
No regex is used anywhere in this project -- all detection is done by
walking the Abstract Syntax Tree, which understands Python's real
grammar instead of guessing from text patterns.
"""

import ast


class CodeParseError(Exception):
    """Raised when the submitted code cannot be parsed into an AST."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def parse_code(code: str) -> ast.AST:
    """
    Parse Python source code into an AST.

    Args:
        code: raw Python source as a string.

    Returns:
        The root ast.Module node.

    Raises:
        CodeParseError: if the code has a syntax error or is empty.
    """
    if not code or not code.strip():
        raise CodeParseError("No code was submitted.")

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise CodeParseError(
            f"Syntax error on line {exc.lineno}: {exc.msg}"
        ) from exc

    return tree
