# /ui/advanced_data_visualizer.py

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from typing import Any, List, Dict, Optional, Union
import math
import ast
import json

# Import from your existing files
from .dynamic_layout_manager import (
    GraphicsObjectWidget, SmoothAnimation, EnhancedParticleEffect as ParticleEffect,
    FONT_FAMILY, ANIMATION_DURATION, GLOW_COLOR, PINK_COLOR,
    LINE_COLOR, SCOPE_COLOR, BACKGROUND_COLOR, HOVER_SCALE
)

# Additional constants for advanced visualizations
ARRAY_CELL_WIDTH = 50
ARRAY_CELL_HEIGHT = 35
TREE_NODE_SIZE = 40
TREE_LEVEL_HEIGHT = 80
LIST_NODE_WIDTH = 80
LIST_NODE_HEIGHT = 40
STRING_CHAR_WIDTH = 25
LOOP_INDICATOR_COLOR = QColor("#ffb86c")
HIGHLIGHT_ANIMATION_COLOR = QColor("#50fa7b")


class ArrayWidget(GraphicsObjectWidget):
    def __init__(self, name: str, array_data: List[Any], parent=None):
        super().__init__(parent)  # Only pass parent to GraphicsObjectWidget
        self.name = name
        self.array_data = array_data.copy() if array_data else []
        self.cell_widgets = []
        self.index_labels = []
        self._width = 0
        self._height = 0

        # Create name text
        self.name_text = QGraphicsTextItem(f'{self.name} = {self.array_data}', self)
        self.name_text.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.name_text.setDefaultTextColor(QColor("#50fa7b"))

        self._create_cells()
        self._update_layout()

    def _create_cells(self):
        """Create cell widgets for array elements"""
        for cell in self.cell_widgets:
            if cell.scene():
                cell.scene().removeItem(cell)
        for label in self.index_labels:
            if label.scene():
                label.scene().removeItem(label)

        self.cell_widgets.clear()
        self.index_labels.clear()

        for i, value in enumerate(self.array_data):
            cell = ArrayCellWidget(i, value, self)
            self.cell_widgets.append(cell)

            # Create index label
            index_label = QGraphicsTextItem(str(i), self)
            index_label.setFont(QFont(FONT_FAMILY, 8))
            index_label.setDefaultTextColor(QColor("#6272a4"))
            self.index_labels.append(index_label)

    def _update_layout(self):
        """Layout array cells horizontally"""
        self.prepareGeometryChange()

        # Position name text
        self.name_text.setPos(10, 5)
        name_height = self.name_text.boundingRect().height()

        # Starting position for cells
        start_x = 10
        start_y = name_height + 15

        if not self.cell_widgets:
            self._width = max(200, self.name_text.boundingRect().width() + 20)
            self._height = start_y + 50
            return

        # Calculate cell widths
        font_metrics = QFontMetrics(QFont(FONT_FAMILY, 10))
        running_x = start_x

        for i, (cell, label) in enumerate(zip(self.cell_widgets, self.index_labels)):
            # Calculate width needed for this cell
            content_width = max(30, font_metrics.width(str(cell.value)) + 18)
            cell.set_custom_width(content_width)

            # Position cell
            cell.setPos(running_x, start_y)

            # Position index label below cell
            label_x = running_x + (content_width - label.boundingRect().width()) / 2
            label.setPos(label_x, start_y + cell._height + 5)

            # Move to next position
            running_x += content_width + 2

        # Update widget dimensions
        self._width = running_x + 10
        self._height = start_y + 35 + 25  # cell height + label height + margins

    def update_array(self, new_array: List[Any]):
        """Update array data with animation"""
        if new_array == self.array_data:
            return

        self.array_data = new_array.copy()
        self.name_text.setPlainText(f'{self.name} = {self.array_data}')
        self._create_cells()
        self._update_layout()

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        # Background
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(80, 250, 123, 50))
        gradient.setColorAt(1, QColor(80, 250, 123, 30))

        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.fillPath(path, QBrush(gradient))

        # Border
        painter.setPen(QPen(QColor("#50fa7b"), 1.5))
        painter.drawPath(path)


