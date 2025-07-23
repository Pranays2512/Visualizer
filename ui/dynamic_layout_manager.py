from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from typing import Any, List, Dict, Optional, Tuple
import math
import random
import time

# --- User-configurable Theme ---
USER_THEME = {
    "font_family": "Fira Code",
    "font_size": 12,
    "color_high_contrast": False,
}
def get_theme_color(name):
    if USER_THEME.get("color_high_contrast"):
        colors = {
            "background": QColor("#0a0a0a"),
            "highlight": QColor("#ffff00"),
        }
        return colors.get(name, QColor("#ffffff"))
    else:
        colors = {
            "background": QColor("#282a36"),
            "highlight": QColor("#50fa7b"),
        }
        return colors.get(name, QColor("#ffffff"))

# --- Constants ---
FONT_FAMILY, ANIMATION_DURATION = USER_THEME["font_family"], 600
GLOW_COLOR, PINK_COLOR, LINE_COLOR = QColor("#50fa7b"), QColor("#ff79c6"), QColor("#bd93f9")
WALL_COLOR, SCOPE_COLOR, BACKGROUND_COLOR = QColor("#44475a"), QColor("#f1fa8c"), get_theme_color("background")
GRID_COLOR = QColor("#343746")
MARGIN, H_SPACING, V_SPACING = 25, 20, 20
MIN_CANVAS_WIDTH, MIN_CANVAS_HEIGHT = 400, 450

class SpringPhysics:
    """Physics-based spring system for natural animations"""

    def __init__(self, mass=1.0, stiffness=200.0, damping=20.0):
        self.mass = mass
        self.stiffness = stiffness
        self.damping = damping
        self.position = QPointF(0, 0)
        self.velocity = QPointF(0, 0)
        self.target = QPointF(0, 0)
        self.settled_threshold = 0.1

    def update(self, dt: float, target_pos: QPointF) -> Tuple[QPointF, bool]:
        """Update spring physics and return new position and settled state"""
        self.target = target_pos

        # Calculate displacement from target
        displacement = self.position - self.target

        # Spring force: F = -k * displacement
        spring_force = -self.stiffness * displacement

        # Damping force: F = -c * velocity
        damping_force = -self.damping * self.velocity

        # Total force
        total_force = spring_force + damping_force

        # Acceleration: a = F/m
        acceleration = total_force / self.mass

        # Update velocity and position
        self.velocity += acceleration * dt
        self.position += self.velocity * dt

        # Check if settled (small displacement and velocity)
        displacement_magnitude = math.sqrt(displacement.x() ** 2 + displacement.y() ** 2)
        velocity_magnitude = math.sqrt(self.velocity.x() ** 2 + self.velocity.y() ** 2)

        settled = (displacement_magnitude < self.settled_threshold and
                   velocity_magnitude < self.settled_threshold)

        return QPointF(self.position), settled

    def set_position(self, pos: QPointF):
        """Set current position without affecting velocity"""
        self.position = pos

    def set_immediate(self, pos: QPointF):
        """Set position and target immediately, stopping all motion"""
        self.position = pos
        self.target = pos
        self.velocity = QPointF(0, 0)


class AdvancedEasing:
    """Collection of advanced easing functions for natural animations"""

    @staticmethod
    def anticipate_overshoot(progress: float, anticipate: float = 0.2, overshoot: float = 1.7) -> float:
        """Easing with anticipation and overshoot for natural feel"""
        if progress < anticipate:
            # Anticipation phase (slight backward movement)
            t = progress / anticipate
            return -anticipate * t * t
        else:
            # Main movement with overshoot
            t = (progress - anticipate) / (1 - anticipate)
            return anticipate + (1 + overshoot) * pow(t, 3) - overshoot * pow(t, 2)

    @staticmethod
    def breathing(progress: float, frequency: float = 2.0, amplitude: float = 0.05) -> float:
        """Subtle breathing effect for idle animations"""
        return 1.0 + amplitude * math.sin(progress * frequency * 2 * math.pi)

    @staticmethod
    def elastic_out_enhanced(progress: float) -> float:
        """Enhanced elastic easing with better parameters"""
        if progress == 0 or progress == 1:
            return progress
        p = 0.4
        s = p / 4
        return math.pow(2, -8 * progress) * math.sin((progress - s) * (2 * math.pi) / p) + 1


