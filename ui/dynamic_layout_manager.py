import math
import random
import time
from typing import Any, List, Optional, Tuple
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

# Configuration
USER_THEME = {"font_family": "Courier New", "font_size": 12, "color_high_contrast": False}
FONT_FAMILY, ANIMATION_DURATION = USER_THEME["font_family"], 600
GLOW_COLOR, PINK_COLOR, LINE_COLOR = QColor("#50fa7b"), QColor("#ff79c6"), QColor("#bd93f9")
WALL_COLOR, SCOPE_COLOR = QColor("#44475a"), QColor("#f1fa8c")
BACKGROUND_COLOR = QColor("#0a0a0a" if USER_THEME["color_high_contrast"] else "#282a36")
GRID_COLOR = QColor("#343746")
MARGIN, H_SPACING, V_SPACING = 25, 20, 20
MIN_CANVAS_WIDTH, MIN_CANVAS_HEIGHT = 400, 450
HOVER_SCALE = 1.05


def get_theme_color(name):
    colors = {"background": QColor("#0a0a0a"), "highlight": QColor("#ffff00")} if USER_THEME[
        "color_high_contrast"] else {"background": QColor("#282a36"), "highlight": QColor("#50fa7b")}
    return colors.get(name, QColor("#ffffff"))


class SpringPhysics:
    def __init__(self, mass=1.0, stiffness=200.0, damping=20.0):
        self.mass, self.stiffness, self.damping = mass, stiffness, damping
        self.position = self.velocity = self.target = QPointF(0, 0)
        self.settled_threshold = 0.1

    def update(self, dt: float, target_pos: QPointF) -> Tuple[QPointF, bool]:
        self.target = target_pos
        displacement = self.position - self.target
        force = (-self.stiffness * displacement - self.damping * self.velocity) / self.mass
        self.velocity += force * dt
        self.position += self.velocity * dt

        settled = (math.sqrt(displacement.x() ** 2 + displacement.y() ** 2) < self.settled_threshold and
                   math.sqrt(self.velocity.x() ** 2 + self.velocity.y() ** 2) < self.settled_threshold)
        return QPointF(self.position), settled

    def set_immediate(self, pos: QPointF):
        self.position = self.target = pos
        self.velocity = QPointF(0, 0)


class AnimationContext:
    def __init__(self):
        self.current_context = "idle"
        self.context_multipliers = {"creating": 1.3, "updating": 0.7, "removing": 1.1, "focusing": 0.9, "idle": 1.0}

    def set_context(self, context_type: str): self.current_context = context_type

    def get_timing_for_context(self, base_duration: int, distance: float = 0) -> int:
        multiplier = self.context_multipliers.get(self.current_context, 1.0)
        distance_factor = min(1.0 + distance / 300.0, 1.8) if distance > 0 else 1.0
        return int(base_duration * multiplier * distance_factor)


class ImportanceTracker:
    def __init__(self):
        self.item_scores, self.interaction_history, self.decay_rate = {}, [], 0.1

    def update_importance(self, item, interaction_type: str):
        weights = {"hover": 0.1, "click": 0.3, "update": 0.5, "focus": 0.7, "error": 1.0}
        weight = weights.get(interaction_type, 0.1)
        current_time = time.time()
        self.interaction_history.append((item, interaction_type, current_time, weight))

        score = sum(w * math.exp(-self.decay_rate * (current_time - t))
                    for i, _, t, w in self.interaction_history if i == item)
        self.item_scores[item] = min(score, 2.0)
        return self.item_scores[item]

    def get_importance(self, item) -> float:
        return max(0.0, self.item_scores.get(item, 0.0) * 0.95)


class SnapZone(QGraphicsObject):
    def __init__(self, target_pos: QPointF, radius: float = 40, parent=None):
        super().__init__(parent)
        self.target_pos, self.radius, self.active = target_pos, radius, False
        self.attraction_strength = 0.3

    def check_magnetic_pull(self, item_pos: QPointF) -> QPointF:
        distance_vec = self.target_pos - item_pos
        distance = math.sqrt(distance_vec.x() ** 2 + distance_vec.y() ** 2)

        if distance < self.radius and distance > 1:
            pull_factor = (1.0 - distance / self.radius) * self.attraction_strength
            return item_pos + distance_vec * pull_factor
        elif distance <= 1:
            return self.target_pos
        return item_pos

    def set_active(self, active: bool):
        self.active = active
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(self.target_pos.x() - self.radius, self.target_pos.y() - self.radius,
                      self.radius * 2, self.radius * 2)

    def paint(self, painter: QPainter, option, widget=None):
        if not self.active: return
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#50fa7b", 60), 2, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(self.target_pos, self.radius, self.radius)
        painter.setPen(QPen(QColor("#50fa7b", 120), 1))
        painter.setBrush(QColor("#50fa7b", 30))
        painter.drawEllipse(self.target_pos, 8, 8)


