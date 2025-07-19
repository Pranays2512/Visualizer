# /ui/dynamic_layout_manager.py

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from typing import Any

# --- UI Constants ---
FONT_FAMILY = "Fira Code"
ANIMATION_DURATION = 300
GLOW_COLOR = QColor("#50fa7b")
PINK_COLOR = QColor("#ff79c6")
LINE_COLOR = QColor("#bd93f9")


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=15, h_spacing=15, v_spacing=15):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            self.invalidate()
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        # Add margins to the calculated size
        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)
        return size

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(+left, +top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._item_list:
            widget = item.widget()
            next_x = x + item.sizeHint().width() + self._h_spacing
            if next_x - self._h_spacing > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + self._v_spacing
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x += item.sizeHint().width() + self._h_spacing
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + bottom
# --- Widget Classes (Largely the same) ---
class SmartVariableWidget(QFrame):
    def __init__(self, name: str, value: Any, parent=None):
        super().__init__(parent)
        self.name = name
        self.value = value
        self.setStyleSheet("""
            QFrame { background-color: rgba(68, 71, 90, 0.95);
                     border: 1px solid #bd93f9; border-radius: 8px; padding: 8px; }
        """)
        layout = QHBoxLayout(self)
        self.name_label = QLabel(self.name)
        self.name_label.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.name_label.setStyleSheet("color: #8be9fd; border: none; background: transparent;")
        self.value_label = QLabel(str(self.value))
        self.value_label.setFont(QFont(FONT_FAMILY, 11))
        self.value_label.setStyleSheet("color: white; border: none; background: transparent;")
        layout.addWidget(self.name_label)
        layout.addWidget(self.value_label)
        self.adjustSize()

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(ANIMATION_DURATION)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.hide()

    def show_animated(self):
        self.show()
        self.animation.start()

    def update_value(self, value: Any):
        self.value = value
        self.value_label.setText(str(value))
        self.adjustSize()
        glow_effect = QGraphicsDropShadowEffect()
        glow_effect.setColor(GLOW_COLOR)
        glow_effect.setBlurRadius(25)
        self.setGraphicsEffect(glow_effect)
        QTimer.singleShot(ANIMATION_DURATION * 2, lambda: self.setGraphicsEffect(self.opacity_effect))


class SmartPrintBlock(QFrame):
    def __init__(self, expression_str: str, result: Any, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame { background-color: rgba(40, 42, 54, 0.95);
                     border: 1px solid #ff79c6; border-radius: 10px; padding: 10px; }
        """)
        main_layout = QVBoxLayout(self)
        title_label = QLabel(f"print({expression_str})")
        title_label.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        title_label.setStyleSheet(f"color: {PINK_COLOR.name()}; background: transparent; border: none;")

        output_container = QFrame()
        output_container.setStyleSheet(
            "border: 1px solid #50fa7b; border-radius: 8px; background-color: #282a36; padding: 8px;")
        output_layout = QHBoxLayout(output_container)
        prints_label = QLabel("Output:")
        prints_label.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        prints_label.setStyleSheet("color: #f8f8f2; border: none; background: transparent;")
        result_label = QLabel(str(result))
        result_label.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        result_label.setStyleSheet(f"color: {GLOW_COLOR.name()}; border: none; background: transparent;")

        output_layout.addWidget(prints_label)
        output_layout.addStretch()
        output_layout.addWidget(result_label)
        main_layout.addWidget(title_label)
        main_layout.addWidget(output_container)
        self.adjustSize()

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(ANIMATION_DURATION)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.hide()

    def show_animated(self):
        self.show()
        self.animation.start()


# --- The Canvas now signals when it needs to be resized ---
class DynamicCanvas(QWidget):
    # Signal that emits the required bounding box of all content
    needs_resize = pyqtSignal(QSize)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("canvasWidget")
        self.layout = FlowLayout(self)
        self.setLayout(self.layout)
        self.connections = []

    def add_widget(self, widget):
        self.layout.addWidget(widget)
        self.check_bounds_and_emit()

    def check_bounds_and_emit(self):
        # The layout's sizeHint is the total required size for all widgets
        required_size = self.layout.sizeHint()
        self.needs_resize.emit(required_size)

    def add_connection(self, start_widget, end_widget):
        self.connections.append((start_widget, end_widget))
        self.update() # Trigger repaint

    def clear_all(self):
        self.connections.clear()
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(LINE_COLOR, 2, Qt.SolidLine)
        painter.setPen(pen)
        for start_widget, end_widget in self.connections:
            if start_widget.isVisible() and end_widget.isVisible():
                painter.drawLine(start_widget.geometry().center(), end_widget.geometry().center())