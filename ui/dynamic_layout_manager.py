# /ui/dynamic_layout_manager.py

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from typing import Any, List, Dict, Optional
import math
import random

# --- Enhanced UI Constants ---
FONT_FAMILY = "Fira Code"
ANIMATION_DURATION = 600
GLOW_COLOR = QColor("#50fa7b")
PINK_COLOR = QColor("#ff79c6")
LINE_COLOR = QColor("#bd93f9")
WALL_COLOR = QColor("#44475a")
SCOPE_COLOR = QColor("#f1fa8c")
BACKGROUND_COLOR = QColor("#282a36")
GRID_COLOR = QColor("#343746")
MARGIN = 25
H_SPACING = 20
V_SPACING = 20
MIN_CANVAS_WIDTH = 400
MIN_CANVAS_HEIGHT = 450
WALL_THICKNESS = 3
EXPANSION_PADDING = 80

# New animation constants for enhanced dynamics
BOUNCE_INTENSITY = 0.15
SPRING_TENSION = 0.8
HOVER_SCALE = 1.05
PULSE_INTENSITY = 1.15

# Add these to your existing constants
CONNECTION_CLEARANCE = 15  # Minimum distance from obstacles
CONNECTION_PADDING = 8  # Extra padding around items for path planning
MIN_SEGMENT_LENGTH = 20  # Minimum length for path segments


class EnhancedEasing:
    """Custom easing curves for more natural animations"""

    @staticmethod
    def elastic_out(progress):
        """Elastic easing with spring-like effect"""
        if progress == 0 or progress == 1:
            return progress
        p = 0.3
        s = p / 4
        return math.pow(2, -10 * progress) * math.sin((progress - s) * (2 * math.pi) / p) + 1

    @staticmethod
    def back_out(progress):
        """Back easing for overshoot effect"""
        c1 = 1.70158
        c3 = c1 + 1
        return 1 + c3 * math.pow(progress - 1, 3) + c1 * math.pow(progress - 1, 2)


class SmoothAnimation(QPropertyAnimation):
    def __init__(self, target, property_name, parent=None, easing_type=None):
        super().__init__(target, property_name, parent)
        self.setDuration(ANIMATION_DURATION)
        self.setEasingCurve(easing_type or QEasingCurve.OutCubic)

    def set_bounce_effect(self):
        """Apply bounce easing for playful effects"""
        self.setEasingCurve(QEasingCurve.OutBounce)

    def set_elastic_effect(self):
        """Apply elastic easing for spring-like effects"""
        self.setEasingCurve(QEasingCurve.OutElastic)


class ParticleEffect(QGraphicsObject):
    """Subtle particle effects for enhanced visual feedback"""

    def __init__(self, start_pos: QPointF, color: QColor, parent=None):
        super().__init__(parent)
        self.particles = []
        self.start_pos = start_pos
        self.color = color
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_particles)
        self.lifetime = 0
        self.max_lifetime = 60  # frames

        for _ in range(8):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(1, 3)
            self.particles.append({
                'x': start_pos.x(),
                'y': start_pos.y(),
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed,
                'life': random.uniform(0.8, 1.0)
            })

        self.timer.start(16)

    def update_particles(self):
        self.lifetime += 1
        for particle in self.particles:
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']
            particle['vy'] += 0.1
            particle['life'] *= 0.98

        if self.lifetime > self.max_lifetime:
            self.timer.stop()
            if self.scene():
                self.scene().removeItem(self)

        self.update()

    def boundingRect(self):
        return QRectF(-50, -50, 100, 100)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        for particle in self.particles:
            if particle['life'] > 0:
                opacity = int(particle['life'] * 255)
                color = QColor(self.color)
                color.setAlpha(opacity)
                painter.setBrush(color)
                painter.setPen(QPen(Qt.NoPen))
                size = particle['life'] * 3
                painter.drawEllipse(QPointF(particle['x'], particle['y']), size / 2, size / 2)


