"""
analyzer.py
-----------
Core static-analysis logic.

Everything here works by walking the AST produced by `parser.py` --
never by scanning the raw text or using regular expressions.

The analyzer looks for a handful of well-known "interview code" shapes:

  * for / while loops, and how deeply they nest
  * a while-loop that halves/doubles a variable each iteration
    (binary-search / log-time pattern), e.g. `while n > 1: n //= 2`
  * sorted() / list.sort() calls (O(n log n))
  * list / dict / set literals and comprehensions (O(n) space)
  * recursive function definitions, and whether a function calls
    itself once (linear recursion) or more than once (branching /
    exponential recursion, e.g. naive Fibonacci)

It then combines those signals into a single Big-O estimate for time
and space. This is deliberately heuristic -- the goal is "usually
right for textbook interview snippets", not a provably-correct
static analyzer.
"""

import ast
from dataclasses import dataclass, field
from typing import List, Dict, Set


@dataclass
class Findings:
    """Container for everything the visitors discover in the code."""

    max_loop_depth: int = 0
    loop_lines: List[int] = field(default_factory=list)

    log_pattern_lines: List[int] = field(default_factory=list)   # while n //= 2 style
    sort_lines: List[int] = field(default_factory=list)          # sorted() / .sort()
    space_lines: List[int] = field(default_factory=list)         # list/dict/set creation

    recursion_detected: bool = False
    recursive_lines: List[int] = field(default_factory=list)
    max_recursive_calls_in_function: int = 0  # highest #self-calls seen in one function


# --------------------------------------------------------------------------
# Loop + data-structure + sort visitor
# --------------------------------------------------------------------------
class LoopAndStructureVisitor(ast.NodeVisitor):
    """
    Walks the tree tracking loop nesting depth and flagging
    sorts / list / dict / set construction along the way.
    """

    def __init__(self, findings: Findings):
        self.findings = findings
        self._current_depth = 0

    # ---- loops -----------------------------------------------------------
    def visit_For(self, node: ast.For):
        self._enter_loop(node)
        self.generic_visit(node)
        self._exit_loop()

    def visit_While(self, node: ast.While):
        if self._is_log_pattern(node):
            # A halving/doubling while-loop is treated as O(log n) and is
            # NOT counted toward normal nesting depth (it doesn't scale
            # multiplicatively the way a linear loop does).
            self.findings.log_pattern_lines.append(node.lineno)
            self.generic_visit(node)
        else:
            self._enter_loop(node)
            self.generic_visit(node)
            self._exit_loop()

    def _enter_loop(self, node):
        self._current_depth += 1
        self.findings.max_loop_depth = max(
            self.findings.max_loop_depth, self._current_depth
        )
        self.findings.loop_lines.append(node.lineno)

    def _exit_loop(self):
        self._current_depth -= 1

    @staticmethod
    def _is_log_pattern(node: ast.While) -> bool:
        """
        Detect the classic 'shrink by a constant factor each iteration'
        loop, e.g.:
            while n > 1:
                n //= 2
            while i < n:
                i *= 2
        We look for an AugAssign using //, /, or * directly inside the
        while loop's own body (not inside a nested loop/function).
        """
        for stmt in node.body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.AugAssign) and isinstance(
                    sub.op, (ast.FloorDiv, ast.Div, ast.Mult)
                ):
                    return True
        return False

    # ---- sorting -----------------------------------------------------------
    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "sorted":
            self.findings.sort_lines.append(node.lineno)
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "sort":
            self.findings.sort_lines.append(node.lineno)
        self.generic_visit(node)

    # ---- data structures (space) -------------------------------------------
    def visit_List(self, node: ast.List):
        self.findings.space_lines.append(node.lineno)
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict):
        self.findings.space_lines.append(node.lineno)
        self.generic_visit(node)

    def visit_Set(self, node: ast.Set):
        self.findings.space_lines.append(node.lineno)
        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp):
        # A comprehension both allocates O(n) space AND performs an
        # implicit O(n) iteration, so we record it as a loop too
        # (at the current nesting depth) in addition to a space hit.
        self.findings.space_lines.append(node.lineno)
        self._enter_loop(node)
        self.generic_visit(node)
        self._exit_loop()

    def visit_DictComp(self, node: ast.DictComp):
        self.findings.space_lines.append(node.lineno)
        self._enter_loop(node)
        self.generic_visit(node)
        self._exit_loop()

    def visit_SetComp(self, node: ast.SetComp):
        self.findings.space_lines.append(node.lineno)
        self._enter_loop(node)
        self.generic_visit(node)
        self._exit_loop()


