import ast
import sys
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from html import escape  # Correctly imported

# --- UI Constants ---
FONT_FAMILY = "Fira Code"  # Adjust if not available. E.g., "Monaco", "Consolas", "Courier New".
ANIMATION_DURATION = 250  # Reduced animation duration for snappier feel
HIGHLIGHT_COLOR = QColor("#bd93f9")
GLOW_COLOR = QColor("#50fa7b")
CYAN_COLOR = QColor("#8be9fd")
PINK_COLOR = QColor("#ff79c6")

# Styles
BLOCK_STYLE = """
QFrame {
    background-color: rgba(40, 42, 54, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 10px;
    padding: 10px;
}
"""

VAR_STYLE = """
QLabel {
    color: white;
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    padding: 8px;
    min-width: 120px; /* Ensure minimum width for variables */
    max-width: 200px; /* Control max width to prevent overflow */
}
"""

OUTPUT_STYLE = """
QTextEdit {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    color: #f8f8f2;
    padding: 5px;
}
"""


class SimpleBlock(QFrame):
    """Base class for all visualization blocks"""

    def __init__(self, title: str, color: QColor, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet(BLOCK_STYLE)
        self.setMaximumWidth(350)  # Maintain consistent width for blocks

        # Main layout for title and content
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(12, 12, 12, 12)

        # Title label
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.title_label.setStyleSheet(f"color: {color.name()}; background: transparent; border: none;")
        self.layout.addWidget(self.title_label)

        # Content area widget (where variables/output/logic text will go)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)  # Layout for content items
        self.content_layout.setSpacing(8)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.content_widget)

        # Animation effect (opacity)
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)

        # Fade in animation
        self.fade_in_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_anim.setDuration(ANIMATION_DURATION)  # Use ANIMATION_DURATION
        self.fade_in_anim.setStartValue(0.0)
        self.fade_in_anim.setEndValue(1.0)
        self.fade_in_anim.setEasingCurve(QEasingCurve.OutQuad)

        # Fade out animation
        self.fade_out_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out_anim.setDuration(ANIMATION_DURATION)  # Use ANIMATION_DURATION
        self.fade_out_anim.setStartValue(1.0)
        self.fade_out_anim.setEndValue(0.0)
        self.fade_out_anim.setEasingCurve(QEasingCurve.InQuad)
        self.fade_out_anim.finished.connect(self.hide)  # Hide widget after fade out

        # Start hidden and transparent
        self.opacity_effect.setOpacity(0.0)
        self.hide()

    def show_animated(self):
        """Show the block with fade-in animation"""
        self.show()
        self.fade_in_anim.start()

    def hide_animated(self):
        """Hide the block with fade-out animation"""
        self.fade_out_anim.start()

    def clear_content(self):
        """Clear all content widgets from the content layout"""
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.updateGeometry()  # Force geometry update after clearing


class VariableBlock(SimpleBlock):
    """Block for displaying variables"""

    def __init__(self, title: str, color: QColor, parent=None):
        super().__init__(title, color, parent)
        self.variables: Dict[str, QLabel] = {}

    def update_variable(self, name: str, value: Any):
        """Update or add a variable"""
        value_str = str(value)
        # FIX: Ensure value_str is always a string before escaping
        display_value = escape(value_str)  # Escape value for display if it contains HTML sensitive chars

        if len(display_value) > 30:  # Truncate long values
            display_value = display_value[:27] + "..."

        # Create a horizontal layout for name and value if not already done
        if name not in self.variables:
            var_widget = QWidget()
            var_layout = QHBoxLayout(var_widget)
            var_layout.setContentsMargins(0, 0, 0, 0)
            var_layout.setSpacing(5)

            name_label = QLabel(f"{name} =")
            name_label.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
            name_label.setStyleSheet("color: #f8f8f2; background: transparent;")
            name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            value_label = QLabel(display_value)  # Use escaped value here
            value_label.setFont(QFont(FONT_FAMILY, 10))
            value_label.setStyleSheet("color: white; background: transparent;")
            value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            value_label.setWordWrap(True)

            var_layout.addWidget(name_label)
            var_layout.addWidget(value_label, 1)  # Value takes expanding space

            var_widget.setStyleSheet(VAR_STYLE)  # Apply style to the whole variable widget
            self.content_layout.addWidget(var_widget)  # Add var_widget, not var_label
            self.variables[name] = value_label  # Store reference to the value label to update it
        else:
            # Update existing variable's value label
            self.variables[name].setText(display_value)  # Use escaped value here

        self._glow_variable(name)
        self.updateGeometry()  # Force parent to re-evaluate its size based on new content

    def _glow_variable(self, name: str):
        """Add glow effect to variable when updated"""
        if name in self.variables:
            # Get the parent QWidget for the variable (the one with VAR_STYLE)
            value_label = self.variables[name]
            var_widget = value_label.parentWidget()  # The QWidget holding name_label and value_label

            if var_widget:
                glow_effect = QGraphicsDropShadowEffect()
                glow_effect.setColor(GLOW_COLOR)
                glow_effect.setBlurRadius(15)
                glow_effect.setOffset(0, 0)
                var_widget.setGraphicsEffect(glow_effect)

                QTimer.singleShot(ANIMATION_DURATION * 2,
                                  lambda: var_widget.setGraphicsEffect(None))  # Reduced glow duration