class GraphicsObjectWidget(QGraphicsObject):
    positionChanged = pyqtSignal()
    hovered = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        self.opacity_animation = SmoothAnimation(self, b"opacity")
        self.pos_animation = SmoothAnimation(self, b'pos')
        self.scale_animation = SmoothAnimation(self, b'scale')
        self.rotation_animation = SmoothAnimation(self, b'rotation')
        self.hover_scale_animation = SmoothAnimation(self, b'scale')
        self.hover_scale_animation.setDuration(200)

        self.entrance_group = QParallelAnimationGroup()
        self.entrance_group.addAnimation(self.opacity_animation)
        self.entrance_group.addAnimation(self.scale_animation)

        self.pos_animation.finished.connect(self.positionChanged.emit)
        self.is_hovering = False

    def hoverEnterEvent(self, event):
        super().hoverEnterEvent(event)
        if not self.is_hovering:
            self.is_hovering = True
            self.hovered.emit(True)
            self._start_hover_animation(True)

    def hoverLeaveEvent(self, event):
        super().hoverLeaveEvent(event)
        if self.is_hovering:
            self.is_hovering = False
            self.hovered.emit(False)
            self._start_hover_animation(False)

    def _start_hover_animation(self, entering: bool):
        target_scale = HOVER_SCALE if entering else 1.0
        self.hover_scale_animation.setStartValue(self.scale())
        self.hover_scale_animation.setEndValue(target_scale)
        self.hover_scale_animation.start()

    def show_animated(self, delay=0):
        def start_animation():
            self.setOpacity(0.0)
            self.setScale(0.7)
            self.setRotation(random.uniform(-5, 5))
            self.show()

            self.opacity_animation.setStartValue(0.0)
            self.opacity_animation.setEndValue(1.0)
            self.scale_animation.setStartValue(0.7)
            self.scale_animation.setEndValue(1.0)
            self.scale_animation.set_bounce_effect()
            self.rotation_animation.setStartValue(self.rotation())
            self.rotation_animation.setEndValue(0.0)

            self.entrance_group.start()
            self.rotation_animation.start()
            self.positionChanged.emit()

        if delay > 0:
            QTimer.singleShot(delay, start_animation)
        else:
            start_animation()

    def remove_animated(self):
        if self.scene():
            particle_effect = ParticleEffect(self.scenePos(), GLOW_COLOR)
            self.scene().addItem(particle_effect)

        exit_group = QParallelAnimationGroup()
        opacity_anim = SmoothAnimation(self, b'opacity')
        opacity_anim.setEndValue(0.0)
        scale_anim = SmoothAnimation(self, b'scale')
        scale_anim.setEndValue(0.3)
        exit_group.addAnimation(opacity_anim)
        exit_group.addAnimation(scale_anim)
        exit_group.finished.connect(self.hide)
        exit_group.start()

    def move_to_position(self, end_pos: QPointF, delay=0, use_arc=False):
        def start_move():
            if (end_pos - self.pos()).manhattanLength() < 1:
                return

            self.pos_animation.setStartValue(self.pos())
            self.pos_animation.setEndValue(end_pos)
            self.pos_animation.setEasingCurve(QEasingCurve.OutCubic)
            self.pos_animation.start()

        if delay > 0:
            QTimer.singleShot(delay, start_move)
        else:
            start_move()

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

        self.value_text = QGraphicsTextItem(f" = {self.value}", self)
        self.value_text.setFont(QFont(FONT_FAMILY, 11))
        self.value_text.setDefaultTextColor(QColor("white"))

        self.type_indicator = QGraphicsEllipseItem(self)
        self.type_indicator.setBrush(self._get_type_color(value))
        self.type_indicator.setPen(QPen(Qt.NoPen))

        # Define the animation attribute here to ensure it exists
        self._pulse_animation = SmoothAnimation(self, b'scale')

        self._update_layout()

    def _get_type_color(self, value):
        type_colors = {
            int: QColor("#f1fa8c"), float: QColor("#ffb86c"),
            str: QColor("#50fa7b"), bool: QColor("#ff79c6"),
            list: QColor("#bd93f9"), dict: QColor("#8be9fd")
        }
        return type_colors.get(type(value), QColor("#6272a4"))

    def _update_layout(self):
        self.prepareGeometryChange()
        self.type_indicator.setRect(8, 12, 8, 8)
        self.name_text.setPos(22, 8)
        name_width = self.name_text.boundingRect().width()
        self.value_text.setPos(22 + name_width, 8)

        value_width = self.value_text.boundingRect().width()
        text_height = max(self.name_text.boundingRect().height(), self.value_text.boundingRect().height())

        self._width = name_width + value_width + 40
        self._height = text_height + 16

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(68, 71, 90, 250))
        gradient.setColorAt(1, QColor(60, 63, 82, 250))

        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.fillPath(path, gradient)

        border_color = LINE_COLOR.lighter(120) if self.is_hovering else LINE_COLOR

        pen = QPen(border_color)
        pen.setWidthF(1.5)
        painter.setPen(pen)

        painter.drawPath(path)

    def update_value(self, value: Any):
        if self.value == value: return

        if self.parentItem() and isinstance(self.parentItem(), ScopeWidget):
            self.parentItem()._update_layout()

        self.value = value
        self.value_text.setPlainText(f" = {value}")
        self.type_indicator.setBrush(self._get_type_color(value))
        self._update_layout()

        self._show_update_effect()

    def _show_update_effect(self):
        """
        FIXED: The pulse animation now uses absolute scaling (from a fixed
        intensity value back to 1.0) to prevent cumulative size increases.
        """
        # Add glow effect
        glow_effect = QGraphicsDropShadowEffect(self)
        glow_effect.setColor(GLOW_COLOR)
        glow_effect.setBlurRadius(20)
        self.setGraphicsEffect(glow_effect)

        # Stop any existing pulse animation to prevent conflicts
        if self._pulse_animation.state() == QAbstractAnimation.Running:
            self._pulse_animation.stop()

        # Always animate from the pulse intensity down to the normal scale
        self._pulse_animation.setStartValue(PULSE_INTENSITY)
        self._pulse_animation.setEndValue(1.0)
        self._pulse_animation.setDuration(400)

        # Ensure the glow effect is removed once the animation finishes
        # Disconnect any previous connection to avoid multiple calls
        try:
            self._pulse_animation.finished.disconnect()
        except TypeError:
            pass  # No connection existed
        self._pulse_animation.finished.connect(lambda: self.setGraphicsEffect(None))

        # Immediately set the scale to the larger size, letting the animation shrink it
        self.setScale(PULSE_INTENSITY)
        self._pulse_animation.start()