# --------------------------------------------------------------------------
# Recursion visitor
# --------------------------------------------------------------------------
class RecursionVisitor(ast.NodeVisitor):
    """
    For every function definition, counts how many times the function
    calls itself within its own body. This lets us distinguish:

      * 0 self-calls  -> not recursive
      * 1 self-call   -> linear recursion, e.g. factorial(n-1)   -> O(n)
      * 2+ self-calls -> branching recursion, e.g. fib(n-1)+fib(n-2) -> O(2^n)

    We only count calls that appear in the function's own body, and we
    stop descending into any *nested* function definition with a
    different name so an inner helper's calls aren't misattributed.
    """

    def __init__(self, findings: Findings):
        self.findings = findings

    def visit_FunctionDef(self, node: ast.FunctionDef):
        call_count, call_lines = self._count_self_calls(node.name, node.body)
        if call_count >= 1:
            self.findings.recursion_detected = True
            self.findings.recursive_lines.extend(call_lines)
            self.findings.max_recursive_calls_in_function = max(
                self.findings.max_recursive_calls_in_function, call_count
            )
        # Still visit the body so nested function defs are analyzed too.
        self.generic_visit(node)

    # Async defs behave the same way for this MVP's purposes.
    visit_AsyncFunctionDef = visit_FunctionDef

    def _count_self_calls(self, func_name: str, body):
        count = 0
        lines: List[int] = []

        class _InnerCallCounter(ast.NodeVisitor):
            def visit_Call(inner_self, call_node: ast.Call):
                nonlocal count
                if isinstance(call_node.func, ast.Name) and call_node.func.id == func_name:
                    count += 1
                    lines.append(call_node.lineno)
                inner_self.generic_visit(call_node)

            def visit_FunctionDef(inner_self, nested_node: ast.FunctionDef):
                # Don't descend into a differently-named nested function;
                # its calls belong to itself, not to `func_name`.
                if nested_node.name == func_name:
                    inner_self.generic_visit(nested_node)
                # else: skip (do not generic_visit) to avoid double counting
                # when RecursionVisitor.visit_FunctionDef reaches it separately.

        counter = _InnerCallCounter()
        for stmt in body:
            counter.visit(stmt)

        return count, lines


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def analyze(tree: ast.AST):
    """
    Run all visitors over the parsed tree and combine their findings
    into a final time/space complexity estimate.

    Returns a dict matching the AnalyzeResponse model.
    """
    findings = Findings()

    LoopAndStructureVisitor(findings).visit(tree)
    RecursionVisitor(findings).visit(tree)

    time_complexity, time_notes = _estimate_time_complexity(findings)
    space_complexity, space_notes = _estimate_space_complexity(findings)

    detected_lines: Set[int] = set()
    detected_lines.update(findings.loop_lines)
    detected_lines.update(findings.log_pattern_lines)
    detected_lines.update(findings.sort_lines)
    detected_lines.update(findings.space_lines)
    detected_lines.update(findings.recursive_lines)

    return {
        "timeComplexity": time_complexity,
        "spaceComplexity": space_complexity,
        "detectedLines": sorted(detected_lines),
        "loopDepth": findings.max_loop_depth,
        "recursionDetected": findings.recursion_detected,
        "explanation": time_notes + space_notes,
    }


def _estimate_time_complexity(f: Findings):
    """
    Priority order (highest complexity signal wins), matching the
    rules given in the spec:

      1. Branching recursion (2+ self-calls)   -> O(2^n)
      2. Linear recursion (1 self-call)        -> O(n)
      3. Triple-nested loops                   -> O(n^3)
      4. Double-nested loops                   -> O(n^2)
      5. Single loop                           -> O(n)
      6. sorted()/.sort() with no loops         -> O(n log n)
      7. Halving/doubling while-loop only       -> O(log n)
      8. Nothing detected                      -> O(1)

    Note: sorting *combined* with an outer loop containing the sort
    call would realistically be O(n^2 log n) etc., but for MVP
    purposes we report the dominant loop-nesting term and mention the
    sort in the notes, since interview snippets rarely stack these.
    """
    notes = []

    if f.recursion_detected:
        if f.max_recursive_calls_in_function >= 2:
            notes.append(
                "Detected a function that calls itself more than once per call "
                "(branching recursion, e.g. naive Fibonacci) -> O(2^n) time."
            )
            return "O(2^n)", notes
        else:
            notes.append(
                "Detected a function that calls itself once per call "
                "(linear recursion, e.g. factorial) -> O(n) time."
            )
            return "O(n)", notes

    if f.max_loop_depth >= 3:
        notes.append(f"Detected {f.max_loop_depth} nested loops -> O(n^3) or higher time.")
        return "O(n^3)", notes

    if f.max_loop_depth == 2:
        notes.append("Detected 2 nested loops -> O(n^2) time.")
        return "O(n^2)", notes

    if f.max_loop_depth == 1:
        note = "Detected a single loop (or sequential loops) -> O(n) time."
        if f.sort_lines:
            note += " A sort call was also found; actual complexity may be higher (e.g. O(n log n) inside the loop)."
        notes.append(note)
        return "O(n)", notes

    if f.sort_lines:
        notes.append("Detected sorted()/.sort() with no surrounding loop -> O(n log n) time.")
        return "O(n log n)", notes

    if f.log_pattern_lines:
        notes.append(
            "Detected a loop that halves/doubles its counter each iteration -> O(log n) time."
        )
        return "O(log n)", notes

    notes.append("No loops, recursion, or sorting detected -> O(1) time.")
    return "O(1)", notes


def _estimate_space_complexity(f: Findings):
    """
    Space heuristic:

      * Branching recursion  -> O(n)  (call stack depth is O(n) even
                                        though the *time* is O(2^n))
      * Linear recursion     -> O(n)  (call stack)
      * List/dict/set created-> O(n)
      * Otherwise            -> O(1)
    """
    notes = []

    if f.recursion_detected:
        notes.append("Recursive call stack grows with input size -> O(n) space.")
        return "O(n)", notes

    if f.space_lines:
        notes.append(
            "Detected creation of a list/dict/set (literal or comprehension) -> O(n) space."
        )
        return "O(n)", notes

    notes.append("No growing data structures or recursion detected -> O(1) space.")
    return "O(1)", notes