class ArrayCellWidget(GraphicsObjectWidget):
    def __init__(self, index: int, value: Any, parent=None):
        super().__init__(parent)
        self.index = index
        self.value = value
        self._width = 50
        self._height = 35

        self.value_text = QGraphicsTextItem(str(value), self)
        self.value_text.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.value_text.setDefaultTextColor(QColor("white"))

        self._update_text_position()

    def set_custom_width(self, width):
        self._width = max(30, width)
        self._update_text_position()

    def _update_text_position(self):
        text_rect = self.value_text.boundingRect()
        x = (self._width - text_rect.width()) / 2
        y = (self._height - text_rect.height()) / 2
        self.value_text.setPos(x, y)

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        # Cell background
        painter.setBrush(QColor("#50fa7b").darker(150))
        painter.setPen(QPen(QColor("#50fa7b"), 1))
        painter.drawRoundedRect(rect, 3, 3)



class StringWidget(GraphicsObjectWidget):
    """Visualizes strings with individual character cells"""

    def __init__(self, name: str, string_data: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.string_data = string_data or ""
        self.char_widgets = []
        self._width = 0
        self._height = 0

        self.name_text = QGraphicsTextItem(f'{self.name} = "{self.string_data}"', self)
        self.name_text.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.name_text.setDefaultTextColor(QColor("#50fa7b"))

        self._create_char_cells()
        self._update_layout()

    def _create_char_cells(self):
        for cell in self.char_widgets:
            if cell.scene():
                cell.scene().removeItem(cell)
        self.char_widgets.clear()

        for i, char in enumerate(self.string_data):
            cell = StringCharWidget(i, char, self)
            self.char_widgets.append(cell)

    def _update_layout(self):
        self.prepareGeometryChange()

        self.name_text.setPos(10, 5)
        name_height = self.name_text.boundingRect().height()

        start_x = 10
        start_y = name_height + 15

        for i, cell in enumerate(self.char_widgets):
            x = start_x + i * (STRING_CHAR_WIDTH + 1)
            cell.setPos(x, start_y)

        if self.string_data:
            self._width = start_x + len(self.string_data) * (STRING_CHAR_WIDTH + 1) + 10
        else:
            self._width = max(200, self.name_text.boundingRect().width() + 20)
        self._height = start_y + 30 + 10

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        # Background
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(80, 250, 123, 50))
        gradient.setColorAt(1, QColor(80, 250, 123, 30))

        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.fillPath(path, QBrush(gradient))

        # Border
        painter.setPen(QPen(QColor("#50fa7b"), 1.5))
        painter.drawPath(path)

    def update_string(self, new_string: str):
        """Update string data with animation"""
        if new_string == self.string_data:
            return

        self.string_data = new_string
        self.name_text.setPlainText(f'{self.name} = "{self.string_data}"')
        self._create_char_cells()
        self._update_layout()

    def highlight_char(self, index: int, color: QColor = HIGHLIGHT_ANIMATION_COLOR):
        """Highlight a specific character"""
        if 0 <= index < len(self.char_widgets):
            self.char_widgets[index].highlight(color)


class StringCharWidget(GraphicsObjectWidget):
    """Individual character in string visualization"""

    def __init__(self, index: int, char: str, parent=None):
        super().__init__(parent)
        self.index = index
        self.char = char

        display_char = char if char != ' ' else '·'  # Show spaces as dots
        self.char_text = QGraphicsTextItem(display_char, self)
        self.char_text.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.char_text.setDefaultTextColor(QColor("white"))

        self._update_text_position()

    def _update_text_position(self):
        text_rect = self.char_text.boundingRect()
        x = (STRING_CHAR_WIDTH - text_rect.width()) / 2
        y = (30 - text_rect.height()) / 2
        self.char_text.setPos(x, y)

    def boundingRect(self):
        return QRectF(0, 0, STRING_CHAR_WIDTH, 30)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        # Character cell background
        painter.setBrush(QColor("#50fa7b").darker(150))
        painter.setPen(QPen(QColor("#50fa7b"), 1))
        painter.drawRoundedRect(rect, 3, 3)

    def highlight(self, color: QColor = HIGHLIGHT_ANIMATION_COLOR):
        """Highlight this character"""
        # Create glow effect
        glow = QGraphicsDropShadowEffect()
        glow.setColor(color)
        glow.setBlurRadius(10)
        self.setGraphicsEffect(glow)

        # Remove glow after animation
        QTimer.singleShot(800, lambda: self.setGraphicsEffect(None))

        # Pulse animation
        pulse_anim = SmoothAnimation(self, b'scale')
        pulse_anim.setStartValue(1.0)
        pulse_anim.setEndValue(1.4)
        pulse_anim.setDuration(200)

        def return_to_normal():
            return_anim = SmoothAnimation(self, b'scale')
            return_anim.setStartValue(1.4)
            return_anim.setEndValue(1.0)
            return_anim.setDuration(200)
            return_anim.start()

        pulse_anim.finished.connect(return_to_normal)
        pulse_anim.start()


