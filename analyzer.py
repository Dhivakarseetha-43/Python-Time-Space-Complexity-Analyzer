

import ast
from dataclasses import dataclass, field
from typing import List, Dict, Set


@dataclass
class Findings:

    max_loop_depth: int = 0
    loop_lines: List[int] = field(default_factory=list)

    log_pattern_lines: List[int] = field(default_factory=list)   
    sort_lines: List[int] = field(default_factory=list)          
    space_lines: List[int] = field(default_factory=list)         

    recursion_detected: bool = False
    recursive_lines: List[int] = field(default_factory=list)
    max_recursive_calls_in_function: int = 0  



# Loop + data-structure + sort visitor

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
        
        for stmt in node.body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.AugAssign) and isinstance(
                    sub.op, (ast.FloorDiv, ast.Div, ast.Mult)
                ):
                    return True
        return False

    # ---- sorting 
    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "sorted":
            self.findings.sort_lines.append(node.lineno)
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "sort":
            self.findings.sort_lines.append(node.lineno)
        self.generic_visit(node)

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
        self.generic_visit(node)

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
                
                if nested_node.name == func_name:
                    inner_self.generic_visit(nested_node)
                

        counter = _InnerCallCounter()
        for stmt in body:
            counter.visit(stmt)

        return count, lines


# Public entry point
def analyze(tree: ast.AST):
    
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
