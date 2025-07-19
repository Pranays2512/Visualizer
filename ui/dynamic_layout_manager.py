# /ui/dynamic_layout_manager.py

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from typing import Any, List, Tuple
import math

# --- UI Constants ---
FONT_FAMILY = "Fira Code"
ANIMATION_DURATION = 400
GLOW_COLOR = QColor("#50fa7b")
PINK_COLOR = QColor("#ff79c6")
LINE_COLOR = QColor("#bd93f9")
WALL_COLOR = QColor("#44475a")
SCOPE_COLOR = QColor("#f1fa8c")
MARGIN = 20
H_SPACING = 15
V_SPACING = 15
MIN_CANVAS_WIDTH = 350
MIN_CANVAS_HEIGHT = 400
WALL_THICKNESS = 2
EXPANSION_PADDING = 50


class SmoothAnimation(QPropertyAnimation):
    def __init__(self, target, property_name, parent=None):
        super().__init__(target, property_name, parent)
        self.setDuration(ANIMATION_DURATION)
        self.setEasingCurve(QEasingCurve.OutCubic)


class GraphicsObjectWidget(QGraphicsObject):
    positionChanged = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.opacity_animation = SmoothAnimation(self, b"opacity")
        self.pos_animation = SmoothAnimation(self, b'pos')
        self.scale_animation = SmoothAnimation(self, b'scale')
        self.entrance_group = QParallelAnimationGroup()
        self.entrance_group.addAnimation(self.opacity_animation)
        self.entrance_group.addAnimation(self.scale_animation)
        self.pos_animation.finished.connect(self.positionChanged.emit)
    def show_animated(self):
        self.setOpacity(0.0)
        self.setScale(0.8)
        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        self.scale_animation.setStartValue(0.8)
        self.scale_animation.setEndValue(1.0)
        self.entrance_group.start()
    def remove_animated(self):
        self.opacity_animation.setStartValue(self.opacity())
        self.opacity_animation.setEndValue(0.0)
        self.opacity_animation.finished.connect(self.hide)
        self.opacity_animation.start()
    def move_to_position(self, end_pos: QPointF, delay=0):
        if delay > 0: QTimer.singleShot(delay, lambda: self._start_move_animation(end_pos))
        else: self._start_move_animation(end_pos)
    def _start_move_animation(self, end_pos: QPointF):
        self.pos_animation.setStartValue(self.pos())
        self.pos_animation.setEndValue(end_pos)
        self.pos_animation.start()
    def get_content_size(self):
        return self.boundingRect().size()


class SmartVariableWidget(GraphicsObjectWidget):
    def __init__(self, name: str, value: Any, parent=None):
        super().__init__(parent)
        self.name, self.value = name, value
        self._width, self._height = 0, 0
        self.name_text = QGraphicsTextItem(self.name, self)
        self.name_text.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.name_text.setDefaultTextColor(QColor("#8be9fd"))
        self.value_text = QGraphicsTextItem(str(self.value), self)
        self.value_text.setFont(QFont(FONT_FAMILY, 11))
        self.value_text.setDefaultTextColor(QColor("white"))
        self._update_layout()
    def _update_layout(self):
        self.name_text.setPos(10, 8)
        name_width = self.name_text.boundingRect().width()
        self.value_text.setPos(name_width + 20, 8)
        value_width = self.value_text.boundingRect().width()
        text_height = max(self.name_text.boundingRect().height(), self.value_text.boundingRect().height())
        self._width = name_width + value_width + 35
        self._height = text_height + 16
    def boundingRect(self): return QRectF(0, 0, self._width, self._height)
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(68, 71, 90, 250))
        gradient.setColorAt(1, QColor(60, 63, 82, 250))
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.fillPath(path, gradient)
        painter.setPen(QPen(QColor("#bd93f9"), 1.5))
        painter.drawPath(path)
    def update_value(self, value: Any):
        if self.value == value: return
        if self.parentItem() and isinstance(self.parentItem(), ScopeWidget):
            self.parentItem().prepareGeometryChange()
        self.value = value
        self.value_text.setPlainText(str(value))
        self._update_layout()
        self.prepareGeometryChange()
        if self.parentItem() and isinstance(self.parentItem(), ScopeWidget):
            self.parentItem()._update_layout()
        self._show_update_glow()
    def _show_update_glow(self):
        glow_effect = QGraphicsDropShadowEffect()
        glow_effect.setColor(GLOW_COLOR)
        glow_effect.setBlurRadius(30)
        glow_effect.setOffset(0, 0)
        self.setGraphicsEffect(glow_effect)
        pulse_animation = SmoothAnimation(glow_effect, b'blurRadius')
        pulse_animation.setStartValue(30)
        pulse_animation.setEndValue(15)
        pulse_animation.setLoopCount(2)
        pulse_animation.start()
        QTimer.singleShot(ANIMATION_DURATION * 2, lambda: self.setGraphicsEffect(None))


