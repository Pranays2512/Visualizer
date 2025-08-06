# /ui/advanced_data_visualizer.py

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from typing import Any, List, Dict, Optional, Union
import math

# Import from your existing files
from .dynamic_layout_manager import (
    GraphicsObjectWidget, SmoothAnimation, EnhancedParticleEffect as ParticleEffect,
    FONT_FAMILY, ANIMATION_DURATION, GLOW_COLOR, PINK_COLOR,
    LINE_COLOR, SCOPE_COLOR, BACKGROUND_COLOR, HOVER_SCALE
)

# Constants
ARRAY_CELL_WIDTH, ARRAY_CELL_HEIGHT = 50, 35
TREE_NODE_SIZE, TREE_LEVEL_HEIGHT = 40, 70
LIST_NODE_WIDTH, LIST_NODE_HEIGHT = 80, 40
STRING_CHAR_WIDTH = 25
LOOP_INDICATOR_COLOR = QColor("#ffb86c")
HIGHLIGHT_ANIMATION_COLOR = QColor("#50fa7b")


class BaseDataWidget(GraphicsObjectWidget):
    """Base class for data visualization widgets"""

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name
        self._width = self._height = 0

    def create_name_text(self, text: str, color: str):
        """Helper to create name text with consistent styling"""
        name_text = QGraphicsTextItem(text, self)
        name_text.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        name_text.setDefaultTextColor(QColor(color))
        return name_text

    def paint_background(self, painter, color: str, dash=False):
        """Helper to paint consistent backgrounds"""
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        # Background gradient
        gradient = QLinearGradient(0, 0, 0, rect.height())
        base_color = QColor(color)
        gradient.setColorAt(0, QColor(base_color.red(), base_color.green(), base_color.blue(), 40))
        gradient.setColorAt(1, QColor(base_color.red(), base_color.green(), base_color.blue(), 20))

        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.fillPath(path, QBrush(gradient))

        # Border
        pen_style = Qt.DashLine if dash else Qt.SolidLine
        painter.setPen(QPen(QColor(color), 1.5, pen_style))
        painter.drawPath(path)

    def add_highlight_effect(self, widget, color=HIGHLIGHT_ANIMATION_COLOR):
        """Add highlight animation to widget"""
        glow = QGraphicsDropShadowEffect()
        glow.setColor(color)
        glow.setBlurRadius(15)
        widget.setGraphicsEffect(glow)
        QTimer.singleShot(1000, lambda: widget.setGraphicsEffect(None))

        # Scale animation
        anim = SmoothAnimation(widget, b'scale')
        anim.setStartValue(1.0)
        anim.setEndValue(1.2)
        anim.setDuration(200)
        anim.finished.connect(lambda: self._return_scale(widget))
        anim.start()

    def _return_scale(self, widget):
        anim = SmoothAnimation(widget, b'scale')
        anim.setStartValue(1.2)
        anim.setEndValue(1.0)
        anim.setDuration(200)
        anim.start()


class CellWidget(GraphicsObjectWidget):
    """Generic cell widget for arrays, strings, etc."""

    def __init__(self, value: Any, width: int, height: int, color: str, parent=None):
        super().__init__(parent)
        self.value = value
        self._width, self._height = width, height
        self.color = color

        self.value_text = QGraphicsTextItem(str(value), self)
        self.value_text.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.value_text.setDefaultTextColor(QColor("white"))
        self._center_text()

    def _center_text(self):
        text_rect = self.value_text.boundingRect()
        x = (self._width - text_rect.width()) / 2
        y = (self._height - text_rect.height()) / 2
        self.value_text.setPos(x, y)

    def set_width(self, width):
        self._width = max(30, width)
        self._center_text()

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(self.color).darker(150))
        painter.setPen(QPen(QColor(self.color), 1))
        painter.drawRoundedRect(self.boundingRect(), 3, 3)