class LinkedListWidget(GraphicsObjectWidget):
    """Visualizes linked lists with nodes and pointers"""

    def __init__(self, name: str, list_data: List[Any], parent=None):
        super().__init__(parent)
        self.name = name
        self.list_data = list_data.copy() if list_data else []
        self.node_widgets = []
        self.arrow_widgets = []
        self._width = 0
        self._height = 0

        self.name_text = QGraphicsTextItem(f"{self.name} (Linked List)", self)
        self.name_text.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.name_text.setDefaultTextColor(QColor("#bd93f9"))

        self._create_nodes()
        self._update_layout()

    def _create_nodes(self):
        # Clear existing nodes and arrows
        for node in self.node_widgets:
            if node.scene():
                node.scene().removeItem(node)
        for arrow in self.arrow_widgets:
            if arrow.scene():
                arrow.scene().removeItem(arrow)

        self.node_widgets.clear()
        self.arrow_widgets.clear()

        # Create nodes
        for i, value in enumerate(self.list_data):
            node = LinkedListNodeWidget(value, self)
            self.node_widgets.append(node)

        # Create arrows between nodes
        for i in range(len(self.node_widgets) - 1):
            arrow = LinkedListArrowWidget(self)
            self.arrow_widgets.append(arrow)

    def _update_layout(self):
        self.prepareGeometryChange()

        # Position name
        self.name_text.setPos(10, 5)
        name_height = self.name_text.boundingRect().height()

        # Position nodes and arrows horizontally
        start_x = 10
        start_y = name_height + 15

        for i, node in enumerate(self.node_widgets):
            x = start_x + i * (LIST_NODE_WIDTH + 30)
            node.setPos(x, start_y)

            # Position arrow after this node (if not last)
            if i < len(self.arrow_widgets):
                arrow_x = x + LIST_NODE_WIDTH + 5
                arrow_y = start_y + LIST_NODE_HEIGHT // 2 - 5
                self.arrow_widgets[i].setPos(arrow_x, arrow_y)

        # Update dimensions
        if self.list_data:
            self._width = start_x + len(self.list_data) * (LIST_NODE_WIDTH + 30) - 20
        else:
            self._width = max(150, self.name_text.boundingRect().width() + 20)
        self._height = start_y + LIST_NODE_HEIGHT + 20

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        # Background
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(189, 147, 249, 40))
        gradient.setColorAt(1, QColor(189, 147, 249, 20))

        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.fillPath(path, QBrush(gradient))

        # Border
        painter.setPen(QPen(QColor("#bd93f9"), 1.5, Qt.DashLine))
        painter.drawPath(path)

    def update_list(self, new_data: List[Any]):
        """Update linked list data"""
        self.list_data = new_data.copy()
        self._create_nodes()
        self._update_layout()

    def highlight_node(self, index: int, color: QColor = HIGHLIGHT_ANIMATION_COLOR):
        """Highlight a specific node"""
        if 0 <= index < len(self.node_widgets):
            self.node_widgets[index].highlight(color)