class OutputBlock(SimpleBlock):
    """Block for displaying output"""

    def __init__(self, parent=None):
        super().__init__("Output", PINK_COLOR, parent)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setFont(QFont(FONT_FAMILY, 10))
        self.text_area.setStyleSheet(OUTPUT_STYLE)
        self.text_area.setMaximumHeight(200)  # Keep max height for scrolling

        self.content_layout.addWidget(self.text_area)

    def add_output(self, text: str):
        """Add text to output"""
        # FIX: Ensure text is escaped before adding to QTextEdit to prevent HTML interpretation
        self.text_area.append(escape(text))
        # Auto-scroll to bottom
        scrollbar = self.text_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self.updateGeometry()  # Force parent to re-evaluate its size (if it can grow)

    def clear_output(self):
        """Clear all output"""
        self.text_area.clear()
        self.updateGeometry()


class FunctionBlock(SimpleBlock):
    """Block for displaying function calls and their local variables"""

    def __init__(self, func_name: str, parent=None):
        super().__init__(f"Call: {func_name}", HIGHLIGHT_COLOR, parent)
        self.func_name = func_name
        self.variables: Dict[str, QLabel] = {}

    def update_local_var(self, name: str, value: Any):
        """Update local variable in function"""
        value_str = str(value)
        # FIX: Ensure value_str is always a string before escaping
        display_value = escape(value_str)  # Escape value for display

        if len(display_value) > 25:  # Truncate long values
            display_value = display_value[:22] + "..."

        if name not in self.variables:
            var_widget = QWidget()
            var_layout = QHBoxLayout(var_widget)
            var_layout.setContentsMargins(0, 0, 0, 0)
            var_layout.setSpacing(5)

            name_label = QLabel(f"{name} =")
            name_label.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
            name_label.setStyleSheet("color: #f8f8f2; background: transparent;")
            name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            value_label = QLabel(display_value)  # Use escaped value
            value_label.setFont(QFont(FONT_FAMILY, 9))
            value_label.setStyleSheet("color: white; background: transparent;")
            value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            value_label.setWordWrap(True)

            var_layout.addWidget(name_label)
            var_layout.addWidget(value_label, 1)

            var_widget.setStyleSheet(
                VAR_STYLE.replace("min-width: 120px", "min-width: 100px"))  # Apply style to var_widget
            self.content_layout.addWidget(var_widget)  # Add var_widget
            self.variables[name] = value_label
        else:
            self.variables[name].setText(display_value)  # Use escaped value
        self.updateGeometry()  # Force parent to re-evaluate its size


# LogicBlock class is removed entirely as per request.