class AnimationContext:
    """Manages animation timing and context for different interaction types"""

    def __init__(self):
        self.current_context = "idle"
        self.animation_queue = []
        self.context_multipliers = {
            "creating": 1.3,
            "updating": 0.7,
            "removing": 1.1,
            "focusing": 0.9,
            "idle": 1.0
        }

    def set_context(self, context_type: str):
        """Set current animation context"""
        self.current_context = context_type

    def get_timing_for_context(self, base_duration: int, distance: float = 0) -> int:
        """Calculate contextual timing with distance factor"""
        context_multiplier = self.context_multipliers.get(self.current_context, 1.0)

        # Distance-based timing adjustment
        distance_factor = 1.0
        if distance > 0:
            distance_factor = min(1.0 + distance / 300.0, 1.8)

        return int(base_duration * context_multiplier * distance_factor)


class ImportanceTracker:
    """Tracks item importance based on interactions for visual hierarchy"""

    def __init__(self):
        self.item_scores = {}
        self.interaction_history = []
        self.decay_rate = 0.1  # How fast importance decays

    def update_importance(self, item, interaction_type: str):
        """Update importance score based on interaction"""
        current_time = time.time()

        # Weight different interaction types
        interaction_weights = {
            "hover": 0.1,
            "click": 0.3,
            "update": 0.5,
            "focus": 0.7,
            "error": 1.0
        }

        weight = interaction_weights.get(interaction_type, 0.1)

        # Add to history
        self.interaction_history.append((item, interaction_type, current_time, weight))

        # Calculate importance score
        score = self._calculate_importance_score(item, current_time)
        self.item_scores[item] = score

        return score

    def _calculate_importance_score(self, item, current_time: float) -> float:
        """Calculate importance score with time decay"""
        score = 0.0

        for hist_item, interaction_type, timestamp, weight in self.interaction_history:
            if hist_item == item:
                # Apply time decay
                time_diff = current_time - timestamp
                decay = math.exp(-self.decay_rate * time_diff)
                score += weight * decay

        return min(score, 2.0)  # Cap at 2.0

    def get_importance(self, item) -> float:
        """Get current importance score for item"""
        current_time = time.time()
        if item in self.item_scores:
            # Apply decay to stored score
            last_score = self.item_scores[item]
            # Simple decay approximation
            return max(0.0, last_score * 0.95)
        return 0.0


class FlowIndicator(QGraphicsObject):
    """Animated flow indicator for connection lines"""

    def __init__(self, connection_line, parent=None):
        super().__init__(parent)
        self.connection = connection_line
        self.progress = 0.0
        self.active = False
        self.glow_radius = 10

        # Animation for flow
        self.flow_animation = QPropertyAnimation(self, b"progress")
        self.flow_animation.setDuration(1500)
        self.flow_animation.setEasingCurve(QEasingCurve.OutCubic)

        # Pulsing glow animation
        self.glow_animation = QPropertyAnimation(self, b"glow_radius")
        self.glow_animation.setDuration(800)
        self.glow_animation.setStartValue(8)
        self.glow_animation.setEndValue(15)
        self.glow_animation.finished.connect(self._reverse_glow)

    def get_progress(self) -> float:
        return self.progress

    def set_progress(self, value: float):
        self.progress = value
        self.update()

    def get_glow_radius(self) -> float:
        return self.glow_radius

    def set_glow_radius(self, value: float):
        self.glow_radius = value
        self.update()

    progress = pyqtProperty(float, get_progress, set_progress)
    glow_radius = pyqtProperty(float, get_glow_radius, set_glow_radius)

    def animate_flow(self, duration: int = 1500):
        """Start flow animation"""
        self.active = True
        self.flow_animation.setDuration(duration)
        self.flow_animation.setStartValue(0.0)
        self.flow_animation.setEndValue(1.0)
        self.flow_animation.finished.connect(self._on_flow_finished)
        self.flow_animation.start()

        # Start glow animation
        self.glow_animation.start()

    def _reverse_glow(self):
        """Reverse glow animation for pulsing effect"""
        if self.active:
            start_val = self.glow_animation.endValue()
            end_val = self.glow_animation.startValue()
            self.glow_animation.setStartValue(start_val)
            self.glow_animation.setEndValue(end_val)
            self.glow_animation.start()

    def _on_flow_finished(self):
        """Clean up when flow animation finishes"""
        self.active = False
        self.glow_animation.stop()
        if self.scene():
            QTimer.singleShot(200, lambda: self.scene().removeItem(self) if self.scene() else None)

    def boundingRect(self) -> QRectF:
        if not self.connection or not hasattr(self.connection, '_path') or self.connection._path.isEmpty():
            return QRectF()
        return self.connection._path.boundingRect().adjusted(-20, -20, 20, 20)

    def paint(self, painter: QPainter, option, widget=None):
        if not self.active or not self.connection or not hasattr(self.connection,
                                                                 '_path') or self.connection._path.isEmpty():
            return

        painter.setRenderHint(QPainter.Antialiasing)

        # Get current position along path
        point = self.connection._path.pointAtPercent(self.progress)

        # Draw glowing dot
        glow_effect = QRadialGradient(point, self.glow_radius)
        glow_effect.setColorAt(0, QColor("#50fa7b", 200))
        glow_effect.setColorAt(0.5, QColor("#50fa7b", 100))
        glow_effect.setColorAt(1, QColor("#50fa7b", 0))

        painter.setBrush(glow_effect)
        painter.setPen(QPen(Qt.NoPen))
        painter.drawEllipse(point, self.glow_radius, self.glow_radius)