class LinkedListNodeWidget(GraphicsObjectWidget):
    """Individual node in linked list"""

    def __init__(self, value: Any, parent=None):
        super().__init__(parent)
        self.value = value

        self.value_text = QGraphicsTextItem(str(value), self)
        self.value_text.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.value_text.setDefaultTextColor(QColor("white"))

        self._update_text_position()

    def _update_text_position(self):
        text_rect = self.value_text.boundingRect()
        x = (LIST_NODE_WIDTH - 15 - text_rect.width()) / 2  # Account for pointer section
        y = (LIST_NODE_HEIGHT - text_rect.height()) / 2
        self.value_text.setPos(x, y)

    def boundingRect(self):
        return QRectF(0, 0, LIST_NODE_WIDTH, LIST_NODE_HEIGHT)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        # Node background
        painter.setBrush(QColor("#bd93f9").darker(130))
        painter.setPen(QPen(QColor("#bd93f9"), 2))
        painter.drawRoundedRect(rect, 6, 6)

        # Draw pointer section
        pointer_rect = QRectF(rect.width() - 15, 5, 10, rect.height() - 10)
        painter.setBrush(QColor("#44475a"))
        painter.drawRoundedRect(pointer_rect, 2, 2)

    def highlight(self, color: QColor = HIGHLIGHT_ANIMATION_COLOR):
        """Highlight this node"""
        # Create glow effect
        glow = QGraphicsDropShadowEffect()
        glow.setColor(color)
        glow.setBlurRadius(15)
        self.setGraphicsEffect(glow)

        # Remove glow after animation
        QTimer.singleShot(1000, lambda: self.setGraphicsEffect(None))

        # Scale animation
        scale_anim = SmoothAnimation(self, b'scale')
        scale_anim.setStartValue(1.0)
        scale_anim.setEndValue(1.2)
        scale_anim.setDuration(200)

        def return_to_normal():
            return_anim = SmoothAnimation(self, b'scale')
            return_anim.setStartValue(1.2)
            return_anim.setEndValue(1.0)
            return_anim.setDuration(200)
            return_anim.start()

        scale_anim.finished.connect(return_to_normal)
        scale_anim.start()


class LinkedListArrowWidget(GraphicsObjectWidget):
    """Arrow connecting linked list nodes"""

    def __init__(self, parent=None):
        super().__init__(parent)

    def boundingRect(self):
        return QRectF(0, 0, 20, 10)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw arrow
        pen = QPen(QColor("#bd93f9"), 2)
        painter.setPen(pen)
        painter.setBrush(QColor("#bd93f9"))

        # Arrow line
        painter.drawLine(0, 5, 15, 5)

        # Arrow head
        arrow_head = QPolygonF([
            QPointF(15, 5),
            QPointF(10, 2),
            QPointF(10, 8)
        ])
        painter.drawPolygon(arrow_head)