class SmartPrintBlock(GraphicsObjectWidget):
    def __init__(self, expression_str: str, result: Any, parent=None):
        super().__init__(parent)
        self._width, self._height = 0, 0
        self.title_text = QGraphicsTextItem(f"print({expression_str})", self)
        self.title_text.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.title_text.setDefaultTextColor(PINK_COLOR)
        self.output_label = QGraphicsTextItem("Output:", self)
        self.output_label.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.output_label.setDefaultTextColor(QColor("#f8f8f2"))
        self.result_text = QGraphicsTextItem(str(result), self)
        self.result_text.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.result_text.setDefaultTextColor(GLOW_COLOR)
        self._update_layout()
    def _update_layout(self):
        self.title_text.setPos(12, 10)
        title_height = self.title_text.boundingRect().height()
        self.output_label.setPos(20, title_height + 20)
        output_width = self.output_label.boundingRect().width()
        self.result_text.setPos(20 + output_width + 10, title_height + 20)
        result_pos = self.result_text.pos()
        result_width = self.result_text.boundingRect().width()
        result_height = self.result_text.boundingRect().height()
        self._width = max(self.title_text.boundingRect().width() + 24, result_pos.x() + result_width + 12)
        self._height = result_pos.y() + result_height + 15
    def boundingRect(self): return QRectF(0, 0, self._width, self._height)
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(40, 42, 54, 250))
        gradient.setColorAt(1, QColor(35, 37, 49, 250))
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        painter.fillPath(path, gradient)
        painter.setPen(QPen(PINK_COLOR, 1.5))
        painter.drawPath(path)
        output_rect = QRectF(self.output_label.pos() - QPointF(8, 4), QSizeF(self.result_text.pos().x() + self.result_text.boundingRect().width() - self.output_label.pos().x() + 8, self.result_text.boundingRect().height() + 8))
        inner_path = QPainterPath()
        inner_path.addRoundedRect(output_rect, 6, 6)
        painter.setPen(QPen(GLOW_COLOR.lighter(120), 1))
        painter.drawPath(inner_path)