class SnapZone(QGraphicsObject):
    """Magnetic snap zone for intuitive item placement"""

    def __init__(self, target_pos: QPointF, radius: float = 40, parent=None):
        super().__init__(parent)
        self.target_pos = target_pos
        self.radius = radius
        self.active = False
        self.attraction_strength = 0.3

    def check_magnetic_pull(self, item_pos: QPointF) -> QPointF:
        """Calculate magnetic pull effect on item position"""
        distance_vec = self.target_pos - item_pos
        distance = math.sqrt(distance_vec.x() ** 2 + distance_vec.y() ** 2)

        if distance < self.radius and distance > 1:
            # Calculate pull strength (stronger closer to center)
            pull_factor = (1.0 - distance / self.radius) * self.attraction_strength
            return item_pos + distance_vec * pull_factor
        elif distance <= 1:
            return self.target_pos

        return item_pos

    def set_active(self, active: bool):
        """Set snap zone visibility"""
        self.active = active
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(
            self.target_pos.x() - self.radius,
            self.target_pos.y() - self.radius,
            self.radius * 2,
            self.radius * 2
        )

    def paint(self, painter: QPainter, option, widget=None):
        if not self.active:
            return

        painter.setRenderHint(QPainter.Antialiasing)

        # Draw subtle snap zone indication
        center = self.target_pos

        # Outer ring
        painter.setPen(QPen(QColor("#50fa7b", 60), 2, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, self.radius, self.radius)

        # Inner target
        painter.setPen(QPen(QColor("#50fa7b", 120), 1))
        painter.setBrush(QColor("#50fa7b", 30))
        painter.drawEllipse(center, 8, 8)


class LayoutPredictor:
    """Predicts optimal positions for new items"""

    def __init__(self, canvas):
        self.canvas = canvas
        self.predicted_layouts = {}
        self.snap_zones = []

    def predict_next_position(self, item_type: str) -> QPointF:
        """Predict where next item should be placed"""
        visible_items = [item for item in self.canvas.items if item.isVisible() and not item.parentItem()]

        if not visible_items:
            return QPointF(MARGIN, MARGIN)

        # Analyze current layout pattern
        if item_type == "variable":
            return self._predict_variable_position(visible_items)
        elif item_type == "print":
            return self._predict_print_position(visible_items)
        elif item_type == "scope":
            return self._predict_scope_position(visible_items)

        return self._predict_generic_position(visible_items)

    def _predict_variable_position(self, existing_items) -> QPointF:
        """Predict position for variable items with better column management"""
        variables = [item for item in existing_items if isinstance(item, SmartVariableWidget)]

        if not variables:
            return QPointF(MARGIN, MARGIN)

        # Find the rightmost column position
        canvas_width = self.canvas.width() - MARGIN
        current_column_x = MARGIN
        current_column_items = []

        # Group variables by column (items with similar x positions)
        columns = {}
        for var in variables:
            x_pos = var.pos().x()
            # Find existing column or create new one
            column_key = None
            for existing_x in columns.keys():
                if abs(x_pos - existing_x) < 50:  # Same column if within 50px
                    column_key = existing_x
                    break

            if column_key is None:
                column_key = x_pos
                columns[column_key] = []

            columns[column_key].append(var)

        # Find column with most space or create new column
        best_column_x = MARGIN
        best_y = MARGIN

        if columns:
            # Try to add to existing column with space
            for col_x, col_items in columns.items():
                col_bottom = max(item.pos().y() + item.boundingRect().height() for item in col_items)
                col_right = col_x + max(item.boundingRect().width() for item in col_items)

                # Check if we can fit in this column without exceeding canvas width
                if col_right + H_SPACING < canvas_width - MARGIN:
                    return QPointF(col_x, col_bottom + V_SPACING)

            # First, try to fill existing columns vertically
            viewport_height = self.canvas.viewport().height()
            for col_x, col_items in columns.items():
                if len(col_items) < 5:  # Max 5 items per column
                    bottom_y = max(item.pos().y() + item.boundingRect().height() for item in col_items)
                    if bottom_y + V_SPACING + 50 < viewport_height - MARGIN:  # 50 = estimated item height
                        return QPointF(col_x, bottom_y + V_SPACING)

            # Create new column only if vertical space is exhausted
            rightmost_column = max(columns.keys())
            rightmost_items = columns[rightmost_column]
            rightmost_width = max(item.boundingRect().width() for item in rightmost_items)

            new_column_x = rightmost_column + rightmost_width + H_SPACING

            # Only create new column if it fits, otherwise stack in existing column
            if new_column_x + 150 < canvas_width:  # Assume average widget width
                return QPointF(new_column_x, MARGIN)
            else:
                # Stack in the shortest column
                shortest_column_x = min(columns.keys(),
                                        key=lambda x: max(item.pos().y() + item.boundingRect().height()
                                                          for item in columns[x]))
                shortest_bottom = max(item.pos().y() + item.boundingRect().height()
                                      for item in columns[shortest_column_x])
                return QPointF(shortest_column_x, shortest_bottom + V_SPACING)

        return QPointF(MARGIN, MARGIN)

    def _get_column_height(self, col_x: float, items: List) -> float:
        """Get the current height used in a column"""
        column_items = [item for item in items if abs(item.pos().x() - col_x) < 50]
        if not column_items:
            return 0
        return max(item.pos().y() + item.boundingRect().height() for item in column_items)

    def _predict_print_position(self, existing_items) -> QPointF:
        """Predict position for print blocks"""
        prints = [item for item in existing_items if isinstance(item, SmartPrintBlock)]

        if prints:
            # Place in next column or below
            rightmost_x = max(item.pos().x() + item.boundingRect().width() for item in existing_items)
            return QPointF(rightmost_x + H_SPACING, MARGIN)

        # Place to the right of variables
        variables = [item for item in existing_items if isinstance(item, SmartVariableWidget)]
        if variables:
            max_var_right = max(var.pos().x() + var.boundingRect().width() for var in variables)
            return QPointF(max_var_right + H_SPACING, MARGIN)

        return QPointF(MARGIN, MARGIN)

    def _predict_scope_position(self, existing_items) -> QPointF:
        """Predict position for scope widgets"""
        # Scopes typically go in their own space
        if existing_items:
            bottom_most = max(item.pos().y() + item.boundingRect().height() for item in existing_items)
            return QPointF(MARGIN, bottom_most + V_SPACING * 2)

        return QPointF(MARGIN, MARGIN)

    def _predict_generic_position(self, existing_items) -> QPointF:
        """Generic position prediction"""
        if existing_items:
            rightmost = max(item.pos().x() + item.boundingRect().width() for item in existing_items)
            return QPointF(rightmost + H_SPACING, MARGIN)

        return QPointF(MARGIN, MARGIN)

    def create_snap_zones(self, item_type: str):
        """Create snap zones for predicted positions"""
        predicted_pos = self.predict_next_position(item_type)

        # Create snap zone at predicted position
        snap_zone = SnapZone(predicted_pos)
        self.snap_zones.append(snap_zone)
        self.canvas.scene.addItem(snap_zone)
        snap_zone.set_active(True)

        # Auto-remove after timeout
        QTimer.singleShot(3000, lambda: self._remove_snap_zone(snap_zone))

        return snap_zone

    def _remove_snap_zone(self, snap_zone: SnapZone):
        """Remove snap zone"""
        if snap_zone in self.snap_zones:
            self.snap_zones.remove(snap_zone)
        if snap_zone.scene():
            snap_zone.scene().removeItem(snap_zone)


class EnhancedParticleEffect(QGraphicsObject):
    """Enhanced particle system with more natural physics"""

    def __init__(self, start_pos: QPointF, color: QColor, particle_count: int = 12, parent=None):
        super().__init__(parent)
        self.particles = []
        self.start_pos = start_pos
        self.color = color
        self.lifetime = 0
        self.max_lifetime = 80

        # Create particles with varied properties
        for _ in range(particle_count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(1.5, 4.0)
            size = random.uniform(2, 5)

            self.particles.append({
                'x': start_pos.x(),
                'y': start_pos.y(),
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed,
                'life': random.uniform(0.9, 1.0),
                'size': size,
                'rotation': random.uniform(0, 360),
                'angular_velocity': random.uniform(-5, 5)
            })

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_particles)
        self.timer.start(16)  # 60 FPS

    def update_particles(self):
        """Update particle physics"""
        self.lifetime += 1

        for particle in self.particles:
            # Update position
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']

            # Apply gravity and air resistance
            particle['vy'] += 0.15  # Gravity
            particle['vx'] *= 0.99  # Air resistance
            particle['vy'] *= 0.99

            # Update rotation
            particle['rotation'] += particle['angular_velocity']

            # Fade out
            particle['life'] *= 0.97

        if self.lifetime > self.max_lifetime:
            self.timer.stop()
            if self.scene():
                self.scene().removeItem(self)

        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-60, -60, 120, 120)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        for particle in self.particles:
            if particle['life'] > 0:
                # Set up particle rendering
                opacity = int(particle['life'] * 255)
                color = QColor(self.color)
                color.setAlpha(opacity)

                painter.save()
                painter.translate(particle['x'], particle['y'])
                painter.rotate(particle['rotation'])

                # Draw particle with glow effect
                glow = QRadialGradient(0, 0, particle['size'])
                glow.setColorAt(0, color)
                glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))

                painter.setBrush(glow)
                painter.setPen(QPen(Qt.NoPen))
                painter.drawEllipse(-particle['size'] / 2, -particle['size'] / 2,
                                    particle['size'], particle['size'])

                painter.restore()