class SmartPrintBlock(GraphicsObjectWidget):
    def __init__(self, expression_str: str, result: Any, parent=None):
        super().__init__(parent)
        self._width, self._height = 0, 0

        self.title_text = QGraphicsTextItem(f"print({expression_str})", self)
        self.title_text.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.title_text.setDefaultTextColor(PINK_COLOR)

        self.result_text = QGraphicsTextItem(f"→ {result}", self)
        self.result_text.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.result_text.setDefaultTextColor(GLOW_COLOR)

        self._update_layout()

    def _update_layout(self):
        self.prepareGeometryChange()
        self.title_text.setPos(15, 10)
        title_height = self.title_text.boundingRect().height()
        self.result_text.setPos(15, title_height + 15)

        self._width = max(self.title_text.boundingRect().width(), self.result_text.boundingRect().width()) + 30
        self._height = self.result_text.pos().y() + self.result_text.boundingRect().height() + 15

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(40, 42, 54, 250))
        gradient.setColorAt(1, QColor(30, 32, 44, 250))

        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.fillPath(path, gradient)

        border_color = PINK_COLOR.lighter(120) if self.is_hovering else PINK_COLOR
        painter.setPen(QPen(border_color, 2))
        painter.drawPath(path)


class ScopeWidget(GraphicsObjectWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)

        self.title_text = QGraphicsTextItem(title, self)
        self.title_text.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.title_text.setDefaultTextColor(SCOPE_COLOR)

        self.child_items: List[GraphicsObjectWidget] = []
        self._width, self._height = 250, 80
        self._update_layout()

    def addItem(self, child_item: GraphicsObjectWidget):
        child_item.setParentItem(self)
        self.child_items.append(child_item)
        self._update_layout()
        child_item.show_animated(delay=len(self.child_items) * 100)

    def _update_layout(self):
        self.prepareGeometryChange()
        self.title_text.setPos(15, 10)
        y_offset = self.title_text.boundingRect().height() + 25
        max_child_width = 0

        for item in self.child_items:
            item.setPos(15, y_offset)
            y_offset += item.boundingRect().height() + 10
            max_child_width = max(max_child_width, item.boundingRect().width())

        self._width = max(self.title_text.boundingRect().width(), max_child_width) + 30
        self._height = y_offset + 10
        self.positionChanged.emit()

    def boundingRect(self):
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        pen = QPen(SCOPE_COLOR, 2, Qt.DashLine)
        pen.setDashPattern([6.0, 3.0])
        painter.setPen(pen)

        painter.setBrush(QColor(40, 42, 54, 180))
        painter.drawPath(path)


