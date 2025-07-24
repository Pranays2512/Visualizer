import ast
import os
from typing import Dict, Any, List, Tuple, Union, Optional, Iterator
from PyQt5.QtWidgets import QTextEdit, QWidget, QMainWindow
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtGui import QTextCursor, QColor, QTextFormat

from .dynamic_layout_manager import DynamicCanvas, SmartVariableWidget, SmartPrintBlock, ScopeWidget
from .advanced_data_visualizer import ArrayWidget, StringWidget, DictionaryWidget

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
        self.iterators: Dict[int, Iterator] = {}


class UIVisualizer(QObject):
    """
    Orchestrates code visualization by parsing Python code, managing an execution
    stack for function calls, and updating the UI canvas.
    """
    executionFinished = pyqtSignal()

    def __init__(self, main_window: QMainWindow, code_editor: QTextEdit, canvas: DynamicCanvas):
        super().__init__(main_window)
        self.main_window = main_window
        self.code_editor = code_editor
        self.canvas = canvas

        self.is_running = False
        self.is_paused = False
        self.speed_interval = 800

        self.functions: Dict[str, ast.FunctionDef] = {}
        self.call_stack: List[CallFrame] = []
        self.return_value: Any = None
        self.awaiting_return_value: Optional[ast.stmt] = None

        self.step_timer = QTimer()
        self.step_timer.setSingleShot(True)
        self.step_timer.timeout.connect(self._next_step)
        self.extra_selections: List[QTextEdit.ExtraSelection] = []

    # Add this method to UIVisualizer class:

    def start(self):
        """
        Starts the visualization. Clears the previous state, parses the code,
        finds functions, and sets up the initial call stack.
        """
        if self.is_running:
            return

        self.is_running = True
        self.is_paused = False

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

        # REMOVE the control flow detection - always use step-by-step
        QTimer.singleShot(200, self._next_step)
    def execute_and_track(self, code):
        """Execute code and track which branches are taken"""
        import tempfile
        import subprocess
        import sys

        # Insert tracking code
        tracked_code = self.insert_tracking_code(code)

        try:
            with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w') as f:
                f.write(tracked_code)
                temp_file = f.name

            result = subprocess.run([sys.executable, temp_file],
                                    capture_output=True, text=True, timeout=5)

            # Parse tracking output to determine which branches were taken
            return self.parse_execution_path(result.stdout)

        except Exception as e:
            print(f"Execution error: {e}")
            return {}
        finally:
            os.unlink(temp_file)

    def insert_tracking_code(self, code):
        """Insert print statements to track execution path"""
        # This is a simplified version - you'd need more sophisticated tracking
        lines = code.split('\n')
        tracked_lines = []

        for i, line in enumerate(lines):
            if 'if ' in line and ':' in line:
                tracked_lines.append(f"print('CONDITION_LINE_{i}')")
                tracked_lines.append(line)
            elif line.strip().startswith('print('):
                tracked_lines.append(f"print('EXECUTING_LINE_{i}')")
                tracked_lines.append(line)
            else:
                tracked_lines.append(line)

        return '\n'.join(tracked_lines)


    def parse_execution_path(self, output):
        """Parse the tracking output to determine execution path"""
        # Simple implementation - you can enhance this
        lines = output.split('\n')
        execution_info = {}

        for line in lines:
            if 'CONDITION_LINE_' in line:
                execution_info['condition_executed'] = True
            elif 'EXECUTING_LINE_' in line:
                execution_info['branch_taken'] = line

        return execution_info

    def pause(self):
        if self.is_running and not self.is_paused:
            self.is_paused = True
            self.step_timer.stop()
            print("Visualization paused.")

    def resume(self):
        if self.is_running and self.is_paused:
            self.is_paused = False
            print("Visualization resumed.")
            self._next_step()

    def set_speed(self, interval: int):
        self.speed_interval = interval

    def _next_step(self):
        if self.is_paused or not self.is_running or not self.call_stack:
            if not self.call_stack and self.is_running:
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
                self.step_timer.start(self.speed_interval)
            return

        node = current_frame.nodes[current_frame.ip]
        self._highlight_line(node.lineno)

        try:
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
                    elif call_node.func.id in self.functions:
                        self.awaiting_return_value = node
                        self._execute_call(call_node)
                current_frame.ip += 1
            elif isinstance(node, ast.Return):
                value = self._evaluate_expression(node.value) if node.value else None
                self._handle_return(value)
            elif isinstance(node, ast.If):
                # First create a condition variable to show what's being evaluated
                try:
                    condition_text = self.code_editor.document().findBlockByLineNumber(node.lineno - 1).text().strip()
                    condition_text = condition_text.replace('if ', '').replace(':', '')
                except:
                    condition_text = "condition"

                test_result = self._evaluate_expression(node.test)

                # Create condition widget showing the result
                condition_widget = SmartVariableWidget(f"if {condition_text}", str(test_result))
                self.canvas.add_item(condition_widget)

                # Then execute the appropriate branch
                body_to_execute = node.body if test_result else node.orelse
                current_frame.nodes[current_frame.ip + 1:current_frame.ip + 1] = body_to_execute
                current_frame.ip += 1
            elif isinstance(node, ast.While):
                loop_id = id(node)

                # Check condition first
                test_result = self._evaluate_expression(node.test)

                if loop_id not in current_frame.iterators:
                    # First time encountering this loop
                    try:
                        condition_text = self.code_editor.document().findBlockByLineNumber(
                            node.lineno - 1).text().strip()
                        condition_text = condition_text.replace('while ', '').replace(':', '')
                    except:
                        condition_text = "condition"

                    loop_widget = SmartVariableWidget(f"while {condition_text}", f"condition: {test_result}")
                    self.canvas.add_item(loop_widget)
                    current_frame.iterators[loop_id] = {'widget': loop_widget, 'iteration': 0}

                loop_info = current_frame.iterators[loop_id]

                if test_result:
                    # Loop continues - inject body and then this loop node again
                    loop_info['iteration'] += 1
                    loop_info['widget'].update_value(f"Iteration {loop_info['iteration']}: {test_result}")

                    # Insert body + loop node back into execution
                    current_frame.nodes[current_frame.ip + 1:current_frame.ip + 1] = node.body + [node]
                else:
                    # Loop finished
                    loop_info['widget'].update_value(f"Loop finished: {test_result}")
                    del current_frame.iterators[loop_id]

                current_frame.ip += 1

            elif isinstance(node, ast.For):
                loop_id = id(node)

                if loop_id not in current_frame.iterators:
                    # Initialize for loop
                    try:
                        loop_text = self.code_editor.document().findBlockByLineNumber(node.lineno - 1).text().strip()
                        loop_text = loop_text.replace(':', '')
                    except:
                        loop_text = f"for {node.target.id} in iterable"

                    iterable = self._evaluate_expression(node.iter)
                    iterator = iter(iterable)

                    loop_widget = SmartVariableWidget(loop_text,
                                                      f"iterating over {len(list(iterable)) if hasattr(iterable, '__len__') else '?'} items")
                    self.canvas.add_item(loop_widget)

                    current_frame.iterators[loop_id] = {
                        'iterator': iterator,
                        'widget': loop_widget,
                        'iteration': 0,
                        'iterable': iterable
                    }

                loop_info = current_frame.iterators[loop_id]

                try:
                    # Get next item
                    item_val = next(loop_info['iterator'])
                    loop_info['iteration'] += 1

                    # Update loop variable in current frame
                    current_frame.locals[node.target.id] = item_val
                    self._update_variable(node.target.id, item_val)

                    # Update loop widget
                    loop_info['widget'].update_value(
                        f"Iteration {loop_info['iteration']}: {node.target.id} = {item_val}")

                    # Inject body + this loop node back for next iteration
                    current_frame.nodes[current_frame.ip + 1:current_frame.ip + 1] = node.body + [node]

                except StopIteration:
                    # Loop finished
                    loop_info['widget'].update_value("Loop completed")
                    del current_frame.iterators[loop_id]

                current_frame.ip += 1
        except Exception as e:
            print(f"Runtime Error on line {getattr(node, 'lineno', '?')}: {e}")
            self._finish_execution()
            return

        if self.is_running:
            self.step_timer.start(self.speed_interval)
    def _execute_assignment(self, node: Union[ast.Assign, ast.AugAssign]):
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
        input_vars_visitor = self.NameVisitor()
        for arg in node.args:
            input_vars_visitor.visit(arg)
        input_items = [frame.variable_widgets[name] for name in input_vars_visitor.names for frame in
                       reversed(self.call_stack) if name in frame.variable_widgets]
        try:
            text_on_line = self.code_editor.document().findBlockByLineNumber(node.lineno - 1).text()
            expression_str = text_on_line[text_on_line.find('(') + 1:text_on_line.rfind(')')].strip()
        except Exception:
            expression_str = "..."
        evaluated_args = [str(self._evaluate_expression(arg)) for arg in node.args]
        item = SmartPrintBlock(expression_str, " ".join(evaluated_args))
        self.canvas.add_item(item)
        for input_item in input_items:
            QTimer.singleShot(50, lambda ii=input_item, oi=item: self.canvas.add_connection(ii, oi))

    def _execute_call(self, node: ast.Call):
        func_name = node.func.id
        # Handle built-in functions that modify data structures
        if func_name in ('append', 'pop', 'remove') and isinstance(node.func, ast.Attribute):
            self._execute_method_call(node)
            return

        func_def = self.functions.get(func_name)
        if not func_def:
            # It might be a built-in we don't handle visually, so we just step over
            return

        evaluated_args = [self._evaluate_expression(arg) for arg in node.args]
        new_frame = CallFrame(func_name, func_def.body, node.lineno)
        param_names = [arg.arg for arg in func_def.args.args]
        new_frame.locals.update(zip(param_names, evaluated_args))
        scope_widget = ScopeWidget(f"Scope: {func_name}()")
        new_frame.scope_widget = scope_widget
        self.canvas.add_item(scope_widget)
        for name, value in new_frame.locals.items():
            self._update_variable(name, value, frame=new_frame)
        self.call_stack.append(new_frame)
        self._refresh_all_connections()

    def _execute_method_call(self, node: ast.Call):
        """A simplified handler for common list/dict method calls."""
        # Get the variable name (e.g., 'my_list' from 'my_list.append(1)')
        var_name = node.func.value.id
        method_name = node.func.attr

        # Evaluate arguments
        args = [self._evaluate_expression(arg) for arg in node.args]

        # Find the variable in the current scope
        for frame in reversed(self.call_stack):
            if var_name in frame.locals:
                target_var = frame.locals[var_name]
                if isinstance(target_var, list):
                    if method_name == 'append':
                        target_var.append(args[0])
                    elif method_name == 'pop':
                        target_var.pop(*args)
                # Update the visualization
                self._update_variable(var_name, target_var, frame=frame)
                break

    def _handle_return(self, value: Any):
        if len(self.call_stack) > 1:
            frame_to_pop = self.call_stack.pop()
            if frame_to_pop.scope_widget:
                frame_to_pop.scope_widget.remove_animated()
            self.return_value = value
        else:
            self.return_value = value
            self._finish_execution()

    def _update_variable(self, var_name: str, value: Any, frame: Optional[CallFrame] = None):
        current_frame = frame or self.call_stack[-1]
        current_frame.locals[var_name] = value
        item = None

        if var_name in current_frame.variable_widgets:
            widget = current_frame.variable_widgets[var_name]
            if isinstance(widget, ArrayWidget) and isinstance(value, list):
                widget.update_array(value)
                return
            elif isinstance(widget, StringWidget) and isinstance(value, str):
                widget.update_string(value)
                return
            elif isinstance(widget, DictionaryWidget) and isinstance(value, dict):
                # Simple recreation for dicts; can be improved with an update method
                pass
            elif isinstance(widget, SmartVariableWidget) and type(value) in (int, float, bool, type(None)):
                widget.update_value(value)
                return
            widget.remove_animated()

        if isinstance(value, list):
            item = ArrayWidget(var_name, value)
        elif isinstance(value, str):
            item = StringWidget(var_name, value)
        elif isinstance(value, dict):
            item = DictionaryWidget(var_name, value)
        else:
            item = SmartVariableWidget(var_name, value)

        if item:
            current_frame.variable_widgets[var_name] = item
            if current_frame.scope_widget:
                current_frame.scope_widget.addItem(item)
            else:
                self.canvas.add_item(item)

    def _evaluate_expression(self, node: ast.AST) -> Any:
        if node is None: return None
        # Literals
        if isinstance(node, ast.Constant): return node.value
        if isinstance(node, (ast.Num, ast.Str, ast.NameConstant)): return ast.literal_eval(node)

        # --- FIX: Added handlers for List, Tuple, and Dict literals ---
        if isinstance(node, ast.List):
            return [self._evaluate_expression(e) for e in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._evaluate_expression(e) for e in node.elts)
        if isinstance(node, ast.Dict):
            return {self._evaluate_expression(k): self._evaluate_expression(v) for k, v in zip(node.keys, node.values)}
        # --- END FIX ---

        if isinstance(node, ast.Name):
            for frame in reversed(self.call_stack):
                if frame.locals.get(node.id) is not None:
                    return frame.locals[node.id]
            raise NameError(f"name '{node.id}' is not defined")

        # Handle method calls (e.g., my_list.append)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            obj = self._evaluate_expression(node.func.value)
            args = [self._evaluate_expression(arg) for arg in node.args]
            return getattr(obj, node.func.attr)(*args)

        # Operations
        if isinstance(node, ast.BinOp):
            left = self._evaluate_expression(node.left)
            right = self._evaluate_expression(node.right)
            op_map = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
                      ast.Div: lambda a, b: a / b, ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b,
                      ast.Pow: lambda a, b: a ** b}
            return op_map[type(node.op)](left, right)

        if isinstance(node, ast.UnaryOp):
            operand = self._evaluate_expression(node.operand)
            op_map = {ast.UAdd: lambda x: +x, ast.USub: lambda x: -x, ast.Not: lambda x: not x}
            return op_map[type(node.op)](operand)

        if isinstance(node, ast.Compare):
            left = self._evaluate_expression(node.left)
            op = node.ops[0]
            right = self._evaluate_expression(node.comparators[0])
            op_map = {ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b, ast.Lt: lambda a, b: a < b,
                      ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b,
                      ast.Is: lambda a, b: a is b, ast.IsNot: lambda a, b: a is not b, ast.In: lambda a, b: a in b,
                      ast.NotIn: lambda a, b: a not in b}
            return op_map[type(op)](left, right)

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
        self.is_paused = False
        self.step_timer.stop()
        print("Visualization execution finished.")
        self.executionFinished.emit()

    def stop(self):
        if self.is_running:
            self.is_running = False
            self.is_paused = False
            self.step_timer.stop()
            self._clear_highlight()
            print("Visualization stopped by user.")

    def _refresh_all_connections(self):
        QTimer.singleShot(300, lambda: [conn.update_path() for conn in self.canvas.connections if
                                        hasattr(conn, 'update_path')])

    class NameVisitor(ast.NodeVisitor):
        def __init__(self):
            self.names: List[str] = []

        def visit_Name(self, node: ast.Name):
            if isinstance(node.ctx, ast.Load) and node.id not in self.names:
                self.names.append(node.id)
            self.generic_visit(node)

    class FunctionFinder(ast.NodeVisitor):
        def __init__(self):
            self.functions: Dict[str, ast.FunctionDef] = {}

        def visit_FunctionDef(self, node: ast.FunctionDef):
            self.functions[node.name] = node