# Renamed class from CodeVisualizer to UIVisualizer as per your request
class UIVisualizer(QObject):  # THIS IS THE CLASS NAME, NOW UIVisualizer
    """Main visualization controller"""

    # FIX: Accept 'parent_window' as an argument to match the 4 arguments given by main_window.py
    def __init__(self, parent_window: QWidget, code_editor: QTextEdit, canvas_widget: QWidget):
        # We call QObject's init, passing the parent_window as QObject parent.
        # This allows UIVisualizer to be properly managed by the parent_window's object tree.
        super().__init__(parent_window)
        self.parent_window = parent_window  # Store reference if needed later
        self.code_editor = code_editor
        self.canvas = canvas_widget  # This is the QWidget for visualization
        self.is_running = False

        # Visualization blocks (initialized as None, created dynamically)
        self.global_vars_block: Optional[VariableBlock] = None
        self.output_block: Optional[OutputBlock] = None
        # self.logic_block: Optional[LogicBlock] = None # LogicBlock removed
        self.function_blocks: List[FunctionBlock] = []

        # Execution state
        self.global_vars: Dict[str, Any] = {}
        self.call_stack: List[Dict[str, Any]] = []

        # Animation timer for steps
        self.step_timer = QTimer()
        self.step_timer.setSingleShot(True)
        self.step_timer.timeout.connect(self._next_step)

        # Prepared execution steps from AST traversal
        self.execution_steps: List[tuple] = []
        self.current_step_index = 0  # Renamed to avoid confusion with current AST node

        # Code highlighting
        self.extra_selections: List[QTextEdit.ExtraSelection] = []

        self._setup_layout()

    def _setup_layout(self):
        """Setup the canvas layout for visualization blocks"""
        # Clear existing layout and widgets from the canvas_widget if any
        if self.canvas.layout():
            # More robust way to clear:
            while self.canvas.layout().count():
                item = self.canvas.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    self._clear_layout_recursively(item.layout())

        # Create main layout for the canvas
        main_layout = QHBoxLayout(self.canvas)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Left column for global variables block
        self.left_column = QVBoxLayout()
        self.left_column.setAlignment(Qt.AlignTop)
        self.left_column.setSpacing(15)
        self.left_column.addStretch()  # Push widgets to top

        # Right column for functions, and output blocks
        self.right_column = QVBoxLayout()
        self.right_column.setAlignment(Qt.AlignTop)
        self.right_column.setSpacing(15)
        self.right_column.addStretch()  # Push widgets to top

        main_layout.addLayout(self.left_column)
        main_layout.addLayout(self.right_column)
        main_layout.addStretch()  # Push columns to left

    def _clear_layout_recursively(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget() is not None:
                    item.widget().deleteLater()
                elif item.layout() is not None:
                    self._clear_layout_recursively(item.layout())

    def start(self):  # RENAMED FROM start_visualization() TO start()
        """Start the visualization process"""
        if self.is_running:
            return

        self.is_running = True
        self._clear_all_blocks()  # Clear old blocks first

        # Reset execution state
        self.global_vars.clear()
        self.call_stack.clear()
        self.execution_steps.clear()
        self.current_step_index = 0
        self._clear_highlight()

        # Get code from editor
        code = self.code_editor.toPlainText().strip()
        if not code:
            # No logic block to show messages
            self.is_running = False
            return

        # Parse and prepare execution steps
        try:
            tree = ast.parse(code)
            self._prepare_execution_steps(tree)
        except SyntaxError as e:
            # No logic block to show messages
            self.is_running = False
            return

        # Start the first step after a short delay to allow UI to settle
        QTimer.singleShot(100, self._next_step)

    def _clear_all_blocks(self):
        """Clears all dynamic blocks and resets their references"""
        # Collect blocks to remove first to avoid modifying list during iteration
        blocks_to_hide = []
        if self.global_vars_block: blocks_to_hide.append(self.global_vars_block)
        if self.output_block: blocks_to_hide.append(self.output_block)
        # if self.logic_block: blocks_to_hide.append(self.logic_block) # LogicBlock removed
        blocks_to_hide.extend(self.function_blocks)

        for block in blocks_to_hide:
            block.hide_animated()
            # Schedule deletion after animation
            QTimer.singleShot(300, block.deleteLater)

        # Reset references after scheduling deletion
        self.global_vars_block = None
        self.output_block = None
        # self.logic_block = None # LogicBlock removed
        self.function_blocks.clear()

        # Clear layouts from any lingering widgets not directly in blocks
        self._clear_layout_recursively(self.left_column)
        self._clear_layout_recursively(self.right_column)

    def _prepare_execution_steps(self, tree):
        """Traverse AST and prepare a list of execution steps (tuples of type and node)"""
        # FIX: Use a proper AST visitor to get execution order
        visitor = CodeExecutionVisitor(self.execution_steps)
        visitor.visit(tree)
        # Add final 'end' step
        self.execution_steps.append(('end', None, None))

    def _next_step(self):
        """Execute the next step in the visualization sequence"""
        if self.current_step_index >= len(self.execution_steps):
            self._finish_execution()
            return

        step_type, node, lineno = self.execution_steps[self.current_step_index]

        # Highlight the current line
        if lineno is not None:
            self._highlight_line(lineno)

        # Execute the step logic
        try:
            if step_type == 'assign':
                self._execute_assignment(node)
            elif step_type == 'print':
                self._execute_print(node)
            elif step_type == 'func_def':
                self._execute_function_def(node)
            elif step_type == 'call':
                self._execute_call(node)  # For non-print calls
            elif step_type == 'end':
                self._finish_execution()
                return  # Exit early to prevent incrementing index past end

        except Exception as e:
            # FIX: No logic block to show runtime errors, print to console or output block
            print(f"Runtime Error: {escape(str(e))}")  # Print to console for debugging
            self._ensure_output_block_exists()  # Ensure output block exists
            if self.output_block:
                self.output_block.add_output(f"ERROR: {escape(str(e))}")  # Add to output block
            self.is_running = False
            self.step_timer.stop()  # Stop timer on error
            return

        self.current_step_index += 1

        # Continue with next step after delay, but only if still running
        if self.is_running:
            self.step_timer.start(200)  # Reduced step delay to 200ms

    def _ensure_global_vars_block_exists(self):
        """Ensures the global variables block exists and is animated, adds to layout if new."""
        if not self.global_vars_block:
            self.global_vars_block = VariableBlock("Global Variables", CYAN_COLOR, parent=self.canvas)
            self.left_column.addWidget(self.global_vars_block)  # Add to top of left column
            self.global_vars_block.show_animated()
            # Force layout update for the new block to take space
            self.canvas.layout().activate()
            self.canvas.adjustSize()

    def _ensure_output_block_exists(self):
        """Ensures the output block exists and is animated, adds to layout if new."""
        if not self.output_block:
            self.output_block = OutputBlock(parent=self.canvas)
            # Insert at top of right column (since logic block is gone)
            self.right_column.insertWidget(0, self.output_block)
            self.output_block.show_animated()
            # Force layout update for the new block to take space
            self.canvas.layout().activate()
            self.canvas.adjustSize()

    # _ensure_logic_block_exists is removed

    def _show_logic_block_and_set_text(self, text: str):
        """
        Helper that previously updated logic block.
        Now, it will print to console and potentially output block for debugging.
        """
        # Since logic block is removed, we can print to console or output block
        # For now, just print to console. If user wants a visual "status" area,
        # a new simple QLabel could be added to the right column.
        print(f"STATUS: {text}")

    def _execute_assignment(self, node: ast.Assign):
        """Execute assignment statement and update UI"""
        # No logic block update here, but we can print to console for debugging
        print(
            f"Executing assignment: {self.code_editor.document().findBlockByLineNumber(node.lineno - 1).text().strip()}")

        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            print("Error: Complex assignment target not visualized.")
            return

        var_name = node.targets[0].id

        try:
            value = self._evaluate_expression(node.value)
        except Exception as e:
            print(f"Error evaluating value for {var_name}: {e}")
            value = "Error"

        # Update scope (global or local)
        if self.call_stack:  # Inside a function
            current_scope = self.call_stack[-1]
            current_scope[var_name] = value
            # Update the most recent function block's local variable display
            if self.function_blocks:
                self.function_blocks[-1].update_local_var(var_name, value)
                self.function_blocks[-1].updateGeometry()  # Force its geometry to update
            print(f"Local var '{var_name}' set to {value}")
        else:  # Global scope
            self.global_vars[var_name] = value
            # Ensure Global Variables Block exists and update it
            self._ensure_global_vars_block_exists()
            if self.global_vars_block:
                self.global_vars_block.update_variable(var_name, value)
                self.global_vars_block.updateGeometry()  # Force its geometry to update
            print(f"Global var '{var_name}' set to {value}")

    def _execute_print(self, node: ast.Call):
        """Execute print statement and update UI"""
        print("Executing print statement...")

        output_value = ""
        if node.args:
            try:
                # Evaluate all arguments and join them for print
                evaluated_args = []
                for arg in node.args:
                    evaluated_args.append(str(self._evaluate_expression(arg)))
                output_value = " ".join(evaluated_args)
            except Exception as e:
                output_value = f"Error evaluating print argument: {e}"

        # Ensure Output Block exists and add content
        self._ensure_output_block_exists()
        if self.output_block:
            self.output_block.add_output(output_value)
        print(f"Printed: '{output_value}'")

    def _execute_function_def(self, node: ast.FunctionDef):
        """Execute function definition and update UI"""
        func_name = node.name
        self.global_vars[func_name] = node  # Store function definition in global scope

        # Ensure Global Variables Block exists and update it
        self._ensure_global_vars_block_exists()
        if self.global_vars_block:
            self.global_vars_block.update_variable(func_name, f"<function {func_name}>")
            self.global_vars_block.updateGeometry()
        print(f"Defined function: '{func_name}'")

    def _execute_call(self, node: ast.Call):
        """Execute function call and update UI"""
        if not isinstance(node.func, ast.Name):
            print("Error: Cannot visualize complex function calls (e.g., methods).")
            return

        func_name = node.func.id

        print(f"Calling function: '{func_name}'")

        # Create new function block for call stack visualization
        func_block = FunctionBlock(func_name, parent=self.canvas)
        # Insert at top of right column
        self.right_column.insertWidget(0, func_block)
        func_block.show_animated()
        self.function_blocks.append(func_block)
        func_block.updateGeometry()

        # Push new scope onto call stack
        new_scope = {}
        # Simulate passing arguments as local variables in the new scope
        if func_name in self.global_vars and isinstance(self.global_vars[func_name], ast.FunctionDef):
            func_def_node = self.global_vars[func_name]
            for i, arg in enumerate(func_def_node.args.args):
                if i < len(node.args):
                    try:
                        arg_value = self._evaluate_expression(node.args[i])
                        new_scope[arg.arg] = arg_value
                        func_block.update_local_var(arg.arg, arg_value)
                    except Exception as e:
                        print(f"Error passing arg '{arg.arg}': {e}")
                else:  # Missing argument
                    new_scope[arg.arg] = "<missing_arg>"
                    func_block.update_local_var(arg.arg, "<missing_arg>")

        self.call_stack.append(new_scope)
        func_block.updateGeometry()  # Ensure geometry updates after adding initial args

        # In a real visualizer, you would now execute the function's body steps
        # For simplicity in this basic model, we just show the call and then immediately return.
        # A more advanced _prepare_execution_steps would insert function body steps here.
        QTimer.singleShot(400, lambda: self._finish_function_call(func_name))

    def _finish_function_call(self, func_name: str):
        """Simulate finishing a function call"""
        if self.call_stack:
            self.call_stack.pop()  # Pop scope

        if self.function_blocks:
            finished_block = self.function_blocks.pop()
            finished_block.hide_animated()  # Hide function block
            QTimer.singleShot(300, finished_block.deleteLater)  # Delete after fade out

        print(f"Function '{func_name}' returned.")
        self.canvas.layout().activate()  # Force main canvas layout to update after block is removed
        self.canvas.adjustSize()

    def _evaluate_expression(self, node: ast.AST):
        """Evaluate an AST expression node based on current scopes"""
        if isinstance(node, ast.Constant):  # For Python 3.8+
            return node.value
        elif isinstance(node, (ast.Num, ast.Str, ast.NameConstant)):  # For older Python or specific types
            return ast.literal_eval(node)  # Safer than eval for constants

        elif isinstance(node, ast.Name):
            # Search current scope (function locals) first, then globals
            for scope in reversed(self.call_stack):
                if node.id in scope:
                    return scope[node.id]
            if node.id in self.global_vars:
                return self.global_vars[node.id]
            raise NameError(f"name '{node.id}' is not defined")

        # FIX: Check if node is an instance of ast.BinOp (binary operation)
        elif isinstance(node, ast.BinOp):
            # This is a binary operation, ensure it has left and right operands
            # We just need to ensure node.left and node.right exist for BinOp
            if not (hasattr(node, 'left') and hasattr(node, 'right')):
                raise ValueError(f"Invalid binary operation node: {type(node).__name__}")

            left = self._evaluate_expression(node.left)
            right = self._evaluate_expression(node.right)

            # Ensure operands are of compatible types
            if not (isinstance(left, (int, float, str)) and isinstance(right, (int, float, str))):
                raise TypeError("Unsupported operand type(s) for binary operation")

            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                return left - right
            elif isinstance(node.op, ast.Mult):
                return left * right
            elif isinstance(node.op, ast.Div):
                # Handle division by zero
                if isinstance(right, (int, float)) and right == 0:
                    raise ZeroDivisionError("division by zero")
                return left / right
            elif isinstance(node.op, ast.FloorDiv):
                return left // right
            elif isinstance(node.op, ast.Mod):
                return left % right
            elif isinstance(node.op, ast.Pow):
                return left ** right
            elif isinstance(node.op, ast.LShift):
                return left << right
            elif isinstance(node.op, ast.RShift):
                return left >> right
            elif isinstance(node.op, ast.BitOr):
                return left | right
            elif isinstance(node.op, ast.BitXor):
                return left ^ right
            elif isinstance(node.op, ast.BitAnd):
                return left & right

        # Add more AST node types as needed (e.g., ast.UnaryOp, ast.Compare, ast.BoolOp)
        raise ValueError(f"Unsupported AST node type for evaluation: {type(node).__name__}")

    def _highlight_line(self, line_number: int):
        """Highlight a line in the code editor"""
        self._clear_highlight()

        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(HIGHLIGHT_COLOR.lighter(120))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)

        cursor = self.code_editor.textCursor()
        cursor.movePosition(QTextCursor.Start)
        cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, line_number - 1)  # line numbers are 1-based

        selection.cursor = cursor
        self.extra_selections = [selection]
        self.code_editor.setExtraSelections(self.extra_selections)

    def _clear_highlight(self):
        """Clear code highlighting"""
        self.extra_selections.clear()
        self.code_editor.setExtraSelections(self.extra_selections)

    def _finish_execution(self):
        """Finish execution and clean up"""
        print("Execution complete")  # Print to console
        self._clear_highlight()
        self.is_running = False
        self.step_timer.stop()  # Ensure timer is stopped
        self.canvas.layout().activate()  # Force final layout update for the canvas
        self.canvas.adjustSize()


