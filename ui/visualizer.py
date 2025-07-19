import sys
import ast
from typing import Dict, Any, List, Tuple, Union, Optional
from PyQt5.QtWidgets import QTextEdit, QWidget, QMainWindow
from PyQt5.QtCore import QObject, QTimer
from PyQt5.QtGui import QTextCursor, QColor, QTextFormat

# Import the enhanced UI components, including the new ScopeWidget
from .dynamic_layout_manager import DynamicCanvas, SmartVariableWidget, SmartPrintBlock, ScopeWidget

HIGHLIGHT_COLOR = QColor("#bd93f9")


class CallFrame:
    """Represents a single frame on the call stack, managing its own scope and execution."""

    def __init__(self, name: str, nodes: List[ast.stmt], lineno: int = 0):
        self.name = name  # e.g., '<module>' or 'my_function'
        self.nodes = nodes  # AST nodes to execute in this frame
        self.lineno = lineno  # Line number where the call was initiated

        self.ip: int = 0  # Instruction Pointer
        self.locals: Dict[str, Any] = {}
        self.variable_widgets: Dict[str, SmartVariableWidget] = {}
        self.scope_widget: Optional[ScopeWidget] = None


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

        # Clear and reset everything for a fresh start
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
            # Find all function definitions first
            finder = self.FunctionFinder()
            finder.visit(tree)
            self.functions = finder.functions

            # The main body consists of nodes that are not function definitions
            main_body_nodes = [node for node in tree.body if not isinstance(node, ast.FunctionDef)]

            # Create the initial call frame for the global scope ('<module>')
            global_frame = CallFrame('<module>', main_body_nodes)
            self.call_stack.append(global_frame)

        except SyntaxError as e:
            print(f"Syntax Error: {e}")
            self.is_running = False
            return

        # Start execution
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

        # If we have a pending assignment waiting for a return value, complete it
        if self.awaiting_return_value:
            node_to_complete = self.awaiting_return_value
            self.awaiting_return_value = None  # Clear the flag

            if isinstance(node_to_complete, ast.Assign):
                # Assign the return value to the target variable
                var_name = node_to_complete.targets[0].id
                self._update_variable(var_name, self.return_value)

            current_frame.ip += 1  # Move to the next instruction

        # Check if the current frame's execution is complete
        if current_frame.ip >= len(current_frame.nodes):
            self._handle_return(None)  # Implicit return of None
            self.step_timer.start(500)
            return

        node = current_frame.nodes[current_frame.ip]
        self._highlight_line(node.lineno)

        try:
            # --- Node Execution Logic ---
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                if isinstance(node.value, ast.Call) and isinstance(node.value.func,
                                                                   ast.Name) and node.value.func.id in self.functions:
                    self.awaiting_return_value = node  # Flag that we're waiting for a return value
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
                        self.awaiting_return_value = node  # Call for side-effects
                        self._execute_call(call_node)
                    else:
                        current_frame.ip += 1  # Ignore other function calls

            elif isinstance(node, ast.Return):
                value = self._evaluate_expression(node.value) if node.value else None
                self._handle_return(value)

            else:
                # For any other statement type, just move to the next one.
                current_frame.ip += 1

        except Exception as e:
            print(f"Runtime Error on line {node.lineno}: {e}")
            self._finish_execution()
            return

        if self.is_running:
            self.step_timer.start(800)  # Delay for better visibility

    def _execute_assignment(self, node: Union[ast.Assign, ast.AugAssign]):
        """Executes an assignment (e.g., x = 1 or x += 1) and updates the UI."""
        var_name = ""
        try:
            if isinstance(node, ast.Assign):
                var_name = node.targets[0].id
                value = self._evaluate_expression(node.value)
            elif isinstance(node, ast.AugAssign):
                var_name = node.target.id
                op_node = ast.BinOp(left=ast.Name(id=var_name, ctx=ast.Load()), op=node.op, right=node.value)
                value = self._evaluate_expression(op_node)

            self._update_variable(var_name, value)

        except Exception as e:
            print(f"Error evaluating assignment for '{var_name}': {e}")

    def _execute_print(self, node: ast.Call):
        """Executes a print statement and creates a visual block on the canvas."""
        input_vars_visitor = self.NameVisitor()
        for arg in node.args:
            input_vars_visitor.visit(arg)

        # Find the widgets for the input variables from the current scope
        current_frame = self.call_stack[-1]
        input_items = []
        for name in input_vars_visitor.names:
            for frame in reversed(self.call_stack):
                if name in frame.variable_widgets:
                    input_items.append(frame.variable_widgets[name])
                    break

        try:
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

        for input_item in input_items:
            self.canvas.add_connection(input_item, item)

    def _execute_call(self, node: ast.Call):
        """Handles a call to a user-defined function, creating a new call frame."""
        func_name = node.func.id
        func_def = self.functions.get(func_name)

        if not func_def:
            raise NameError(f"Function '{func_name}' is not defined.")

        # Evaluate arguments in the CALLER's scope
        caller_frame = self.call_stack[-1]
        evaluated_args = [self._evaluate_expression(arg) for arg in node.args]

        # Create the new frame for the function being called
        new_frame_nodes = func_def.body
        new_frame = CallFrame(func_name, new_frame_nodes, node.lineno)

        # Bind arguments to parameters in the new frame's local scope
        param_names = [arg.arg for arg in func_def.args.args]
        for name, value in zip(param_names, evaluated_args):
            new_frame.locals[name] = value

        # Create a visual scope widget on the canvas
        scope_widget = ScopeWidget(f"{func_name}()")
        new_frame.scope_widget = scope_widget
        self.canvas.add_item(scope_widget)

        # Populate the scope widget with initial argument variables
        for name, value in new_frame.locals.items():
            var_widget = SmartVariableWidget(name, value)
            new_frame.variable_widgets[name] = var_widget
            scope_widget.addItem(var_widget)

        self.call_stack.append(new_frame)

    def _handle_return(self, value: Any):
        """Handles returning from a function, popping the call stack."""
        if len(self.call_stack) > 1:  # Can't return from <module>
            frame_to_pop = self.call_stack.pop()
            if frame_to_pop.scope_widget:
                frame_to_pop.scope_widget.remove_animated()  # Visual cleanup
            self.return_value = value
        else:
            self._finish_execution()

    def _update_variable(self, var_name: str, value: Any):
        """Creates or updates a variable and its corresponding UI widget in the correct scope."""
        current_frame = self.call_stack[-1]
        current_frame.locals[var_name] = value

        # Determine the target dictionary for widgets (frame's or scope's)
        target_widget_dict = current_frame.variable_widgets

        if var_name in target_widget_dict:
            target_widget_dict[var_name].update_value(value)
        else:
            item = SmartVariableWidget(var_name, value)
            target_widget_dict[var_name] = item

            # Add the widget to the scope container or the main canvas
            if current_frame.scope_widget:
                current_frame.scope_widget.addItem(item)
            else:
                self.canvas.add_item(item)

    def _evaluate_expression(self, node: ast.AST) -> Any:
        """
        Safely evaluates an AST expression node by recursively processing it.
        Searches for variables in the current scope stack.
        """
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, (ast.Num, ast.Str, ast.NameConstant)):  # Legacy
            return ast.literal_eval(node)
        elif isinstance(node, ast.Name):
            # Search from the current scope outwards to the global scope
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
            op_map = {ast.UAdd: lambda x: +x, ast.USub: lambda x: -x}
            return op_map[type(node.op)](operand)
        else:
            raise TypeError(f"Unsupported expression type: {type(node).__name__}")

    def _highlight_line(self, line_number: int):
        """Highlights the currently executing line."""
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
        """Clears all line highlighting."""
        self.extra_selections.clear()
        self.code_editor.setExtraSelections(self.extra_selections)

    def _finish_execution(self):
        """Cleans up after visualization is complete."""
        self._clear_highlight()
        self.is_running = False
        self.step_timer.stop()
        print("Visualization execution finished.")

    def stop(self):
        """Public method to stop the visualization."""
        if self.is_running:
            self.is_running = False
            self.step_timer.stop()
            self._clear_highlight()
            print("Visualization stopped by user.")

    class NameVisitor(ast.NodeVisitor):
        """An AST visitor to collect variable names being read (loaded)."""

        def __init__(self):
            self.names: List[str] = []

        def visit_Name(self, node: ast.Name):
            if isinstance(node.ctx, ast.Load):
                self.names.append(node.id)
            self.generic_visit(node)

    class FunctionFinder(ast.NodeVisitor):
        """An AST visitor that finds all top-level function definitions."""

        def __init__(self):
            self.functions: Dict[str, ast.FunctionDef] = {}

        def visit_FunctionDef(self, node: ast.FunctionDef):
            self.functions[node.name] = node
            # Do not visit children of the function