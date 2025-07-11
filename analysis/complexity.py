import ast

class ComplexityAnalyzer(ast.NodeVisitor):
    """
    Analyzes Python code using AST to provide a heuristic estimation
    of time and space complexity.
    """
    def __init__(self):
        self.loop_depth = 0
        self.max_loop_depth = 0
        self.space_is_linear = False

    def visit_For(self, node):
        self.loop_depth += 1
        self.max_loop_depth = max(self.max_loop_depth, self.loop_depth)
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_While(self, node):
        self.loop_depth += 1
        self.max_loop_depth = max(self.max_loop_depth, self.loop_depth)
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_ListComp(self, node):
        self.space_is_linear = True
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'append':
            if self.loop_depth > 0:
                self.space_is_linear = True
        self.generic_visit(node)

    def analyze(self, code):
        self.loop_depth = 0
        self.max_loop_depth = 0
        self.space_is_linear = False
        try:
            tree = ast.parse(code)
            self.visit(tree)
            if self.max_loop_depth == 0:
                time_complexity = "O(1)"
            elif self.max_loop_depth == 1:
                time_complexity = "O(n)"
            elif self.max_loop_depth == 2:
                time_complexity = "O(n^2)"
            else:
                time_complexity = f"O(n^{self.max_loop_depth})"
            space_complexity = "O(n)" if self.space_is_linear else "O(1)"
            return {"time": time_complexity, "space": space_complexity}
        except SyntaxError:
            return {"time": "N/A", "space": "N/A"}