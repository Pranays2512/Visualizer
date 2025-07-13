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
        return 0

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
        self.glow_effect = None
        self._setup_ui()
        self._setup_animations()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.name_label = QLabel(f"{self.name} →")
        self.name_label.setFont(QFont("Fira Code", 10, QFont.Bold))
        self.name_label.setAlignment(Qt.AlignVCenter)
        self.name_label.setStyleSheet("color: #f8f8f2; background: transparent;")

        self.value_block = QLabel(str(self.value))
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

    def _setup_animations(self):
        # Set up opacity effect for fade-in animation
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)

        # Create fade-in animation
        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(500)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.OutCubic)

        # Create scale animation
        self.scale_animation = QPropertyAnimation(self, b"geometry")
        self.scale_animation.setDuration(400)
        self.scale_animation.setEasingCurve(QEasingCurve.OutBack)

        # Create glow animation for value updates
        self.glow_animation = QPropertyAnimation(self, b"glow_intensity")
        self.glow_animation.setDuration(300)
        self.glow_animation.setStartValue(0)
        self.glow_animation.setEndValue(50)
        self.glow_animation.setEasingCurve(QEasingCurve.OutQuad)

    def animate_creation(self):
        """Animate the widget appearing for the first time."""
        # Start with 0 opacity
        self.opacity_effect.setOpacity(0.0)

        # Get final geometry
        final_geometry = self.geometry()

        # Start from a smaller size
        start_geometry = QRect(
            final_geometry.x() + final_geometry.width() // 4,
            final_geometry.y() + final_geometry.height() // 4,
            final_geometry.width() // 2,
            final_geometry.height() // 2
        )

        self.setGeometry(start_geometry)

        # Set up scale animation
        self.scale_animation.setStartValue(start_geometry)
        self.scale_animation.setEndValue(final_geometry)

        # Start both animations
        self.fade_in_animation.start()
        self.scale_animation.start()

    def animate_value_update(self):
        """Animate the widget when its value is updated."""
        # Create temporary glow effect
        if not self.glow_effect:
            self.glow_effect = QGraphicsDropShadowEffect(self)
            self.glow_effect.setBlurRadius(20)
            self.glow_effect.setColor(QColor("#50fa7b"))  # Green glow for updates
            self.glow_effect.setOffset(0, 0)
            self.value_block.setGraphicsEffect(self.glow_effect)

            # Remove glow after animation
            QTimer.singleShot(600, lambda: self.value_block.setGraphicsEffect(None))
            QTimer.singleShot(600, lambda: setattr(self, 'glow_effect', None))

    # Property for glow animation
    def _get_glow_intensity(self):
        return getattr(self, '_glow_intensity', 0)

    def _set_glow_intensity(self, value):
        self._glow_intensity = value
        if self.glow_effect:
            self.glow_effect.setBlurRadius(value)

    glow_intensity = pyqtProperty(int, _get_glow_intensity, _set_glow_intensity)

    def set_value(self, value):
        self.value = value
        self.value_block.setText(str(value))
        self.animate_value_update()  # Add animation for value updates

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
        self.setMaximumWidth(400)
        self._setup_ui(function_name)
        self._setup_animations()

    def _setup_ui(self, function_name):
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            FunctionFrame {
                background-color: rgba(40, 42, 54, 0.8);
                border: 1px solid #bd93f9;
                border-radius: 10px;
            }
        """)

        self.frame_layout = QVBoxLayout(self)
        self.frame_layout.setContentsMargins(10, 5, 10, 10)
        self.frame_layout.setSpacing(5)

        self.title_label = QLabel(f"Call: {function_name}", self)
        self.title_label.setFont(QFont("Fira Code", 12, QFont.Bold))
        self.title_label.setStyleSheet("color: #bd93f9; border: none; background: transparent; padding: 5px;")
        self.frame_layout.addWidget(self.title_label)

        self.locals_container = QWidget()
        self.locals_layout = QVBoxLayout(self.locals_container)
        self.locals_layout.setContentsMargins(10, 5, 0, 5)
        self.locals_layout.setSpacing(15)
        self.frame_layout.addWidget(self.locals_container)

    def _setup_animations(self):
        # Set up opacity effect for fade-in animation
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)

        # Create fade-in animation
        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(600)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.OutCubic)

        # Create slide animation
        self.slide_animation = QPropertyAnimation(self, b"geometry")
        self.slide_animation.setDuration(500)
        self.slide_animation.setEasingCurve(QEasingCurve.OutQuart)

    def animate_creation(self):
        """Animate the frame appearing for the first time."""
        # Start with 0 opacity
        self.opacity_effect.setOpacity(0.0)

        # Get final geometry
        final_geometry = self.geometry()

        # Start from the right (slide in from right)
        start_geometry = QRect(
            final_geometry.x() + 100,  # Start 100px to the right
            final_geometry.y(),
            final_geometry.width(),
            final_geometry.height()
        )

        self.setGeometry(start_geometry)

        # Set up slide animation
        self.slide_animation.setStartValue(start_geometry)
        self.slide_animation.setEndValue(final_geometry)

        # Start both animations
        self.fade_in_animation.start()
        self.slide_animation.start()

    def add_or_update_local_var(self, name, value):
        if name not in self.local_variables:
            var_widget = VariableDisplay(name, value, self)
            self.locals_layout.addWidget(var_widget)
            self.local_variables[name] = var_widget
            # Animate the new variable creation
            QTimer.singleShot(50, var_widget.animate_creation)  # Small delay for layout
        else:
            self.local_variables[name].set_value(value)


class UIVisualizer(QObject):
    """Manages a dynamic, animated visualization of Python code execution."""
    ITEM_SPACING = 15

    def __init__(self, parent, code_editor, canvas_widget):
        super().__init__(parent)
        self.code_editor = code_editor
        self.canvas = canvas_widget
        self.variable_widgets = {}
        self.function_frames = []
        self.output_display_widget = None
        self.animation_queue = QSequentialAnimationGroup()
        self.extra_selections = []
        self._setup_layout()

    def _setup_layout(self):
        self.main_layout = QHBoxLayout(self.canvas)
        self.main_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.main_layout.setSpacing(40)

        left_column_container = QWidget()
        self.left_column_layout = QVBoxLayout(left_column_container)
        self.left_column_layout.setAlignment(Qt.AlignTop)
        self.left_column_layout.setSpacing(self.ITEM_SPACING)

        right_column_container = QWidget()
        self.right_column_layout = QVBoxLayout(right_column_container)
        self.right_column_layout.setAlignment(Qt.AlignTop)
        self.right_column_layout.setSpacing(self.ITEM_SPACING)

        self.main_layout.addWidget(left_column_container)
        self.main_layout.addWidget(right_column_container)
        self.main_layout.addStretch()

    def _clear_layout(self, layout):
        """Helper function to recursively clear a layout of all widgets."""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def start(self):
        """Clears the canvas and starts a new visualization sequence."""
        self.animation_queue.stop()
        self._clear_highlight()
        self._clear_layout(self.left_column_layout)
        self._clear_layout(self.right_column_layout)

        self.variable_widgets.clear()
        self.function_frames.clear()
        self.output_display_widget = None

        self.animation_queue = QSequentialAnimationGroup()
        self.animation_queue.finished.connect(self._clear_highlight)

        code = self.code_editor.toPlainText().strip()
        if code:
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
            TracingCodeVisitor(self).visit(tree)
        except SyntaxError as e:
            self.animation_queue.addAnimation(
                FunctionAnimation(lambda: self._add_print_animation(f'"{escape(str(e))}"'))
            )

    def _find_func_def(self, name, call_stack):
        for scope in reversed(call_stack):
            if name in scope and isinstance(scope[name], ast.FunctionDef):
                return scope[name]
        return None

    def _evaluate_expression(self, expr_str, call_stack):
        try:
            merged_scope = {}
            for scope in call_stack:
                merged_scope.update(scope)
            return eval(expr_str, {"__builtins__": {"range": range}}, merged_scope)
        except Exception as e:
            return f"Error: {e}"

    def _add_assignment_animation(self, var_name, value, is_local):
        if is_local and self.function_frames:
            self.function_frames[-1].add_or_update_local_var(var_name, value)
        else:
            if var_name not in self.variable_widgets:
                new_widget = VariableDisplay(var_name, value, self.canvas)
                self.variable_widgets[var_name] = new_widget
                self.left_column_layout.addWidget(new_widget)
                # Animate the new variable creation
                QTimer.singleShot(50, new_widget.animate_creation)  # Small delay for layout
            else:
                self.variable_widgets[var_name].set_value(value)

    def _add_print_animation(self, result):
        if self.output_display_widget is None:
            self.output_display_widget = VariableDisplay("Prints", result, self.canvas)
            self.output_display_widget.value_block.setWordWrap(True)
            self.output_display_widget.value_block.setAlignment(Qt.AlignLeft)
            self.right_column_layout.addWidget(self.output_display_widget)
            # Animate the prints widget creation
            QTimer.singleShot(50, self.output_display_widget.animate_creation)
        else:
            current_text = self.output_display_widget.value
            self.output_display_widget.set_value(f"{current_text}\n{result}")

    def _add_function_call_animation(self, frame):
        self.function_frames.append(frame)
        self.right_column_layout.addWidget(frame)
        # Animate the function frame creation
        QTimer.singleShot(50, frame.animate_creation)

    def _add_function_return_animation(self):
        if self.function_frames:
            frame_to_remove = self.function_frames.pop()
            frame_to_remove.deleteLater()


class TracingCodeVisitor(ast.NodeVisitor):
    """AST visitor that builds the animation sequence."""

    def __init__(self, outer_visualizer):
        self.outer = outer_visualizer
        self.call_stack = [{}]

    @property
    def current_scope(self):
        return self.call_stack[-1]

    def visit_statement(self, node):
        """Adds a highlight animation for any statement node."""
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
            is_local = len(self.call_stack) > 1
            self.outer.animation_queue.addAnimation(
                FunctionAnimation(
                    lambda n=var_name, v=value, l=is_local: self.outer._add_assignment_animation(n, v, l))
            )

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
                is_local = len(self.call_stack) > 1
                self.outer.animation_queue.addAnimation(
                    FunctionAnimation(
                        lambda n=var_name, v=value, l=is_local: self.outer._add_assignment_animation(n, v, l))
                )

    def visit_Expr(self, node):
        self.visit_statement(node)
        if isinstance(node.value, ast.Call):
            func_name = getattr(node.value.func, 'id', '')
            if func_name == 'print':
                if node.value.args:
                    arg_code = ast.unparse(node.value.args[0])
                    result = self.outer._evaluate_expression(arg_code, self.call_stack)
                    self.outer.animation_queue.addAnimation(
                        FunctionAnimation(lambda r=result: self.outer._add_print_animation(r))
                    )
            else:
                self.visit_Call(node.value)

    def visit_Call(self, node):
        func_name = getattr(node.func, 'id', None)
        func_def = self.outer._find_func_def(func_name, self.call_stack)

        if func_name and isinstance(func_def, ast.FunctionDef):
            frame = FunctionFrame(func_name, self.outer.canvas)
            new_scope = {}
            arg_names = [arg.arg for arg in func_def.args.args]
            for i, arg_node in enumerate(node.args):
                if i < len(arg_names):
                    arg_value = self.outer._evaluate_expression(ast.unparse(arg_node), self.call_stack)
                    new_scope[arg_names[i]] = arg_value
                    frame.add_or_update_local_var(arg_names[i], arg_value)

            self.outer.animation_queue.addAnimation(
                FunctionAnimation(lambda f=frame: self.outer._add_function_call_animation(f))
            )
            self.call_stack.append(new_scope)

            return_value = None
            for stmt in func_def.body:
                signal = self.visit(stmt)
                if isinstance(signal, tuple) and signal[0] == 'return':
                    return_value = signal[1]
                    break

            self.call_stack.pop()
            self.outer.animation_queue.addAnimation(
                FunctionAnimation(self.outer._add_function_return_animation)
            )
            return return_value
        else:
            return self.outer._evaluate_expression(ast.unparse(node), self.call_stack)

    def visit_Return(self, node):
        self.visit_statement(node)
        value = None
        if node.value:
            value = self.outer._evaluate_expression(ast.unparse(node.value), self.call_stack)
        return ('return', value)

    def visit_If(self, node):
        self.visit_statement(node)
        condition_code = ast.unparse(node.test)
        result = self.outer._evaluate_expression(condition_code, self.call_stack)
        branch_to_visit = node.body if result else node.orelse
        for stmt in branch_to_visit:
            signal = self.visit(stmt)
            if signal:
                return signal
        return None

    def visit_Break(self, node):
        self.visit_statement(node)
        return ('break',)

    def visit_Continue(self, node):
        self.visit_statement(node)
        return ('continue',)

    def visit_While(self, node):
        max_iterations = 100
        count = 0
        condition_code = ast.unparse(node.test)
        while count < max_iterations and self.outer._evaluate_expression(condition_code, self.call_stack):
            self.visit_statement(node)
            signal = None
            for stmt in node.body:
                signal = self.visit(stmt)
                if signal:
                    break
            if signal and signal[0] == 'break':
                break
            if signal and signal[0] == 'return':
                return signal
            count += 1
        if count == max_iterations:
            self.outer.animation_queue.addAnimation(
                FunctionAnimation(
                    lambda: self.outer._add_print_animation(f"Loop stopped after {max_iterations} iterations."))
            )
        return None

    def visit_For(self, node):
        self.visit_statement(node)
        iter_code = ast.unparse(node.iter)
        target_name = node.target.id
        iterable = self.outer._evaluate_expression(iter_code, self.call_stack)
        if isinstance(iterable, str) and "Error" in iterable:
            self.outer.animation_queue.addAnimation(
                FunctionAnimation(lambda it=iterable: self.outer._add_print_animation(it))
            )
            return None

        is_local = len(self.call_stack) > 1
        for item in iterable:
            self.current_scope[target_name] = item
            self.outer.animation_queue.addAnimation(
                FunctionAnimation(
                    lambda n=target_name, i=item, l=is_local: self.outer._add_assignment_animation(n, i, l))
            )

            signal = None
            for stmt in node.body:
                signal = self.visit(stmt)
                if signal:
                    break

            if signal and signal[0] == 'break':
                break
            if signal and signal[0] == 'return':
                return signal
        return None

    def generic_visit(self, node):
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        signal = self.visit(item)
                        if signal:
                            return signal
            elif isinstance(value, ast.AST):
                signal = self.visit(value)
                if signal:
                    return signal
        return None