class ArrayWidget(BaseDataWidget):
    """Optimized array visualization"""

    def __init__(self, name: str, array_data: List[Any], parent=None):
        super().__init__(name, parent)
        self.array_data = array_data.copy() if array_data else []
        self.cell_widgets = []
        self.index_labels = []

        self.name_text = self.create_name_text(f'{name} = {self.array_data}', "#50fa7b")
        self._create_cells()
        self._layout()

    def _create_cells(self):
        # Clear existing
        for item in self.cell_widgets + self.index_labels:
            if item.scene():
                item.scene().removeItem(item)
        self.cell_widgets.clear()
        self.index_labels.clear()

        font_metrics = QFontMetrics(QFont(FONT_FAMILY, 10))
        for i, value in enumerate(self.array_data):
            # Create cell
            width = max(30, font_metrics.width(str(value)) + 18)
            cell = CellWidget(value, width, ARRAY_CELL_HEIGHT, "#50fa7b", self)
            self.cell_widgets.append(cell)

            # Create index label
            label = QGraphicsTextItem(str(i), self)
            label.setFont(QFont(FONT_FAMILY, 8))
            label.setDefaultTextColor(QColor("#6272a4"))
            self.index_labels.append(label)

    def _layout(self):
        self.prepareGeometryChange()
        self.name_text.setPos(10, 5)
        name_height = self.name_text.boundingRect().height()
        start_y = name_height + 15

        x = 10
        for cell, label in zip(self.cell_widgets, self.index_labels):
            cell.setPos(x, start_y)
            label_x = x + (cell._width - label.boundingRect().width()) / 2
            label.setPos(label_x, start_y + cell._height + 5)
            x += cell._width + 2

        self._width = x + 10 if self.cell_widgets else max(200, self.name_text.boundingRect().width() + 20)
        self._height = start_y + ARRAY_CELL_HEIGHT + 30

    def update_array(self, new_array: List[Any]):
        if new_array != self.array_data:
            self.array_data = new_array.copy()
            self.name_text.setPlainText(f'{self.name} = {self.array_data}')
            self._create_cells()
            self._layout()

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        self.paint_background(painter, "#50fa7b")


class StringWidget(BaseDataWidget):
    """Optimized string visualization"""

    def __init__(self, name: str, string_data: str, parent=None):
        super().__init__(name, parent)
        self.string_data = string_data or ""
        self.char_widgets = []

        self.name_text = self.create_name_text(f'{name} = "{string_data}"', "#50fa7b")
        self._create_chars()
        self._layout()

    def _create_chars(self):
        for char in self.char_widgets:
            if char.scene():
                char.scene().removeItem(char)
        self.char_widgets = [CellWidget(c if c != ' ' else '·', STRING_CHAR_WIDTH, 30, "#50fa7b", self)
                             for c in self.string_data]

    def _layout(self):
        self.prepareGeometryChange()
        self.name_text.setPos(10, 5)
        name_height = self.name_text.boundingRect().height()
        start_y = name_height + 15

        for i, char in enumerate(self.char_widgets):
            char.setPos(10 + i * (STRING_CHAR_WIDTH + 1), start_y)

        self._width = 10 + len(self.string_data) * (STRING_CHAR_WIDTH + 1) + 10 if self.string_data else max(200,
                                                                                                             self.name_text.boundingRect().width() + 20)
        self._height = start_y + 40

    def update_string(self, new_string: str):
        if new_string != self.string_data:
            self.string_data = new_string
            self.name_text.setPlainText(f'{self.name} = "{new_string}"')
            self._create_chars()
            self._layout()

    def highlight_char(self, index: int, color=HIGHLIGHT_ANIMATION_COLOR):
        if 0 <= index < len(self.char_widgets):
            self.add_highlight_effect(self.char_widgets[index], color)

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        self.paint_background(painter, "#50fa7b")