class LayoutPredictor:
    def __init__(self, canvas):
        self.canvas, self.snap_zones = canvas, []

    def predict_next_position(self, item_type: str) -> QPointF:
        visible_items = [item for item in self.canvas.items if item.isVisible() and not item.parentItem()]
        if not visible_items: return QPointF(MARGIN, MARGIN)

        return {
            "variable": self._predict_variable_position,
            "print": self._predict_print_position,
            "scope": self._predict_scope_position
        }.get(item_type, self._predict_generic_position)(visible_items)

    def _predict_variable_position(self, existing_items) -> QPointF:
        variables = [item for item in existing_items if isinstance(item, SmartVariableWidget)]
        if not variables: return QPointF(MARGIN, MARGIN)

        # Group by columns
        columns = {}
        for var in variables:
            x_pos = var.pos().x()
            column_key = next((x for x in columns.keys() if abs(x_pos - x) < 50), x_pos)
            columns.setdefault(column_key, []).append(var)

        # Try existing columns first
        for col_x, col_items in columns.items():
            if len(col_items) < 5:
                bottom_y = max(item.pos().y() + item.boundingRect().height() for item in col_items)
                if bottom_y + V_SPACING + 50 < self.canvas.viewport().height() - MARGIN:
                    return QPointF(col_x, bottom_y + V_SPACING)

        # New column if space available
        rightmost = max(columns.keys())
        width = max(item.boundingRect().width() for item in columns[rightmost])
        new_x = rightmost + width + H_SPACING

        if new_x + 150 < self.canvas.width():
            return QPointF(new_x, MARGIN)

        # Stack in shortest column
        shortest_x = min(columns.keys(), key=lambda x: max(i.pos().y() + i.boundingRect().height() for i in columns[x]))
        bottom = max(i.pos().y() + i.boundingRect().height() for i in columns[shortest_x])
        return QPointF(shortest_x, bottom + V_SPACING)

    def _predict_print_position(self, existing_items) -> QPointF:
        prints = [item for item in existing_items if isinstance(item, SmartPrintBlock)]
        if prints:
            rightmost = max(item.pos().x() + item.boundingRect().width() for item in existing_items)
            return QPointF(rightmost + H_SPACING, MARGIN)

        variables = [item for item in existing_items if isinstance(item, SmartVariableWidget)]
        if variables:
            max_right = max(var.pos().x() + var.boundingRect().width() for var in variables)
            return QPointF(max_right + H_SPACING, MARGIN)

        return QPointF(MARGIN, MARGIN)

    def _predict_scope_position(self, existing_items) -> QPointF:
        if existing_items:
            bottom = max(item.pos().y() + item.boundingRect().height() for item in existing_items)
            return QPointF(MARGIN, bottom + V_SPACING * 2)
        return QPointF(MARGIN, MARGIN)

    def _predict_generic_position(self, existing_items) -> QPointF:
        if existing_items:
            rightmost = max(item.pos().x() + item.boundingRect().width() for item in existing_items)
            return QPointF(rightmost + H_SPACING, MARGIN)
        return QPointF(MARGIN, MARGIN)

    def create_snap_zones(self, item_type: str):
        snap_zone = SnapZone(self.predict_next_position(item_type))
        self.snap_zones.append(snap_zone)
        self.canvas.scene.addItem(snap_zone)
        snap_zone.set_active(True)
        QTimer.singleShot(3000, lambda: self._remove_snap_zone(snap_zone))
        return snap_zone

    def _remove_snap_zone(self, snap_zone):
        if snap_zone in self.snap_zones: self.snap_zones.remove(snap_zone)
        if snap_zone.scene(): snap_zone.scene().removeItem(snap_zone)