class FlowConnectionLine(QGraphicsObject):
    def __init__(self, start_item, end_item, parent=None):
        super().__init__(parent)
        self.start_item, self.end_item = start_item, end_item
        self._path = QPainterPath()
        self._current_strategy = "direct"
        self.setZValue(-1)

        if hasattr(start_item, 'positionChanged'):
            start_item.positionChanged.connect(self.update_path)
        if hasattr(end_item, 'positionChanged'):
            end_item.positionChanged.connect(self.update_path)

        QTimer.singleShot(50, self.update_path)

    def _get_obstacle_items(self):
        if not self.scene():
            return []

        obstacles = []
        for item in self.scene().items():
            if (item == self or item == self.start_item or item == self.end_item or
                    isinstance(item, FlowConnectionLine) or isinstance(item, ParticleEffect)):
                continue

            if isinstance(item, (SmartVariableWidget, SmartPrintBlock, ScopeWidget)):
                obstacles.append(item)
        return obstacles

    def _expand_rect_for_clearance(self, rect):
        return rect.adjusted(-CONNECTION_CLEARANCE, -CONNECTION_CLEARANCE,
                             CONNECTION_CLEARANCE, CONNECTION_CLEARANCE)

    def _path_intersects_obstacles(self, path, obstacles):
        path_rect = path.boundingRect()

        for obstacle in obstacles:
            obstacle_rect = self._expand_rect_for_clearance(obstacle.sceneBoundingRect())
            if path_rect.intersects(obstacle_rect):
                for t in [i / 20.0 for i in range(21)]:
                    point = path.pointAtPercent(t)
                    if obstacle_rect.contains(point):
                        return True
        return False

    def _get_connection_points(self):
        if not self.scene():
            return QPointF(), QPointF()

        start_rect = self.start_item.sceneBoundingRect()
        end_rect = self.end_item.sceneBoundingRect()

        start_point = QPointF(start_rect.right(), start_rect.center().y())
        end_point = QPointF(end_rect.left(), end_rect.center().y())

        if end_rect.center().x() < start_rect.center().x():
            start_point = QPointF(start_rect.left(), start_rect.center().y())
            end_point = QPointF(end_rect.right(), end_rect.center().y())

        return start_point, end_point

    def _try_direct_path(self):
        start_point, end_point = self._get_connection_points()
        path = QPainterPath()
        path.moveTo(start_point)
        dx = end_point.x() - start_point.x()
        ctrl1 = QPointF(start_point.x() + dx * 0.4, start_point.y())
        ctrl2 = QPointF(start_point.x() + dx * 0.6, end_point.y())
        path.cubicTo(ctrl1, ctrl2, end_point)
        return path

    def _try_horizontal_first_path(self):
        start_point, end_point = self._get_connection_points()
        horizontal_distance = abs(end_point.x() - start_point.x()) * 0.6
        waypoint_x = start_point.x() + (
            horizontal_distance if end_point.x() > start_point.x() else -horizontal_distance)
        waypoint = QPointF(waypoint_x, start_point.y())
        waypoint2 = QPointF(waypoint_x, end_point.y())
        return self._create_smooth_path_through_points([start_point, waypoint, waypoint2, end_point])

    def _try_vertical_first_path(self):
        start_point, end_point = self._get_connection_points()
        vertical_offset = 40 if end_point.y() > start_point.y() else -40
        waypoint = QPointF(start_point.x(), start_point.y() + vertical_offset)
        waypoint2 = QPointF(end_point.x(), start_point.y() + vertical_offset)
        return self._create_smooth_path_through_points([start_point, waypoint, waypoint2, end_point])

    def _try_arc_path(self):
        start_point, end_point = self._get_connection_points()
        mid_x = (start_point.x() + end_point.x()) / 2
        mid_y = (start_point.y() + end_point.y()) / 2
        arc_offset = 60
        if start_point.y() < end_point.y():
            mid_y -= arc_offset
        else:
            mid_y += arc_offset
        waypoint = QPointF(mid_x, mid_y)
        return self._create_smooth_path_through_points([start_point, waypoint, end_point])

    def _create_smooth_path_through_points(self, points):
        if len(points) < 2:
            return QPainterPath()

        path = QPainterPath()
        path.moveTo(points[0])

        if len(points) == 2:
            path.lineTo(points[1])
        elif len(points) == 3:
            path.quadTo(points[1], points[2])
        else:
            for i in range(len(points) - 1):
                start = points[i]
                end = points[i + 1]
                if i == 0:
                    ctrl = QPointF(start.x() + (end.x() - start.x()) * 0.5, start.y())
                    path.quadTo(ctrl, end)
                else:
                    path.lineTo(end)
        return path

    @pyqtSlot()
    def update_path(self):
        if (not self.scene() or not self.start_item.isVisible() or
                not self.end_item.isVisible()):
            self._path = QPainterPath()
            self.update()
            return

        self.prepareGeometryChange()
        obstacles = self._get_obstacle_items()

        strategies = [
            ("direct", self._try_direct_path),
            ("horizontal_first", self._try_horizontal_first_path),
            ("vertical_first", self._try_vertical_first_path),
            ("arc", self._try_arc_path)
        ]

        best_path = None
        for strategy_name, strategy_func in strategies:
            try:
                path = strategy_func()
                if not self._path_intersects_obstacles(path, obstacles):
                    best_path = path
                    self._current_strategy = strategy_name
                    break
            except Exception as e:
                print(f"Strategy {strategy_name} failed: {e}")
                continue

        self._path = best_path if best_path else self._try_direct_path()
        self.update()

    def boundingRect(self):
        return self._path.boundingRect().adjusted(-5, -5, 5, 5)

    def paint(self, painter, option, widget=None):
        if not self._path.isEmpty():
            painter.setRenderHint(QPainter.Antialiasing)

            color = LINE_COLOR
            if self._current_strategy == "horizontal_first":
                color = LINE_COLOR.lighter(110)
            elif self._current_strategy == "vertical_first":
                color = LINE_COLOR.lighter(120)
            elif self._current_strategy == "arc":
                color = LINE_COLOR.lighter(130)

            pen = QPen(color, 2, Qt.SolidLine)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(self._path)

            self._draw_arrow_head(painter, pen)

    def _draw_arrow_head(self, painter, pen):
        if self._path.isEmpty():
            return

        path_length = self._path.length()
        if path_length < 20:
            return

        end_point = self._path.pointAtPercent(1.0)
        direction_point = self._path.pointAtPercent(0.95)

        dx = end_point.x() - direction_point.x()
        dy = end_point.y() - direction_point.y()

        if abs(dx) < 0.1 and abs(dy) < 0.1: return
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0: return
        dx /= length
        dy /= length

        arrow_length = 8
        arrow_width = 4

        p1 = QPointF(end_point.x() - arrow_length * dx + arrow_width * dy,
                     end_point.y() - arrow_length * dy - arrow_width * dx)
        p2 = QPointF(end_point.x() - arrow_length * dx - arrow_width * dy,
                     end_point.y() - arrow_length * dy + arrow_width * dx)

        painter.setBrush(pen.color())
        painter.setPen(QPen(pen.color(), 1))
        arrow_path = QPainterPath()
        arrow_path.moveTo(end_point)
        arrow_path.lineTo(p1)
        arrow_path.lineTo(p2)
        arrow_path.closeSubpath()
        painter.drawPath(arrow_path)