# Global instances
animation_context = AnimationContext()
importance_tracker = ImportanceTracker()


class SmoothAnimation(QPropertyAnimation):
    """Enhanced animation class with contextual timing"""

    def __init__(self, target, property_name, parent=None, easing_type=None):
        super().__init__(target, property_name, parent)

        # Get contextual duration
        base_duration = ANIMATION_DURATION
        if hasattr(target, 'pos') and hasattr(target, 'previous_pos'):
            try:
                distance = (target.pos() - target.previous_pos).manhattanLength()
            except:
                distance = 0
        else:
            distance = 0

        duration = animation_context.get_timing_for_context(base_duration, distance)
        self.setDuration(duration)

        # Set enhanced easing
        if easing_type:
            self.setEasingCurve(easing_type)
        else:
            self.setEasingCurve(QEasingCurve.OutCubic)

    def set_anticipation_effect(self):
        """Apply anticipation easing"""
        self.setEasingCurve(QEasingCurve.OutBack)

    def set_elastic_effect(self):
        """Apply enhanced elastic easing"""
        self.setEasingCurve(QEasingCurve.OutElastic)

    def set_bounce_effect(self):
        """Apply bounce easing"""
        self.setEasingCurve(QEasingCurve.OutBounce)


class GraphicsObjectWidget(QGraphicsObject):
    """Enhanced base class with physics-based animations and importance tracking"""

    positionChanged = pyqtSignal()
    hovered = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        # Physics-based movement
        self.physics = SpringPhysics(mass=0.8, stiffness=180, damping=15)
        self.physics_timer = QTimer(self)
        self.physics_timer.timeout.connect(self._update_physics)
        self.target_pos = self.pos()
        self.previous_pos = self.pos()

        # Enhanced animations
        self.opacity_animation = SmoothAnimation(self, b"opacity")
        self.scale_animation = SmoothAnimation(self, b'scale')
        self.rotation_animation = SmoothAnimation(self, b'rotation')

        # Hover animations
        self.hover_scale_animation = SmoothAnimation(self, b'scale')
        self.hover_scale_animation.setDuration(200)

        # Importance-based scaling
        self.importance_animation = SmoothAnimation(self, b'scale')
        self.importance_animation.setDuration(400)

        # Breathing animation for idle state
        self.breathing_animation = QPropertyAnimation(self, b'scale')
        self.breathing_animation.setDuration(3000)
        self.breathing_animation.setLoopCount(-1)  # Infinite
        self.breathing_timer = QTimer()
        self.breathing_timer.timeout.connect(self._start_breathing)

        # Animation groups
        self.entrance_group = QParallelAnimationGroup()
        self.entrance_group.addAnimation(self.opacity_animation)
        self.entrance_group.addAnimation(self.scale_animation)

        # State tracking
        self.is_hovering = False
        self.current_importance = 0.0

        # Connect signals
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
        """Handle hover state changes"""
        if hovering:
            self.breathing_timer.stop()
            self.breathing_animation.stop()
        else:
            # Restart breathing after hover ends
            self.breathing_timer.start(2000)  # 2 second delay

    def _start_hover_animation(self, entering: bool):
        """Enhanced hover animation with importance consideration"""
        base_scale = 1.0 + (self.current_importance * 0.1)  # Importance affects base scale
        target_scale = (HOVER_SCALE + self.current_importance * 0.05) if entering else base_scale

        self.hover_scale_animation.setStartValue(self.scale())
        self.hover_scale_animation.setEndValue(target_scale)
        self.hover_scale_animation.set_anticipation_effect() if entering else None
        self.hover_scale_animation.start()

    def _start_breathing(self):
        """Start subtle breathing animation for idle state"""
        if not self.is_hovering and self.isVisible():
            current_scale = self.scale()
            breath_amount = 0.02 + (self.current_importance * 0.01)

            self.breathing_animation.setStartValue(current_scale)
            self.breathing_animation.setEndValue(current_scale + breath_amount)
            self.breathing_animation.setEasingCurve(QEasingCurve.InOutSine)
            self.breathing_animation.start()

    def _update_physics(self):
        """Update physics-based position"""
        new_pos, settled = self.physics.update(0.016, self.target_pos)
        self.setPos(new_pos)

        if settled:
            self.physics_timer.stop()
            self.positionChanged.emit()

    def show_animated(self, delay: int = 0):
        """Enhanced entrance animation with physics"""

        def start_animation():
            animation_context.set_context("creating")

            # Set initial state
            self.setOpacity(0.0)
            self.setScale(0.6)
            self.setRotation(random.uniform(-10, 10))
            self.show()

            # Physics setup
            self.physics.set_immediate(self.pos())

            # Configure animations
            self.opacity_animation.setStartValue(0.0)
            self.opacity_animation.setEndValue(1.0)

            self.scale_animation.setStartValue(0.6)
            self.scale_animation.setEndValue(1.0)
            self.scale_animation.set_elastic_effect()

            self.rotation_animation.setStartValue(self.rotation())
            self.rotation_animation.setEndValue(0.0)
            self.rotation_animation.set_anticipation_effect()

            # Start animations
            self.entrance_group.start()
            self.rotation_animation.start()

            # Start breathing after entrance
            self.breathing_timer.start(3000)

            # Track creation importance
            importance_tracker.update_importance(self, "focus")

        if delay > 0:
            QTimer.singleShot(delay, start_animation)
        else:
            start_animation()

    def remove_animated(self):
        """Enhanced removal animation with particles"""
        animation_context.set_context("removing")

        # Stop all ongoing animations
        self.breathing_timer.stop()
        self.breathing_animation.stop()
        self.physics_timer.stop()

        if self.scene():
            # Create enhanced particle effect
            particle_effect = EnhancedParticleEffect(self.scenePos(), GLOW_COLOR, 15)
            self.scene().addItem(particle_effect)

        # Exit animation group
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
        """Physics-based movement to a new position"""

        def start_move():
            animation_context.set_context("updating")
            self.previous_pos = self.pos()
            self.target_pos = end_pos

            # Ensure the physics timer is running for the movement
            if not self.physics_timer.isActive():
                self.physics_timer.start(16)  # ~60 FPS update rate

        if delay > 0:
            QTimer.singleShot(delay, start_move)
        else:
            start_move()


