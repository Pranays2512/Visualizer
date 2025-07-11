import re
import ast
from html import escape
from PyQt5.QtCore import (QObject, QTimer, QPropertyAnimation, QRect, QEasingCurve,
                          QSequentialAnimationGroup, QPoint, pyqtProperty, QAbstractAnimation, Qt,
                          QParallelAnimationGroup)
from PyQt5.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit,
                             QGraphicsDropShadowEffect, QFrame, QGraphicsOpacityEffect)
from PyQt5.QtGui import QFont, QTextCursor, QTextFormat, QColor


class FunctionAnimation(QAbstractAnimation):
    """A custom animation class that simply calls a function when it runs."""

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self._func = func
        self._called = False

    def duration(self) -> int:
        return 0  # Instantaneous

    def updateCurrentTime(self, currentTime: int):
        if not self._called:
            self._func()
            self._called = True


class VariableDisplay(QWidget):
    """A widget to display a variable's name and its value in a styled block."""

    def __init__(self, name, value, parent=None):
        super().__init__(parent)
        self.name = name
        self.value = value

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.name_label = QLabel(f"{name} →")
        self.name_label.setFont(QFont("Fira Code", 10, QFont.Bold))
        self.name_label.setAlignment(Qt.AlignVCenter)
        self.name_label.setStyleSheet("color: #f8f8f2; background: transparent;")

        self.value_block = QLabel(str(value))
        self.value_block.setFont(QFont("Fira Code", 14))
        self.value_block.setAlignment(Qt.AlignCenter)
        self.value_block.setWordWrap(True)
        self.value_block.setMinimumSize(100, 50)
        self.value_block.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                padding: 5px;
            }
        """)

        layout.addWidget(self.name_label)
        layout.addWidget(self.value_block)
        self.setStyleSheet("background: transparent; border: none;")
        self.adjustSize()
        self.glow_effect = None

    def set_value(self, value):
        self.value = value
        self.value_block.setText(str(value))
        self.adjustSize()

    def glow(self, turn_on=True):
        if turn_on and not self.glow_effect:
            self.glow_effect = QGraphicsDropShadowEffect(self)
            self.glow_effect.setBlurRadius(35)
            self.glow_effect.setColor(QColor("#FFFFFF"))
            self.glow_effect.setOffset(0, 0)
            self.value_block.setGraphicsEffect(self.glow_effect)
        elif not turn_on and self.glow_effect:
            self.value_block.setGraphicsEffect(None)
            self.glow_effect = None


class FunctionFrame(QFrame):
    """A widget to visualize a single function call frame on the call stack."""

    def __init__(self, function_name, parent=None):
        super().__init__(parent)
        self.local_variables = {}
        self.next_var_pos = QPoint(10, 40)
        self.max_width = 350  # Prevent frames from getting too wide

        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(40, 42, 54, 0.8);
                border: 1px solid #bd93f9;
                border-radius: 10px;
            }
        """)

        self.title_label = QLabel(f"Call: {function_name}", self)
        self.title_label.setFont(QFont("Fira Code", 12, QFont.Bold))
        self.title_label.setStyleSheet("color: #bd93f9; border: none; background: transparent; padding: 5px;")
        self.title_label.adjustSize()
        self.title_label.move(5, 5)

    def add_or_update_local_var(self, name, value):
        if name not in self.local_variables:
            var_widget = VariableDisplay(name, value, self)
            var_widget.move(self.next_var_pos)
            var_widget.show()
            self.local_variables[name] = var_widget
            self.next_var_pos += QPoint(0, var_widget.sizeHint().height() + 15)
        else:
            self.local_variables[name].set_value(value)

        self.adjust_size()

    def adjust_size(self):
        max_w = self.title_label.width() + 20
        max_h = self.next_var_pos.y()
        for var in self.local_variables.values():
            max_w = max(max_w, var.x() + var.width() + 10)

        final_width = min(max_w, self.max_width)
        self.setFixedSize(final_width, max_h)