class TreeWidget(GraphicsObjectWidget):
    """Visualizes binary trees with nodes and connections"""

    def __init__(self, name: str, tree_data: Dict, parent=None):
        super().__init__(parent)
        self.name = name
        self.tree_data = tree_data or {}
        self.node_widgets = {}
        self.connection_lines = []
        self._width = 0
        self._height = 0

        self.name_text = QGraphicsTextItem(f"{self.name} (Binary Tree)", self)
        self.name_text.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.name_text.setDefaultTextColor(QColor("#f1fa8c"))

        if self.tree_data:
            self._create_tree_nodes()
        self._update_layout()

    def update_tree(self, new_tree_data: Dict):
        """Update tree with new data and proper layout"""
        self.tree_data = new_tree_data or {}

        # Clear existing nodes and connections
        for node_widget in self.node_widgets.values():
            if node_widget.scene():
                node_widget.scene().removeItem(node_widget)
        for connection in self.connection_lines:
            if connection.scene():
                connection.scene().removeItem(connection)

        self.node_widgets.clear()
        self.connection_lines.clear()

        if self.tree_data:
            self._create_tree_nodes()
        self._update_layout()

    def highlight_path(self, path: List[Any]):
        """Highlight a path through the tree (for traversal visualization)"""
        # This can be used to show tree traversal
        for node_id, widget in self.node_widgets.items():
            widget.setGraphicsEffect(None)  # Clear previous highlights

        # Highlight nodes in path
        for value in path:
            for node_id, widget in self.node_widgets.items():
                if widget.value == value:
                    widget.highlight(QColor("#50fa7b"))
                    break

    def _create_tree_nodes(self):
        """Create tree nodes recursively"""
        if not self.tree_data:
            return

        # Calculate tree structure
        self.tree_positions = {}
        self._calculate_positions(self.tree_data, 0, 0, 200)

        # Create node widgets
        self._create_nodes_recursive(self.tree_data, None)

    def _calculate_positions(self, node_data, level, position, width):
        """Calculate positions for tree nodes"""
        if not isinstance(node_data, dict) or 'value' not in node_data:
            return

        node_id = id(node_data)
        self.tree_positions[node_id] = {
            'level': level,
            'position': position,
            'x': position,
            'y': level * TREE_LEVEL_HEIGHT
        }

        # Calculate positions for children
        if 'left' in node_data and node_data['left']:
            self._calculate_positions(node_data['left'], level + 1, position - width // 2, width // 2)

        if 'right' in node_data and node_data['right']:
            self._calculate_positions(node_data['right'], level + 1, position + width // 2, width // 2)

    def _create_nodes_recursive(self, node_data, parent_widget):
        """Recursively create node widgets"""
        if not isinstance(node_data, dict) or 'value' not in node_data:
            return None

        node_widget = TreeNodeWidget(node_data['value'], self)
        node_id = id(node_data)
        self.node_widgets[node_id] = node_widget

        # Create connections to children
        if 'left' in node_data and node_data['left']:
            left_widget = self._create_nodes_recursive(node_data['left'], node_widget)
            if left_widget:
                connection = TreeConnectionWidget(node_widget, left_widget, self)
                self.connection_lines.append(connection)

        if 'right' in node_data and node_data['right']:
            right_widget = self._create_nodes_recursive(node_data['right'], node_widget)
            if right_widget:
                connection = TreeConnectionWidget(node_widget, right_widget, self)
                self.connection_lines.append(connection)

        return node_widget

    def _update_layout(self):
        self.prepareGeometryChange()

        # Position name
        self.name_text.setPos(10, 5)
        name_height = self.name_text.boundingRect().height()

        start_y = name_height + 20

        # Position nodes based on calculated positions
        if hasattr(self, 'tree_positions') and self.tree_positions:
            min_x = min(pos['x'] for pos in self.tree_positions.values())
            max_x = max(pos['x'] for pos in self.tree_positions.values())
            max_level = max(pos['level'] for pos in self.tree_positions.values())

            # Offset to make all positions positive
            x_offset = 50 - min_x

            for node_id, position in self.tree_positions.items():
                if node_id in self.node_widgets:
                    widget = self.node_widgets[node_id]
                    x = position['x'] + x_offset
                    y = start_y + position['y']
                    widget.setPos(x, y)

            self._width = max_x - min_x + 100
            self._height = start_y + (max_level + 1) * TREE_LEVEL_HEIGHT
        else:
            self._width = max(200, self.name_text.boundingRect().width() + 20)
            self._height = start_y + 50

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        # Background
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(241, 250, 140, 40))
        gradient.setColorAt(1, QColor(241, 250, 140, 20))

        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.fillPath(path, QBrush(gradient))

        # Border
        painter.setPen(QPen(QColor("#f1fa8c"), 1.5, Qt.DashLine))
        painter.drawPath(path)


class TreeNodeWidget(GraphicsObjectWidget):
    """Individual node in tree visualization"""

    def __init__(self, value: Any, parent=None):
        super().__init__(parent)
        self.value = value

        self.value_text = QGraphicsTextItem(str(value), self)
        self.value_text.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.value_text.setDefaultTextColor(QColor("#282a36"))

        self._update_text_position()

    def _update_text_position(self):
        text_rect = self.value_text.boundingRect()
        x = (TREE_NODE_SIZE - text_rect.width()) / 2
        y = (TREE_NODE_SIZE - text_rect.height()) / 2
        self.value_text.setPos(x, y)

    def boundingRect(self):
        return QRectF(0, 0, TREE_NODE_SIZE, TREE_NODE_SIZE)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        # Node circle
        painter.setPen(QPen(QColor("#f1fa8c"), 2))
        painter.setBrush(QColor("#f1fa8c"))
        painter.drawEllipse(rect)

    def highlight(self, color: QColor = HIGHLIGHT_ANIMATION_COLOR):
        """Highlight this node"""
        glow = QGraphicsDropShadowEffect()
        glow.setColor(color)
        glow.setBlurRadius(20)
        self.setGraphicsEffect(glow)

        QTimer.singleShot(1000, lambda: self.setGraphicsEffect(None))


class TreeConnectionWidget(QGraphicsObject):
    """Line connecting two tree nodes"""

    def __init__(self, start_node, end_node, parent=None):
        super().__init__(parent)
        self.start_node = start_node
        self.end_node = end_node
        self.setZValue(-1)  # Ensure lines are drawn behind nodes

    def boundingRect(self):
        # A rect that encompasses both nodes
        return self.start_node.sceneBoundingRect().united(self.end_node.sceneBoundingRect())

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        start_point = self.start_node.scenePos() + QPointF(TREE_NODE_SIZE / 2, TREE_NODE_SIZE)
        end_point = self.end_node.scenePos() + QPointF(TREE_NODE_SIZE / 2, 0)

        pen = QPen(QColor("#6272a4"), 2, Qt.SolidLine)
        painter.setPen(pen)
        painter.drawLine(start_point, end_point)


class DictionaryWidget(GraphicsObjectWidget):
    """Visualizes dictionaries (hash maps) with key-value pairs"""

    def __init__(self, name: str, dict_data: Dict, parent=None):
        super().__init__(parent)
        self.name = name
        self.dict_data = dict_data.copy() if dict_data else {}
        self.pair_widgets = {}
        self._width = 300
        self._height = 0

        self.name_text = QGraphicsTextItem(f"{self.name} {{}}", self)
        self.name_text.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.name_text.setDefaultTextColor(QColor("#ff79c6"))

        self._create_pairs()
        self._update_layout()

    def _create_pairs(self):
        for widget in self.pair_widgets.values():
            if widget.scene():
                widget.scene().removeItem(widget)
        self.pair_widgets.clear()

        for key, value in self.dict_data.items():
            pair_widget = KeyValuePairWidget(key, value, self)
            self.pair_widgets[key] = pair_widget

    def _update_layout(self):
        self.prepareGeometryChange()

        self.name_text.setPos(15, 10)
        y_offset = self.name_text.boundingRect().height() + 25
        max_width = self.name_text.boundingRect().width()

        for key, widget in self.pair_widgets.items():
            widget.setPos(15, y_offset)
            y_offset += widget.boundingRect().height() + 8
            max_width = max(max_width, widget.boundingRect().width())

        self._width = max_width + 30
        self._height = y_offset + 10
        self.positionChanged.emit()

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(255, 121, 198, 40))
        gradient.setColorAt(1, QColor(255, 121, 198, 20))

        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        painter.fillPath(path, QBrush(gradient))

        pen = QPen(QColor("#ff79c6"), 1.5, Qt.DashLine)
        painter.setPen(pen)
        painter.drawPath(path)

    def highlight_key(self, key: Any, color: QColor = HIGHLIGHT_ANIMATION_COLOR):
        if key in self.pair_widgets:
            self.pair_widgets[key].highlight(color)