class SmartVariableWidget(GraphicsObjectWidget):
    """A widget to represent a variable with its name and value"""
    def __init__(self, name: str, value: Any, parent=None):
        super().__init__(parent)
        self.name = name
        self.value = value
        self._font = QFont(FONT_FAMILY, 10)
        self._update_size()

    def _update_size(self):
        font_metrics = QFontMetrics(self._font)
        name_width = font_metrics.width(self.name)
        value_width = font_metrics.width(str(self.value))
        content_width = max(name_width, value_width)
        # Reduced margin and min-width
        self.width = max(50, content_width + 24)  # shrinks more for short vars
        self.height = 40

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect(), 8, 8)
        painter.fillPath(path, QBrush(WALL_COLOR))
        painter.setPen(PINK_COLOR)
        font = QFont(FONT_FAMILY, 10, QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(10, 5, self.width - 20, 20), Qt.AlignLeft, self.name)
        painter.setPen(GLOW_COLOR)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(QRectF(10, 22, self.width - 20, 20), Qt.AlignLeft, str(self.value))

    def update_value(self, new_value: Any):
        if self.value == new_value:
            return
        self.value = new_value
        self._update_size()
        # Animate the update
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
HOVER_SCALE = 1.05

class SmartPrintBlock(GraphicsObjectWidget):
    """A widget to represent a print statement output"""

    def __init__(self, expression: str, value: str, parent=None):
        super().__init__(parent)
        self.expression = expression
        self.value = value

        # More accurate width calculation
        font_metrics = QFontMetrics(QFont(FONT_FAMILY, 9))
        text = f'{self.expression} -> {self.value}'
        text_width = font_metrics.width(text)
        self.width = max(150, text_width + 30)  # Reduced minimum from 200
        self.height = 40

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect(), 5, 5)
        painter.setBrush(QColor(BACKGROUND_COLOR).lighter(120))
        painter.setPen(QPen(LINE_COLOR, 2))
        painter.drawPath(path)

        painter.setPen(Qt.white)
        painter.setFont(QFont(FONT_FAMILY, 9))
        text = f'{self.expression} -> {self.value}'
        painter.drawText(self.boundingRect().adjusted(10, 5, -10, -5), Qt.AlignVCenter | Qt.AlignLeft, text)


