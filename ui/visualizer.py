import sys
import ast
from typing import Dict, Any, List
from PyQt5.QtWidgets import QTextEdit, QWidget, QMainWindow
from PyQt5.QtCore import QObject, QTimer, QSize
from PyQt5.QtGui import QTextCursor, QColor, QTextFormat

from .dynamic_layout_manager import DynamicCanvas, SmartVariableWidget, SmartPrintBlock

HIGHLIGHT_COLOR = QColor("#bd93f9")


class UIVisualizer(QObject):
    def __init__(self, main_window: QMainWindow, code_editor: QTextEdit, canvas: DynamicCanvas):
        super().__init__(main_window)
        self.main_window = main_window
        self.code_editor = code_editor
        self.canvas = canvas

        self.is_running = False
        self.global_vars: Dict[str, Any] = {}
        self.variable_widgets: Dict[str, SmartVariableWidget] = {}
        self.step_timer = QTimer()
        self.step_timer.setSingleShot(True)
        self.step_timer.timeout.connect(self._next_step)
        self.execution_steps: List[tuple] = []
        self.current_step_index = 0
        self.extra_selections: List[QTextEdit.ExtraSelection] = []

    def start(self):
        if self.is_running: return
        self.is_running = True
        self.canvas.clear_all()
        self.variable_widgets.clear()
        self.global_vars.clear()
        self.execution_steps.clear()
        self.current_step_index = 0
        self._clear_highlight()

        code = self.code_editor.toPlainText().strip()
        if not code:
            self.is_running = False
            return

        try:
            tree = ast.parse(code)
            # FIX: Access nested class via `self`
            visitor = self.CodeExecutionVisitor()
            visitor.visit(tree)
            self.execution_steps = visitor.steps
            self.execution_steps.append(('end', None, None))
        except SyntaxError as e:
            print(f"Syntax Error: {e}")
            self.is_running = False
            return
        QTimer.singleShot(100, self._next_step)

    def _next_step(self):
        if self.current_step_index >= len(self.execution_steps) or not self.is_running:
            self._finish_execution()
            return
        step_type, node, lineno = self.execution_steps[self.current_step_index]
        if lineno: self._highlight_line(lineno)
        try:
            if step_type == 'assign':
                self._execute_assignment(node)
            elif step_type == 'print':
                self._execute_print(node)
            elif step_type == 'end':
                self._finish_execution(); return
        except Exception as e:
            print(f"Runtime Error on line {lineno}: {e}");
            self._finish_execution();
            return
        self.current_step_index += 1
        if self.is_running: self.step_timer.start(600)

    def _execute_assignment(self, node: ast.Assign):
        var_name = node.targets[0].id
        value = self._evaluate_expression(node.value)
        self.global_vars[var_name] = value

        if var_name in self.variable_widgets:
            self.variable_widgets[var_name].update_value(value)
            # No animation on update, but still trigger a resize check
            QTimer.singleShot(0, self.canvas.check_bounds_and_emit)
        else:
            widget = SmartVariableWidget(var_name, value)
            self.variable_widgets[var_name] = widget
            self.canvas.add_widget(widget)  # This will trigger the resize check
            widget.show_animated()

    def _execute_print(self, node: ast.Call):
        # FIX: Access nested class via `self`
        input_vars_visitor = self.NameVisitor()
        for arg in node.args:
            input_vars_visitor.visit(arg)

        input_widgets = [self.variable_widgets[name] for name in input_vars_visitor.names if
                         name in self.variable_widgets]

        try:
            text_on_line = self.code_editor.document().findBlockByLineNumber(node.lineno - 1).text()
            start, end = text_on_line.find('(') + 1, text_on_line.rfind(')')
            expression_str = text_on_line[start:end].strip() if start > 0 and end != -1 else "..."
        except:
            expression_str = "..."

        evaluated_args = [str(self._evaluate_expression(arg)) for arg in node.args]
        final_result = " ".join(evaluated_args)

        widget = SmartPrintBlock(expression_str, final_result)
        self.canvas.add_widget(widget)  # This triggers resize check
        widget.show_animated()

        for input_widget in input_widgets:
            self.canvas.add_connection(input_widget, widget)
    def _evaluate_expression(self, node: ast.AST):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, (ast.Num, ast.Str, ast.NameConstant)):
            # Note: ast.Num and ast.Str are deprecated in Python 3.8+
            # ast.Constant is the modern way. This provides backward compatibility.
            return ast.literal_eval(node)
        elif isinstance(node, ast.Name):
            if node.id in self.global_vars: return self.global_vars[node.id]
            raise NameError(f"name '{node.id}' is not defined")
        elif isinstance(node, ast.BinOp):
            left, right = self._evaluate_expression(node.left), self._evaluate_expression(node.right)
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            if isinstance(node.op, ast.Div): return left / right
            raise TypeError(f"Unsupported binary operator: {type(node.op).__name__}")
        raise TypeError(f"Unsupported expression type: {type(node).__name__}")

    def _highlight_line(self, line_number: int):
        self._clear_highlight()
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(HIGHLIGHT_COLOR.lighter(120))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        cursor = self.code_editor.textCursor()
        cursor.movePosition(QTextCursor.Start)
        cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, line_number - 1)
        selection.cursor = cursor
        self.extra_selections.append(selection)
        self.code_editor.setExtraSelections(self.extra_selections)

    def _clear_highlight(self):
        self.extra_selections.clear()
        self.code_editor.setExtraSelections(self.extra_selections)

    def _finish_execution(self):
        self._clear_highlight()
        self.is_running = False
        self.step_timer.stop()
        print("Execution finished.")

    class NameVisitor(ast.NodeVisitor):
        def __init__(self):
            self.names = []

        def visit_Name(self, node):
            self.names.append(node.id)

    class CodeExecutionVisitor(ast.NodeVisitor):
        def __init__(self):
            self.steps: List[tuple] = []

        def visit_Assign(self, node: ast.Assign):
            self.steps.append(('assign', node, node.lineno))

        def visit_Expr(self, node: ast.Expr):
            if isinstance(node.value, ast.Call):
                call_node = node.value
                if isinstance(call_node.func, ast.Name) and call_node.func.id == 'print':
                    self.steps.append(('print', call_node, node.lineno))