class KeyValuePairWidget(GraphicsObjectWidget):
    """A single key-value pair for the DictionaryWidget"""

    def __init__(self, key: Any, value: Any, parent=None):
        super().__init__(parent)
        self.key = key
        self.value = value
        self._width = 0
        self._height = 0

        self.key_text = QGraphicsTextItem(f'"{key}":', self)
        self.key_text.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.key_text.setDefaultTextColor(QColor("#ffb86c"))

        self.value_text = QGraphicsTextItem(str(value), self)
        self.value_text.setFont(QFont(FONT_FAMILY, 10))
        self.value_text.setDefaultTextColor(QColor("white"))

        self._update_layout()

    def _update_layout(self):
        self.prepareGeometryChange()
        self.key_text.setPos(10, 5)
        key_width = self.key_text.boundingRect().width()
        self.value_text.setPos(15 + key_width, 5)

        self._width = self.value_text.pos().x() + self.value_text.boundingRect().width() + 10
        self._height = max(self.key_text.boundingRect().height(), self.value_text.boundingRect().height()) + 10

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()
        painter.setBrush(QColor(68, 71, 90, 180))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 5, 5)

    def highlight(self, color: QColor):
        glow = QGraphicsDropShadowEffect()
        glow.setColor(color)
        glow.setBlurRadius(15)
        self.setGraphicsEffect(glow)
        QTimer.singleShot(1000, lambda: self.setGraphicsEffect(None))


