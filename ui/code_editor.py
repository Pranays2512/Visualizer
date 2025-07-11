from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QTextEdit
from PyQt5.QtGui import QFont, QPainter, QColor, QTextCharFormat, QTextCursor
from PyQt5.QtCore import Qt, QSize, QRect, QTimer, pyqtSlot

from .highlighter import PythonHighlighter


class CodeEditor(QPlainTextEdit):
    """
    The main code editor widget, including line numbers, syntax highlighting,
    error checking, auto-completion, and hover tooltips.
    """

    def __init__(self):
        super().__init__()
        self.setFont(QFont("JetBrains Mono", 10))
        self.line_number_area = LineNumberArea(self)
        self.highlighter = PythonHighlighter(self.document())

        # Cache for extra selections to avoid recreating them
        self._current_line_selection = None

        # Use pyqtSlot for more efficient signal connections
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.textChanged.connect(self.schedule_analysis)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

        # Analysis timer with optimized delay
        self._analysis_timer = QTimer(self)
        self._analysis_timer.setSingleShot(True)
        self._analysis_timer.timeout.connect(self.run_code_analysis)

    @pyqtSlot()
    def schedule_analysis(self):
        """Schedules code analysis to run after a short delay of inactivity."""
        # Increased delay to reduce CPU usage during rapid typing
        self._analysis_timer.start(800)  # 800ms delay for better performance

    @pyqtSlot()
    def run_code_analysis(self):
        """Triggers the highlighter to analyze the code and then applies diagnostics."""
        # Only analyze if there's actual text to analyze
        text = self.toPlainText()
        if text.strip():
            self.highlighter.analyze_code(text)
            self.apply_diagnostics()

    def apply_diagnostics(self):
        """Applies wavy underlines and tooltips for errors and warnings."""
        # Start with current line selection if it exists
        extra_selections = []
        if self._current_line_selection:
            extra_selections.append(self._current_line_selection)

        # Reuse format objects for better performance
        error_format = QTextCharFormat()
        error_format.setUnderlineColor(QColor("red"))
        error_format.setUnderlineStyle(QTextCharFormat.WaveUnderline)

        warning_format = QTextCharFormat()
        warning_format.setUnderlineColor(QColor(255, 220, 0))  # Yellow
        warning_format.setUnderlineStyle(QTextCharFormat.WaveUnderline)

        # Process diagnostics
        cursor = self.textCursor()
        for diagnostic in self.highlighter.diagnostics:
            selection = QTextEdit.ExtraSelection()

            # Choose format based on severity
            if diagnostic["severity"] == "error":
                selection.format = error_format
            else:  # warning
                selection.format = warning_format

            # Set tooltip
            selection.format.setToolTip(diagnostic["message"])

            # Position cursor
            block = self.document().findBlockByNumber(diagnostic["line"] - 1)
            if block.isValid():
                cursor.setPosition(block.position() + diagnostic["col"])
                cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, diagnostic["length"])
                selection.cursor = cursor
                extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def keyPressEvent(self, event):
        """Handles auto-completion of brackets and quotes."""
        cursor = self.textCursor()
        key = event.key()
        closing = {ord('('): ')', ord('['): ']', ord('{'): '}', ord('"'): '"', ord("'"): "'"}
        if key in closing:
            cursor.insertText(chr(key) + closing[key])
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)
        else:
            super().keyPressEvent(event)

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 10 + self.fontMetrics().width('9') * digits

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        """Paints the line numbers in the line number area."""
        # Set up the painter with optimized rendering hints
        painter = QPainter(self.line_number_area)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setPen(QColor(160, 160, 160))

        # Get the font metrics once
        font_height = self.fontMetrics().height()
        right_margin = 5
        area_width = self.line_number_area.width() - right_margin

        # Get the visible area
        event_rect = event.rect()

        # Start with the first visible block
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()

        # Calculate initial position
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()

        # Paint only visible line numbers
        while block.isValid():
            # Calculate the block's bottom position
            bottom = top + self.blockBoundingRect(block).height()

            # Only process if the block is in the visible area
            if block.isVisible() and bottom >= event_rect.top() and top <= event_rect.bottom():
                # Draw the line number
                number = str(block_number + 1)
                painter.drawText(0, int(top), area_width, int(font_height), 
                                Qt.AlignRight, number)

            # Move to the next block
            block = block.next()
            top = bottom

            # Stop if we've gone past the visible area
            if top > event_rect.bottom():
                break

            block_number += 1

    @pyqtSlot()
    def highlight_current_line(self):
        """Highlights the current line with a subtle background color."""
        extra_selections = [s for s in self.extraSelections() 
                           if not s.format.property(QTextCharFormat.FullWidthSelection)]

        if not self.isReadOnly():
            if not self._current_line_selection:
                self._current_line_selection = QTextEdit.ExtraSelection()
                line_color = QColor(255, 255, 255, 30)
                self._current_line_selection.format.setBackground(line_color)
                self._current_line_selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)


            self._current_line_selection.cursor = self.textCursor()
            self._current_line_selection.cursor.clearSelection()

            extra_selections.insert(0, self._current_line_selection)

        self.setExtraSelections(extra_selections)


class LineNumberArea(QWidget):
    """A widget to display line numbers for the code editor."""

    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)
