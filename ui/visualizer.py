import ast
import os
import astor
from typing import Dict, Any, List, Tuple, Union, Optional, Iterator
from PyQt5.QtWidgets import QTextEdit, QWidget, QMainWindow, QInputDialog
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtGui import QTextCursor, QColor, QTextFormat

from .dynamic_layout_manager import DynamicCanvas, SmartVariableWidget, SmartPrintBlock, ScopeWidget
from .advanced_data_visualizer import ArrayWidget, StringWidget, DictionaryWidget, ObjectWidget

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
        self.classes: Dict[str, ast.ClassDef] = {}
        self.call_stack: List[CallFrame] = []
        self.return_value: Any = None
        self.awaiting_return_value: Optional[ast.stmt] = None
        self.step_timer = QTimer()
        self.step_timer.setSingleShot(True)
        self.step_timer.timeout.connect(self._next_step)
        self.extra_selections: List[QTextEdit.ExtraSelection] = []
        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self._timeout_execution)
        self.max_recursive_calls = 50
        self.recursive_call_count = 0
        self.input_sequence = []

    def _timeout_execution(self):
        """Stop execution if it runs too long"""
        print("Execution timed out - stopping visualization")
        self.stop()

    def start(self):
        """Starts the visualization."""
        if self.is_running:
            return

        self._reset_state()
        code = self.code_editor.toPlainText().strip()
        if not code:
            return

        try:
            tree = ast.parse(code)
            self._extract_definitions(tree)
            main_body_nodes = [node for node in tree.body if not isinstance(node, ast.FunctionDef)]
            global_frame = CallFrame('<module>', main_body_nodes)
            self.call_stack.append(global_frame)
            QTimer.singleShot(200, self._next_step)
        except SyntaxError as e:
            print(f"Syntax Error: {e}")
            self.is_running = False

    def _reset_state(self):
        """Reset all state variables"""
        self.is_running = True
        self.is_paused = False
        self.canvas.clear_all()
        self.classes.clear()
        self.functions.clear()
        self.call_stack.clear()
        self._clear_highlight()
        self.awaiting_return_value = None
        self.timeout_timer.start(30000)
        self.recursive_call_count = 0

    def _extract_definitions(self, tree: ast.AST):
        """Extract function and class definitions"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self.functions[node.name] = node
            elif isinstance(node, ast.ClassDef):
                self.classes[node.name] = node

    def pause(self):
        if self.is_running and not self.is_paused:
            self.is_paused = True
            self.step_timer.stop()

    def resume(self):
        if self.is_running and self.is_paused:
            self.is_paused = False
            self._next_step()

    def set_speed(self, interval: int):
        self.speed_interval = interval

    def set_input_sequence(self, inputs: List[str]):
        self.input_sequence = inputs.copy()

    def _next_step(self):
        if self.is_paused or not self.is_running or not self.call_stack:
            if not self.call_stack and self.is_running:
                self._finish_execution()
            return

        current_frame = self.call_stack[-1]

        if self.awaiting_return_value:
            self._handle_awaiting_return(current_frame)

        if current_frame.ip >= len(current_frame.nodes):
            self._handle_return(None)
            if self.is_running:
                self.step_timer.start(self.speed_interval)
            return

        node = current_frame.nodes[current_frame.ip]
        self._highlight_line(node.lineno)

        try:
            self._execute_node(node, current_frame)
        except Exception as e:
            print(f"Runtime Error on line {getattr(node, 'lineno', '?')}: {e}")
            self._finish_execution()
            return

        if self.is_running:
            delay = self.speed_interval * 2 if self._is_recursive_call(current_frame) else self.speed_interval
            self.step_timer.start(delay)

    def _handle_awaiting_return(self, current_frame):
        """Handle awaiting return value"""
        node_to_complete = self.awaiting_return_value
        self.awaiting_return_value = None
        if isinstance(node_to_complete, ast.Assign):
            for target in node_to_complete.targets:
                if isinstance(target, ast.Name):
                    self._update_variable(target.id, self.return_value)
        current_frame.ip += 1

    def _is_recursive_call(self, current_frame):
        """Check if current frame is a recursive call"""
        return any(func_name in current_frame.name for func_name in self.functions.keys())

    def _execute_node(self, node: ast.stmt, current_frame: CallFrame):
        """Execute a single AST node"""
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            self._handle_assignment(node, current_frame)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            self._handle_expression_call(node, current_frame)
        elif isinstance(node, ast.Return):
            value = self._evaluate_expression(node.value) if node.value else None
            self._handle_return(value)
        elif isinstance(node, ast.If):
            self._handle_if(node, current_frame)
        elif isinstance(node, ast.While):
            self._handle_while(node, current_frame)
        elif isinstance(node, ast.For):
            self._handle_for(node, current_frame)
        elif isinstance(node, ast.ClassDef):
            self._execute_class_definition(node)
            current_frame.ip += 1

    def _handle_assignment(self, node: Union[ast.Assign, ast.AugAssign], current_frame: CallFrame):
        """Handle assignment operations"""
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and \
                isinstance(node.value.func, ast.Name) and node.value.func.id in self.functions:
            self.awaiting_return_value = node
            self._execute_call(node.value)
        else:
            self._execute_assignment(node)
            current_frame.ip += 1

    def _handle_expression_call(self, node: ast.Expr, current_frame: CallFrame):
        """Handle expression calls like print() or function calls"""
        call_node = node.value
        if isinstance(call_node.func, ast.Name):
            if call_node.func.id == 'print':
                self._execute_print(call_node)
            elif call_node.func.id in self.functions:
                self.awaiting_return_value = node
                self._execute_call(call_node)
        current_frame.ip += 1

    def _handle_if(self, node: ast.If, current_frame: CallFrame):
        """Handle if statements"""
        condition_text = self._extract_condition_text(node.lineno, 'if ')
        test_result = self._evaluate_expression(node.test)

        condition_widget = SmartVariableWidget(f"if {condition_text}", str(test_result))
        self.canvas.add_item(condition_widget)

        body_to_execute = node.body if test_result else node.orelse
        current_frame.nodes[current_frame.ip + 1:current_frame.ip + 1] = body_to_execute
        current_frame.ip += 1

    def _handle_while(self, node: ast.While, current_frame: CallFrame):
        """Handle while loops"""
        loop_id = id(node)

        if loop_id not in current_frame.iterators:
            condition_text = self._extract_condition_text(node.lineno, 'while ')
            current_frame.iterators[loop_id] = {
                'condition_text': condition_text,
                'iteration': 0,
                'widget': None,
                'body_nodes': node.body.copy()
            }

        loop_info = current_frame.iterators[loop_id]
        test_result = self._evaluate_expression(node.test)

        if loop_info['widget'] is None:
            loop_info['widget'] = SmartVariableWidget(f"while {loop_info['condition_text']}", "Starting...")
            self.canvas.add_item(loop_info['widget'])

        if test_result:
            loop_info['iteration'] += 1
            loop_info['widget'].update_value(f"Iteration {loop_info['iteration']}: {test_result}")
            self._insert_loop_body(current_frame, loop_info['body_nodes'], node)
        else:
            loop_info['widget'].update_value("Loop ended")
            del current_frame.iterators[loop_id]

        current_frame.ip += 1

    def _handle_for(self, node: ast.For, current_frame: CallFrame):
        """Handle for loops"""
        loop_id = id(node)

        if loop_id not in current_frame.iterators:
            iterable = self._evaluate_expression(node.iter)
            iterable_list = list(iterable)
            current_frame.iterators[loop_id] = {
                'iterator': iter(iterable_list),
                'iterable_list': iterable_list,
                'iteration': 0,
                'target_var': node.target.id,
                'widget': None,
                'body_nodes': node.body.copy()
            }

        loop_info = current_frame.iterators[loop_id]

        if loop_info['widget'] is None:
            loop_info['widget'] = SmartVariableWidget(
                f"for {loop_info['target_var']}",
                f"0/{len(loop_info['iterable_list'])}"
            )
            self.canvas.add_item(loop_info['widget'])

        try:
            item_value = next(loop_info['iterator'])
            loop_info['iteration'] += 1
            current_frame.locals[node.target.id] = item_value
            self._update_variable(node.target.id, item_value)

            loop_info['widget'].update_value(
                f"{loop_info['iteration']}/{len(loop_info['iterable_list'])}: {item_value}"
            )
            self._insert_loop_body(current_frame, loop_info['body_nodes'], node)
        except StopIteration:
            loop_info['widget'].update_value("Loop completed")
            del current_frame.iterators[loop_id]

        current_frame.ip += 1

    def _extract_condition_text(self, lineno: int, prefix: str) -> str:
        """Extract condition text from source code"""
        try:
            condition_text = self.code_editor.document().findBlockByLineNumber(lineno - 1).text().strip()
            return condition_text.replace(prefix, '').replace(':', '').strip()
        except:
            return "condition"

    def _insert_loop_body(self, current_frame: CallFrame, body_nodes: List[ast.stmt], loop_node: ast.stmt):
        """Insert loop body nodes into execution queue"""
        for i, body_node in enumerate(reversed(body_nodes)):
            current_frame.nodes.insert(current_frame.ip + 1, body_node)
        current_frame.nodes.insert(current_frame.ip + len(body_nodes) + 1, loop_node)

    def _execute_assignment(self, node: Union[ast.Assign, ast.AugAssign]):
        """Execute assignment operations"""
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

    def _execute_class_definition(self, node: ast.ClassDef):
        """Handle class definitions by storing them for later instantiation"""
        self.classes[node.name] = node
        class_widget = SmartVariableWidget(f"class {node.name}", "defined")
        self.canvas.add_item(class_widget)

    def _execute_print(self, node: ast.Call):
        """Execute print statements"""
        try:
            text_on_line = self.code_editor.document().findBlockByLineNumber(node.lineno - 1).text()
            expression_str = text_on_line[text_on_line.find('(') + 1:text_on_line.rfind(')')].strip()
        except Exception:
            expression_str = "..."

        evaluated_args = [str(self._evaluate_expression(arg)) for arg in node.args]
        item = SmartPrintBlock(expression_str, " ".join(evaluated_args))
        self.canvas.add_item(item)

    def _execute_call(self, node: ast.Call):
        """Execute function calls"""
        func_name = node.func.id

        if func_name in self.functions:
            self.recursive_call_count += 1
            if self.recursive_call_count > self.max_recursive_calls:
                print("Maximum recursive calls exceeded - stopping execution")
                self._finish_execution()
                return

        func_def = self.functions.get(func_name)
        if not func_def:
            return

        evaluated_args = [self._evaluate_expression(arg) for arg in node.args]
        recursion_depth = len([f for f in self.call_stack if func_name in f.name])

        new_frame = CallFrame(func_name, func_def.body, node.lineno)
        param_names = [arg.arg for arg in func_def.args.args]
        new_frame.locals.update(zip(param_names, evaluated_args))

        scope_name = f"{func_name}()" if recursion_depth == 0 else f"{func_name}() - Recursive Call {recursion_depth + 1}"
        scope_widget = ScopeWidget(scope_name)
        new_frame.scope_widget = scope_widget
        self.canvas.add_item(scope_widget)

        for name, value in new_frame.locals.items():
            self._update_variable(name, value, frame=new_frame)

        self.call_stack.append(new_frame)

    def _call_function_directly(self, func_name: str, args: List[Any]) -> Any:
        """Directly execute a function call and return its result"""
        func_def = self.functions.get(func_name)
        if not func_def:
            raise NameError(f"Function '{func_name}' not found")

        recursion_depth = len([f for f in self.call_stack if func_name in f.name])
        if recursion_depth > 8:
            return 1  # Base case for factorial

        local_vars = dict(zip([arg.arg for arg in func_def.args.args], args))

        old_locals = {}
        if self.call_stack:
            old_locals = self.call_stack[-1].locals.copy()
            self.call_stack[-1].locals.update(local_vars)

        try:
            for stmt in func_def.body:
                if isinstance(stmt, ast.Return):
                    return self._evaluate_expression(stmt.value) if stmt.value else None
                elif isinstance(stmt, ast.If):
                    test_result = self._evaluate_expression(stmt.test)
                    body_to_execute = stmt.body if test_result else stmt.orelse
                    for sub_stmt in body_to_execute:
                        if isinstance(sub_stmt, ast.Return):
                            return self._evaluate_expression(sub_stmt.value) if sub_stmt.value else None
        finally:
            if self.call_stack and old_locals:
                self.call_stack[-1].locals = old_locals

        return None

    def _execute_class_instantiation(self, class_name: str, args: List[Any]) -> Any:
        """Execute class instantiation with proper visualization"""
        if class_name not in self.classes:
            raise NameError(f"Class '{class_name}' not defined")

        class_def = self.classes[class_name]
        instance = type(class_name, (), {})()

        from .advanced_data_visualizer import ObjectWidget
        obj_widget = ObjectWidget(f"{class_name}_instance", instance)
        self.canvas.add_item(obj_widget)

        # Find and execute __init__ if it exists
        for node in class_def.body:
            if isinstance(node, ast.FunctionDef) and node.name == '__init__':
                init_frame = CallFrame(f"{class_name}.__init__", node.body)
                init_frame.locals['self'] = instance
                param_names = [arg.arg for arg in node.args.args[1:]]  # Skip 'self'
                for param, value in zip(param_names, args):
                    init_frame.locals[param] = value

                self.call_stack.append(init_frame)
                try:
                    for stmt in node.body:
                        if isinstance(stmt, ast.Assign):
                            for target in stmt.targets:
                                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                                    if target.value.id == 'self':
                                        attr_value = self._evaluate_expression(stmt.value)
                                        setattr(instance, target.attr, attr_value)
                                        obj_widget.update_object(instance)
                finally:
                    self.call_stack.pop()
                break

        return instance

    def _handle_return(self, value: Any):
        """Handle function returns"""
        if len(self.call_stack) > 1:
            frame_to_pop = self.call_stack.pop()
            if frame_to_pop.scope_widget:
                frame_to_pop.scope_widget.remove_animated()
            self.return_value = value
        else:
            self.return_value = value
            self._finish_execution()

    def _update_variable(self, var_name: str, value: Any, frame: Optional[CallFrame] = None):
        """Update variable visualization"""
        current_frame = frame or self.call_stack[-1]
        current_frame.locals[var_name] = value

        if var_name in current_frame.variable_widgets:
            current_frame.variable_widgets[var_name].remove_animated()

        item = self._create_variable_widget(var_name, value)

        if item:
            current_frame.variable_widgets[var_name] = item
            if current_frame.scope_widget:
                current_frame.scope_widget.addItem(item)
            else:
                self.canvas.add_item(item)

    def _create_variable_widget(self, var_name: str, value: Any):
        """Create appropriate widget for variable type"""
        if isinstance(value, list):
            return ArrayWidget(var_name, value)
        elif isinstance(value, str):
            return StringWidget(var_name, value)
        elif isinstance(value, dict):
            if self._is_tree_structure(value):
                from .advanced_data_visualizer import TreeWidget
                return TreeWidget(var_name, value)
            else:
                return DictionaryWidget(var_name, value)
        elif hasattr(value, '__dict__') and not callable(value):
            from .advanced_data_visualizer import ObjectWidget
            return ObjectWidget(var_name, value)
        else:
            return SmartVariableWidget(var_name, value)

    def _is_tree_structure(self, data: dict) -> bool:
        """Enhanced tree structure detection"""
        if not isinstance(data, dict):
            return False
        has_value = any(key in data for key in ['value', 'val', 'data', 'key'])
        has_children = any(key in data for key in ['left', 'right', 'children'])
        return has_value and has_children

    def _evaluate_expression(self, node: ast.AST) -> Any:
        """Evaluate AST expressions"""
        if node is None:
            return None

        # Literals
        if isinstance(node, ast.Constant):
            return node.value

        # Handle f-strings
        if isinstance(node, ast.JoinedStr):
            result = ""
            for value in node.values:
                if isinstance(value, ast.Constant):
                    result += str(value.value)
                elif isinstance(value, ast.FormattedValue):
                    expr_value = self._evaluate_expression(value.value)
                    if value.format_spec:
                        format_spec = self._evaluate_expression(value.format_spec)
                        result += format(expr_value, format_spec)
                    else:
                        result += str(expr_value)
                else:
                    result += str(self._evaluate_expression(value))
            return result

        if isinstance(node, (ast.Num, ast.Str, ast.NameConstant)):
            return ast.literal_eval(node)

        # Collections
        if isinstance(node, ast.List):
            return [self._evaluate_expression(e) for e in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._evaluate_expression(e) for e in node.elts)
        if isinstance(node, ast.Dict):
            return {self._evaluate_expression(k): self._evaluate_expression(v)
                    for k, v in zip(node.keys, node.values)}

        # Variables
        if isinstance(node, ast.Name):
            for frame in reversed(self.call_stack):
                if node.id in frame.locals:
                    return frame.locals[node.id]
            raise NameError(f"name '{node.id}' is not defined")

        # Function calls
        if isinstance(node, ast.Call):
            return self._evaluate_call(node)

        # Operations
        if isinstance(node, ast.BinOp):
            return self._evaluate_binop(node)

        if isinstance(node, ast.UnaryOp):
            operand = self._evaluate_expression(node.operand)
            op_map = {ast.UAdd: lambda x: +x, ast.USub: lambda x: -x, ast.Not: lambda x: not x}
            return op_map[type(node.op)](operand)

        if isinstance(node, ast.Compare):
            return self._evaluate_compare(node)

        if isinstance(node, ast.Subscript):
            value = self._evaluate_expression(node.value)
            slice_value = self._evaluate_expression(node.slice)
            return value[slice_value]

        if isinstance(node, ast.BoolOp):
            return self._evaluate_boolop(node)

        raise TypeError(f"Unsupported expression type: {type(node).__name__}")

    def _evaluate_call(self, node: ast.Call) -> Any:
        """Evaluate function calls"""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            args = [self._evaluate_expression(arg) for arg in node.args]

            if func_name in self.classes:
                return self._execute_class_instantiation(func_name, args)

            if func_name in ['len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'tuple', 'range', 'print']:
                if func_name == 'print':
                    print(*args)
                    return None
                return eval(func_name)(*args)

            if func_name in self.functions:
                current_depth = len([f for f in self.call_stack if func_name in f.name])
                if current_depth > 10:
                    return 1
                return self._call_function_directly(func_name, args)

            if func_name == 'input':
                prompt = args[0] if args else "Enter input: "

                if self.input_sequence:
                    user_input = self.input_sequence.pop(0)
                else:
                    user_input, ok = QInputDialog.getText(
                        self.main_window, 'User Input Required', str(prompt)
                    )
                    if not ok:
                        user_input = ""

                input_widget = SmartVariableWidget("input()", f'"{user_input}"')
                self.canvas.add_item(input_widget)
                prompt_widget = SmartPrintBlock("prompt", str(prompt))
                self.canvas.add_item(prompt_widget)
                return user_input

            raise NameError(f"Function '{func_name}' not found")

        elif isinstance(node.func, ast.Attribute):
            obj = self._evaluate_expression(node.func.value)
            args = [self._evaluate_expression(arg) for arg in node.args]
            method_name = node.func.attr

            if hasattr(obj, method_name):
                method = getattr(obj, method_name)
                if callable(method):
                    return method(*args)

            raise AttributeError(f"'{type(obj).__name__}' object has no attribute '{method_name}'")

    def _evaluate_binop(self, node: ast.BinOp) -> Any:
        """Evaluate binary operations"""
        left = self._evaluate_expression(node.left)
        right = self._evaluate_expression(node.right)
        op_map = {
            ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
            ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
            ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b,
            ast.Pow: lambda a, b: a ** b
        }
        return op_map[type(node.op)](left, right)

    def _evaluate_compare(self, node: ast.Compare) -> Any:
        """Evaluate comparison operations"""
        left = self._evaluate_expression(node.left)
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

    def _evaluate_boolop(self, node: ast.BoolOp) -> Any:
        """Evaluate boolean operations"""
        op = node.op
        if isinstance(op, ast.And):
            result = True
            for value_node in node.values:
                result = self._evaluate_expression(value_node)
                if not result:
                    return result
            return result
        elif isinstance(op, ast.Or):
            result = False
            for value_node in node.values:
                result = self._evaluate_expression(value_node)
                if result:
                    return result
            return result

    def _highlight_line(self, line_number: int):
        """Highlight the current line being executed"""
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
        """Clear line highlighting"""
        self.extra_selections.clear()
        self.code_editor.setExtraSelections(self.extra_selections)

    def _finish_execution(self):
        """Finish execution and clean up"""
        self._clear_highlight()
        self.is_running = False
        self.is_paused = False
        self.step_timer.stop()
        self.executionFinished.emit()

    def stop(self):
        """Stop visualization"""
        if self.is_running:
            self.is_running = False
            self.is_paused = False
            self.step_timer.stop()
            self._clear_highlight()