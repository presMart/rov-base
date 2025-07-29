"""
logging_panel.py

Implements the LoggingPanel for the ROV GUI. Displays live log output to the user
with automatic line count management and auto-scroll behavior. Designed to support
real-time diagnostics, status, and error reporting.
"""

from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QTextEdit


class LoggingPanel(QGroupBox):
    """
    Panel for displaying a live, scrollable log of system messages and events.

    - Appends new messages as they arrive (via append_log).
    - Maintains a maximum number of lines for performance and readability.
    - Auto-scrolls to latest entry on update.
    """

    def __init__(self, parent=None, max_lines: int = 500):
        """
        Args:
            parent (QWidget, optional): Parent widget for panel hierarchy.
            max_lines (int): Maximum number of log lines to keep/display.
        """
        super().__init__("Log Output", parent)
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.log_box)

        self.max_lines = max_lines
        self.log_lines = []

    def append_log(self, message: str):
        """
        Append a message to the log display, enforcing the max_lines limit.

        Args:
            message (str): Message string to add to the log panel.
        """
        self.log_lines.append(message)
        if len(self.log_lines) > self.max_lines:
            self.log_lines = self.log_lines[-self.max_lines:]

        self.log_box.setPlainText("\n".join(self.log_lines))
        scrollbar = self.log_box.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(scrollbar.maximum())
