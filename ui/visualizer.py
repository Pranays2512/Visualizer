import re
import ast
from html import escape
from PyQt5.QtCore import (QObject, QTimer, QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup,
                          pyqtProperty, QAbstractAnimation, Qt, QParallelAnimationGroup, QEvent)
from PyQt5.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit,
                             QGraphicsDropShadowEffect, QFrame, QGraphicsOpacityEffect, QApplication)
from PyQt5.QtGui import QFont, QTextCursor, QTextFormat, QColor

# --- UI Constants ---
FONT_FAMILY = "Fira Code"
ANIMATION_DURATION = 400
HIGHLIGHT_COLOR = QColor("#bd93f9")
GLOW_COLOR = QColor("#50fa7b")

VAR_DISPLAY_STYLE = """
QLabel {
    color: white;
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 10px;
    padding: 5px;
}
"""
FUNC_FRAME_STYLE = f"""
QFrame {{
    background-color: rgba(40, 42, 54, 0.8);
    border: 1px solid {HIGHLIGHT_COLOR.name()};
    border-radius: 10px;
}}
"""
TITLE_LABEL_STYLE = f"color: {HIGHLIGHT_COLOR.name()}; border: none; background: transparent; padding: 5px;"


class FunctionAnimation(QAbstractAnimation):
    """A custom animation class that simply calls a function when it runs."""
    def __init__(self, func, parent=None):
        super().__init__(parent)
        self._func, self._called = func, False
    def duration(self) -> int: return 0
    def updateCurrentTime(self, currentTime: int):
        if not self._called: self._func(); self._called = True