class LinkedListWidget(BaseDataWidget):
    """Optimized linked list visualization"""

    def __init__(self, name: str, list_data: List[Any], parent=None):
        super().__init__(name, parent)
        self.list_data = list_data.copy() if list_data else []
        self.node_widgets = []
        self.arrow_widgets = []

        self.name_text = self.create_name_text(f"{name} (Linked List)", "#bd93f9")
        self._create_nodes()
        self._layout()

    def _create_nodes(self):
        # Clear existing
        for item in self.node_widgets + self.arrow_widgets:
            if item.scene():
                item.scene().removeItem(item)
        self.node_widgets.clear()
        self.arrow_widgets.clear()

        # Create nodes and arrows
        for value in self.list_data:
            self.node_widgets.append(LinkedListNodeWidget(value, self))
        for _ in range(len(self.node_widgets) - 1):
            self.arrow_widgets.append(LinkedListArrowWidget(self))

    def _layout(self):
        self.prepareGeometryChange()
        self.name_text.setPos(10, 5)
        name_height = self.name_text.boundingRect().height()
        start_y = name_height + 15

        for i, node in enumerate(self.node_widgets):
            x = 10 + i * (LIST_NODE_WIDTH + 30)
            node.setPos(x, start_y)

            if i < len(self.arrow_widgets):
                self.arrow_widgets[i].setPos(x + LIST_NODE_WIDTH + 5, start_y + LIST_NODE_HEIGHT // 2 - 5)

        self._width = 10 + len(self.list_data) * (LIST_NODE_WIDTH + 30) - 20 if self.list_data else max(150,
                                                                                                        self.name_text.boundingRect().width() + 20)
        self._height = start_y + LIST_NODE_HEIGHT + 20

    def update_list(self, new_data: List[Any]):
        self.list_data = new_data.copy()
        self._create_nodes()
        self._layout()

    def highlight_node(self, index: int, color=HIGHLIGHT_ANIMATION_COLOR):
        if 0 <= index < len(self.node_widgets):
            self.add_highlight_effect(self.node_widgets[index], color)

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        self.paint_background(painter, "#bd93f9", dash=True)


class LinkedListNodeWidget(GraphicsObjectWidget):
    """Linked list node"""

    def __init__(self, value: Any, parent=None):
        super().__init__(parent)
        self.value = value

        self.value_text = QGraphicsTextItem(str(value), self)
        self.value_text.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.value_text.setDefaultTextColor(QColor("white"))

        text_rect = self.value_text.boundingRect()
        self.value_text.setPos((LIST_NODE_WIDTH - 15 - text_rect.width()) / 2,
                               (LIST_NODE_HEIGHT - text_rect.height()) / 2)

    def boundingRect(self):
        return QRectF(0, 0, LIST_NODE_WIDTH, LIST_NODE_HEIGHT)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        painter.setBrush(QColor("#bd93f9").darker(130))
        painter.setPen(QPen(QColor("#bd93f9"), 2))
        painter.drawRoundedRect(rect, 6, 6)

        # Pointer section
        pointer_rect = QRectF(rect.width() - 15, 5, 10, rect.height() - 10)
        painter.setBrush(QColor("#44475a"))
        painter.drawRoundedRect(pointer_rect, 2, 2)


class LinkedListArrowWidget(GraphicsObjectWidget):
    """Arrow between linked list nodes"""

    def boundingRect(self):
        return QRectF(0, 0, 20, 10)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#bd93f9"), 2))
        painter.setBrush(QColor("#bd93f9"))

        painter.drawLine(0, 5, 15, 5)
        painter.drawPolygon(QPolygonF([QPointF(15, 5), QPointF(10, 2), QPointF(10, 8)]))


class TreeWidget(BaseDataWidget):
    """Optimized tree visualization"""

    def __init__(self, name: str, tree_data: Dict, parent=None):
        super().__init__(name, parent)
        self.tree_data = tree_data or {}
        self.node_widgets = {}
        self.connection_lines = []

        self.name_text = self.create_name_text(f"{name} (Binary Tree)", "#f1fa8c")

        if self.tree_data:
            self._create_tree()

    def _create_tree(self):
        # Clear existing
        for item in list(self.node_widgets.values()) + self.connection_lines:
            if item.scene():
                item.scene().removeItem(item)
        self.node_widgets.clear()
        self.connection_lines.clear()

        # Calculate positions and create nodes
        self.positions = {}
        self._calc_positions(self.tree_data, 0, 0, 200)
        self._create_nodes(self.tree_data)
        self._layout()

    def _calc_positions(self, node, level, pos, width):
        if not isinstance(node, dict) or 'value' not in node or level > 6:
            return

        node_id = id(node)
        self.positions[node_id] = {'level': level, 'x': max(-300, min(300, pos)), 'y': level * TREE_LEVEL_HEIGHT}

        child_width = max(width / 2.5, 40)
        if 'left' in node and node['left']:
            self._calc_positions(node['left'], level + 1, pos - child_width, child_width)
        if 'right' in node and node['right']:
            self._calc_positions(node['right'], level + 1, pos + child_width, child_width)

    def _create_nodes(self, node):
        if not isinstance(node, dict) or 'value' not in node:
            return None

        widget = TreeNodeWidget(node['value'], self)
        self.node_widgets[id(node)] = widget

        # Create child connections
        for child_key in ['left', 'right']:
            if child_key in node and node[child_key]:
                child_widget = self._create_nodes(node[child_key])
                if child_widget:
                    connection = TreeConnectionWidget(widget, child_widget, self)
                    self.connection_lines.append(connection)

        return widget

    def _layout(self):
        self.prepareGeometryChange()
        self.name_text.setPos(10, 5)
        start_y = self.name_text.boundingRect().height() + 20

        if self.positions:
            min_x = min(p['x'] for p in self.positions.values())
            x_offset = 50 - min_x

            for node_id, pos in self.positions.items():
                if node_id in self.node_widgets:
                    self.node_widgets[node_id].setPos(pos['x'] + x_offset, start_y + pos['y'])

            max_x = max(p['x'] for p in self.positions.values())
            max_level = max(p['level'] for p in self.positions.values())
            self._width = max_x - min_x + 100
            self._height = start_y + (max_level + 1) * TREE_LEVEL_HEIGHT
        else:
            self._width = max(200, self.name_text.boundingRect().width() + 20)
            self._height = start_y + 50

    def update_tree(self, new_tree_data: Dict):
        self.tree_data = new_tree_data or {}
        if self.tree_data:
            self._create_tree()
        else:
            self._layout()

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        self.paint_background(painter, "#f1fa8c", dash=True)


class TreeNodeWidget(GraphicsObjectWidget):
    """Tree node widget"""

    def __init__(self, value: Any, parent=None):
        super().__init__(parent)
        self.value = value

        self.value_text = QGraphicsTextItem(str(value), self)
        self.value_text.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.value_text.setDefaultTextColor(QColor("#282a36"))

        text_rect = self.value_text.boundingRect()
        self.value_text.setPos((TREE_NODE_SIZE - text_rect.width()) / 2,
                               (TREE_NODE_SIZE - text_rect.height()) / 2)

    def boundingRect(self):
        return QRectF(0, 0, TREE_NODE_SIZE, TREE_NODE_SIZE)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#f1fa8c"), 2))
        painter.setBrush(QColor("#f1fa8c"))
        painter.drawEllipse(self.boundingRect())


class TreeConnectionWidget(QGraphicsObject):
    """Tree connection line"""

    def __init__(self, start_node, end_node, parent=None):
        super().__init__(parent)
        self.start_node = start_node
        self.end_node = end_node
        self.setZValue(-1)

    def boundingRect(self):
        if self.start_node and self.end_node:
            start_pos = self.start_node.pos()
            end_pos = self.end_node.pos()
            return QRectF(min(start_pos.x(), end_pos.x()) - 10, min(start_pos.y(), end_pos.y()) - 10,
                          abs(end_pos.x() - start_pos.x()) + TREE_NODE_SIZE + 20,
                          abs(end_pos.y() - start_pos.y()) + TREE_NODE_SIZE + 20)
        return QRectF(0, 0, 100, 100)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        if self.parentItem():
            start_local = self.parentItem().mapFromItem(self.start_node, TREE_NODE_SIZE / 2, TREE_NODE_SIZE)
            end_local = self.parentItem().mapFromItem(self.end_node, TREE_NODE_SIZE / 2, 0)
            start_point = self.mapFromParent(start_local)
            end_point = self.mapFromParent(end_local)
        else:
            start_point = self.start_node.pos() + QPointF(TREE_NODE_SIZE / 2, TREE_NODE_SIZE)
            end_point = self.end_node.pos() + QPointF(TREE_NODE_SIZE / 2, 0)

        painter.setPen(QPen(QColor("#6272a4"), 2))
        painter.drawLine(start_point, end_point)


class DictionaryWidget(BaseDataWidget):
    """Optimized dictionary visualization"""

    def __init__(self, name: str, dict_data: Dict, parent=None):
        super().__init__(name, parent)
        self.dict_data = dict_data.copy() if dict_data else {}
        self.pair_widgets = {}
        self._width = 300

        self.name_text = self.create_name_text(f"{name} {{}}", "#ff79c6")
        self._create_pairs()
        self._layout()

    def _create_pairs(self):
        for widget in self.pair_widgets.values():
            if widget.scene():
                widget.scene().removeItem(widget)
        self.pair_widgets = {k: KeyValuePairWidget(k, v, self) for k, v in self.dict_data.items()}

    def _layout(self):
        self.prepareGeometryChange()
        self.name_text.setPos(15, 10)
        y = self.name_text.boundingRect().height() + 25
        max_width = self.name_text.boundingRect().width()

        for widget in self.pair_widgets.values():
            widget.setPos(15, y)
            y += widget.boundingRect().height() + 8
            max_width = max(max_width, widget.boundingRect().width())

        self._width = max_width + 30
        self._height = y + 10

    def highlight_key(self, key: Any, color=HIGHLIGHT_ANIMATION_COLOR):
        if key in self.pair_widgets:
            self.add_highlight_effect(self.pair_widgets[key], color)

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        self.paint_background(painter, "#ff79c6", dash=True)


class KeyValuePairWidget(GraphicsObjectWidget):
    """Key-value pair widget"""

    def __init__(self, key: Any, value: Any, parent=None):
        super().__init__(parent)
        self.key, self.value = key, value

        self.key_text = QGraphicsTextItem(f'"{key}":', self)
        self.key_text.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.key_text.setDefaultTextColor(QColor("#ffb86c"))

        self.value_text = QGraphicsTextItem(str(value), self)
        self.value_text.setFont(QFont(FONT_FAMILY, 10))
        self.value_text.setDefaultTextColor(QColor("white"))

        self.key_text.setPos(10, 5)
        self.value_text.setPos(15 + self.key_text.boundingRect().width(), 5)

        self._width = self.value_text.pos().x() + self.value_text.boundingRect().width() + 10
        self._height = max(self.key_text.boundingRect().height(), self.value_text.boundingRect().height()) + 10

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(68, 71, 90, 180))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.boundingRect(), 5, 5)


