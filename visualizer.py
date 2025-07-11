from PyQt5.QtCore import QObject, QEvent, QTimer, QPropertyAnimation, QRect, QSize
from PyQt5.QtWidgets import QGraphicsOpacityEffect, QPlainTextEdit

class UIVisualizer(QObject):
    def __init__(self, parent, code_editor, input_box, output_area, input_label):
        super().__init__(parent)
        self.code_editor = code_editor
        self.input_box = input_box
        self.output_area = output_area
        self.input_label = input_label

        self._is_merged = False
        self._input_faded = False
        self._input_original_geom = None
        self._output_original_geom = None

        self.input_opacity_effect = None
        self.animations = []

        self.code_editor.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.code_editor and event.type() == QEvent.Resize and self._is_merged:
            self._adjust_merged_geometry()
        return super().eventFilter(obj, event)

    def start(self):
        code = self.code_editor.toPlainText().strip()
        if not code:
            self.output_area.setPlainText("No code to visualize.")
            return

        self._merge_panels()
        QTimer.singleShot(650, lambda: self._run_visualization_animation(code))

    def revert_if_merged(self):
        if self._is_merged:
            self._revert_merge()

    def _merge_panels(self):
        if self._is_merged:
            return
        self._is_merged = True
        self._input_original_geom = self.input_box.geometry()
        self._output_original_geom = self.output_area.geometry()

        self._fade_out_input_label()
        self.input_box.setPlainText("")

        target_geom = self._calculate_merged_geometry()
        if not target_geom:
            return

        for widget in [self.input_box, self.output_area]:
            anim = QPropertyAnimation(widget, b"geometry")
            anim.setDuration(600)
            anim.setStartValue(widget.geometry())
            anim.setEndValue(target_geom)
            anim.start()
            self.animations.append(anim)

    def _revert_merge(self):
        if not (self._input_original_geom and self._output_original_geom):
            return

        for widget, geom in [(self.input_box, self._input_original_geom), (self.output_area, self._output_original_geom)]:
            anim = QPropertyAnimation(widget, b"geometry")
            anim.setDuration(400)
            anim.setEndValue(geom)
            anim.start()
            self.animations.append(anim)

        self._fade_in_input_label()
        self._is_merged = False

    def _run_visualization_animation(self, code):
        self.output_area.clear()
        lines = code.split('\n')
        self.vis_index = 0

        def show_next_line():
            if self.vis_index >= len(lines):
                self.output_area.insertPlainText("\nVisualization Finished.\n")
                return

            line = lines[self.vis_index].strip()
            if line:
                self.output_area.insertPlainText(f"👉 {line}\n")
                self.output_area.insertPlainText(f"# Executing step {self.vis_index + 1}\n\n")

            self.vis_index += 1
            QTimer.singleShot(600, show_next_line)

        show_next_line()

    def _calculate_merged_geometry(self):
        if not (self._input_original_geom and self._output_original_geom):
            return None

        editor_geom = self.code_editor.geometry()
        spacing = self.input_box.parent().layout().spacing() if self.input_box.parent() and self.input_box.parent().layout() else 10
        new_height = self._input_original_geom.height() + self._output_original_geom.height() + spacing

        return QRect(self._input_original_geom.topLeft(), QSize(editor_geom.width(), new_height))

    def _adjust_merged_geometry(self):
        target_rect = self._calculate_merged_geometry()
        if target_rect:
            self.input_box.setGeometry(target_rect)
            self.output_area.setGeometry(target_rect)

    def _fade_out_input_label(self):
        if not self._input_faded:
            self.input_opacity_effect = QGraphicsOpacityEffect(self.input_label)
            self.input_label.setGraphicsEffect(self.input_opacity_effect)
            anim = QPropertyAnimation(self.input_opacity_effect, b"opacity")
            anim.setDuration(500)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.start()
            self.animations.append(anim)
            self._input_faded = True

    def _fade_in_input_label(self):
        if self._input_faded and self.input_opacity_effect:
            anim = QPropertyAnimation(self.input_opacity_effect, b"opacity")
            anim.setDuration(500)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.start()
            self.animations.append(anim)
            self._input_faded = False