class ScopeWidget(GraphicsObjectWidget):
    """A widget to represent a scope (e.g., a function call) that contains variables."""

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name
        self._items = []
        self._width = 250
        self._height = 80

        self.name_text = QGraphicsTextItem(name, self)
        self.name_text.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.name_text.setDefaultTextColor(SCOPE_COLOR)
        self.name_text.setPos(15, 10)
        self.setZValue(-1)  # Appear behind variables

        self._update_layout()

    def addItem(self, item: QGraphicsItem):
        """Adds a variable widget to this scope."""
        item.setParentItem(self)
        self._items.append(item)
        self._update_layout()

    def _update_layout(self):
        """Arranges the items vertically within the scope."""
        self.prepareGeometryChange()
        y_offset = self.name_text.boundingRect().height() + 25
        max_item_width = 0

        for item in self._items:
            item.setPos(15, y_offset)
            y_offset += item.boundingRect().height() + V_SPACING / 2
            if item.boundingRect().width() > max_item_width:
                max_item_width = item.boundingRect().width()

        # Adjust size
        self._height = y_offset
        self._width = max(250, max_item_width + 30)
        self.positionChanged.emit()
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        # Border
        pen = QPen(SCOPE_COLOR, 1.5, Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor(BACKGROUND_COLOR).lighter(110))
        painter.drawPath(path)


