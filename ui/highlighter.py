import ast
from PyQt5.QtGui import QColor, QFont, QTextCharFormat, QSyntaxHighlighter
from PyQt5.QtCore import QRegExp


class PythonHighlighter(QSyntaxHighlighter):
    """
    Handles syntax highlighting and analyzes code for errors and warnings.
    """

    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []
        self.diagnostics = []

        # --- Syntax Highlighting Rules ---
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#FFB86C"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "def", "class", "if", "elif", "else", "try", "except", "finally",
            "while", "for", "in", "return", "import", "from", "as", "pass", "raise",
            "with", "yield", "assert", "break", "continue", "lambda", "and", "or", "not",
            "is", "None", "True", "False", "global", "nonlocal", "del"
        ]
        self.highlighting_rules += [(QRegExp(fr"\b{word}\b"), keyword_format) for word in keywords]

        class_format = QTextCharFormat()
        class_format.setForeground(QColor("#8BE9FD"))
        self.highlighting_rules.append((QRegExp(r"\bclass\s+[A-Za-z_][A-Za-z0-9_]*"), class_format))

        func_format = QTextCharFormat()
        func_format.setForeground(QColor("#50FA7B"))
        self.highlighting_rules.append((QRegExp(r"\bdef\s+[A-Za-z_][A-Za-z0-9_]*"), func_format))

        builtin_func_format = QTextCharFormat()
        builtin_func_format.setForeground(QColor("#FF79C6"))
        builtins = [
            "print", "len", "range", "int", "str", "float", "input", "open", "list",
            "dict", "set", "tuple", "type", "isinstance", "hasattr", "getattr", "setattr",
            "min", "max", "sum", "abs", "round", "sorted", "reversed", "enumerate", "zip"
        ]
        self.highlighting_rules += [(QRegExp(fr"\b{word}\b"), builtin_func_format) for word in builtins]

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#F1FA8C"))
        self.highlighting_rules.append((QRegExp(r'"[^"\\n]*"'), string_format))
        self.highlighting_rules.append((QRegExp(r"'[^'\\n]*'"), string_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6272A4"))
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((QRegExp(r"#.*"), comment_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#BD93F9"))
        self.highlighting_rules.append((QRegExp(r"\b[0-9]+\b"), number_format))

        decorator_format = QTextCharFormat()
        decorator_format.setForeground(QColor("#FF79C6"))
        self.highlighting_rules.append((QRegExp(r"@\w+"), decorator_format))

    def highlightBlock(self, text):
        """Applies syntax highlighting rules to the current text block."""
        for pattern, fmt in self.highlighting_rules:
            index = pattern.indexIn(text)
            while index >= 0:
                length = pattern.matchedLength()
                self.setFormat(index, length, fmt)
                index = pattern.indexIn(text, index + length)

    def analyze_code(self, text):
        """Analyzes code for syntax errors and style warnings."""
        self.diagnostics = []

        # 1. Check for syntax errors
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            diagnostic = {
                "line": e.lineno,
                "col": e.offset or 1,
                "length": 1,
                "message": f"Syntax Error: {e.msg}",
                "severity": "error"
            }
            self.diagnostics.append(diagnostic)
            self.rehighlight()
            return  # Stop analysis if there's a syntax error

        # 2. Check for unused variables (style warning)
        visitor = UnusedVariableVisitor()
        visitor.visit(tree)
        for name, (lineno, col) in visitor.assigned_vars.items():
            if name not in visitor.used_vars:
                diagnostic = {
                    "line": lineno,
                    "col": col,
                    "length": len(name),
                    "message": f"Warning: Unused variable '{name}'",
                    "severity": "warning"
                }
                self.diagnostics.append(diagnostic)

        self.rehighlight()


class UnusedVariableVisitor(ast.NodeVisitor):
    """An AST visitor to find unused variables."""

    def __init__(self):
        self.assigned_vars = {}
        self.used_vars = set()

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.assigned_vars[target.id] = (target.lineno, target.col_offset)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used_vars.add(node.id)
        self.generic_visit(node)