class CodeExecutionVisitor(ast.NodeVisitor):
    """
    AST NodeVisitor to prepare a linear list of execution steps.
    This is a simplified visitor and needs to be expanded for full language support.
    """

    def __init__(self, execution_steps: List[tuple]):
        self.execution_steps = execution_steps

    def visit_Assign(self, node: ast.Assign):
        # Visit the value expression first to ensure it's evaluated
        # FIX: Ensure generic_visit is called correctly for sub-nodes
        for target in node.targets:
            self.generic_visit(target)  # Visit target (e.g., if it's a tuple assignment)
        self.generic_visit(node.value)  # Visit value (e.g., if it's a binary op)
        self.execution_steps.append(('assign', node, node.lineno))

    def visit_Expr(self, node: ast.Expr):
        # If it's a call expression (like print or function call)
        if isinstance(node.value, ast.Call):
            call_node = node.value
            # Visit arguments first to ensure they are evaluated
            for arg in call_node.args:
                self.generic_visit(arg)

            if isinstance(call_node.func, ast.Name) and call_node.func.id == 'print':
                self.execution_steps.append(('print', call_node, node.lineno))
            else:
                self.execution_steps.append(('call', call_node, node.lineno))
        else:
            # For other expressions (e.g., just a literal or name on a line)
            self.generic_visit(node.value)  # Visit the expression itself if it's not a call

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Only record function definition, not its body execution yet
        self.execution_steps.append(('func_def', node, node.lineno))
        # Do NOT visit the body here; function body execution is triggered by a 'call' step
        # self.generic_visit(node) # Avoid this to prevent premature body execution

    def generic_visit(self, node: ast.AST):
        # Default visit method that visits all children.
        # This needs to be carefully managed to ensure execution order.
        # For simple linear code, it's okay, but for control flow,
        # specific visit_If, visit_For, etc. methods are crucial.
        super().generic_visit(node)