class UIVisualizer(QObject):
    """Manages a dynamic, animated visualization of Python code execution."""

    def __init__(self, parent, code_editor, canvas_widget):
        super().__init__(parent)
        self.code_editor = code_editor
        self.canvas = canvas_widget

        self.variable_widgets = {}
        self.output_display_widget = None
        self.function_frames = []
        self.animation_queue = QSequentialAnimationGroup()
        self.next_var_pos = QPoint(20, 20)
        self.current_column_width = 0
        self.extra_selections = []

    def start(self):
        self.animation_queue.stop()
        self._clear_highlight()

        for widget in self.variable_widgets.values():
            widget.deleteLater()
        for frame in self.function_frames:
            frame.deleteLater()
        if self.output_display_widget:
            self.output_display_widget.deleteLater()

        self.variable_widgets.clear()
        self.function_frames.clear()
        self.output_display_widget = None
        # Start global variables below the top area reserved for the output block
        self.next_var_pos = QPoint(20, 80)
        self.current_column_width = 0
        self.animation_queue = QSequentialAnimationGroup()
        self.animation_queue.finished.connect(self._clear_highlight)

        code = self.code_editor.toPlainText().strip()
        if not code:
            return

        self._build_animation_sequence(code)
        self.animation_queue.start()

    def _highlight_line(self, line_number):
        self._clear_highlight()
        selection = QTextEdit.ExtraSelection()
        highlight_color = QColor("#bd93f9")
        highlight_color.setAlpha(90)
        selection.format.setBackground(highlight_color)
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)

        block = self.code_editor.document().findBlockByLineNumber(line_number - 1)
        if block.isValid():
            selection.cursor = QTextCursor(block)
            self.extra_selections.append(selection)
            self.code_editor.setExtraSelections(self.extra_selections)

    def _clear_highlight(self):
        self.extra_selections = []
        self.code_editor.setExtraSelections(self.extra_selections)

    def _build_animation_sequence(self, code):
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            self._add_print_animation(f'"{escape(str(e))}"')
            return

        class TracingCodeVisitor(ast.NodeVisitor):
            def __init__(self, outer_visualizer):
                self.outer = outer_visualizer
                self.call_stack = [{}]  # Start with one global scope

            @property
            def current_scope(self):
                return self.call_stack[-1]

            def visit(self, node):
                method = 'visit_' + node.__class__.__name__
                visitor = getattr(self, method, self.generic_visit)
                result = visitor(node)
                return result

            def visit_statement(self, node):
                if hasattr(node, 'lineno'):
                    self.outer.animation_queue.addAnimation(
                        FunctionAnimation(lambda ln=node.lineno: self.outer._highlight_line(ln))
                    )
                    self.outer.animation_queue.addPause(200)

            def visit_FunctionDef(self, node):
                self.visit_statement(node)
                self.current_scope[node.name] = node

            def visit_Assign(self, node):
                self.visit_statement(node)
                value_node = node.value

                if isinstance(value_node, ast.Call):
                    value = self.visit_Call(value_node)
                else:
                    value = self.outer._evaluate_expression(ast.unparse(value_node), self.call_stack)

                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    var_name = node.targets[0].id
                    self.current_scope[var_name] = value
                    self.outer._add_assignment_animation(var_name, value, len(self.call_stack) > 1)

            def visit_AugAssign(self, node):
                self.visit_statement(node)
                if isinstance(node.target, ast.Name):
                    var_name = node.target.id
                    op_map = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/'}
                    if type(node.op) in op_map:
                        op_str = op_map[type(node.op)]
                        value_code = f"{var_name} {op_str} ({ast.unparse(node.value)})"
                        value = self.outer._evaluate_expression(value_code, self.call_stack)
                        self.current_scope[var_name] = value
                        self.outer._add_assignment_animation(var_name, value, len(self.call_stack) > 1)

            def visit_Expr(self, node):
                self.visit_statement(node)
                if isinstance(node.value, ast.Call):
                    func_name = getattr(node.value.func, 'id', '')
                    if func_name == 'print':
                        if node.value.args:
                            arg_code = ast.unparse(node.value.args[0])
                            result = self.outer._evaluate_expression(arg_code, self.call_stack)
                            self.outer._add_print_animation(result)
                    else:
                        self.visit_Call(node.value)  # It's a user function call

            def visit_Call(self, node):
                func_name = getattr(node.func, 'id', None)
                func_def = self.outer._find_func_def(func_name, self.call_stack)

                if func_name and isinstance(func_def, ast.FunctionDef):
                    # User-defined function call
                    # Pre-build the frame with arguments to get its size *before* animating
                    frame = FunctionFrame(func_name, self.outer.canvas)

                    new_scope = {}
                    arg_names = [arg.arg for arg in func_def.args.args]
                    for i, arg_node in enumerate(node.args):
                        if i < len(arg_names):
                            arg_value = self.outer._evaluate_expression(ast.unparse(arg_node), self.call_stack)
                            new_scope[arg_names[i]] = arg_value
                            # Add args to the frame widget immediately to calculate its final size
                            frame.add_or_update_local_var(arg_names[i], arg_value)

                    # Pass the fully-built frame to the animation method
                    self.outer._add_function_call_animation(frame)

                    self.call_stack.append(new_scope)

                    return_value = None
                    for stmt in func_def.body:
                        signal = self.visit(stmt)
                        if isinstance(signal, tuple) and signal[0] == 'return':
                            return_value = signal[1]
                            break

                    self.call_stack.pop()
                    self.outer._add_function_return_animation()
                    return return_value
                else:
                    # Built-in or unknown function
                    return self.outer._evaluate_expression(ast.unparse(node), self.call_stack)

            def visit_Return(self, node):
                self.visit_statement(node)
                value = None
                if node.value:
                    value = self.outer._evaluate_expression(ast.unparse(node.value), self.call_stack)
                return 'return', value

            def visit_If(self, node):
                self.visit_statement(node)
                condition_code = ast.unparse(node.test)
                result = self.outer._evaluate_expression(condition_code, self.call_stack)
                branch_to_visit = node.body if result else node.orelse
                for stmt in branch_to_visit:
                    signal = self.visit(stmt)
                    if signal: return signal
                return None

            def visit_Break(self, node):
                self.visit_statement(node)
                return 'break'

            def visit_Continue(self, node):
                self.visit_statement(node)
                return 'continue'

            def visit_While(self, node):
                max_iterations = 100
                count = 0
                condition_code = ast.unparse(node.test)
                while count < max_iterations and self.outer._evaluate_expression(condition_code, self.call_stack):
                    self.visit_statement(node)
                    signal = None
                    for stmt in node.body:
                        signal = self.visit(stmt)
                        if signal: break
                    if signal == 'break': break
                    if signal and signal[0] == 'return': return signal
                    count += 1
                if count == max_iterations:
                    self.outer._add_print_animation(f"Loop stopped after {max_iterations} iterations.")
                return None

            def visit_For(self, node):
                self.visit_statement(node)
                iter_code = ast.unparse(node.iter)
                target_name = node.target.id
                iterable = self.outer._evaluate_expression(iter_code, self.call_stack)
                if isinstance(iterable, str) and "Error" in iterable:
                    self.outer._add_print_animation(iterable)
                    return None
                for item in iterable:
                    self.current_scope[target_name] = item
                    self.outer._add_assignment_animation(target_name, item, len(self.call_stack) > 1)

                    signal = None
                    for stmt in node.body:
                        signal = self.visit(stmt)
                        if signal: break

                    if signal == 'break': break
                    if signal and signal[0] == 'return': return signal
                return None

            def generic_visit(self, node):
                for field, value in ast.iter_fields(node):
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, ast.AST):
                                signal = self.visit(item)
                                if signal: return signal
                    elif isinstance(value, ast.AST):
                        signal = self.visit(value)
                        if signal: return signal
                return None

        TracingCodeVisitor(self).visit(tree)

    def _find_func_def(self, name, call_stack):
        """Finds a function definition by searching the call stack from local to global."""
        for scope in reversed(call_stack):
            if name in scope and isinstance(scope[name], ast.FunctionDef):
                return scope[name]
        return None

    def _evaluate_expression(self, expr_str, call_stack):
        try:
            # Create a merged scope for evaluation, local overrides global
            merged_scope = {}
            for scope in call_stack:
                merged_scope.update(scope)
            return eval(expr_str, {"__builtins__": {"range": range}}, merged_scope)
        except Exception as e:
            return f"Error: {e}"

    def _add_assignment_animation(self, var_name, value, is_local):
        if is_local:
            # Assignment is in a function frame
            if self.function_frames:
                frame = self.function_frames[-1]
                self.animation_queue.addAnimation(
                    FunctionAnimation(lambda f=frame, n=var_name, v=value: f.add_or_update_local_var(n, v))
                )
        else:
            # Assignment is in the global scope
            if var_name not in self.variable_widgets:
                new_widget = VariableDisplay(var_name, value, self.canvas)
                new_widget.hide()
                self.variable_widgets[var_name] = new_widget
                widget_size = new_widget.sizeHint()
                self.current_column_width = max(self.current_column_width, widget_size.width())

                vertical_limit = self.canvas.height() - 20
                if self.next_var_pos.y() + widget_size.height() > vertical_limit and self.next_var_pos.y() > 80:
                    new_column_x = self.next_var_pos.x() + self.current_column_width + 20
                    self.next_var_pos.setX(new_column_x)
                    self.next_var_pos.setY(80)
                    self.current_column_width = widget_size.width()

                end_rect = QRect(self.next_var_pos, widget_size)
                start_rect = QRect(self.next_var_pos.x(), self.next_var_pos.y(), widget_size.width(), 0)
                self.next_var_pos += QPoint(0, widget_size.height() + 15)
                anim = QPropertyAnimation(new_widget, b"geometry")
                anim.setDuration(500)
                anim.setStartValue(start_rect)
                anim.setEndValue(end_rect)
                anim.setEasingCurve(QEasingCurve.OutBack)
                self.animation_queue.addPause(100)
                self.animation_queue.addAnimation(FunctionAnimation(new_widget.show))
                self.animation_queue.addAnimation(anim)
            else:
                var_widget = self.variable_widgets[var_name]
                self.animation_queue.addAnimation(FunctionAnimation(lambda w=var_widget: w.glow(True)))
                self.animation_queue.addPause(300)
                self.animation_queue.addAnimation(FunctionAnimation(lambda w=var_widget, v=value: w.set_value(v)))
                self.animation_queue.addPause(500)
                self.animation_queue.addAnimation(FunctionAnimation(lambda w=var_widget: w.glow(False)))
        self.animation_queue.addPause(200)

    def _add_print_animation(self, result):
        if self.output_display_widget is None:
            self.output_display_widget = VariableDisplay("Prints", result, self.canvas)

            # Match appearance with other VariableDisplay blocks
            self.output_display_widget.value_block.setWordWrap(True)
            self.output_display_widget.value_block.setAlignment(Qt.AlignCenter)
            self.output_display_widget.setMinimumSize(100, 50)

            # Calculate position below all other widgets to prevent overlap
            bottom_y = 20
            widgets = list(self.variable_widgets.values()) + self.function_frames
            if widgets:
                last_widget = widgets[-1]
                bottom_y = last_widget.y() + last_widget.height() + 20

            # Position at bottom-right within canvas
            max_width = self.canvas.width() * 0.4
            widget_size = self.output_display_widget.sizeHint()
            pos_x = self.canvas.width() - int(max_width) - 20
            pos_y = min(bottom_y, self.canvas.height() - widget_size.height() - 20)

            self.output_display_widget.setGeometry(pos_x, pos_y, int(max_width), widget_size.height())

            # Fade-in effect
            opacity_effect = QGraphicsOpacityEffect(self.output_display_widget)
            opacity_effect.setOpacity(0.0)
            self.output_display_widget.setGraphicsEffect(opacity_effect)
            self.output_display_widget.show()

            anim = QPropertyAnimation(opacity_effect, b"opacity")
            anim.setDuration(500)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            self.animation_queue.addAnimation(anim)
            self.animation_queue.addPause(200)

        self.animation_queue.addAnimation(FunctionAnimation(lambda: self.output_display_widget.glow(True)))
        self.animation_queue.addPause(300)
        self.animation_queue.addAnimation(FunctionAnimation(lambda r=result: self.output_display_widget.set_value(r)))
        self.animation_queue.addPause(500)
        self.animation_queue.addAnimation(FunctionAnimation(lambda: self.output_display_widget.glow(False)))
        self.animation_queue.addPause(200)

    def _add_function_call_animation(self, frame):
        """Animates a new function frame appearing on the call stack, handling scrolling."""
        frame.hide()
        self.function_frames.append(frame)

        # Position the first frame below the "Prints" block if it exists
        y_pos = 0
        if len(self.function_frames) > 1:
            # This is a subsequent frame, stack it below the previous one
            prev_frame = self.function_frames[-2]
            y_pos = prev_frame.y() + prev_frame.height() + 10
        else:
            # This is the first frame. Position it below the output block if it exists.
            y_pos = 20
            if self.output_display_widget:
                y_pos = self.output_display_widget.y() + self.output_display_widget.height() + 10

        # Frame is already sized correctly, so we can get its final position
        pos_x = self.canvas.width() - frame.width() - 20

        # Check if the new frame will overflow the canvas
        overflow = (y_pos + frame.height()) - self.canvas.height() + 20

        parallel_anim_group = QParallelAnimationGroup()

        if overflow > 0:
            # Animate all existing frames scrolling up
            for f in self.function_frames[:-1]:
                scroll_anim = QPropertyAnimation(f, b"pos")
                scroll_anim.setDuration(400)
                scroll_anim.setEndValue(f.pos() - QPoint(0, overflow))
                scroll_anim.setEasingCurve(QEasingCurve.InOutCubic)
                parallel_anim_group.addAnimation(scroll_anim)
            # Adjust the target y_pos for the new frame
            y_pos -= overflow

        # Set up the animation for the new frame
        frame.move(pos_x, y_pos)
        end_rect = frame.geometry()
        start_rect = QRect(self.canvas.width(), y_pos, end_rect.width(), end_rect.height())

        anim = QPropertyAnimation(frame, b"geometry")
        anim.setDuration(500)
        anim.setStartValue(start_rect)
        anim.setEndValue(end_rect)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        parallel_anim_group.addAnimation(anim)

        self.animation_queue.addAnimation(FunctionAnimation(frame.show))
        self.animation_queue.addAnimation(parallel_anim_group)
        self.animation_queue.addPause(200)

    def _add_function_return_animation(self):
        """Animates the top function frame disappearing from the call stack."""
        if not self.function_frames:
            return

        frame_to_remove = self.function_frames.pop()

        start_rect = frame_to_remove.geometry()
        end_rect = QRect(self.canvas.width(), start_rect.y(), start_rect.width(), start_rect.height())

        anim = QPropertyAnimation(frame_to_remove, b"geometry")
        anim.setDuration(500)
        anim.setStartValue(start_rect)
        anim.setEndValue(end_rect)
        anim.setEasingCurve(QEasingCurve.InCubic)

        self.animation_queue.addAnimation(anim)
        self.animation_queue.addAnimation(FunctionAnimation(frame_to_remove.deleteLater))
        self.animation_queue.addPause(200)