class EnhancedParticleEffect(QGraphicsObject):
    def __init__(self, start_pos: QPointF, color: QColor, particle_count: int = 12, parent=None):
        super().__init__(parent)
        self.particles, self.start_pos, self.color = [], start_pos, color
        self.lifetime, self.max_lifetime = 0, 80

        for _ in range(particle_count):
            angle, speed, size = random.uniform(0, 2 * math.pi), random.uniform(1.5, 4.0), random.uniform(2, 5)
            self.particles.append({
                'x': start_pos.x(), 'y': start_pos.y(),
                'vx': math.cos(angle) * speed, 'vy': math.sin(angle) * speed,
                'life': random.uniform(0.9, 1.0), 'size': size,
                'rotation': random.uniform(0, 360), 'angular_velocity': random.uniform(-5, 5)
            })

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_particles)
        self.timer.start(16)

    def update_particles(self):
        self.lifetime += 1
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vy'] += 0.15
            p['vx'] *= 0.99
            p['vy'] *= 0.99
            p['rotation'] += p['angular_velocity']
            p['life'] *= 0.97

        if self.lifetime > self.max_lifetime:
            self.timer.stop()
            if self.scene(): self.scene().removeItem(self)
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-60, -60, 120, 120)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        for p in self.particles:
            if p['life'] > 0:
                color = QColor(self.color)
                color.setAlpha(int(p['life'] * 255))
                painter.save()
                painter.translate(p['x'], p['y'])
                painter.rotate(p['rotation'])
                glow = QRadialGradient(0, 0, p['size'])
                glow.setColorAt(0, color)
                glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
                painter.setBrush(glow)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QRectF(-p['size'] / 2, -p['size'] / 2, p['size'], p['size']))
                painter.restore()


# Global instances
animation_context = AnimationContext()
importance_tracker = ImportanceTracker()


class SmoothAnimation(QPropertyAnimation):
    def __init__(self, target, property_name, parent=None, easing_type=None):
        super().__init__(target, property_name, parent)

        distance = 0
        if hasattr(target, 'pos') and hasattr(target, 'previous_pos'):
            try:
                distance = (target.pos() - target.previous_pos).manhattanLength()
            except:
                pass

        duration = animation_context.get_timing_for_context(ANIMATION_DURATION, distance)
        self.setDuration(duration)
        self.setEasingCurve(easing_type or QEasingCurve.OutCubic)

    def set_anticipation_effect(self):
        self.setEasingCurve(QEasingCurve.OutBack)

    def set_elastic_effect(self):
        self.setEasingCurve(QEasingCurve.OutElastic)

    def set_bounce_effect(self):
        self.setEasingCurve(QEasingCurve.OutBounce)