class ObjectWidget(BaseDataWidget):
    """Optimized object visualization"""

    def __init__(self, name: str, obj_data: object, parent=None):
        super().__init__(name, parent)
        self.obj_data = obj_data
        self.class_name = obj_data.__class__.__name__
        self.attribute_widgets = {}
        self.expanded = True

        self.header_text = self.create_name_text(f"{name}: {self.class_name}", "#8be9fd")
        self.toggle_button = QGraphicsTextItem("▼", self)
        self.toggle_button.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.toggle_button.setDefaultTextColor(QColor("#8be9fd"))

        self._create_attributes()
        self._layout()

    def _create_attributes(self):
        for widget in self.attribute_widgets.values():
            if widget.scene():
                widget.scene().removeItem(widget)
        self.attribute_widgets.clear()

        # Get attributes
        if hasattr(self.obj_data, '__dict__'):
            attrs = {k: v for k, v in self.obj_data.__dict__.items() if not k.startswith('_') and not callable(v)}
        else:
            attrs = {}
            for attr in dir(self.obj_data):
                if not attr.startswith('_') and not callable(getattr(self.obj_data, attr, None)):
                    try:
                        attrs[attr] = getattr(self.obj_data, attr)
                    except:
                        pass

        self.attribute_widgets = {name: ObjectAttributeWidget(name, value, self) for name, value in attrs.items()}

    def _layout(self):
        self.prepareGeometryChange()
        self.header_text.setPos(25, 10)
        self.toggle_button.setPos(5, 10)

        y = self.header_text.boundingRect().height() + 20
        max_width = self.header_text.boundingRect().width() + 30

        for widget in self.attribute_widgets.values():
            if self.expanded:
                widget.setPos(15, y)
                widget.show()
                y += widget.boundingRect().height() + 5
                max_width = max(max_width, widget.boundingRect().width() + 30)
            else:
                widget.hide()

        self._width = max_width
        self._height = y + 10

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.pos().x() < 20:
            self.expanded = not self.expanded
            self.toggle_button.setPlainText("▼" if self.expanded else "▶")
            self._layout()

    def update_object(self, new_obj):
        self.obj_data = new_obj
        self.class_name = new_obj.__class__.__name__
        self.header_text.setPlainText(f"{self.name}: {self.class_name}")
        self._create_attributes()
        self._layout()

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        self.paint_background(painter, "#8be9fd")