class DynamicCanvas(QGraphicsView):
    """The main canvas managing the scene, items, and interactions, now with dynamic rearrangement & adaptivity."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.connections = []
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setBackgroundBrush(BACKGROUND_COLOR)
        self.setMinimumSize(MIN_CANVAS_WIDTH, MIN_CANVAS_HEIGHT)
        self.layout_predictor = LayoutPredictor(self)
        self._install_resize_handler()

    def _install_resize_handler(self):
        """Make the canvas adapt when its window or parent resizes."""
        self.viewport().installEventFilter(self)
        if hasattr(self.parent(), "resizeEvent"):
            parent_resize = self.parent().resizeEvent
            def new_resizeEvent(event):
                self._auto_resize_canvas()
                parent_resize(event)
            self.parent().resizeEvent = new_resizeEvent

    def eventFilter(self, obj, event):
        """Auto-resize scene on viewport resize."""
        if obj == self.viewport() and event.type() == QEvent.Resize:
            self._auto_resize_canvas()
        return super().eventFilter(obj, event)

    def add_item(self, item: QGraphicsItem, item_type: Optional[str] = None):
        """Adds a new widget to the canvas with animation and proper sizing."""
        # Predict position as before
        if not item_type:
            if isinstance(item, SmartVariableWidget):
                item_type = 'variable'
            elif isinstance(item, SmartPrintBlock):
                item_type = 'print'
            elif isinstance(item, ScopeWidget):
                item_type = 'scope'
            else:
                item_type = 'generic'

        predicted_pos = self.layout_predictor.predict_next_position(item_type)
        viewport_width = self.viewport().width()
        viewport_height = self.viewport().height()

        if predicted_pos.x() + 150 > viewport_width - MARGIN:
            predicted_pos.setX(MARGIN)

        if self.items:
            max_y = max(
                item.pos().y() + item.boundingRect().height() for item in self.items if hasattr(item, 'pos'))
            predicted_pos.setY(max_y + V_SPACING)

        item.setPos(predicted_pos)
        QTimer.singleShot(50, self.ensure_positive_positions)
        self.scene.addItem(item)
        self.items.append(item)

        QTimer.singleShot(100, self._auto_resize_canvas)
        if hasattr(item, 'show_animated'):
            item.show_animated(delay=len(self.items) * 20)

        # Rearrange after bulk operations or if items could overlap
        if len(self.items) >= 20 or self._needs_rearrangement():
            self.rearrange_all()

    def rearrange_all(self):
        """Rearrange widgets to avoid overlap using a simple grid layout."""
        if not self.items:
            return
        grid_w = int(math.sqrt(len(self.items))) + 1
        grid_spacing_x, grid_spacing_y = 170, 80
        for i, item in enumerate(self.items):
            grid_x = i % grid_w
            grid_y = i // grid_w
            target_x = MARGIN + grid_x * grid_spacing_x
            target_y = MARGIN + grid_y * grid_spacing_y
            if hasattr(item, 'move_to_position'):
                item.move_to_position(QPointF(target_x, target_y))
            else:
                item.setPos(target_x, target_y)
        self._auto_resize_canvas()

    def _needs_rearrangement(self):
        """Detect if widgets overlap/clutter (simple bounding check)."""
        for i, it1 in enumerate(self.items):
            rect1 = it1.sceneBoundingRect().adjusted(-5, -5, 5, 5)
            for j, it2 in enumerate(self.items):
                if i != j:
                    rect2 = it2.sceneBoundingRect()
                    if rect1.intersects(rect2):
                        return True
        return False

    def _auto_resize_canvas(self):
        """Automatically resize canvas based on content and viewport."""
        if not self.items:
            return
        max_right = 0
        max_bottom = 0
        for item in self.items:
            if hasattr(item, 'pos') and hasattr(item, 'boundingRect'):
                item_right = item.pos().x() + item.boundingRect().width()
                item_bottom = item.pos().y() + item.boundingRect().height()
                max_right = max(max_right, item_right)
                max_bottom = max(max_bottom, item_bottom)
        required_width = max(max_right + MARGIN, MIN_CANVAS_WIDTH)
        required_height = max(max_bottom + MARGIN, MIN_CANVAS_HEIGHT)
        viewport_width = self.viewport().width()
        viewport_height = self.viewport().height()
        scene_width = max(viewport_width, required_width)
        scene_height = max(viewport_height, required_height)
        self.scene.setSceneRect(0, 0, scene_width, scene_height)

    def ensure_positive_positions(self):
        """Ensure no items have negative positions."""
        min_x = float('inf')
        min_y = float('inf')
        for item in self.items:
            if hasattr(item, 'pos'):
                min_x = min(min_x, item.pos().x())
                min_y = min(min_y, item.pos().y())
        # Shift everything into visible area if any at negative positions
        if min_x < MARGIN or min_y < MARGIN:
            offset_x = max(0, MARGIN - min_x)
            offset_y = max(0, MARGIN - min_y)
            for item in self.items:
                if hasattr(item, 'pos'):
                    cp = item.pos()
                    item.setPos(cp.x() + offset_x, cp.y() + offset_y)

    def add_connection(self, item1, item2):
        # [Your connection logic; unchanged]
        pass

    def clear_all(self):
        self.scene.clear()
        self.items.clear()
        self.connections.clear()

    # --- Accessibility: Keyboard Shortcuts ---
    def keyPressEvent(self, event):
        """Keyboard scaling and navigation for accessibility."""
        if event.key() == Qt.Key_Plus:
            self.scale(1.1, 1.1)
        elif event.key() == Qt.Key_Minus:
            self.scale(0.9, 0.9)
        elif event.key() == Qt.Key_Tab:
            # Focus next widget (simple focus, optional: highlight it)
            self._focus_next_item()
        elif event.key() == Qt.Key_H:
            USER_THEME["color_high_contrast"] = not USER_THEME["color_high_contrast"]
            self.setBackgroundBrush(get_theme_color("background"))
            self.viewport().update()
        else:
            super().keyPressEvent(event)

    def _focus_next_item(self):
        if not self.items:
            return
        # Find current focus
        focused = [i for i, item in enumerate(self.items) if item.hasFocus()]
        next_idx = 0
        if focused:
            next_idx = (focused[0] + 1) % len(self.items)
        self.items[next_idx].setFocus()
        self.items[next_idx].update()


    def add_connection(self, item1, item2):
        # A simple connection implementation if needed
        pass

    def clear_all(self):
        self.scene.clear()
        self.items.clear()
        self.connections.clear()