class GraphicsObjectWidget(QGraphicsObject):
    positionChanged = pyqtSignal()
    hovered = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        # Physics and animations
        self.physics = SpringPhysics(mass=0.8, stiffness=180, damping=15)
        self.physics_timer = QTimer(self)
        self.physics_timer.timeout.connect(self._update_physics)
        self.target_pos = self.previous_pos = self.pos()

        # Animation setup
        self.opacity_animation = SmoothAnimation(self, b"opacity")
        self.scale_animation = SmoothAnimation(self, b'scale')
        self.rotation_animation = SmoothAnimation(self, b'rotation')
        self.hover_scale_animation = SmoothAnimation(self, b'scale')
        self.hover_scale_animation.setDuration(200)

        self.entrance_group = QParallelAnimationGroup()
        self.entrance_group.addAnimation(self.opacity_animation)
        self.entrance_group.addAnimation(self.scale_animation)

        self.is_hovering = self.current_importance = False
        self.hovered.connect(self._on_hover_changed)

    def hoverEnterEvent(self, event):
        super().hoverEnterEvent(event)
        if not self.is_hovering:
            self.is_hovering = True
            self.hovered.emit(True)
            importance_tracker.update_importance(self, "hover")
            self._start_hover_animation(True)

    def hoverLeaveEvent(self, event):
        super().hoverLeaveEvent(event)
        if self.is_hovering:
            self.is_hovering = False
            self.hovered.emit(False)
            self._start_hover_animation(False)

    def _on_hover_changed(self, hovering: bool):
        pass

    def _start_hover_animation(self, entering: bool):
        base_scale = 1.0 + (self.current_importance * 0.1)
        target_scale = (HOVER_SCALE + self.current_importance * 0.05) if entering else base_scale
        self.hover_scale_animation.setStartValue(self.scale())
        self.hover_scale_animation.setEndValue(target_scale)
        if entering: self.hover_scale_animation.set_anticipation_effect()
        self.hover_scale_animation.start()

    def _update_physics(self):
        new_pos, settled = self.physics.update(0.016, self.target_pos)
        self.setPos(new_pos)
        if settled:
            self.physics_timer.stop()
            self.positionChanged.emit()

    def show_animated(self, delay: int = 0):
        def start_animation():
            try:
                if not self.scene() or not self.isVisible(): return
                animation_context.set_context("creating")
                self.setOpacity(0.0)
                self.setScale(0.6)
                self.setRotation(random.uniform(-10, 10))
                self.show()
                self.physics.set_immediate(self.pos())

                self.opacity_animation.setStartValue(0.0)
                self.opacity_animation.setEndValue(1.0)
                self.scale_animation.setStartValue(0.6)
                self.scale_animation.setEndValue(1.0)
                self.scale_animation.set_elastic_effect()
                self.rotation_animation.setStartValue(self.rotation())
                self.rotation_animation.setEndValue(0.0)
                self.rotation_animation.set_anticipation_effect()

                self.entrance_group.start()
                self.rotation_animation.start()
                importance_tracker.update_importance(self, "focus")
            except RuntimeError:
                pass

        QTimer.singleShot(delay, start_animation) if delay > 0 else start_animation()

    def remove_animated(self):
        animation_context.set_context("removing")
        self.physics_timer.stop()

        if self.scene():
            particle_effect = EnhancedParticleEffect(self.scenePos(), GLOW_COLOR, 15)
            self.scene().addItem(particle_effect)

        exit_group = QParallelAnimationGroup()
        opacity_anim = SmoothAnimation(self, b'opacity')
        opacity_anim.setEndValue(0.0)
        scale_anim = SmoothAnimation(self, b'scale')
        scale_anim.setEndValue(0.2)
        scale_anim.set_anticipation_effect()
        rotation_anim = SmoothAnimation(self, b'rotation')
        rotation_anim.setEndValue(random.uniform(15, 25))

        exit_group.addAnimation(opacity_anim)
        exit_group.addAnimation(scale_anim)
        exit_group.addAnimation(rotation_anim)
        exit_group.finished.connect(self.hide)
        exit_group.start()

    def move_to_position(self, end_pos: QPointF, delay: int = 0):
        def start_move():
            animation_context.set_context("updating")
            self.previous_pos = self.pos()
            self.target_pos = end_pos
            if not self.physics_timer.isActive():
                self.physics_timer.start(16)

        QTimer.singleShot(delay, start_move) if delay > 0 else start_move()


class SmartVariableWidget(GraphicsObjectWidget):
    def __init__(self, name: str, value: Any, parent=None):
        super().__init__(parent)
        self.name, self.value = name, value
        self._font = QFont(FONT_FAMILY, 10)
        self._update_size()

    def _update_size(self):
        fm = QFontMetrics(self._font)
        content_width = max(fm.width(self.name), fm.width(str(self.value)))
        self.width = max(50, content_width + 24)
        self.height = 40

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect(), 8, 8)
        painter.fillPath(path, QBrush(WALL_COLOR))

        painter.setPen(PINK_COLOR)
        painter.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        painter.drawText(QRectF(10, 5, self.width - 20, 20), Qt.AlignLeft, self.name)

        painter.setPen(GLOW_COLOR)
        painter.setFont(QFont(FONT_FAMILY, 10))
        painter.drawText(QRectF(10, 22, self.width - 20, 20), Qt.AlignLeft, str(self.value))

    def update_value(self, new_value: Any):
        if self.value == new_value: return
        self.value = new_value
        self._update_size()
        self.setScale(1.15)
        anim = SmoothAnimation(self, b'scale')
        anim.setStartValue(1.15)
        anim.setEndValue(1.0)
        anim.setDuration(400)
        anim.setEasingCurve(QEasingCurve.OutBounce)
        anim.start()
        self.prepareGeometryChange()
        self.update()
        if self.parentItem() and hasattr(self.parentItem(), "_update_layout"):
            self.parentItem()._update_layout()


class SmartPrintBlock(GraphicsObjectWidget):
    def __init__(self, expression: str, value: str, parent=None):
        super().__init__(parent)
        self.expression, self.value = expression, value
        fm = QFontMetrics(QFont(FONT_FAMILY, 9))
        text_width = fm.width(f'{expression} -> {value}')
        self.width = max(150, text_width + 30)
        self.height = 40

    def boundingRect(self) -> QRectF: return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect(), 5, 5)
        painter.setBrush(QColor(BACKGROUND_COLOR).lighter(120))
        painter.setPen(QPen(LINE_COLOR, 2))
        painter.drawPath(path)
        painter.setPen(Qt.white)
        painter.setFont(QFont(FONT_FAMILY, 9))
        painter.drawText(self.boundingRect().adjusted(10, 5, -10, -5),
                         Qt.AlignVCenter | Qt.AlignLeft, f'{self.expression} -> {self.value}')


