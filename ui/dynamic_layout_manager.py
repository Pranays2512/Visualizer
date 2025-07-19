# /ui/dynamic_layout_manager.py

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from typing import Any, List, Tuple

# --- UI Constants ---
FONT_FAMILY = "Fira Code"
ANIMATION_DURATION = 300
GLOW_COLOR = QColor("#50fa7b")
PINK_COLOR = QColor("#ff79c6")
LINE_COLOR = QColor("#bd93f9")
WALL_COLOR = QColor("#44475a")
MARGIN = 20
H_SPACING = 15
V_SPACING = 15
MIN_CANVAS_WIDTH = 800
MIN_CANVAS_HEIGHT = 600
WALL_THICKNESS = 3


class GraphicsObjectWidget(QGraphicsObject):
    """Base class for custom graphics items that can be animated and have signals."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)  # Disable manual moving
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

        self.opacity_effect = QGraphicsOpacityEffect()
        self.animation = QPropertyAnimation(self, b"opacity")
        self.animation.setDuration(ANIMATION_DURATION)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.setOpacity(0.0)

        # Position animation
        self.pos_animation_obj = QPropertyAnimation(self, b'pos')
        self.pos_animation_obj.setDuration(ANIMATION_DURATION)
        self.pos_animation_obj.setEasingCurve(QEasingCurve.OutQuad)

    def show_animated(self):
        self.setOpacity(0.0)
        self.animation.setDirection(QPropertyAnimation.Forward)
        self.animation.start()

    def move_to_position(self, end_pos: QPointF):
        """Smooth animation to new position"""
        self.pos_animation_obj.setEndValue(end_pos)
        self.pos_animation_obj.start()

    def get_content_size(self):
        """Return the actual content size of the widget"""
        return self.boundingRect().size()


class SmartVariableWidget(GraphicsObjectWidget):
    def __init__(self, name: str, value: Any, parent=None):
        super().__init__(parent)
        self.name = name
        self.value = value

        # Create child QGraphicsTextItems
        self.name_text = QGraphicsTextItem(self.name, self)
        self.name_text.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.name_text.setDefaultTextColor(QColor("#8be9fd"))

        self.value_text = QGraphicsTextItem(str(self.value), self)
        self.value_text.setFont(QFont(FONT_FAMILY, 11))
        self.value_text.setDefaultTextColor(QColor("white"))

        self._update_layout()

    def _update_layout(self):
        self.name_text.setPos(10, 10)
        self.value_text.setPos(self.name_text.boundingRect().width() + 20, 10)
        self.width = self.value_text.pos().x() + self.value_text.boundingRect().width() + 10
        self.height = max(self.name_text.boundingRect().height(), self.value_text.boundingRect().height()) + 20

    def boundingRect(self):
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect(), 8, 8)
        painter.fillPath(path, QColor(68, 71, 90, 240))
        painter.setPen(QPen(QColor("#bd93f9"), 1))
        painter.drawPath(path)

    def update_value(self, value: Any):
        self.value = value
        self.value_text.setPlainText(str(value))
        old_size = self.boundingRect().size()
        self._update_layout()
        new_size = self.boundingRect().size()

        # Only call prepareGeometryChange if size actually changed
        if old_size != new_size:
            self.prepareGeometryChange()

        # Glow effect for updates
        glow_effect = QGraphicsDropShadowEffect()
        glow_effect.setColor(GLOW_COLOR)
        glow_effect.setBlurRadius(25)
        self.setGraphicsEffect(glow_effect)
        QTimer.singleShot(ANIMATION_DURATION * 2, lambda: self.setGraphicsEffect(None))


class SmartPrintBlock(GraphicsObjectWidget):
    def __init__(self, expression_str: str, result: Any, parent=None):
        super().__init__(parent)
        self.title_text = QGraphicsTextItem(f"print({expression_str})", self)
        self.title_text.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.title_text.setDefaultTextColor(PINK_COLOR)

        self.prints_label = QGraphicsTextItem("Output:", self)
        self.prints_label.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.prints_label.setDefaultTextColor(QColor("#f8f8f2"))

        self.result_label = QGraphicsTextItem(str(result), self)
        self.result_label.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.result_label.setDefaultTextColor(GLOW_COLOR)

        self._update_layout()

    def _update_layout(self):
        self.title_text.setPos(10, 10)
        self.prints_label.setPos(20, self.title_text.boundingRect().height() + 25)
        self.result_label.setPos(self.prints_label.pos().x() + self.prints_label.boundingRect().width() + 15,
                                 self.prints_label.pos().y())
        self.width = max(self.title_text.boundingRect().width(),
                         self.result_label.pos().x() + self.result_label.boundingRect().width()) + 20
        self.height = self.result_label.pos().y() + self.result_label.boundingRect().height() + 20

    def boundingRect(self):
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        # Main background
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect(), 10, 10)
        painter.fillPath(path, QColor(40, 42, 54, 240))
        painter.setPen(QPen(PINK_COLOR, 1))
        painter.drawPath(path)

        # Inner result box
        inner_rect = QRectF(self.prints_label.pos() - QPointF(10, 5),
                            self.result_label.pos() + QPointF(self.result_label.boundingRect().width() + 10,
                                                              self.result_label.boundingRect().height() + 5))
        path = QPainterPath()
        path.addRoundedRect(inner_rect, 8, 8)
        painter.setPen(QPen(GLOW_COLOR, 1))
        painter.drawPath(path)


class ConnectionLine(QGraphicsLineItem):
    def __init__(self, start_item, end_item, parent=None):
        super().__init__(parent)
        self.start_item = start_item
        self.end_item = end_item
        self.setPen(QPen(LINE_COLOR, 2, Qt.DashLine))
        self.setZValue(-1)  # Draw behind items
        self.update_positions()

    def update_positions(self):
        if self.start_item and self.end_item:
            start_center = self.start_item.sceneBoundingRect().center()
            end_center = self.end_item.sceneBoundingRect().center()
            self.setLine(QLineF(start_center, end_center))


class SmartLayoutManager:
    """Handles intelligent positioning and layout of items"""

    def __init__(self, canvas_rect: QRectF):
        self.canvas_rect = canvas_rect
        self.occupied_rects: List[QRectF] = []
        self.current_row_y = MARGIN + WALL_THICKNESS
        self.current_row_max_height = 0
        self.rows: List[Tuple[float, float, float]] = []  # (y, max_height, rightmost_x)

    def find_position(self, item_size: QSizeF) -> QPointF:
        """Find the best position for an item without overlapping"""
        width, height = item_size.width(), item_size.height()

        # Try to place in current row first
        if self._can_fit_in_current_row(width, height):
            return self._place_in_current_row(width, height)

        # Start a new row
        return self._start_new_row(width, height)

    def _can_fit_in_current_row(self, width: float, height: float) -> bool:
        """Check if item can fit in the current row"""
        if not self.rows:
            return True

        current_row = self.rows[-1] if self.rows else None
        if current_row is None:
            return True

        _, _, rightmost_x = current_row
        available_width = self.canvas_rect.width() - WALL_THICKNESS - MARGIN - rightmost_x - H_SPACING

        return available_width >= width

    def _place_in_current_row(self, width: float, height: float) -> QPointF:
        """Place item in the current row"""
        if not self.rows:
            x = MARGIN + WALL_THICKNESS
            y = MARGIN + WALL_THICKNESS
            self.rows.append((y, height, x + width))
            return QPointF(x, y)

        current_row = self.rows[-1]
        row_y, max_height, rightmost_x = current_row

        x = rightmost_x + H_SPACING
        y = row_y

        # Update row info
        new_max_height = max(max_height, height)
        new_rightmost_x = x + width
        self.rows[-1] = (row_y, new_max_height, new_rightmost_x)

        return QPointF(x, y)

    def _start_new_row(self, width: float, height: float) -> QPointF:
        """Start a new row for the item"""
        if self.rows:
            last_row_y, last_row_height, _ = self.rows[-1]
            y = last_row_y + last_row_height + V_SPACING
        else:
            y = MARGIN + WALL_THICKNESS

        x = MARGIN + WALL_THICKNESS
        self.rows.append((y, height, x + width))

        return QPointF(x, y)

    def get_required_canvas_size(self) -> QSizeF:
        """Calculate the minimum canvas size needed"""
        if not self.rows:
            return QSizeF(MIN_CANVAS_WIDTH, MIN_CANVAS_HEIGHT)

        # Find the rightmost point and bottom point
        max_right = 0
        max_bottom = 0

        for row_y, row_height, rightmost_x in self.rows:
            max_right = max(max_right, rightmost_x)
            max_bottom = max(max_bottom, row_y + row_height)

        # Add margins and wall thickness
        required_width = max_right + MARGIN + WALL_THICKNESS
        required_height = max_bottom + MARGIN + WALL_THICKNESS

        # Ensure minimum size
        required_width = max(required_width, MIN_CANVAS_WIDTH)
        required_height = max(required_height, MIN_CANVAS_HEIGHT)

        return QSizeF(required_width, required_height)


class DynamicCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

        # Initialize with minimum size
        initial_rect = QRectF(0, 0, MIN_CANVAS_WIDTH, MIN_CANVAS_HEIGHT)
        self.scene.setSceneRect(initial_rect)

        self.items_list: List[GraphicsObjectWidget] = []
        self.connections: List[ConnectionLine] = []
        self.layout_manager = SmartLayoutManager(initial_rect)
        self.wall_items: List[QGraphicsRectItem] = []

        # Create initial walls
        self._create_walls()

    def _create_walls(self):
        """Create wall boundaries around the canvas"""
        self._clear_walls()
        rect = self.scene.sceneRect()

        # Wall style
        wall_pen = QPen(WALL_COLOR, WALL_THICKNESS)
        wall_brush = QBrush(WALL_COLOR.darker(150))

        # Top wall
        top_wall = QGraphicsRectItem(0, 0, rect.width(), WALL_THICKNESS)
        top_wall.setPen(wall_pen)
        top_wall.setBrush(wall_brush)
        top_wall.setZValue(-10)

        # Bottom wall
        bottom_wall = QGraphicsRectItem(0, rect.height() - WALL_THICKNESS,
                                        rect.width(), WALL_THICKNESS)
        bottom_wall.setPen(wall_pen)
        bottom_wall.setBrush(wall_brush)
        bottom_wall.setZValue(-10)

        # Left wall
        left_wall = QGraphicsRectItem(0, 0, WALL_THICKNESS, rect.height())
        left_wall.setPen(wall_pen)
        left_wall.setBrush(wall_brush)
        left_wall.setZValue(-10)

        # Right wall
        right_wall = QGraphicsRectItem(rect.width() - WALL_THICKNESS, 0,
                                       WALL_THICKNESS, rect.height())
        right_wall.setPen(wall_pen)
        right_wall.setBrush(wall_brush)
        right_wall.setZValue(-10)

        # Add walls to scene and track them
        for wall in [top_wall, bottom_wall, left_wall, right_wall]:
            self.scene.addItem(wall)
            self.wall_items.append(wall)

    def _clear_walls(self):
        """Remove existing walls"""
        for wall in self.wall_items:
            self.scene.removeItem(wall)
        self.wall_items.clear()

    def _expand_canvas_if_needed(self):
        """Dynamically expand canvas size based on content"""
        required_size = self.layout_manager.get_required_canvas_size()
        current_rect = self.scene.sceneRect()

        needs_expansion = (required_size.width() > current_rect.width() or
                           required_size.height() > current_rect.height())

        if needs_expansion:
            # Expand canvas
            new_width = max(required_size.width(), current_rect.width())
            new_height = max(required_size.height(), current_rect.height())

            new_rect = QRectF(0, 0, new_width, new_height)
            self.scene.setSceneRect(new_rect)

            # Update layout manager
            self.layout_manager.canvas_rect = new_rect

            # Recreate walls with new size
            self._create_walls()

            # Update all connection lines
            for connection in self.connections:
                connection.update_positions()

    def add_item(self, item: GraphicsObjectWidget):
        """Add an item to the canvas with smart positioning"""
        self.items_list.append(item)

        # Calculate position using layout manager
        item_size = item.get_content_size()
        target_pos = self.layout_manager.find_position(item_size)

        # Add to scene first
        self.scene.addItem(item)

        # Position the item
        item.setPos(target_pos)

        # Expand canvas if needed
        self._expand_canvas_if_needed()

        # Animate the item
        item.show_animated()

    def add_connection(self, start_widget, end_widget):
        """Add a connection line between two widgets"""
        line = ConnectionLine(start_widget, end_widget)
        self.connections.append(line)
        self.scene.addItem(line)

    def clear_all(self):
        """Clear all items and reset the canvas"""
        self.scene.clear()
        self.items_list.clear()
        self.connections.clear()
        self.wall_items.clear()

        # Reset to initial size
        initial_rect = QRectF(0, 0, MIN_CANVAS_WIDTH, MIN_CANVAS_HEIGHT)
        self.scene.setSceneRect(initial_rect)
        self.layout_manager = SmartLayoutManager(initial_rect)

        # Recreate walls
        self._create_walls()

    def resizeEvent(self, event):
        """Handle resize events"""
        super().resizeEvent(event)
        # Ensure the view shows the whole scene
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)