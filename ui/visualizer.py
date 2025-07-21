import sys
import ast
from typing import Dict, Any, List, Tuple, Union, Optional, Iterator
from PyQt5.QtWidgets import QTextEdit, QWidget, QMainWindow
from PyQt5.QtCore import QObject, QTimer
from PyQt5.QtGui import QTextCursor, QColor, QTextFormat

# Import the enhanced UI components, including the new ScopeWidget
from .dynamic_layout_manager import DynamicCanvas, SmartVariableWidget, SmartPrintBlock, ScopeWidget

HIGHLIGHT_COLOR = QColor("#bd93f9")


class CallFrame:
    """Represents a single frame on the call stack, managing its own scope and execution."""

    def __init__(self, name: str, nodes: List[ast.stmt], lineno: int = 0):
        self.name = name
        self.nodes = nodes
        self.lineno = lineno

        self.ip: int = 0
        self.locals: Dict[str, Any] = {}
        self.variable_widgets: Dict[str, SmartVariableWidget] = {}
        self.scope_widget: Optional[ScopeWidget] = None
        # Add a dictionary to track iterators for for-loops
        self.iterators: Dict[int, Iterator] = {}


class UIVisualizer(QObject):
    """
    Orchestrates code visualization by parsing Python code, managing an execution
    stack for function calls, and updating the UI canvas.
    """

    def __init__(self, main_window: QMainWindow, code_editor: QTextEdit, canvas: DynamicCanvas):
        super().__init__(main_window)
        self.main_window = main_window
        self.code_editor = code_editor
        self.canvas = canvas

        self.is_running = False
        self.functions: Dict[str, ast.FunctionDef] = {}
        self.call_stack: List[CallFrame] = []
        self.return_value: Any = None
        self.awaiting_return_value: Optional[ast.stmt] = None

        self.step_timer = QTimer()
        self.step_timer.setSingleShot(True)
        self.step_timer.timeout.connect(self._next_step)
        self.extra_selections: List[QTextEdit.ExtraSelection] = []

    def start(self):
        """
        Starts the visualization. Clears the previous state, parses the code,
        finds functions, and sets up the initial call stack.
        """
        if self.is_running:
            return

        self.is_running = True

        self.canvas.clear_all()
        self.functions.clear()
        self.call_stack.clear()
        self._clear_highlight()
        self.awaiting_return_value = None

        code = self.code_editor.toPlainText().strip()
        if not code:
            self.is_running = False
            return

        try:
            tree = ast.parse(code)
            finder = self.FunctionFinder()
            finder.visit(tree)
            self.functions = finder.functions

            main_body_nodes = [node for node in tree.body if not isinstance(node, ast.FunctionDef)]

            global_frame = CallFrame('<module>', main_body_nodes)
            self.call_stack.append(global_frame)

        except SyntaxError as e:
            print(f"Syntax Error: {e}")
            self.is_running = False
            return

        QTimer.singleShot(200, self._next_step)

    def _next_step(self):
        """
        Executes the next single step in the current call frame, handling
        assignments, prints, function calls, and returns.
        """
        if not self.is_running or not self.call_stack:
            self._finish_execution()
            return

        current_frame = self.call_stack[-1]

        if self.awaiting_return_value:
            node_to_complete = self.awaiting_return_value
            self.awaiting_return_value = None

            if isinstance(node_to_complete, ast.Assign):
                for target in node_to_complete.targets:
                    if isinstance(target, ast.Name):
                        self._update_variable(target.id, self.return_value)

            current_frame.ip += 1

        if current_frame.ip >= len(current_frame.nodes):
            self._handle_return(None)
            if self.is_running:
                self.step_timer.start(500)
            return

        node = current_frame.nodes[current_frame.ip]
        self._highlight_line(node.lineno)

        try:
            # --- Node Execution Logic ---
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                if isinstance(node.value, ast.Call) and isinstance(node.value.func,
                                                                   ast.Name) and node.value.func.id in self.functions:
                    self.awaiting_return_value = node
                    self._execute_call(node.value)
                else:
                    self._execute_assignment(node)
                    current_frame.ip += 1

            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call_node = node.value
                if isinstance(call_node.func, ast.Name):
                    if call_node.func.id == 'print':
                        self._execute_print(call_node)
                        current_frame.ip += 1
                    elif call_node.func.id in self.functions:
                        self.awaiting_return_value = node
                        self._execute_call(call_node)
                    else:
                        current_frame.ip += 1
                else:
                    current_frame.ip += 1

            elif isinstance(node, ast.Return):
                value = self._evaluate_expression(node.value) if node.value else None
                self._handle_return(value)

            elif isinstance(node, ast.If):
                test_result = self._evaluate_expression(node.test)
                body_to_execute = node.body if test_result else node.orelse
                # Inject the chosen branch into the execution stream
                current_frame.nodes[current_frame.ip + 1:current_frame.ip + 1] = body_to_execute
                current_frame.ip += 1

            elif isinstance(node, ast.While):
                test_result = self._evaluate_expression(node.test)
                if test_result:
                    # If true, inject the body and the loop itself to run again
                    nodes_to_inject = node.body + [node]
                    current_frame.nodes[current_frame.ip + 1:current_frame.ip + 1] = nodes_to_inject
                current_frame.ip += 1

            elif isinstance(node, ast.For):
                loop_id = node.lineno
                # Setup iterator on first entry
                if loop_id not in current_frame.iterators:
                    iterable = self._evaluate_expression(node.iter)
                    current_frame.iterators[loop_id] = iter(iterable)

                iterator = current_frame.iterators[loop_id]
                try:
                    # Get next item
                    item = next(iterator)
                    # Create an assignment for the loop variable
                    assign_node = ast.Assign(targets=[node.target], value=ast.Constant(value=item))
                    ast.copy_location(assign_node, node)
                    # Inject assignment, body, and the loop itself to continue
                    nodes_to_inject = [assign_node] + node.body + [node]
                    current_frame.nodes[current_frame.ip + 1:current_frame.ip + 1] = nodes_to_inject
                except StopIteration:
                    # Loop finished, clean up iterator
                    del current_frame.iterators[loop_id]

                current_frame.ip += 1

            else:
                current_frame.ip += 1

        except Exception as e:
            print(f"Runtime Error on line {getattr(node, 'lineno', '?')}: {e}")
            self._finish_execution()
            return

        if self.is_running:
            self.step_timer.start(800)

    def _execute_assignment(self, node: Union[ast.Assign, ast.AugAssign]):
        """Executes an assignment (e.g., x = 1 or x += 1) and updates the UI."""
        value = self._evaluate_expression(node.value)

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._update_variable(target.id, value)
        elif isinstance(node, ast.AugAssign):
            var_name = node.target.id
            current_value = self._evaluate_expression(ast.Name(id=var_name, ctx=ast.Load()))
            op_map = {
                ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
                ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
                ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b,
                ast.Pow: lambda a, b: a ** b,
            }
            new_value = op_map[type(node.op)](current_value, value)
            self._update_variable(var_name, new_value)

    def _execute_print(self, node: ast.Call):
        """Executes a print statement and creates a visual block on the canvas."""
        input_vars_visitor = self.NameVisitor()
        for arg in node.args:
            input_vars_visitor.visit(arg)
        # Find the widgets for the input variables from the current scope
        input_items = []
        for name in input_vars_visitor.names:
            for frame in reversed(self.call_stack):
                if name in frame.variable_widgets:
                    input_items.append(frame.variable_widgets[name])
                    break
        try:
            # This part is for display only and can fail gracefully
            text_on_line = self.code_editor.document().findBlockByLineNumber(node.lineno - 1).text()
            start = text_on_line.find('(') + 1
            end = text_on_line.rfind(')')
            expression_str = text_on_line[start:end].strip()
        except Exception:
            expression_str = "..."
        evaluated_args = [str(self._evaluate_expression(arg)) for arg in node.args]
        final_result = " ".join(evaluated_args)
        item = SmartPrintBlock(expression_str, final_result)
        self.canvas.add_item(item)
        # Enhanced connection creation with delay to ensure proper positioning
        for input_item in input_items:
            def create_delayed_connection(input_widget, output_widget):
                connection = self.canvas.add_connection(input_widget, output_widget)
                # Force path update after a short delay
                QTimer.singleShot(200, connection.update_path)

            QTimer.singleShot(50, lambda ii=input_item, oi=item: create_delayed_connection(ii, oi))

    def _execute_call(self, node: ast.Call):
        """Handles a call to a user-defined function, creating a new call frame."""
        func_name = node.func.id
        func_def = self.functions.get(func_name)

        if not func_def:
            raise NameError(f"Function '{func_name}' is not defined.")

        evaluated_args = [self._evaluate_expression(arg) for arg in node.args]

        new_frame_nodes = func_def.body
        new_frame = CallFrame(func_name, new_frame_nodes, node.lineno)

        param_names = [arg.arg for arg in func_def.args.args]
        for name, value in zip(param_names, evaluated_args):
            new_frame.locals[name] = value

        scope_widget = ScopeWidget(f"Scope: {func_name}()")
        new_frame.scope_widget = scope_widget
        self.canvas.add_item(scope_widget)

        for name, value in new_frame.locals.items():
            var_widget = SmartVariableWidget(name, value)
            new_frame.variable_widgets[name] = var_widget
            scope_widget.addItem(var_widget)
        self.call_stack.append(new_frame)
        self._refresh_all_connections()

    def _handle_return(self, value: Any):
        if len(self.call_stack) > 1:
            frame_to_pop = self.call_stack.pop()
            if frame_to_pop.scope_widget:
                frame_to_pop.scope_widget.remove_animated()
            self.return_value = value
        else:
            self.return_value = value
            self._finish_execution()

    def _update_variable(self, var_name: str, value: Any):
        current_frame = self.call_stack[-1]
        current_frame.locals[var_name] = value

        if var_name in current_frame.variable_widgets:
            current_frame.variable_widgets[var_name].update_value(value)
        else:
            item = SmartVariableWidget(var_name, value)
            current_frame.variable_widgets[var_name] = item

            if current_frame.scope_widget:
                current_frame.scope_widget.addItem(item)
            else:
                self.canvas.add_item(item)

    def _evaluate_expression(self, node: ast.AST) -> Any:
        """
        Safely evaluates an AST expression node by recursively processing it.
        Searches for variables in the current scope stack.
        """
        if node is None:
            return None
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, (ast.Num, ast.Str, ast.NameConstant)):
            return ast.literal_eval(node)
        elif isinstance(node, ast.Name):
            for frame in reversed(self.call_stack):
                if node.id in frame.locals:
                    return frame.locals[node.id]
            raise NameError(f"name '{node.id}' is not defined")
        elif isinstance(node, ast.BinOp):
            left = self._evaluate_expression(node.left)
            right = self._evaluate_expression(node.right)
            op_map = {
                ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
                ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
                ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b,
                ast.Pow: lambda a, b: a ** b,
            }
            return op_map[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self._evaluate_expression(node.operand)
            op_map = {ast.UAdd: lambda x: +x, ast.USub: lambda x: -x, ast.Not: lambda x: not x}
            return op_map[type(node.op)](operand)
        elif isinstance(node, ast.Compare):
            left = self._evaluate_expression(node.left)
            # Note: This handles simple comparisons (e.g., a == b), not chained (a < b < c)
            op = node.ops[0]
            right = self._evaluate_expression(node.comparators[0])
            op_map = {
                ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b,
                ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b,
                ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b,
                ast.Is: lambda a, b: a is b, ast.IsNot: lambda a, b: a is not b,
                ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b
            }
            return op_map[type(op)](left, right)
        elif isinstance(node, ast.BoolOp):
            # Handle 'and' and 'or' with short-circuiting
            if isinstance(node.op, ast.And):
                for value_node in node.values:
                    result = self._evaluate_expression(value_node)
                    if not result:
                        return result
                return result
            elif isinstance(node.op, ast.Or):
                for value_node in node.values:
                    result = self._evaluate_expression(value_node)
                    if result:
                        return result
                return result
        else:
            raise TypeError(f"Unsupported expression type: {type(node).__name__}")

    def _highlight_line(self, line_number: int):
        self._clear_highlight()
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(HIGHLIGHT_COLOR)
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
        print("Visualization execution finished.")

    def stop(self):
        if self.is_running:
            self.is_running = False
            self.step_timer.stop()
            self._clear_highlight()
            print("Visualization stopped by user.")

    def _refresh_all_connections(self):
        """Refresh all connections when the scene changes significantly."""
        QTimer.singleShot(300, lambda: [conn.update_path() for conn in self.canvas.connections])

    def _batch_update_connections(self):
        """Update all connections in a batch to avoid redundant calculations."""
        if not hasattr(self, '_connection_update_timer'):
            self._connection_update_timer = QTimer()
            self._connection_update_timer.setSingleShot(True)
            self._connection_update_timer.timeout.connect(self._perform_batch_connection_update)
        self._connection_update_timer.start(150)

    def _perform_batch_connection_update(self):
        """Actually perform the connection updates."""
        for connection in self.canvas.connections:
            connection.update_path()

    class NameVisitor(ast.NodeVisitor):
        """An AST visitor to collect variable names being read (loaded)."""

        def __init__(self):
            self.names: List[str] = []

        def visit_Name(self, node: ast.Name):
            if isinstance(node.ctx, ast.Load):
                if node.id not in self.names:
                    self.names.append(node.id)
            self.generic_visit(node)

    class FunctionFinder(ast.NodeVisitor):
        """An AST visitor that finds all top-level function definitions."""

        def __init__(self):
            self.functions: Dict[str, ast.FunctionDef] = {}

        def visit_FunctionDef(self, node: ast.FunctionDef):
            self.functions[node.name] = node