class DynamicCanvas(QGraphicsView):
    """A QGraphicsView that manages the dynamic layout of visualization items."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(BACKGROUND_COLOR))
        self.setFrameShape(QFrame.NoFrame)

        self.items: List[GraphicsObjectWidget] = []
        self.connections: List[FlowConnectionLine] = []

        self.layout_timer = QTimer(self)
        self.layout_timer.setSingleShot(True)
        self.layout_timer.timeout.connect(self._reorganize_layout)

    def add_item(self, item: GraphicsObjectWidget):
        self.items.append(item)
        self.scene.addItem(item)
        item.show_animated()
        self.layout_timer.start(10)

    def add_connection(self, start_item: GraphicsObjectWidget, end_item: GraphicsObjectWidget):
        """Creates a flow connection line between two items."""
        connection = FlowConnectionLine(start_item, end_item)
        self.connections.append(connection)
        self.scene.addItem(connection)
        return connection

    def _reorganize_layout(self):
        """Enhanced layout that considers connections."""
        visible_items = [item for item in self.items
                         if item.isVisible() and not item.parentItem()]
        if not visible_items:
            return

        columns: List[List[GraphicsObjectWidget]] = []
        current_column: List[GraphicsObjectWidget] = []
        for item in visible_items:
            if isinstance(item, (ScopeWidget, SmartPrintBlock)):
                if current_column:
                    columns.append(current_column)
                columns.append([item])
                current_column = []
            else:
                current_column.append(item)
        if current_column:
            columns.append(current_column)

        x_offset = MARGIN
        max_scene_height = 0
        for col_index, col_items in enumerate(columns):
            y_offset = MARGIN
            max_col_width = 0
            for item in col_items:
                item.move_to_position(QPointF(x_offset, y_offset))
                size = item.get_content_size()
                y_offset += size.height() + V_SPACING
                max_col_width = max(max_col_width, size.width())

            connection_spacing = H_SPACING
            if self._columns_have_connections(col_index, columns):
                connection_spacing += CONNECTION_CLEARANCE * 2

            x_offset += max_col_width + connection_spacing
            max_scene_height = max(max_scene_height, y_offset)

        self._update_all_connections()

        new_scene_width = max(self.width(), x_offset + EXPANSION_PADDING)
        new_scene_height = max(self.height(), max_scene_height + EXPANSION_PADDING)
        self.scene.setSceneRect(0, 0, new_scene_width, new_scene_height)

    def _columns_have_connections(self, col_index, columns):
        """Check if a column has connections to other columns."""
        if col_index >= len(columns):
            return False

        current_column_items = set(columns[col_index])
        for connection in self.connections:
            if (connection.start_item in current_column_items or
                    connection.end_item in current_column_items):
                return True
        return False

    def _update_all_connections(self):
        """Force update all connections after layout changes."""
        for connection in self.connections:
            QTimer.singleShot(100, connection.update_path)

    def clear_all(self):
        self.items.clear()
        self.connections.clear()
        self.scene.clear()
        self.scene.setSceneRect(0, 0, self.width(), self.height())

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        grid_size = 25
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)

        lines = []
        for x in range(left, int(rect.right()), grid_size):
            lines.append(QLineF(x, rect.top(), x, rect.bottom()))
        for y in range(top, int(rect.bottom()), grid_size):
            lines.append(QLineF(rect.left(), y, rect.right(), y))

        painter.setPen(QPen(GRID_COLOR, 1))
        painter.drawLines(lines)