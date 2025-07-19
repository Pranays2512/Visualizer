# /ui/main_window.py

import os, sys, tempfile, subprocess
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel, QHBoxLayout,
                             QGraphicsDropShadowEffect, QSplitter, QMainWindow, QStackedWidget,
                             QGraphicsOpacityEffect, QSizePolicy)
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtCore import Qt, QPropertyAnimation, QRect, QSize

from .code_editor import CodeEditor
from analysis.complexity import ComplexityAnalyzer
from .dynamic_layout_manager import DynamicCanvas
from .visualizer import UIVisualizer


class FrostedCompiler(QMainWindow):
    def __init__(self):
        super().__init__()
        self.is_dark, self._cached_styles = True, {}
        self._ui_state = {'merged': False, 'input_faded': False}
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Frosted Glass Python Compiler")
        self.resize(1200, 700)
        self.setMinimumSize(900, 600)
        self.setStyleSheet("background: transparent;")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowMinimizeButtonHint |
                            Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint)

        central_widget = QWidget();
        self.setCentralWidget(central_widget)
        self.container = QWidget(self)
        self.container.setStyleSheet(self.get_container_style())

        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(25, 25, 25, 25)
        self.main_layout.setSpacing(20)
        self.editor_layout, self.editor_split = QHBoxLayout(), QSplitter(Qt.Horizontal)
        self.editor_split.setHandleWidth(2)

        self.code_editor = CodeEditor()
        self.code_editor.setPlaceholderText("Write your Python code here...")
        self.code_editor.setFont(QFont("Fira Code", 14))
        self.apply_editor_theme()
        self._apply_shadow(self.code_editor, 25)

        right_column, right_widget = QVBoxLayout(), QWidget()

        self.input_label = QLabel("Input")
        self.input_label.setFont(QFont("Fira Code", 12, QFont.Bold))
        self.input_label.setStyleSheet(self.label_style())

        def make_box(widget_type=QTextEdit, font_size=12, readonly=False, fixed_height=None):
            box = widget_type()
            box.setFont(QFont("Fira Code", font_size))
            box.setReadOnly(readonly)
            if fixed_height: box.setFixedHeight(fixed_height)
            box.setStyleSheet(self.get_code_editor_style())
            self._apply_shadow(box)
            return box

        self.view_stack = QStackedWidget()

        # Page 0: Standard view
        standard_view_widget = QWidget()
        standard_view_layout = QVBoxLayout(standard_view_widget)
        standard_view_layout.setContentsMargins(0, 0, 0, 0)
        standard_view_layout.setSpacing(20)
        self.input_box = make_box(fixed_height=150)
        self.output_area = make_box(readonly=True)
        standard_view_layout.addWidget(self.input_box)
        standard_view_layout.addWidget(self.output_area)
        self.view_stack.addWidget(standard_view_widget)

        # Page 1: Enhanced Visualization canvas
        self.visualization_canvas = DynamicCanvas()
        self.visualization_canvas.setStyleSheet(self.get_code_editor_style())
        self._apply_shadow(self.visualization_canvas)

        # Set minimum size for the canvas
        self.visualization_canvas.setMinimumSize(600, 400)

        self.view_stack.addWidget(self.visualization_canvas)

        right_column.addWidget(self.input_label)
        right_column.addWidget(self.view_stack)
        right_widget.setLayout(right_column)

        self.editor_split.addWidget(self.code_editor)
        self.editor_split.addWidget(right_widget)
        self.editor_split.setSizes([800, 400])
        self.editor_layout.addWidget(self.editor_split)
        self.main_layout.addLayout(self.editor_layout)

        self._setup_buttons()
        QVBoxLayout(central_widget).addWidget(self.container)

        self.visualizer = UIVisualizer(self, self.code_editor, self.visualization_canvas)

    def _setup_buttons(self):
        button_layout = QHBoxLayout();
        button_layout.setSpacing(15)
        buttons = [
            ("▶ Run", self.run_code), ("✨ Visualize", self.visualize_code),
            ("Analyze", self.analyze_code_complexity), ("Reset", self.reset), ("Theme", self.toggle_theme)
        ]
        for label, action in buttons:
            btn = QPushButton(label);
            btn.clicked.connect(action)
            self._style_button(btn);
            button_layout.addWidget(btn)
        self.main_layout.addLayout(button_layout)

    def _style_button(self, button):
        button.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                padding: 8px 18px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.15); }
            QPushButton:pressed { background-color: rgba(255, 255, 255, 0.25); }
        """)
        self._apply_shadow(button, 20)

    def _apply_shadow(self, widget, radius=20):
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(radius)
        glow.setColor(QColor(255, 255, 255, 70))
        glow.setOffset(0, 0)
        widget.setGraphicsEffect(glow)

    def get_container_style(self):
        return """
            background-color: rgba(255, 255, 255, 0.15);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 20px;
        """

    def get_code_editor_style(self):
        key = f"editor_style_{self.is_dark}"
        if key not in self._cached_styles:
            dark_style = """
                QWidget {
                    background-color: rgba(30, 30, 30, 0.95);
                    color: #ffffff;
                    border-radius: 12px;
                    padding: 15px;
                    font-family: 'Fira Code', 'Consolas', monospace;
                    border: 1px solid #444444;
                }
            """
            light_style = """
                QWidget {
                    background-color: rgba(255, 255, 255, 0.95);
                    color: #1e1e1e;
                    border-radius: 12px;
                    padding: 15px;
                    font-family: 'Fira Code', 'Consolas', monospace;
                    border: 1px solid #e0e0e0;
                }
            """
            self._cached_styles[key] = dark_style if self.is_dark else light_style
        return self._cached_styles[key]

    def label_style(self, top=False):
        key = f"label_style_{self.is_dark}_{top}"
        if key not in self._cached_styles:
            margin = "margin-top: 15px;" if top else ""
            self._cached_styles[key] = (
                f"padding: 6px 10px; {margin} margin-bottom: 5px; border-radius: 8px; background-color: rgba(255,255,255,0.08);"
                if self.is_dark else
                f"color: #0033aa; padding: 6px 10px; {margin} margin-bottom: 5px; border-radius: 8px; background-color: rgba(0,0,0,0.05);"
            )
        return self._cached_styles[key]

    def apply_editor_theme(self):
        self.code_editor.setStyleSheet(self.get_code_editor_style())
        if hasattr(self.code_editor, 'highlighter'):
            self.code_editor.highlighter.rehighlight()

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        for w in [self.code_editor, self.input_box, self.output_area, self.visualization_canvas]:
            if w: w.setStyleSheet(self.get_code_editor_style())
        self.apply_editor_theme()

    def _reset_canvas_on_view_change(self):
        """Reset canvas state when switching between views"""
        if hasattr(self.visualizer, 'stop'):
            self.visualizer.stop()

    def _fade_out_input_label(self):
        if not self._ui_state['input_faded']:
            self.input_opacity = getattr(self, 'input_opacity', QGraphicsOpacityEffect(self.input_label))
            self.input_label.setGraphicsEffect(self.input_opacity)
            self.fade_anim = getattr(self, 'fade_anim', QPropertyAnimation(self.input_opacity, b"opacity"))
            self.fade_anim.setDuration(500)
            self.fade_anim.setStartValue(1.0)
            self.fade_anim.setEndValue(0.0)
            self.fade_anim.start()
            self._ui_state['input_faded'] = True

    def _fade_in_input_label(self):
        if self._ui_state['input_faded']:
            self.fade_anim.setDirection(QPropertyAnimation.Forward)
            self.fade_anim.setStartValue(self.input_opacity.opacity())
            self.fade_anim.setEndValue(1.0)
            self.fade_anim.start()
            self._ui_state['input_faded'] = False

    def _switch_to_visualize_view(self):
        if self.view_stack.currentIndex() != 1:
            self._fade_out_input_label()
            self.view_stack.setCurrentIndex(1)

    def _switch_to_standard_view(self):
        if self.view_stack.currentIndex() != 0:
            self._reset_canvas_on_view_change()
            self._fade_in_input_label()
            self.view_stack.setCurrentIndex(0)

    def visualize_code(self):
        self._switch_to_visualize_view()
        self.visualizer.start()

    def run_code(self):
        self._switch_to_standard_view()
        code, input_text = self.code_editor.toPlainText().strip(), self.input_box.toPlainText()
        if hasattr(self.code_editor, 'run_code_analysis'):
            self.code_editor.run_code_analysis()
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w', encoding='utf-8') as temp_file:
            temp_file.write(code)
            temp_filename = temp_file.name
        try:
            result = subprocess.run([sys.executable, temp_filename], input=input_text, capture_output=True, text=True,
                                    timeout=5)
            self.output_area.setPlainText(result.stdout if result.returncode == 0 else result.stderr)
        except Exception as e:
            self.output_area.setPlainText(f"Error: {e}")
        finally:
            try:
                os.unlink(temp_filename)
            except OSError:
                pass

    def analyze_code_complexity(self):
        self._switch_to_standard_view()
        code = self.code_editor.toPlainText().strip()
        if not code: self.output_area.setPlainText("No code to analyze."); return
        try:
            complexity = ComplexityAnalyzer().analyze(code)
            self.output_area.setPlainText(
                f"--- Complexity Analysis ---\n\nTime Complexity: {complexity['time']}\nSpace Complexity: {complexity['space']}"
            )
        except Exception as e:
            self.output_area.setPlainText(f"Could not analyze complexity: {e}")

    def reset(self):
        self._switch_to_standard_view()
        self.code_editor.clear()
        self.output_area.clear()
        self.input_box.clear()
        self.editor_split.setSizes([800, 400])