class ObjectAttributeWidget(GraphicsObjectWidget):
    """Object attribute widget"""

    def __init__(self, attr_name: str, attr_value: Any, parent=None):
        super().__init__(parent)
        self.attr_name, self.attr_value = attr_name, attr_value

        # Format value
        if isinstance(attr_value, str):
            value_str = f'"{attr_value}"'
        elif isinstance(attr_value, (list, tuple)):
            value_str = f"{type(attr_value).__name__}({len(attr_value)} items)"
        elif hasattr(attr_value, '__dict__'):
            value_str = f"{attr_value.__class__.__name__} object"
        else:
            value_str = str(attr_value)

        self.name_text = QGraphicsTextItem(f"{attr_name}:", self)
        self.name_text.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        self.name_text.setDefaultTextColor(QColor("#ffb86c"))

        self.value_text = QGraphicsTextItem(value_str, self)
        self.value_text.setFont(QFont(FONT_FAMILY, 9))
        self.value_text.setDefaultTextColor(QColor("white"))

        self.name_text.setPos(10, 5)
        name_width = self.name_text.boundingRect().width()
        self.value_text.setPos(15 + name_width, 5)

        self._width = self.value_text.pos().x() + self.value_text.boundingRect().width() + 10
        self._height = max(self.name_text.boundingRect().height(), self.value_text.boundingRect().height()) + 10

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(68, 71, 90, 120))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.boundingRect(), 4, 4)