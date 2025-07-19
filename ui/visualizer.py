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
        """Start the visualization process"""
        if self.is_running:
            return

        self.is_running = True

        # Clear and reset everything
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
            # Parse the code and create execution steps
            tree = ast.parse(code)
            visitor = self.CodeExecutionVisitor()
            visitor.visit(tree)
            self.execution_steps = visitor.steps
            self.execution_steps.append(('end', None, None))

            print(f"Created {len(self.execution_steps)} execution steps")

        except SyntaxError as e:
            print(f"Syntax Error: {e}")
            self.is_running = False
            return

        # Start execution with a small delay
        QTimer.singleShot(200, self._next_step)

    def _next_step(self):
        """Execute the next step in the visualization"""
        if self.current_step_index >= len(self.execution_steps) or not self.is_running:
            self._finish_execution()
            return

        step_type, node, lineno = self.execution_steps[self.current_step_index]

        # Highlight the current line
        if lineno:
            self._highlight_line(lineno)

        try:
            if step_type == 'assign':
                self._execute_assignment(node)
            elif step_type == 'print':
                self._execute_print(node)
            elif step_type == 'end':
                self._finish_execution()
                return

        except Exception as e:
            print(f"Runtime Error on line {lineno}: {e}")
            self._finish_execution()
            return

        self.current_step_index += 1

        # Continue to next step with timing
        if self.is_running:
            self.step_timer.start(800)  # Slightly longer delay for better visibility

    def _execute_assignment(self, node: ast.Assign):
        """Execute an assignment and update/create variable widgets"""
        if not isinstance(node.targets[0], ast.Name):
            return  # Skip complex assignments for now

        var_name = node.targets[0].id

        try:
            value = self._evaluate_expression(node.value)
            self.global_vars[var_name] = value

            if var_name in self.variable_widgets:
                # Update existing widget
                self.variable_widgets[var_name].update_value(value)
            else:
                # Create new widget
                item = SmartVariableWidget(var_name, value)
                self.variable_widgets[var_name] = item
                self.canvas.add_item(item)

        except Exception as e:
            print(f"Error evaluating assignment: {e}")

    def _execute_print(self, node: ast.Call):
        """Execute a print statement and create a print block"""
        # Find variable names used in the print arguments
        input_vars_visitor = self.NameVisitor()
        for arg in node.args:
            input_vars_visitor.visit(arg)

        # Get corresponding widget items for input variables
        input_items = []
        for name in input_vars_visitor.names:
            if name in self.variable_widgets:
                input_items.append(self.variable_widgets[name])

        # Extract the expression string from the source code
        try:
            text_on_line = self.code_editor.document().findBlockByLineNumber(node.lineno - 1).text()
            start = text_on_line.find('(') + 1
            end = text_on_line.rfind(')')
            if start > 0 and end != -1:
                expression_str = text_on_line[start:end].strip()
            else:
                expression_str = "..."
        except:
            expression_str = "..."

        # Evaluate the print arguments
        try:
            evaluated_args = []
            for arg in node.args:
                result = self._evaluate_expression(arg)
                evaluated_args.append(str(result))

            final_result = " ".join(evaluated_args)
        except Exception as e:
            final_result = f"Error: {e}"

        # Create print block
        item = SmartPrintBlock(expression_str, final_result)
        self.canvas.add_item(item)

        # Create connections to input variables
        for input_item in input_items:
            self.canvas.add_connection(input_item, item)

    def _evaluate_expression(self, node: ast.AST):
        """Safely evaluate an AST expression"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, (ast.Num, ast.Str, ast.NameConstant)):
            # For older Python versions
            return ast.literal_eval(node)
        elif isinstance(node, ast.Name):
            if node.id in self.global_vars:
                return self.global_vars[node.id]
            else:
                raise NameError(f"name '{node.id}' is not defined")
        elif isinstance(node, ast.BinOp):
            left = self._evaluate_expression(node.left)
            right = self._evaluate_expression(node.right)

            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                return left - right
            elif isinstance(node.op, ast.Mult):
                return left * right
            elif isinstance(node.op, ast.Div):
                return left / right
            elif isinstance(node.op, ast.FloorDiv):
                return left // right
            elif isinstance(node.op, ast.Mod):
                return left % right
            elif isinstance(node.op, ast.Pow):
                return left ** right
            else:
                raise TypeError(f"Unsupported binary operator: {type(node.op).__name__}")
        elif isinstance(node, ast.UnaryOp):
            operand = self._evaluate_expression(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +operand
            elif isinstance(node.op, ast.USub):
                return -operand
            else:
                raise TypeError(f"Unsupported unary operator: {type(node.op).__name__}")
        else:
            raise TypeError(f"Unsupported expression type: {type(node).__name__}")

    def _highlight_line(self, line_number: int):
        """Highlight the currently executing line in the code editor"""
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
        """Clear line highlighting"""
        self.extra_selections.clear()
        self.code_editor.setExtraSelections(self.extra_selections)

    def _finish_execution(self):
        """Clean up after execution is complete"""
        self._clear_highlight()
        self.is_running = False
        self.step_timer.stop()
        print("Visualization execution finished.")

    def stop(self):
        """Stop the visualization"""
        self.is_running = False
        self.step_timer.stop()
        self._clear_highlight()
        print("Visualization stopped.")

    class NameVisitor(ast.NodeVisitor):
        """AST visitor to collect variable names"""

        def __init__(self):
            self.names = []

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Load):  # Only variable reads
                self.names.append(node.id)

    class CodeExecutionVisitor(ast.NodeVisitor):
        """AST visitor to create execution steps"""

        def __init__(self):
            self.steps: List[tuple] = []

        def visit_Assign(self, node: ast.Assign):
            """Handle assignment statements"""
            # Only handle simple name assignments for now
            if (len(node.targets) == 1 and
                    isinstance(node.targets[0], ast.Name)):
                self.steps.append(('assign', node, node.lineno))

        def visit_AugAssign(self, node: ast.AugAssign):
            """Handle augmented assignment (+=, -=, etc.)"""
            if isinstance(node.target, ast.Name):
                self.steps.append(('assign', node, node.lineno))

        def visit_Expr(self, node: ast.Expr):
            """Handle expression statements (like print calls)"""
            if isinstance(node.value, ast.Call):
                call_node = node.value
                if (isinstance(call_node.func, ast.Name) and
                        call_node.func.id == 'print'):
                    self.steps.append(('print', call_node, node.lineno))

        def generic_visit(self, node):
            """Continue visiting child nodes"""
            super().generic_visit(node)