class ScopeWidget(GraphicsObjectWidget):
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name, self._items = name, []
        self._width, self._height = 250, 80

        self.name_text = QGraphicsTextItem(name, self)
        self.name_text.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.name_text.setDefaultTextColor(SCOPE_COLOR)
        self.name_text.setPos(15, 10)
        self.setZValue(-1)
        self._update_layout()

    def addItem(self, item: QGraphicsItem):
        item.setParentItem(self)
        self._items.append(item)
        self._update_layout()

    def _update_layout(self):
        self.prepareGeometryChange()
        y_offset = self.name_text.boundingRect().height() + 25
        max_item_width = 0

        for item in self._items:
            item.setPos(15, y_offset)
            y_offset += item.boundingRect().height() + V_SPACING / 2
            max_item_width = max(max_item_width, item.boundingRect().width())

        self._height = y_offset
        self._width = max(250, max_item_width + 30)
        self.positionChanged.emit()
        self.update()

    def boundingRect(self) -> QRectF: return QRectF(0, 0, self._width, self._height)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect(), 10, 10)
        painter.setPen(QPen(SCOPE_COLOR, 1.5, Qt.DashLine))
        painter.setBrush(QColor(BACKGROUND_COLOR).lighter(110))
        painter.drawPath(path)


class DynamicCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setBackgroundBrush(BACKGROUND_COLOR)
        self.setMinimumSize(MIN_CANVAS_WIDTH, MIN_CANVAS_HEIGHT)
        self.layout_predictor = LayoutPredictor(self)
        self._install_resize_handler()
        self.execution_state = {
            'current_line': 0, 'in_condition': False, 'condition_result': None,
            'loop_iteration': 0, 'execution_path': []
        }

    def _install_resize_handler(self):
        self.viewport().installEventFilter(self)
        if hasattr(self.parent(), "resizeEvent"):
            parent_resize = self.parent().resizeEvent

            def new_resizeEvent(event):
                self._auto_resize_canvas()
                parent_resize(event)

            self.parent().resizeEvent = new_resizeEvent

    def eventFilter(self, obj, event):
        if obj == self.viewport() and event.type() == QEvent.Resize:
            self._auto_resize_canvas()
        return super().eventFilter(obj, event)

    def add_item(self, item: QGraphicsItem, item_type: Optional[str] = None):
        if not item_type:
            if isinstance(item, SmartVariableWidget):
                item_type = 'variable'
            elif isinstance(item, SmartPrintBlock):
                item_type = 'print'
            elif isinstance(item, ScopeWidget):
                item_type = 'scope'
            elif hasattr(item, '__class__') and 'Widget' in item.__class__.__name__:
                if item.__class__.__name__ in ['ArrayWidget', 'StringWidget', 'TreeWidget', 'ObjectWidget']:
                    item_type = 'data_structure'
                elif item.__class__.__name__ == 'DictionaryWidget':
                    item_type = 'dictionary'

        predicted_pos = {
            'scope': self._get_scope_position,
            'data_structure': self._get_data_structure_position,
            'dictionary': self._get_data_structure_position,
            'print': self._get_next_print_position
        }.get(item_type, lambda: self.layout_predictor.predict_next_position(item_type))()

        item.setPos(predicted_pos)
        self.scene.addItem(item)
        self.items.append(item)

        if hasattr(item, 'show_animated'):
            item.show_animated(delay=len(self.items) * 30)

        if hasattr(item, '__class__') and 'Tree' in item.__class__.__name__:
            QTimer.singleShot(100, self._auto_resize_canvas_for_tree)

        QTimer.singleShot(200, self._auto_resize_canvas)

    def _get_scope_position(self):
        scopes = [item for item in self.items if isinstance(item, ScopeWidget)]
        if scopes:
            rightmost = max(item.pos().x() + item.boundingRect().width() for item in self.items)
            bottom = max(scope.pos().y() + scope.boundingRect().height() for scope in scopes)
            return QPointF(rightmost + H_SPACING, bottom + V_SPACING)
        elif self.items:
            rightmost = max(item.pos().x() + item.boundingRect().width() for item in self.items)
            return QPointF(rightmost + H_SPACING * 2, MARGIN)
        return QPointF(400, MARGIN)

    def _get_data_structure_position(self):
        data_structures = [item for item in self.items
                           if hasattr(item, '__class__') and 'Widget' in item.__class__.__name__
                           and not isinstance(item, (SmartVariableWidget, SmartPrintBlock, ScopeWidget))]

        if data_structures:
            bottom = max(ds.pos().y() + ds.boundingRect().height() for ds in data_structures)
            return QPointF(MARGIN, bottom + V_SPACING * 2)
        else:
            variables = [item for item in self.items if isinstance(item, SmartVariableWidget)]
            if variables:
                bottom = max(var.pos().y() + var.boundingRect().height() for var in variables)
                return QPointF(MARGIN, bottom + V_SPACING * 2)
            return QPointF(MARGIN, MARGIN)

    def _get_next_print_position(self):
        prints = [item for item in self.items if isinstance(item, SmartPrintBlock)]
        left_column_width = 200
        start_x = MARGIN + left_column_width + H_SPACING

        if not prints: return QPointF(start_x, MARGIN)
        last_print = prints[-1]
        return QPointF(start_x, last_print.pos().y() + last_print.boundingRect().height() + V_SPACING)

    def _auto_resize_canvas_for_tree(self):
        tree_widgets = [item for item in self.items if hasattr(item, '__class__') and 'Tree' in item.__class__.__name__]
        if tree_widgets:
            max_width = max(tw.boundingRect().width() for tw in tree_widgets)
            max_height = max(tw.boundingRect().height() for tw in tree_widgets)
            scene_width = max(self.viewport().width(), max_width + 100)
            scene_height = max(self.viewport().height(), max_height + 100)
            self.scene.setSceneRect(0, 0, scene_width, scene_height)

    def rearrange_all(self):
        if not self.items: return
        grid_w = int(math.sqrt(len(self.items))) + 1
        grid_spacing_x, grid_spacing_y = 170, 80
        for i, item in enumerate(self.items):
            grid_x, grid_y = i % grid_w, i // grid_w
            target_x = MARGIN + grid_x * grid_spacing_x
            target_y = MARGIN + grid_y * grid_spacing_y
            if hasattr(item, 'move_to_position'):
                item.move_to_position(QPointF(target_x, target_y))
            else:
                item.setPos(target_x, target_y)
        self._auto_resize_canvas()

    def _auto_resize_canvas(self):
        if not self.items: return
        max_right = max_bottom = 0
        for item in self.items:
            if hasattr(item, 'pos') and hasattr(item, 'boundingRect'):
                max_right = max(max_right, item.pos().x() + item.boundingRect().width())
                max_bottom = max(max_bottom, item.pos().y() + item.boundingRect().height())

        required_width = max(max_right + MARGIN, MIN_CANVAS_WIDTH)
        required_height = max(max_bottom + MARGIN, MIN_CANVAS_HEIGHT)
        scene_width = max(self.viewport().width(), required_width)
        scene_height = max(self.viewport().height(), required_height)
        self.scene.setSceneRect(0, 0, scene_width, scene_height)

    def ensure_positive_positions(self):
        min_x = min_y = float('inf')
        for item in self.items:
            if hasattr(item, 'pos'):
                min_x, min_y = min(min_x, item.pos().x()), min(min_y, item.pos().y())

        if min_x < MARGIN or min_y < MARGIN:
            offset_x, offset_y = max(0, MARGIN - min_x), max(0, MARGIN - min_y)
            for item in self.items:
                if hasattr(item, 'pos'):
                    item.setPos(item.pos().x() + offset_x, item.pos().y() + offset_y)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Plus:
            self.scale(1.1, 1.1)
        elif event.key() == Qt.Key_Minus:
            self.scale(0.9, 0.9)
        elif event.key() == Qt.Key_Tab:
            self._focus_next_item()
        elif event.key() == Qt.Key_H:
            USER_THEME["color_high_contrast"] = not USER_THEME["color_high_contrast"]
            self.setBackgroundBrush(get_theme_color("background"))
            self.viewport().update()
        else:
            super().keyPressEvent(event)

    def _focus_next_item(self):
        if not self.items: return
        focused = [i for i, item in enumerate(self.items) if item.hasFocus()]
        next_idx = (focused[0] + 1) % len(self.items) if focused else 0
        self.items[next_idx].setFocus()
        self.items[next_idx].update()

    def clear_all(self):
        self.scene.clear()
        self.items.clear()