class ObjectWidget(GraphicsObjectWidget):
    """Visualizes class instances with their attributes and methods"""

    def __init__(self, name: str, obj_data: object, parent=None):
        super().__init__(parent)
        self.name = name
        self.obj_data = obj_data
        self.class_name = obj_data.__class__.__name__
        self.attribute_widgets = {}
        self._width = 0
        self._height = 0
        self.expanded = True

        # Header text showing class name
        self.header_text = QGraphicsTextItem(f"{self.name}: {self.class_name}", self)
        self.header_text.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.header_text.setDefaultTextColor(QColor("#8be9fd"))  # Cyan for objects

        # Expand/collapse button
        self.toggle_button = QGraphicsTextItem("▼", self)
        self.toggle_button.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.toggle_button.setDefaultTextColor(QColor("#8be9fd"))

        self._create_attributes()
        self._update_layout()

    def _create_attributes(self):
        """Create widgets for object attributes"""
        # Clear existing attribute widgets
        for widget in self.attribute_widgets.values():
            if widget.scene():
                widget.scene().removeItem(widget)
        self.attribute_widgets.clear()

        # Get object attributes (excluding methods and private attributes)
        if hasattr(self.obj_data, '__dict__'):
            attributes = {k: v for k, v in self.obj_data.__dict__.items()
                          if not k.startswith('_') and not callable(v)}
        else:
            # For objects without __dict__ (like built-in types)
            attributes = {}
            for attr in dir(self.obj_data):
                if not attr.startswith('_') and not callable(getattr(self.obj_data, attr)):
                    try:
                        attributes[attr] = getattr(self.obj_data, attr)
                    except:
                        pass

        # Create attribute widgets
        for attr_name, attr_value in attributes.items():
            attr_widget = ObjectAttributeWidget(attr_name, attr_value, self)
            self.attribute_widgets[attr_name] = attr_widget

    def _update_layout(self):
        self.prepareGeometryChange()

        # Position header
        self.header_text.setPos(25, 10)
        self.toggle_button.setPos(5, 10)

        header_height = self.header_text.boundingRect().height()
        y_offset = header_height + 20
        max_width = self.header_text.boundingRect().width() + 30

        if self.expanded:
            # Position attribute widgets
            for attr_widget in self.attribute_widgets.values():
                attr_widget.setPos(15, y_offset)
                attr_widget.show()
                y_offset += attr_widget.boundingRect().height() + 5
                max_width = max(max_width, attr_widget.boundingRect().width() + 30)
        else:
            # Hide attribute widgets when collapsed
            for attr_widget in self.attribute_widgets.values():
                attr_widget.hide()

        self._width = max_width
        self._height = y_offset + 10
        self.positionChanged.emit()

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        # Background gradient
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(139, 233, 253, 40))  # Cyan theme
        gradient.setColorAt(1, QColor(139, 233, 253, 20))

        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.fillPath(path, QBrush(gradient))

        # Border
        painter.setPen(QPen(QColor("#8be9fd"), 2))
        painter.drawPath(path)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        # Toggle expansion when clicking the button area
        if event.pos().x() < 20:
            self.toggle_expansion()

    def toggle_expansion(self):
        """Toggle between expanded and collapsed states"""
        self.expanded = not self.expanded
        self.toggle_button.setPlainText("▼" if self.expanded else "▶")
        self._update_layout()

    def update_object(self, new_obj):
        """Update object data and refresh visualization"""
        self.obj_data = new_obj
        self.class_name = new_obj.__class__.__name__
        self.header_text.setPlainText(f"{self.name}: {self.class_name}")
        self._create_attributes()
        self._update_layout()


class ObjectAttributeWidget(GraphicsObjectWidget):
    """Widget for individual object attributes"""

    def __init__(self, attr_name: str, attr_value: Any, parent=None):
        super().__init__(parent)
        self.attr_name = attr_name
        self.attr_value = attr_value
        self._width = 0
        self._height = 0

        # Attribute name
        self.name_text = QGraphicsTextItem(f"{attr_name}:", self)
        self.name_text.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        self.name_text.setDefaultTextColor(QColor("#ffb86c"))  # Orange for attribute names

        # Attribute value
        value_str = self._format_value(attr_value)
        self.value_text = QGraphicsTextItem(value_str, self)
        self.value_text.setFont(QFont(FONT_FAMILY, 9))
        self.value_text.setDefaultTextColor(QColor("white"))

        self._update_layout()

    def _format_value(self, value):
        """Format attribute value for display"""
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, (list, tuple)):
            return f"{type(value).__name__}({len(value)} items)"
        elif hasattr(value, '__dict__'):
            return f"{value.__class__.__name__} object"
        else:
            return str(value)

    def _update_layout(self):
        self.prepareGeometryChange()

        self.name_text.setPos(10, 5)
        name_width = self.name_text.boundingRect().width()
        self.value_text.setPos(15 + name_width, 5)

        self._width = self.value_text.pos().x() + self.value_text.boundingRect().width() + 10
        self._height = max(self.name_text.boundingRect().height(),
                           self.value_text.boundingRect().height()) + 10

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        # Subtle background for attributes
        painter.setBrush(QColor(68, 71, 90, 120))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 4, 4)