class AnimatableWidget(QWidget):
    """Base class for widgets that animate on creation and removal."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_animating = False

        self.setStyleSheet("background: transparent; border: none;")
        container_layout = QVBoxLayout(self)
        container_layout.setContentsMargins(0, 0, 0, 0)

        self.content_widget = QFrame(self)
        container_layout.addWidget(self.content_widget)

        self._setup_animations()
        self._setup_ui()

    def _setup_ui(self):
        raise NotImplementedError("Subclasses must implement _setup_ui")

    def _setup_animations(self):
        self.opacity_effect = QGraphicsOpacityEffect(self.content_widget)
        self.opacity_effect.setOpacity(0.0)
        self.content_widget.setGraphicsEffect(self.opacity_effect)

        fade_duration = ANIMATION_DURATION - 100
        # Creation
        self.creation_anim_group = QParallelAnimationGroup(self)
        self.creation_height_anim = QPropertyAnimation(self.content_widget, b"maximumHeight")
        self.creation_height_anim.setDuration(ANIMATION_DURATION)
        self.creation_height_anim.setEasingCurve(QEasingCurve.OutCubic)
        creation_fade = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        creation_fade.setDuration(fade_duration)
        creation_fade.setEndValue(1.0)
        self.creation_anim_group.addAnimation(self.creation_height_anim)
        self.creation_anim_group.addAnimation(creation_fade)
        self.creation_anim_group.finished.connect(self._on_animation_finished)
        # Removal
        self.removal_anim_group = QParallelAnimationGroup(self)
        self.removal_height_anim = QPropertyAnimation(self.content_widget, b"maximumHeight")
        self.removal_height_anim.setDuration(ANIMATION_DURATION)
        self.removal_height_anim.setEasingCurve(QEasingCurve.InCubic)
        removal_fade = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        removal_fade.setDuration(fade_duration)
        removal_fade.setEndValue(0.0)
        self.removal_anim_group.addAnimation(self.removal_height_anim)
        self.removal_anim_group.addAnimation(removal_fade)
        self.removal_anim_group.finished.connect(self.deleteLater)

    def _on_animation_finished(self):
        self.is_animating = False
        self.content_widget.setMaximumHeight(16777215)  # Unlock height

    def animate_creation(self):
        if self.is_animating: return
        self.is_animating = True
        QTimer.singleShot(0, self._do_creation_animation)

    def animate_removal(self):
        if self.is_animating: return
        self.is_animating = True
        if not self.parentWidget() or not self.parentWidget().isVisible():
            self.deleteLater()
            return
        self.removal_height_anim.setStartValue(self.content_widget.height())
        self.removal_height_anim.setEndValue(0)
        self.removal_anim_group.start()

    def _finalize_state(self):
        self.content_widget.setMaximumHeight(16777215)
        if self.opacity_effect: self.opacity_effect.setOpacity(1.0)
        self.update(); self.repaint()
        self.is_animating = False

    def _do_creation_animation(self):
        if not self.parentWidget().isVisible():
            self._finalize_state()
            return
        end_height = self.content_widget.sizeHint().height()
        self.content_widget.setMaximumHeight(0)
        self.creation_height_anim.setStartValue(0)
        self.creation_height_anim.setEndValue(end_height)
        self.creation_anim_group.start()


class VariableDisplay(AnimatableWidget):
    """A widget that displays a variable with a glow-on-update effect."""
    def __init__(self, name, value, parent=None):
        self.name, self.value = name, value
        self.glow_effect = None
        super().__init__(parent)
        self._setup_glow_animation()

    def _setup_ui(self):
        content_layout = QHBoxLayout(self.content_widget)
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(10)

        self.name_label = QLabel(f"{self.name} →", font=QFont(FONT_FAMILY, 10, QFont.Bold))
        self.name_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        self.name_label.setStyleSheet("color: #f8f8f2; background: transparent;")

        self.value_block = QLabel(str(self.value), font=QFont(FONT_FAMILY, 14))
        self.value_block.setAlignment(Qt.AlignCenter)
        self.value_block.setWordWrap(True)
        self.value_block.setMinimumSize(100, 50)
        self.value_block.setStyleSheet(VAR_DISPLAY_STYLE)

        content_layout.addWidget(self.name_label)
        content_layout.addWidget(self.value_block)

    def _setup_glow_animation(self):
        self.glow_animation = QPropertyAnimation(self, b"glow_intensity")
        self.glow_animation.setDuration(ANIMATION_DURATION - 100)
        self.glow_animation.setEasingCurve(QEasingCurve.OutQuad)
        self.glow_animation.finished.connect(self._on_glow_finished)

    def _on_glow_finished(self):
        if self.glow_animation.direction() == QPropertyAnimation.Forward:
            self.glow_animation.setDirection(QPropertyAnimation.Backward)
            self.glow_animation.start()
        else:
            if self.value_block and self.glow_effect:
                self.value_block.setGraphicsEffect(None)
            self.glow_effect = None

    def animate_value_update(self):
        self.glow_animation.stop()
        if not self.glow_effect:
            self.glow_effect = QGraphicsDropShadowEffect(self)
            self.glow_effect.setColor(GLOW_COLOR)
            self.glow_effect.setOffset(0, 0)
            self.value_block.setGraphicsEffect(self.glow_effect)
        self.glow_animation.setDirection(QPropertyAnimation.Forward)
        self.glow_animation.setStartValue(0)
        self.glow_animation.setEndValue(40)
        self.glow_animation.start()

    glow_intensity = pyqtProperty(int, lambda self: getattr(self, '_glow_intensity', 0),
                                  lambda self, v: self.glow_effect.setBlurRadius(v) if hasattr(self, 'glow_effect') and self.glow_effect else None)

    def set_value(self, value):
        if self.value != value:
            self.value = value
            self.value_block.setText(str(value))
            self.animate_value_update()


class FunctionFrame(AnimatableWidget):
    """A widget that displays a function call frame and its local variables."""
    def __init__(self, function_name, parent=None):
        self.function_name = function_name
        self.local_variables = {}
        super().__init__(parent)
        self.setMaximumWidth(400)

    def _setup_ui(self):
        self.content_widget.setFrameShape(QFrame.StyledPanel)
        self.content_widget.setStyleSheet(FUNC_FRAME_STYLE)
        frame_layout = QVBoxLayout(self.content_widget)
        frame_layout.setContentsMargins(10, 5, 10, 10)
        frame_layout.setSpacing(5)

        title_label = QLabel(f"Call: {self.function_name}", font=QFont(FONT_FAMILY, 12, QFont.Bold))
        title_label.setStyleSheet(TITLE_LABEL_STYLE)
        frame_layout.addWidget(title_label)

        self.locals_container = QWidget()
        self.locals_layout = QVBoxLayout(self.locals_container)
        self.locals_layout.setContentsMargins(10, 5, 0, 5)
        self.locals_layout.setSpacing(15)
        frame_layout.addWidget(self.locals_container)

    def _do_creation_animation(self):
        if not self.parentWidget().isVisible():
            self._finalize_state()
            return
        # Temporarily unlock child heights to calculate our final size correctly
        child_vars = self.findChildren(VariableDisplay)
        original_heights = {var: var.content_widget.maximumHeight() for var in child_vars}
        for var in child_vars: var.content_widget.setMaximumHeight(16777215)

        self.content_widget.layout().activate()
        end_height = self.content_widget.sizeHint().height()

        # Restore child heights for their own animations
        for var, height in original_heights.items(): var.content_widget.setMaximumHeight(height)

        self.content_widget.setMaximumHeight(0)
        self.creation_height_anim.setStartValue(0)
        self.creation_height_anim.setEndValue(end_height)
        self.creation_anim_group.start()

    def add_or_update_local_var(self, name, value):
        if name not in self.local_variables:
            var_widget = VariableDisplay(name, value, self)
            self.locals_layout.addWidget(var_widget)
            self.local_variables[name] = var_widget
            QTimer.singleShot(20, var_widget.animate_creation)
        else:
            self.local_variables[name].set_value(value)


class UIVisualizer(QObject):
    ITEM_SPACING = 15
    def __init__(self, parent, code_editor, canvas_widget):
        super().__init__(parent)
        self.code_editor, self.canvas = code_editor, canvas_widget
        self.variable_widgets, self.function_frames = {}, []
        self.output_display_widget = None
        self.animation_queue = QSequentialAnimationGroup()
        self.extra_selections, self.is_running = [], False
        self._setup_layout()
        QApplication.instance().installEventFilter(self)

    def _setup_layout(self):
        self.main_layout = QHBoxLayout(self.canvas)
        self.main_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.main_layout.setSpacing(40)
        self.left_column_layout = QVBoxLayout()
        self.left_column_layout.setAlignment(Qt.AlignTop)
        self.left_column_layout.setSpacing(self.ITEM_SPACING)
        self.right_column_layout = QVBoxLayout()
        self.right_column_layout.setAlignment(Qt.AlignTop)
        self.right_column_layout.setSpacing(self.ITEM_SPACING)
        self.main_layout.addLayout(self.left_column_layout)
        self.main_layout.addLayout(self.right_column_layout)
        self.main_layout.addStretch()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            elif item.layout(): self._clear_layout(item.layout())

    def start(self):
        if self.is_running: return
        self.is_running = True
        self.animation_queue.stop()
        self._clear_highlight()
        self._clear_layout(self.left_column_layout)
        self._clear_layout(self.right_column_layout)
        self.variable_widgets.clear(); self.function_frames.clear()
        self.output_display_widget = None
        self.animation_queue = QSequentialAnimationGroup()
        self.animation_queue.finished.connect(self._on_animation_finished)
        code = self.code_editor.toPlainText().strip()
        if code:
            self._build_animation_sequence(code)
            self.animation_queue.start()
        else: self.is_running = False

    def eventFilter(self, obj, event):
        if event.type() == QEvent.WindowStateChange:
            QTimer.singleShot(100, lambda: self.canvas.update() if self.canvas else None)
        return super().eventFilter(obj, event)

    def _on_animation_finished(self):
        self._clear_highlight(); self.is_running = False

    def _highlight_line(self, line_number):
        self._clear_highlight()
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(HIGHLIGHT_COLOR.lighter(130))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        block = self.code_editor.document().findBlockByLineNumber(line_number - 1)
        if block.isValid():
            selection.cursor = QTextCursor(block)
            self.extra_selections.append(selection)
            self.code_editor.setExtraSelections(self.extra_selections)

    def _clear_highlight(self):
        self.extra_selections.clear()
        self.code_editor.setExtraSelections(self.extra_selections)

    def _build_animation_sequence(self, code):
        try: TracingCodeVisitor(self).visit(ast.parse(code))
        except SyntaxError as e: self._add_print_animation(f'SyntaxError: {escape(str(e))}')

    def _find_func_def(self, name, call_stack):
        for scope in reversed(call_stack):
            if name in scope and isinstance(scope[name], ast.FunctionDef): return scope[name]
        return None

    def _evaluate_expression(self, expr_str, call_stack):
        try:
            merged_scope = {k: v for scope in call_stack for k, v in scope.items() if not isinstance(v, ast.AST)}
            return eval(expr_str, {"__builtins__": globals()['__builtins__']}, merged_scope)
        except Exception as e: return f"Error: {e}"

    def _add_assignment_animation(self, var_name, value, is_local):
        if is_local and self.function_frames:
            self.function_frames[-1].add_or_update_local_var(var_name, value)
        elif var_name not in self.variable_widgets:
            new_widget = VariableDisplay(var_name, value, self.canvas)
            self.variable_widgets[var_name] = new_widget
            self.left_column_layout.addWidget(new_widget)
            QTimer.singleShot(20, new_widget.animate_creation)
        else: self.variable_widgets[var_name].set_value(value)

    def _add_print_animation(self, result):
        if self.output_display_widget is None:
            self.output_display_widget = VariableDisplay("Prints", result, self.canvas)
            self.output_display_widget.value_block.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.right_column_layout.addWidget(self.output_display_widget)
            QTimer.singleShot(20, self.output_display_widget.animate_creation)
        else:
            self.output_display_widget.set_value(f"{self.output_display_widget.value}\n{result}")

    def _add_function_call_animation(self, frame):
        self.function_frames.append(frame)
        self.right_column_layout.addWidget(frame)
        QTimer.singleShot(20, frame.animate_creation)

    def _add_function_return_animation(self):
        if self.function_frames: self.function_frames.pop().animate_removal()


class TracingCodeVisitor(ast.NodeVisitor):
    def __init__(self, outer_visualizer):
        self.outer, self.call_stack = outer_visualizer, [{}]
        self.control_flow_signals = ('return', 'break', 'continue')

    @property
    def current_scope(self): return self.call_stack[-1]

    def _execute_body(self, body_nodes):
        for stmt in body_nodes:
            if isinstance(stmt, ast.AST):
                signal = self.visit(stmt)
                if signal and isinstance(signal, tuple) and signal[0] in self.control_flow_signals:
                    return signal
        return None

    def _handle_runtime_error(self, exception, context_message):
        error_message = f"Error in {context_message}: {escape(str(exception))}"
        self.outer.animation_queue.addAnimation(FunctionAnimation(lambda: self.outer._add_print_animation(error_message)))

    def visit_statement(self, node):
        if hasattr(node, 'lineno'):
            self.outer.animation_queue.addAnimation(FunctionAnimation(lambda: self.outer._highlight_line(node.lineno)))
            self.outer.animation_queue.addPause(150)

    def visit_FunctionDef(self, node):
        self.visit_statement(node)
        self.current_scope[node.name] = node

    def visit_Assign(self, node):
        self.visit_statement(node)
        value = self.visit(node.value) if isinstance(node.value, ast.Call) else self.outer._evaluate_expression(ast.unparse(node.value), self.call_stack)
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                self.current_scope[var_name] = value
                self.outer.animation_queue.addAnimation(FunctionAnimation(
                    lambda n=var_name, v=value: self.outer._add_assignment_animation(n, v, len(self.call_stack) > 1)))
                self.outer.animation_queue.addPause(50)

    def visit_AugAssign(self, node):
        self.visit_statement(node)
        if isinstance(node.target, ast.Name):
            op_map = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/', ast.Mod: '%'}
            if type(node.op) in op_map:
                var_name, op_str = node.target.id, op_map[type(node.op)]
                value_code = f"{var_name} {op_str} ({ast.unparse(node.value)})"
                value = self.outer._evaluate_expression(value_code, self.call_stack)
                self.current_scope[var_name] = value
                self.outer.animation_queue.addAnimation(FunctionAnimation(
                    lambda n=var_name, v=value: self.outer._add_assignment_animation(n, v, len(self.call_stack) > 1)))
                self.outer.animation_queue.addPause(50)

    def visit_Expr(self, node):
        self.visit_statement(node)
        if isinstance(node.value, ast.Call):
            if getattr(node.value.func, 'id', '') == 'print':
                result = ""
                if node.value.args:
                    result = str(self.outer._evaluate_expression(ast.unparse(node.value.args[0]), self.call_stack))
                self.outer.animation_queue.addAnimation(FunctionAnimation(lambda r=result: self.outer._add_print_animation(r)))
                self.outer.animation_queue.addPause(50)
            else: self.visit(node.value)

    def visit_Call(self, node):
        func_name = getattr(node.func, 'id', None)
        if not func_name: return self.outer._evaluate_expression(ast.unparse(node), self.call_stack)
        func_def = self.outer._find_func_def(func_name, self.call_stack)
        if func_def:
            frame = FunctionFrame(func_name, self.outer.canvas)
            new_scope = {arg.arg: self.outer._evaluate_expression(ast.unparse(val_node), self.call_stack)
                         for arg, val_node in zip(func_def.args.args, node.args)}
            for name, value in new_scope.items(): frame.add_or_update_local_var(name, value)
            self.outer.animation_queue.addAnimation(FunctionAnimation(lambda f=frame: self.outer._add_function_call_animation(f)))
            self.outer.animation_queue.addPause(150)
            self.call_stack.append(new_scope)
            return_value = None
            try:
                signal = self._execute_body(func_def.body)
                if signal and signal[0] == 'return': return_value = signal[1]
            except Exception as e: self._handle_runtime_error(e, f"function {func_name}")
            self.call_stack.pop()
            self.outer.animation_queue.addAnimation(FunctionAnimation(self.outer._add_function_return_animation))
            self.outer.animation_queue.addPause(150)
            return return_value
        return self.outer._evaluate_expression(ast.unparse(node), self.call_stack)

    def visit_Return(self, node):
        self.visit_statement(node)
        value = self.outer._evaluate_expression(ast.unparse(node.value), self.call_stack) if node.value else None
        return 'return', value

    def visit_If(self, node):
        self.visit_statement(node)
        try:
            result = self.outer._evaluate_expression(ast.unparse(node.test), self.call_stack)
            return self._execute_body(node.body if result else node.orelse)
        except Exception as e: self._handle_runtime_error(e, "if condition")
        return None

    def visit_Break(self, node): self.visit_statement(node); return 'break',
    def visit_Continue(self, node): self.visit_statement(node); return 'continue',

    def _loop_visitor(self, node, max_iter, condition_checker, body_executor):
        for i in range(max_iter):
            try:
                if not condition_checker(i): break
            except Exception as e:
                self._handle_runtime_error(e, "loop condition")
                break
            signal = body_executor(i)
            if signal:
                if signal[0] == 'return': return signal
                if signal[0] == 'break': break
                if signal[0] == 'continue': continue
        else: self.outer._add_print_animation(f"Loop stopped after {max_iter} iterations.")
        return None

    def visit_While(self, node):
        def condition_checker(_): return self.outer._evaluate_expression(ast.unparse(node.test), self.call_stack)
        def body_executor(_): self.visit_statement(node); return self._execute_body(node.body)
        return self._loop_visitor(node, 50, condition_checker, body_executor)

    def visit_For(self, node):
        if not isinstance(node.target, ast.Name): return None
        target_name = node.target.id
        try: iterable = self.outer._evaluate_expression(ast.unparse(node.iter), self.call_stack)
        except Exception as e: self._handle_runtime_error(e, "for loop iterable"); return None

        if isinstance(iterable, str) and "Error" in iterable:
            self.outer._add_print_animation(iterable)
            return None

        iterable = list(iterable)
        def condition_checker(i): return i < len(iterable)
        def body_executor(i):
            item = iterable[i]
            self.current_scope[target_name] = item
            self.outer.animation_queue.addAnimation(FunctionAnimation(
                lambda n=target_name, it=item: self.outer._add_assignment_animation(n, it, len(self.call_stack) > 1)))
            self.outer.animation_queue.addPause(50)
            self.visit_statement(node)
            return self._execute_body(node.body)
        return self._loop_visitor(node, 20, condition_checker, body_executor)

    def generic_visit(self, node):
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                signal = self._execute_body(value)
                if signal: return signal
            elif isinstance(value, ast.AST):
                signal = self.visit(value)
                if signal and isinstance(signal, tuple) and signal[0] in self.control_flow_signals:
                    return signal
        return None