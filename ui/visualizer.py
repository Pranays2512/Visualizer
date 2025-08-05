import ast
import os
import astor
from typing import Dict, Any, List, Tuple, Union, Optional, Iterator
from PyQt5.QtWidgets import QTextEdit, QWidget, QMainWindow
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
        self.classes: Dict[str, ast.ClassDef] = {}  # Make sure this exists
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
        self.classes.clear()
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

    def set_input_sequence(self, inputs: List[str]):
        """Set a sequence of inputs for programs that require user input"""
        self.input_sequence = inputs.copy()

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

                # CHANGE: Fix condition text extraction
                if loop_id not in current_frame.iterators:
                    try:
                        # Use the actual line from code editor instead of astor
                        line_number = node.lineno - 1
                        condition_text = self.code_editor.document().findBlockByLineNumber(line_number).text().strip()
                        condition_text = condition_text.replace('while ', '').replace(':', '').strip()
                    except:
                        condition_text = "condition"

                    current_frame.iterators[loop_id] = {
                        'condition_text': condition_text,
                        'iteration': 0,
                        'widget': None,
                        'body_nodes': node.body.copy()  # ADD: Store body nodes
                    }

                loop_info = current_frame.iterators[loop_id]
                test_result = self._evaluate_expression(node.test)

                # CHANGE: Create widget only once and update it
                if loop_info['widget'] is None:
                    loop_info['widget'] = SmartVariableWidget(f"while {loop_info['condition_text']}", "Starting...")
                    self.canvas.add_item(loop_info['widget'])

                if test_result:
                    loop_info['iteration'] += 1
                    loop_info['widget'].update_value(f"Iteration {loop_info['iteration']}: {test_result}")

                    # ADD: Insert loop body nodes BEFORE current position, not AT current position
                    for i, body_node in enumerate(reversed(loop_info['body_nodes'])):
                        current_frame.nodes.insert(current_frame.ip + 1, body_node)

                    # ADD: Insert the while loop again after body for next iteration
                    current_frame.nodes.insert(current_frame.ip + len(loop_info['body_nodes']) + 1, node)
                else:
                    loop_info['widget'].update_value("Loop ended")
                    del current_frame.iterators[loop_id]

                current_frame.ip += 1
            elif isinstance(node, ast.ClassDef):
                self._execute_class_definition(node)
                current_frame.ip += 1



            elif isinstance(node, ast.For):

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
                        'body_nodes': node.body.copy()  # ADD: Store body nodes

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
                    # Update loop variable in current frame
                    current_frame.locals[node.target.id] = item_value
                    self._update_variable(node.target.id, item_value)
                    # Update loop widget
                    loop_info['widget'].update_value(
                        f"{loop_info['iteration']}/{len(loop_info['iterable_list'])}: {item_value}"
                    )

                    for i, body_node in enumerate(reversed(loop_info['body_nodes'])):
                        current_frame.nodes.insert(current_frame.ip + 1, body_node)
                    current_frame.nodes.insert(current_frame.ip + len(loop_info['body_nodes']) + 1, node)

                except StopIteration:
                    loop_info['widget'].update_value("Loop completed")
                    del current_frame.iterators[loop_id]
                current_frame.ip += 1
        except Exception as e:
            print(f"Runtime Error on line {getattr(node, 'lineno', '?')}: {e}")
            self._finish_execution()
            return

        if self.is_running:
            self.step_timer.start(self.speed_interval)

    def _execute_function_directly(self, func_def: ast.FunctionDef, args: List[Any]) -> Any:
        """Execute function with proper recursion visualization"""

        # Check recursion depth to prevent infinite loops
        current_recursion_depth = len([f for f in self.call_stack if func_def.name in f.name])
        MAX_RECURSION_DEPTH = 50  # Safety limit

        if current_recursion_depth > MAX_RECURSION_DEPTH:
            return None  # Or raise RecursionError

        # Create new frame for this function call
        new_frame = CallFrame(f"{func_def.name}", func_def.body)
        param_names = [arg.arg for arg in func_def.args.args]
        new_frame.locals.update(zip(param_names, args))

        # Create scope widget for recursion visualization
        scope_name = f"{func_def.name}({', '.join(map(str, args))})"
        if current_recursion_depth > 0:
            scope_name += f" [Depth {current_recursion_depth + 1}]"

        scope_widget = ScopeWidget(scope_name)
        new_frame.scope_widget = scope_widget
        self.canvas.add_item(scope_widget)

        # Show parameters in scope
        for name, value in new_frame.locals.items():
            self._update_variable(name, value, frame=new_frame)

        # Add to call stack
        self.call_stack.append(new_frame)

        try:
            # Execute function body step by step instead of all at once
            for stmt in func_def.body:
                if isinstance(stmt, ast.Return):
                    if stmt.value:
                        result = self._evaluate_expression(stmt.value)
                        # Show return value in scope
                        return_widget = SmartVariableWidget("return", result)
                        scope_widget.addItem(return_widget)
                        return result
                    else:
                        return None
                elif isinstance(stmt, ast.Assign):
                    value = self._evaluate_expression(stmt.value)
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            new_frame.locals[target.id] = value
                            self._update_variable(target.id, value, frame=new_frame)
                elif isinstance(stmt, ast.If):
                    # Handle conditional returns
                    test_result = self._evaluate_expression(stmt.test)
                    body_to_execute = stmt.body if test_result else stmt.orelse

                    for sub_stmt in body_to_execute:
                        if isinstance(sub_stmt, ast.Return):
                            if sub_stmt.value:
                                result = self._evaluate_expression(sub_stmt.value)
                                return_widget = SmartVariableWidget("return", result)
                                scope_widget.addItem(return_widget)
                                return result
                            else:
                                return None
                        elif isinstance(sub_stmt, ast.Assign):
                            value = self._evaluate_expression(sub_stmt.value)
                            for target in sub_stmt.targets:
                                if isinstance(target, ast.Name):
                                    new_frame.locals[target.id] = value
                                    self._update_variable(target.id, value, frame=new_frame)

            return None

        finally:
            # Clean up - remove frame from stack
            if new_frame in self.call_stack:
                self.call_stack.remove(new_frame)
            # Delay removal of scope widget for visualization
            if scope_widget:
                QTimer.singleShot(2000, scope_widget.remove_animated)
    def _execute_assignment_in_frame(self, stmt: ast.Assign, frame: CallFrame):
        """Execute assignment within a specific frame"""
        value = self._evaluate_expression(stmt.value)
        for target in stmt.targets:
            if isinstance(target, ast.Name):
                frame.locals[target.id] = value
                self._update_variable(target.id, value, frame=frame)

    def _execute_if_in_frame(self, stmt: ast.If, frame: CallFrame) -> Any:
        """Execute if statement within a frame, return any return value"""
        test_result = self._evaluate_expression(stmt.test)
        body_to_execute = stmt.body if test_result else stmt.orelse

        for sub_stmt in body_to_execute:
            if isinstance(sub_stmt, ast.Return):
                if sub_stmt.value:
                    return self._evaluate_expression(sub_stmt.value)
                else:
                    return None
            elif isinstance(sub_stmt, ast.Assign):
                self._execute_assignment_in_frame(sub_stmt, frame)

        return None

    def _execute_class_instantiation(self, class_name: str, args: List[Any]) -> Any:
        """Execute class instantiation with proper visualization"""
        if class_name not in self.classes:
            raise NameError(f"Class '{class_name}' not defined")

        class_def = self.classes[class_name]

        # Create instance object with proper attributes
        instance = type(class_name, (), {})()

        # Create visual representation immediately
        from .advanced_data_visualizer import ObjectWidget
        obj_widget = ObjectWidget(f"{class_name}_instance", instance)
        self.canvas.add_item(obj_widget)

        # Find and execute __init__ if it exists
        for node in class_def.body:
            if isinstance(node, ast.FunctionDef) and node.name == '__init__':
                # Execute __init__ in a temporary frame
                init_frame = CallFrame(f"{class_name}.__init__", node.body)
                init_frame.locals['self'] = instance

                # Set up parameters
                param_names = [arg.arg for arg in node.args.args[1:]]  # Skip 'self'
                for param, value in zip(param_names, args):
                    init_frame.locals[param] = value

                # Execute __init__ body
                self.call_stack.append(init_frame)
                try:
                    for stmt in node.body:
                        if isinstance(stmt, ast.Assign):
                            # Handle self.attribute = value
                            for target in stmt.targets:
                                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                                    if target.value.id == 'self':
                                        attr_value = self._evaluate_expression(stmt.value)
                                        setattr(instance, target.attr, attr_value)
                                        # Update visual representation
                                        obj_widget.update_object(instance)
                finally:
                    self.call_stack.pop()
                break

        return instance
    def _execute_class_instantiation(self, class_name: str, args: List[Any]) -> Any:
        """Properly instantiate and visualize class objects"""
        if class_name not in self.classes:
            # Try built-in classes
            if class_name in ['list', 'dict', 'set', 'tuple']:
                return eval(class_name)(*args)
            raise NameError(f"Class '{class_name}' not defined")

        class_def = self.classes[class_name]

        # Create instance object
        instance = type(class_name, (), {})()

        # Find and execute __init__ if it exists
        init_method = None
        for node in class_def.body:
            if isinstance(node, ast.FunctionDef) and node.name == '__init__':
                init_method = node
                break

        if init_method:
            # Execute __init__ with proper scope
            init_frame = CallFrame(f"{class_name}.__init__", init_method.body)
            init_frame.locals['self'] = instance

            # Set up parameters
            param_names = [arg.arg for arg in init_method.args.args[1:]]  # Skip 'self'
            for param, value in zip(param_names, args):
                init_frame.locals[param] = value

            # Execute __init__ body
            old_stack_len = len(self.call_stack)
            self.call_stack.append(init_frame)

            try:
                for stmt in init_method.body:
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                                if target.value.id == 'self':
                                    attr_value = self._evaluate_expression(stmt.value)
                                    setattr(instance, target.attr, attr_value)
            finally:
                if len(self.call_stack) > old_stack_len:
                    self.call_stack.pop()

        return instance

    def _call_function_directly(self, func_name: str, args: List[Any]) -> Any:
        """Directly execute a function call and return its result - SIMPLIFIED RECURSION"""
        func_def = self.functions.get(func_name)
        if not func_def:
            raise NameError(f"Function '{func_name}' not found")

        # Create a simple execution context
        local_vars = {}
        param_names = [arg.arg for arg in func_def.args.args]

        # Set up parameters
        for param, value in zip(param_names, args):
            local_vars[param] = value

        # Execute function body directly
        for stmt in func_def.body:
            if isinstance(stmt, ast.Return):
                if stmt.value:
                    # Temporarily add local vars to a mock frame for evaluation
                    temp_frame = CallFrame(f"{func_name}_temp", [])
                    temp_frame.locals = local_vars
                    self.call_stack.append(temp_frame)
                    try:
                        result = self._evaluate_expression(stmt.value)
                        return result
                    finally:
                        self.call_stack.pop()
                else:
                    return None
            elif isinstance(stmt, ast.If):
                # Handle if statements in function
                temp_frame = CallFrame(f"{func_name}_temp", [])
                temp_frame.locals = local_vars
                self.call_stack.append(temp_frame)
                try:
                    test_result = self._evaluate_expression(stmt.test)
                    body_to_execute = stmt.body if test_result else stmt.orelse

                    for sub_stmt in body_to_execute:
                        if isinstance(sub_stmt, ast.Return):
                            if sub_stmt.value:
                                result = self._evaluate_expression(sub_stmt.value)
                                return result
                            else:
                                return None
                        elif isinstance(sub_stmt, ast.Assign):
                            value = self._evaluate_expression(sub_stmt.value)
                            for target in sub_stmt.targets:
                                if isinstance(target, ast.Name):
                                    local_vars[target.id] = value
                finally:
                    self.call_stack.pop()
            elif isinstance(stmt, ast.Assign):
                # Handle assignments in function
                temp_frame = CallFrame(f"{func_name}_temp", [])
                temp_frame.locals = local_vars
                self.call_stack.append(temp_frame)
                try:
                    value = self._evaluate_expression(stmt.value)
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            local_vars[target.id] = value
                finally:
                    self.call_stack.pop()

        return None  # If no explicit return

    def _execute_recursive_function(self, func_name: str, args: List[Any]) -> Any:
        """Execute recursive function using Python's exec for proper recursion handling"""
        func_def = self.functions.get(func_name)
        if not func_def:
            raise NameError(f"Function '{func_name}' not found")

        # Convert AST back to code string
         # You might need to install this: pip install astor

        try:
            # Try using astor to convert AST to code
            func_code = astor.to_source(func_def)
        except:
            # Fallback: reconstruct function manually
            func_code = self._reconstruct_function_code(func_def)

        # Create execution environment with current variables
        exec_globals = {}
        exec_locals = {}

        # Add current variables to execution context
        for frame in reversed(self.call_stack):
            exec_locals.update(frame.locals)

        # Execute the function definition
        exec(func_code, exec_globals, exec_locals)

        # Call the function
        if func_name in exec_locals:
            return exec_locals[func_name](*args)
        elif func_name in exec_globals:
            return exec_globals[func_name](*args)
        else:
            raise NameError(f"Function {func_name} not found after execution")

    def _reconstruct_function_code(self, func_def: ast.FunctionDef) -> str:
        """Manually reconstruct function code from AST (fallback method)"""
        lines = []

        # Function signature
        params = [arg.arg for arg in func_def.args.args]
        signature = f"def {func_def.name}({', '.join(params)}):"
        lines.append(signature)

        # Function body - simplified reconstruction
        for stmt in func_def.body:
            if isinstance(stmt, ast.Return):
                if stmt.value:
                    # This is a simplified reconstruction - you might need to enhance this
                    if isinstance(stmt.value, ast.Constant):
                        lines.append(f"    return {stmt.value.value}")
                    elif isinstance(stmt.value, ast.Name):
                        lines.append(f"    return {stmt.value.id}")
                    elif isinstance(stmt.value, ast.BinOp):
                        # Handle simple binary operations
                        if isinstance(stmt.value.left, ast.Name) and isinstance(stmt.value.right, ast.Call):
                            left_name = stmt.value.left.id
                            if isinstance(stmt.value.right.func, ast.Name):
                                right_func = stmt.value.right.func.id
                                if isinstance(stmt.value.op, ast.Mult):
                                    # Handle n * factorial(n-1) pattern
                                    lines.append(f"    return {left_name} * {right_func}({left_name} - 1)")
                    else:
                        lines.append("    return None")
                else:
                    lines.append("    return None")
            elif isinstance(stmt, ast.If):
                # Simplified if statement reconstruction
                if isinstance(stmt.test, ast.Compare):
                    # Handle n <= 1 pattern
                    lines.append("    if n <= 1:")
                    for body_stmt in stmt.body:
                        if isinstance(body_stmt, ast.Return) and isinstance(body_stmt.value, ast.Constant):
                            lines.append(f"        return {body_stmt.value.value}")

        return '\n'.join(lines)

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

    def _execute_class_definition(self, node: ast.ClassDef):
        """Handle class definitions by storing them for later instantiation"""
        # Store the class definition
        self.classes[node.name] = node

        # Create a simple widget to show class was defined
        class_widget = SmartVariableWidget(f"class {node.name}", "defined")
        self.canvas.add_item(class_widget)

    def _execute_print(self, node: ast.Call):
        try:
            text_on_line = self.code_editor.document().findBlockByLineNumber(node.lineno - 1).text()
            expression_str = text_on_line[text_on_line.find('(') + 1:text_on_line.rfind(')')].strip()
        except Exception:
            expression_str = "..."

        evaluated_args = [str(self._evaluate_expression(arg)) for arg in node.args]
        item = SmartPrintBlock(expression_str, " ".join(evaluated_args))
        self.canvas.add_item(item)

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

        # Check if this is a recursive call
        recursion_depth = len([f for f in self.call_stack if func_name in f.name])

        new_frame = CallFrame(func_name, func_def.body, node.lineno)
        param_names = [arg.arg for arg in func_def.args.args]
        new_frame.locals.update(zip(param_names, evaluated_args))

        # Create scope widget with recursion depth indication
        scope_name = f"{func_name}()" if recursion_depth == 0 else f"{func_name}() - Recursive Call {recursion_depth + 1}"
        scope_widget = ScopeWidget(scope_name)
        new_frame.scope_widget = scope_widget
        self.canvas.add_item(scope_widget)

        # Show parameters
        for name, value in new_frame.locals.items():
            self._update_variable(name, value, frame=new_frame)

        self.call_stack.append(new_frame)

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

    def set_input_sequence(self, inputs: List[str]):
        """Set a sequence of inputs for programs that require user input"""
        self.input_sequence = inputs.copy()

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

        # Remove existing widget if it exists
        if var_name in current_frame.variable_widgets:
            widget = current_frame.variable_widgets[var_name]
            widget.remove_animated()

        # CREATE: Better type detection for trees
        item = None
        if isinstance(value, list):
            item = ArrayWidget(var_name, value)
        elif isinstance(value, str):
            item = StringWidget(var_name, value)
        elif isinstance(value, dict):
            # ADD: Check if it's a tree structure
            if self._is_tree_structure(value):
                from .advanced_data_visualizer import TreeWidget
                item = TreeWidget(var_name, value)
            else:
                item = DictionaryWidget(var_name, value)
        elif hasattr(value, '__dict__') and not callable(value):
            from .advanced_data_visualizer import ObjectWidget
            item = ObjectWidget(var_name, value)
        else:
            item = SmartVariableWidget(var_name, value)

        if item:
            current_frame.variable_widgets[var_name] = item
            if current_frame.scope_widget:
                current_frame.scope_widget.addItem(item)
            else:
                self.canvas.add_item(item)

    # ADD: Improve tree detection method (around line 380)
    def _is_tree_structure(self, data: dict) -> bool:
        """Enhanced tree structure detection"""
        if not isinstance(data, dict):
            return False

        # Check for common tree patterns
        tree_indicators = [
            {'value', 'left', 'right'},  # Binary tree
            {'data', 'children'},  # General tree
            {'val', 'left', 'right'},  # LeetCode style
            {'key', 'left', 'right'}  # BST
        ]

        data_keys = set(data.keys())
        for pattern in tree_indicators:
            if pattern.issubset(data_keys) or (
                    'value' in data_keys and any(k in data_keys for k in ['left', 'right', 'children'])):
                return True

        return False
    def _is_tree_structure(self, data: dict) -> bool:
            """Check if dictionary represents a tree structure"""
            if not isinstance(data, dict):
                return False

            # Simple heuristic: check if it has 'value' and 'left'/'right' keys
            required_keys = {'value'}
            optional_keys = {'left', 'right', 'children'}

            if not required_keys.issubset(data.keys()):
                return False

            return any(key in data for key in optional_keys)

    def _evaluate_expression(self, node: ast.AST) -> Any:
        if node is None:
            return None

        # Literals
        if isinstance(node, ast.Constant):
            return node.value
        # Handle f-strings (JoinedStr nodes)
        if isinstance(node, ast.JoinedStr):
            result = ""
            for value in node.values:
                if isinstance(value, ast.Constant):
                    result += str(value.value)
                elif isinstance(value, ast.FormattedValue):
                    # Evaluate the expression inside the f-string
                    expr_value = self._evaluate_expression(value.value)
                    # Handle format specification if present
                    if value.format_spec:
                        format_spec = self._evaluate_expression(value.format_spec)
                        result += format(expr_value, format_spec)
                    else:
                        result += str(expr_value)
                else:
                    # Fallback for other types
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

        # Function calls - THIS IS THE CRITICAL FIX
        # Around line 470, in the ast.Call handling section:
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                args = [self._evaluate_expression(arg) for arg in node.args]

                # ADD: Handle class instantiation properly
                if func_name in self.classes:
                    instance = self._execute_class_instantiation(func_name, args)
                    # CREATE: Visualization for the instance
                    return instance

                # Handle built-in functions
                if func_name in ['len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'tuple', 'range', 'print']:
                    if func_name == 'print':
                        print(*args)
                        return None
                    return eval(func_name)(*args)

                # Handle user-defined functions - FIXED RECURSION
                if func_name in self.functions:
                    func_def = self.functions[func_name]
                    return self._execute_function_directly(func_def, args)

                # Handle input function
                if func_name == 'input':
                    # ADD: Proper input handling
                    prompt = args[0] if args else "Enter input: "

                    if hasattr(self, 'input_sequence') and self.input_sequence:
                        user_input = self.input_sequence.pop(0)
                    else:
                        # Show input dialog for interactive input
                        from PyQt5.QtWidgets import QInputDialog
                        user_input, ok = QInputDialog.getText(
                            self.main_window,
                            'User Input Required',
                            str(prompt)
                        )
                        if not ok:
                            user_input = ""

                    # CREATE: Visual representation of input
                    input_widget = SmartVariableWidget("input()", f'"{user_input}"')
                    self.canvas.add_item(input_widget)

                    # ADD: Also show what was prompted
                    prompt_widget = SmartPrintBlock("prompt", str(prompt))
                    self.canvas.add_item(prompt_widget)

                    return user_input

                # If no other function matched, raise an error
                raise NameError(f"Function '{func_name}' not found")

            # Handle method calls
            elif isinstance(node.func, ast.Attribute):
                obj = self._evaluate_expression(node.func.value)
                args = [self._evaluate_expression(arg) for arg in node.args]
                method_name = node.func.attr

                if hasattr(obj, method_name):
                    method = getattr(obj, method_name)
                    if callable(method):
                        return method(*args)

                raise AttributeError(f"'{type(obj).__name__}' object has no attribute '{method_name}'")

        # Operations
        if isinstance(node, ast.BinOp):
            left = self._evaluate_expression(node.left)
            right = self._evaluate_expression(node.right)
            op_map = {
                ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
                ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
                ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b,
                ast.Pow: lambda a, b: a ** b
            }
            return op_map[type(node.op)](left, right)

        if isinstance(node, ast.UnaryOp):
            operand = self._evaluate_expression(node.operand)
            op_map = {ast.UAdd: lambda x: +x, ast.USub: lambda x: -x, ast.Not: lambda x: not x}
            return op_map[type(node.op)](operand)

        if isinstance(node, ast.Compare):
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

        # Handle subscripting (e.g., list[0])
        if isinstance(node, ast.Subscript):
            value = self._evaluate_expression(node.value)
            slice_value = self._evaluate_expression(node.slice)
            return value[slice_value]

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

    def _instantiate_class(self, class_name: str, args: List[ast.AST], keywords: List[ast.keyword]):
        """Create an instance of a user-defined class"""
        class_def = self.classes[class_name]

        # Evaluate arguments
        arg_values = [self._evaluate_expression(arg) for arg in args]

        # Create a simple object representation
        class_instance = type(class_name, (), {})()

        # Look for __init__ method in class
        init_method = None
        for node in class_def.body:
            if isinstance(node, ast.FunctionDef) and node.name == '__init__':
                init_method = node
                break

        # If __init__ exists, execute it
        if init_method:
            # Create frame for __init__
            init_frame = CallFrame(f"{class_name}.__init__", init_method.body)

            # Set up parameters (self + args)
            param_names = [arg.arg for arg in init_method.args.args]
            if param_names and param_names[0] == 'self':
                init_frame.locals['self'] = class_instance
                # Map remaining parameters to arguments
                for param, value in zip(param_names[1:], arg_values):
                    init_frame.locals[param] = value

            # Execute __init__ body (simplified - you might want to make this more robust)
            for stmt in init_method.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                            if target.value.id == 'self':
                                # Setting instance attribute
                                attr_value = self._evaluate_expression_in_frame(stmt.value, init_frame)
                                setattr(class_instance, target.attr, attr_value)

        return class_instance



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
