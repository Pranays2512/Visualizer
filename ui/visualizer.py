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

    def __init__(self, name: str, nodes: List[ast.stmt], lineno: int = 0, recursion_level: int = 0,
                 call_args: List[Any] = None):
        self.name = name
        self.nodes = nodes
        self.lineno = lineno
        self.ip: int = 0
        self.locals: Dict[str, Any] = {}
        self.variable_widgets: Dict[str, SmartVariableWidget] = {}
        self.scope_widget: Optional[ScopeWidget] = None
        self.iterators: Dict[int, Iterator] = {}
        self.recursion_level = recursion_level
        self.call_args = call_args or []
        self.return_value: Any = None
        self.is_recursive_call = recursion_level > 0
        self.call_trace_widget = None  # Widget to show the recursive call trace


class RecursionTracker:
    """Tracks recursive function calls and their relationships"""

    def __init__(self):
        self.call_tree: Dict[str, List[Dict]] = {}  # Function name -> list of calls
        self.max_depth = 8  # Reasonable recursion depth limit
        self.current_calls: Dict[str, int] = {}  # Function name -> current depth

    def can_recurse(self, func_name: str) -> bool:
        """Check if we can make another recursive call"""
        current_depth = self.current_calls.get(func_name, 0)
        return current_depth < self.max_depth

    def start_call(self, func_name: str, args: List[Any]) -> int:
        """Start a new function call, returns the recursion level"""
        current_depth = self.current_calls.get(func_name, 0)
        self.current_calls[func_name] = current_depth + 1

        if func_name not in self.call_tree:
            self.call_tree[func_name] = []

        call_info = {
            'level': current_depth,
            'args': args.copy(),
            'return_value': None,
            'timestamp': len(self.call_tree[func_name])
        }
        self.call_tree[func_name].append(call_info)

        return current_depth

    def end_call(self, func_name: str, return_value: Any):
        """End a function call and record its return value"""
        if func_name in self.current_calls and self.current_calls[func_name] > 0:
            self.current_calls[func_name] -= 1

            # Record return value in the most recent call
            if func_name in self.call_tree and self.call_tree[func_name]:
                self.call_tree[func_name][-1]['return_value'] = return_value

    def get_base_case_value(self, func_name: str, args: List[Any]) -> Any:
        """Get appropriate base case value for common recursive functions"""
        if func_name == 'factorial':
            n = args[0] if args else 1
            return 1 if n <= 1 else n
        elif func_name == 'fibonacci':
            n = args[0] if args else 1
            return n if n <= 1 else 1
        elif func_name == 'gcd':
            if len(args) >= 2:
                return args[0] if args[1] == 0 else 1
            return 1
        elif func_name == 'power':
            if len(args) >= 2:
                return 1 if args[1] == 0 else args[0]
            return 1
        else:
            return None

    def reset(self):
        """Reset the tracker for a new execution"""
        self.call_tree.clear()
        self.current_calls.clear()


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
        self.input_sequence = []

        # NEW: Recursion tracking
        self.recursion_tracker = RecursionTracker()
        self.recursion_widgets: Dict[str, Any] = {}  # Track recursion visualization widgets

        # CRITICAL FIX: Track whether we're in visualization mode or evaluation mode
        self.in_expression_evaluation = False

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
        self.in_expression_evaluation = False

        # Reset recursion tracking
        self.recursion_tracker.reset()
        self.recursion_widgets.clear()

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
            self._handle_return(current_frame.return_value)
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
            delay = int(self.speed_interval * 1.5) if current_frame.is_recursive_call else self.speed_interval
            self.step_timer.start(delay)

    def _handle_awaiting_return(self, current_frame):
        """Handle awaiting return value"""
        node_to_complete = self.awaiting_return_value
        self.awaiting_return_value = None

        print(
            f"HANDLE_AWAITING_RETURN: Processing return value {self.return_value} for node type {type(node_to_complete).__name__}")

        if isinstance(node_to_complete, ast.Assign):
            for target in node_to_complete.targets:
                if isinstance(target, ast.Name):
                    self._update_variable(target.id, self.return_value)
        elif isinstance(node_to_complete, ast.Expr):
            # This was a standalone expression call, just ignore the return value
            pass

        current_frame.ip += 1

    def update_computation_step(self, func_name: str, step_info: str):
        """Track intermediate computation steps"""
        if func_name in self.call_tree and self.call_tree[func_name]:
            current_call = self.call_tree[func_name][-1]
            if 'steps' not in current_call:
                current_call['steps'] = []
            current_call['steps'].append(step_info)

    def _execute_node(self, node: ast.stmt, current_frame: CallFrame):
        """Execute a single AST node"""
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            self._handle_assignment(node, current_frame)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            self._handle_expression_call(node, current_frame)
        elif isinstance(node, ast.Return):
            # Mark that we're evaluating an expression (which might contain function calls)
            was_in_evaluation = self.in_expression_evaluation
            self.in_expression_evaluation = True
            try:
                value = self._evaluate_expression(node.value) if node.value else None
            finally:
                self.in_expression_evaluation = was_in_evaluation

            current_frame.return_value = value
            # Show return value in recursion tracking
            if current_frame.is_recursive_call and current_frame.call_trace_widget:
                current_frame.call_trace_widget.update_value(
                    f"Level {current_frame.recursion_level}: {current_frame.call_args} → {value}"
                )
            current_frame.ip = len(current_frame.nodes)  # Jump to end
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
            # This is a function call assignment - use full visualization
            print(f"ASSIGNMENT CALL: Setting up awaiting return for {node.value.func.id}")
            self.awaiting_return_value = node
            self._execute_call(node.value)
            # DON'T increment IP here - it will be incremented after we get the return value
        else:
            self._execute_assignment(node)
            current_frame.ip += 1

    def _handle_expression_call(self, node: ast.Expr, current_frame: CallFrame):
        """Handle expression calls like print() or function calls"""
        call_node = node.value
        if isinstance(call_node.func, ast.Name):
            if call_node.func.id == 'print':
                self._execute_print(call_node)
                current_frame.ip += 1
            elif call_node.func.id in self.functions:
                # This is a standalone function call - use full visualization
                print(f"EXPRESSION CALL: Setting up awaiting return for {call_node.func.id}")
                self.awaiting_return_value = node
                self._execute_call(call_node)
                # DON'T increment IP here - it will be incremented after we get the return value
            else:
                current_frame.ip += 1
        else:
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
        # Mark that we're evaluating an expression (which might contain function calls)
        was_in_evaluation = self.in_expression_evaluation
        self.in_expression_evaluation = True
        try:
            value = self._evaluate_expression(node.value)
        finally:
            self.in_expression_evaluation = was_in_evaluation

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
        """Execute function calls with proper recursion handling and visualization"""
        func_name = node.func.id
        func_def = self.functions.get(func_name)
        if not func_def:
            return

        evaluated_args = [self._evaluate_expression(arg) for arg in node.args]

        print(f"EXECUTE_CALL: {func_name}({evaluated_args}) - in_expression_evaluation={self.in_expression_evaluation}")

        # Check if we can make this recursive call
        if not self.recursion_tracker.can_recurse(func_name):
            # Hit recursion limit - use base case
            base_value = self.recursion_tracker.get_base_case_value(func_name, evaluated_args)
            self.return_value = base_value

            # Create a base case visualization
            base_case_widget = SmartVariableWidget(
                f"{func_name}({', '.join(map(str, evaluated_args))})",
                f"Base case: {base_value}"
            )
            self.canvas.add_item(base_case_widget)
            return

        # Start tracking this call
        recursion_level = self.recursion_tracker.start_call(func_name, evaluated_args)

        print(f"Creating detailed function visualization for {func_name} with recursion_level {recursion_level}")

        # Create new frame with recursion info
        new_frame = CallFrame(
            func_name,
            func_def.body.copy(),
            node.lineno,
            recursion_level,
            evaluated_args
        )

        # Set up parameters
        param_names = [arg.arg for arg in func_def.args.args]
        new_frame.locals.update(zip(param_names, evaluated_args))

        # ALWAYS create visualization for function calls that come from the main execution flow
        # Create detailed function visualization
        scope_name = f"🔧 {func_name}({', '.join(map(str, evaluated_args))})"
        scope_widget = ScopeWidget(scope_name)
        new_frame.scope_widget = scope_widget
        self.canvas.add_item(scope_widget)

        print(f"Created scope widget: {scope_widget}")

        # Add function signature info
        signature_widget = SmartVariableWidget(
            f"Function: {func_name}",
            f"Parameters: {len(evaluated_args)}, Line: {func_def.lineno}"
        )
        scope_widget.addItem(signature_widget)
        print(f"Added signature widget to scope")

        # Show parameter mapping
        for param, value in zip(param_names, evaluated_args):
            param_widget = SmartVariableWidget(f"param {param}", str(value))
            scope_widget.addItem(param_widget)
            new_frame.variable_widgets[param] = param_widget
            print(f"Added parameter widget: {param}={value}")

        # Add the new frame to call stack
        self.call_stack.append(new_frame)

    def _might_be_recursive(self, func_def: ast.FunctionDef) -> bool:
        """Check if a function might be recursive by looking for self-calls"""
        for node in ast.walk(func_def):
            if (isinstance(node, ast.Call) and
                    isinstance(node.func, ast.Name) and
                    node.func.id == func_def.name):
                return True
        return False

    def _update_recursion_tree(self, func_name: str):
        """Update the recursion tree visualization with step-by-step breakdown"""
        if func_name not in self.recursion_widgets:
            return

        tree_widget = self.recursion_widgets[func_name]
        call_tree = self.recursion_tracker.call_tree.get(func_name, [])

        if call_tree:
            # Build visual tree showing the computation steps
            current_calls = [f for f in self.call_stack if f.name == func_name]
            active_level = len(current_calls) - 1 if current_calls else -1

            tree_lines = [f"📊 {func_name} Recursion Tree:"]

            for i, call_info in enumerate(call_tree):
                level = call_info['level']
                args = call_info['args']
                return_val = call_info.get('return_value', '?')

                # Create visual indentation
                indent = "  " * level
                branch = "├─" if i < len(call_tree) - 1 else "└─"

                # Show computation status
                if return_val == '?' and level <= active_level:
                    status = "🔄 Computing..."
                elif return_val != '?':
                    status = f"✅ = {return_val}"
                else:
                    status = "⏳ Pending..."

                tree_lines.append(f"{indent}{branch} {func_name}({', '.join(map(str, args))}) {status}")

                # Add intermediate steps for active computation
                if return_val == '?' and level == active_level:
                    current_frame = current_calls[level] if level < len(current_calls) else None
                    if current_frame and current_frame.locals:
                        for var_name, var_value in current_frame.locals.items():
                            if var_name not in [arg.arg for arg in self.functions[func_name].args.args]:
                                tree_lines.append(f"{indent}    💭 {var_name} = {var_value}")

            # Limit display to prevent overflow
            display_lines = tree_lines[-10:] if len(tree_lines) > 10 else tree_lines
            tree_widget.update_value("\n".join(display_lines))

    def _handle_return(self, value: Any):
        """Handle function returns with detailed recursion tracking"""
        if len(self.call_stack) > 1:
            frame_to_pop = self.call_stack.pop()

            print(f"HANDLE_RETURN: Returning from {frame_to_pop.name} with value {value}")

            # Enhanced recursion tracking with computation steps
            if frame_to_pop.is_recursive_call:
                self.recursion_tracker.end_call(frame_to_pop.name, value)

                # Show how the result was computed
                if frame_to_pop.call_trace_widget:
                    computation_summary = self._get_computation_summary(frame_to_pop, value)
                    frame_to_pop.call_trace_widget.update_value(
                        f"Level {frame_to_pop.recursion_level}: {frame_to_pop.call_args} → {value}\n{computation_summary}"
                    )

            # Update recursion tree with new return value
            if frame_to_pop.name in self.recursion_widgets:
                self._update_recursion_tree(frame_to_pop.name)

            # Keep scope visible longer for recursive calls to show the computation
            if frame_to_pop.scope_widget:
                if frame_to_pop.is_recursive_call:
                    QTimer.singleShot(2000, frame_to_pop.scope_widget.remove_animated)
                else:
                    frame_to_pop.scope_widget.remove_animated()

            self.return_value = value
        else:
            self.return_value = value
            self._finish_execution()

    def _get_computation_summary(self, frame: CallFrame, result: Any) -> str:
        """Generate a summary of how the result was computed"""
        func_name = frame.name
        args = frame.call_args

        # Common recursive function patterns
        if func_name == 'factorial' and len(args) >= 1:
            n = args[0]
            if n <= 1:
                return f"Base case: {n}! = 1"
            else:
                return f"Computed: {n} × {n - 1}! = {result}"

        elif func_name == 'fibonacci' and len(args) >= 1:
            n = args[0]
            if n <= 1:
                return f"Base case: fib({n}) = {n}"
            else:
                return f"Computed: fib({n - 1}) + fib({n - 2}) = {result}"

        else:
            # Generic computation summary
            local_vars = {k: v for k, v in frame.locals.items()
                          if k not in [arg.arg for arg in self.functions[func_name].args.args]}
            if local_vars:
                vars_str = ", ".join(f"{k}={v}" for k, v in list(local_vars.items())[:3])
                return f"Local vars: {vars_str}"
            return f"Returned: {result}"

    def _call_function_directly(self, func_name: str, args: List[Any]) -> Any:
        """Directly execute a function call and return its result - used for expression evaluation"""
        func_def = self.functions.get(func_name)
        if not func_def:
            raise NameError(f"Function '{func_name}' not found")

        print(f"CALL_FUNCTION_DIRECTLY: {func_name}({args}) - in_expression_evaluation={self.in_expression_evaluation}")

        # For direct calls (in expressions), use a simpler approach with recursion limits
        current_depth = len([f for f in self.call_stack if func_name in f.name])
        if current_depth > 8:
            return self.recursion_tracker.get_base_case_value(func_name, args)

        # Create a temporary execution context
        local_vars = dict(zip([arg.arg for arg in func_def.args.args], args))
        old_locals = {}

        if self.call_stack:
            old_locals = self.call_stack[-1].locals.copy()
            self.call_stack[-1].locals.update(local_vars)

        try:
            # Mark that we're in expression evaluation mode
            was_in_evaluation = self.in_expression_evaluation
            self.in_expression_evaluation = True

            for stmt in func_def.body:
                if isinstance(stmt, ast.Return):
                    result = self._evaluate_expression(stmt.value) if stmt.value else None
                    return result
                elif isinstance(stmt, ast.If):
                    test_result = self._evaluate_expression(stmt.test)
                    body_to_execute = stmt.body if test_result else stmt.orelse
                    for sub_stmt in body_to_execute:
                        if isinstance(sub_stmt, ast.Return):
                            result = self._evaluate_expression(sub_stmt.value) if sub_stmt.value else None
                            return result
        finally:
            self.in_expression_evaluation = was_in_evaluation
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

    def _update_variable(self, var_name: str, value: Any, frame: Optional[CallFrame] = None):
        """Update variable visualization"""
        current_frame = frame or self.call_stack[-1]
        current_frame.locals[var_name] = value

        # Remove old widget if it exists
        if var_name in current_frame.variable_widgets:
            current_frame.variable_widgets[var_name].remove_animated()

        item = self._create_variable_widget(var_name, value)

        if item:
            current_frame.variable_widgets[var_name] = item
            # This is the key part - add to function scope if it exists
            if current_frame.scope_widget:
                current_frame.scope_widget.addItem(item)
                print(f"Adding variable {var_name}={value} to scope widget")
            else:
                self.canvas.add_item(item)
                print(f"Adding variable {var_name}={value} to main canvas")

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

            print(f"EVALUATE_CALL: {func_name}({args}) - in_expression_evaluation={self.in_expression_evaluation}")

            if func_name in self.classes:
                return self._execute_class_instantiation(func_name, args)

            if func_name in ['len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'tuple', 'range', 'print']:
                if func_name == 'print':
                    print(*args)
                    return None
                return eval(func_name)(*args)

            if func_name in self.functions:
                # CRITICAL: Only use direct call if we're in expression evaluation mode
                # Otherwise, this should go through the full visualization pipeline
                if self.in_expression_evaluation:
                    print(f"Using direct call for {func_name} (in expression evaluation)")
                    current_depth = len([f for f in self.call_stack if func_name in f.name])
                    if current_depth > 10:
                        return self.recursion_tracker.get_base_case_value(func_name, args)
                    return self._call_function_directly(func_name, args)
                else:
                    print(f"ERROR: Function call {func_name} in expression but not in evaluation mode!")
                    # This means we have a function call in an expression that should be visualized
                    # For now, fall back to direct call to prevent infinite loops
                    current_depth = len([f for f in self.call_stack if func_name in f.name])
                    if current_depth > 10:
                        return self.recursion_tracker.get_base_case_value(func_name, args)
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