class ScopeWidget(GraphicsObjectWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title_text = QGraphicsTextItem(title, self)
        self.title_text.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.title_text.setDefaultTextColor(SCOPE_COLOR)
        self.title_text.setPos(15, 10)
        self.child_items: List[GraphicsObjectWidget] = []
        self._width, self._height = 250, 70
        self._update_layout()
    def addItem(self, child_item: GraphicsObjectWidget):
        child_item.setParentItem(self)
        self.child_items.append(child_item)
        self._update_layout()
        child_item.show_animated()
    def _update_layout(self):
        self.prepareGeometryChange()
        y_offset = self.title_text.boundingRect().height() + 25
        max_child_width = 0
        for item in self.child_items:
            item.setPos(15, y_offset)
            y_offset += item.boundingRect().height() + 8
            max_child_width = max(max_child_width, item.boundingRect().width())
        self._width = max(self.title_text.boundingRect().width() + 30, max_child_width + 30)
        self._height = y_offset + 10
        self.positionChanged.emit()
    def boundingRect(self): return QRectF(0, 0, self._width, self._height)
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.setPen(QPen(SCOPE_COLOR, 2, Qt.DotLine))
        painter.setBrush(QColor(40, 42, 54, 220))
        painter.drawPath(path)
    def get_content_size(self):
        self._update_layout()
        return self.boundingRect().size()


class ConnectionLine(QGraphicsObject):
    def __init__(self, start_item, end_item, parent=None):
        super().__init__(parent)
        self.start_item, self.end_item = start_item, end_item
        self._path = QPainterPath()
        self._pen = QPen(LINE_COLOR, 2.5, Qt.DashLine)
        self._pen.setCapStyle(Qt.RoundCap)
        self.setZValue(-1)
        if hasattr(start_item, 'positionChanged'): start_item.positionChanged.connect(self.update_path)
        if hasattr(end_item, 'positionChanged'): end_item.positionChanged.connect(self.update_path)
        self.update_path()
    def boundingRect(self): return self._path.boundingRect()
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self._pen)
        painter.drawPath(self._path)
    @pyqtSlot()
    def update_path(self):
        if not self.scene() or not self.start_item or not self.end_item: return
        self.prepareGeometryChange()
        start_rect, end_rect = self.start_item.sceneBoundingRect(), self.end_item.sceneBoundingRect()
        start_point, end_point = QPointF(start_rect.right(), start_rect.center().y()), QPointF(end_rect.left(), end_rect.center().y())
        path = QPainterPath()
        path.moveTo(start_point)
        control_offset = abs(end_point.x() - start_point.x()) * 0.4
        control1, control2 = QPointF(start_point.x() + control_offset, start_point.y()), QPointF(end_point.x() - control_offset, end_point.y())
        path.cubicTo(control1, control2, end_point)
        self._path = path


class SmartLayoutManager:
    def __init__(self, canvas_rect: QRectF):
        self.canvas_rect = canvas_rect
        self.rows: List[Tuple[float, float, float]] = []
        self._min_row_height = 60
    def find_position(self, item_size: QSizeF) -> QPointF:
        width, height = item_size.width(), item_size.height()
        height = max(height, self._min_row_height)
        if self.rows:
            current_row = self.rows[-1]
            _, _, rightmost_x = current_row
            available_width = (self.canvas_rect.width() - WALL_THICKNESS - MARGIN - rightmost_x - H_SPACING)
            if available_width >= width:
                return self._place_in_row(width, height, len(self.rows) - 1)
        return self._start_new_row(width, height)
    def _place_in_row(self, width: float, height: float, row_index: int) -> QPointF:
        row_y, max_height, rightmost_x = self.rows[row_index]
        x = rightmost_x + H_SPACING
        y = row_y + max(0, (max_height - height) / 2)
        self.rows[row_index] = (row_y, max(max_height, height), x + width)
        return QPointF(x, y)
    def _start_new_row(self, width: float, height: float) -> QPointF:
        if self.rows:
            last_row_y, last_row_height, _ = self.rows[-1]
            y = last_row_y + last_row_height + V_SPACING
        else:
            y = MARGIN + WALL_THICKNESS
        x = MARGIN + WALL_THICKNESS
        self.rows.append((y, height, x + width))
        return QPointF(x, y)
    def reset(self): self.rows.clear()
    def get_required_canvas_size(self) -> QSizeF:
        if not self.rows: return QSizeF(MIN_CANVAS_WIDTH, MIN_CANVAS_HEIGHT)
        max_right, max_bottom = 0, 0
        for row_y, row_height, rightmost_x in self.rows:
            max_right = max(max_right, rightmost_x)
            max_bottom = max(max_bottom, row_y + row_height)
        required_width = max(max_right + MARGIN + EXPANSION_PADDING, MIN_CANVAS_WIDTH)
        required_height = max(max_bottom + MARGIN + EXPANSION_PADDING, MIN_CANVAS_HEIGHT)
        return QSizeF(required_width, required_height)


class DynamicCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

        # --- MODIFIED: Set final scrollbar and size policy behavior ---
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))

        initial_rect = QRectF(0, 0, MIN_CANVAS_WIDTH, MIN_CANVAS_HEIGHT)
        self.scene.setSceneRect(initial_rect)

        self.items_list: List[GraphicsObjectWidget] = []
        self.connections: List[ConnectionLine] = []
        self.layout_manager = SmartLayoutManager(initial_rect)
        self.wall_items: List[QGraphicsRectItem] = []

        self.expansion_animation = QPropertyAnimation(self.scene, b'sceneRect')
        self.expansion_animation.setDuration(ANIMATION_DURATION)
        self.expansion_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.expansion_animation.finished.connect(self._create_walls)
        self._create_walls()

    # --- REMOVED custom sizeHint and other layout overrides ---

    def _create_walls(self):
        for wall in self.wall_items: self.scene.removeItem(wall)
        self.wall_items.clear()
        rect = self.scene.sceneRect()
        wall_pen = QPen(WALL_COLOR, WALL_THICKNESS)
        wall_brush = QBrush(QColor(WALL_COLOR.red(), WALL_COLOR.green(), WALL_COLOR.blue(), 200))
        walls_data = [
            (0, 0, rect.width(), WALL_THICKNESS), (0, rect.height() - WALL_THICKNESS, rect.width(), WALL_THICKNESS),
            (0, 0, WALL_THICKNESS, rect.height()), (rect.width() - WALL_THICKNESS, 0, WALL_THICKNESS, rect.height())]
        for x, y, w, h in walls_data:
            wall = self.scene.addRect(x, y, w, h, wall_pen, wall_brush)
            wall.setZValue(-10)
        self.wall_items.append(wall)

    def _expand_canvas_if_needed(self):
        required_size = self.layout_manager.get_required_canvas_size()
        current_rect = self.scene.sceneRect()
        if required_size.width() > current_rect.width() or required_size.height() > current_rect.height():
            new_width = max(required_size.width(), current_rect.width())
            new_height = max(required_size.height(), current_rect.height())
            new_rect = QRectF(0, 0, new_width, new_height)
            self.expansion_animation.setStartValue(current_rect)
            self.expansion_animation.setEndValue(new_rect)
            self.expansion_animation.start()
            self.layout_manager.canvas_rect = new_rect

    def scroll_to_item(self, item: QGraphicsItem):
        """Scrolls the view to ensure the given item is visible."""
        if item:
            self.ensureVisible(item, 50, 50)

    def add_item(self, item: GraphicsObjectWidget):
        self.items_list.append(item)
        item.positionChanged.connect(self._update_connections)
        item_size = item.get_content_size()
        target_pos = self.layout_manager.find_position(item_size)
        self.scene.addItem(item)
        item.setPos(target_pos)
        self._expand_canvas_if_needed()
        item.show_animated()

        # Auto-scroll to the new item
        QTimer.singleShot(100, lambda: self.scroll_to_item(item))

    def add_connection(self, start_widget, end_widget):
        line = ConnectionLine(start_widget, end_widget)
        self.connections.append(line)
        self.scene.addItem(line)
        line.setOpacity(0.0)
        anim = SmoothAnimation(line, b"opacity", line)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        QTimer.singleShot(200, anim.start)

    @pyqtSlot()
    def _update_connections(self):
        for conn in self.connections:
            conn.update_path()

    def clear_all(self):
        self.scene.clear()
        self.items_list.clear()
        self.connections.clear()
        self.wall_items.clear()
        initial_rect = QRectF(0, 0, MIN_CANVAS_WIDTH, MIN_CANVAS_HEIGHT)
        self.scene.setSceneRect(initial_rect)
        self.layout_manager = SmartLayoutManager(initial_rect)
        self._create_walls()

    def resizeEvent(self, event):
        """Let the default behavior handle resizing."""
        super().resizeEvent(event)