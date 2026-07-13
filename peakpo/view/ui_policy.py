"""Shared visual policy for PeakPo Qt controls.

Keep common button dimensions and non-stateful button styles in one location.
Stateful mode controls retain their controller-specific styles because their
appearance communicates application state rather than button role.
"""

from qtpy import QtWidgets


COMPACT_HEIGHT = 25
STANDARD_HEIGHT = 28
TOOLBAR_COMPACT_WIDTH = 84


COLORS = {
    "toolbar": "rgba(255, 255, 255, 0.045)",
    "toolbar_hover": "rgba(255, 255, 255, 0.085)",
    "toolbar_pressed": "rgba(255, 255, 255, 0.13)",
    "toolbar_border": "rgba(255, 255, 255, 0.16)",
    "success": "#2f8a57",
    "success_hover": "#3a9d66",
    "success_pressed": "#267048",
    "success_border": "#225f3d",
    "important": "#d6a800",
    "important_hover": "#e0b31b",
    "important_pressed": "#b88f00",
    "important_border": "#8f6f00",
}


def set_button_height(button, height=STANDARD_HEIGHT):
    """Apply a fixed, role-based button height."""
    button.setMinimumHeight(height)
    button.setMaximumHeight(height)


def set_toolbar_compact_width(button):
    """Apply the common width used by textual compact-toolbar controls."""
    button.setMinimumWidth(TOOLBAR_COMPACT_WIDTH)
    button.setMaximumWidth(TOOLBAR_COMPACT_WIDTH)
    button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)


def apply_flat_toolbar_style(button, compact=False):
    """Style a neutral top-toolbar button."""
    button.setFlat(True)
    button.setAutoDefault(False)
    button.setDefault(False)
    padding = "2px 8px" if compact else "3px 14px"
    font_weight = "600" if compact else "500"
    button.setStyleSheet(
        "QPushButton {"
        f"background-color: {COLORS['toolbar']};"
        "color: #f2f2f2;"
        "border: 1px solid rgba(255, 255, 255, 0.08);"
        "border-radius: 6px;"
        f"padding: {padding};"
        f"font-weight: {font_weight};"
        "}"
        "QPushButton:hover {"
        f"background-color: {COLORS['toolbar_hover']};"
        f"border: 1px solid {COLORS['toolbar_border']};"
        "}"
        "QPushButton:pressed {"
        f"background-color: {COLORS['toolbar_pressed']};"
        "border: 1px solid rgba(255, 255, 255, 0.2);"
        "}"
        "QPushButton:focus {"
        "outline: none;"
        "border: 1px solid rgba(255, 255, 255, 0.18);"
        "}"
    )


def apply_colored_toolbar_style(
        button, base_color, hover_color, pressed_color, border_color,
        text_color="#1f1f1f", compact=False):
    """Style a semantic top-toolbar action button."""
    button.setFlat(True)
    button.setAutoDefault(False)
    button.setDefault(False)
    padding = "2px 8px" if compact else "3px 14px"
    font_weight = "600" if compact else "500"
    button.setStyleSheet(
        "QPushButton {"
        f"background-color: {base_color}; color: {text_color};"
        f"border: 1px solid {border_color}; border-radius: 6px;"
        f"padding: {padding}; font-weight: {font_weight};"
        "}"
        "QPushButton:hover {"
        f"background-color: {hover_color}; border: 1px solid {border_color};"
        "}"
        "QPushButton:pressed {"
        f"background-color: {pressed_color}; border: 1px solid {border_color};"
        "}"
        "QPushButton:focus {"
        f"outline: none; border: 1px solid {border_color};"
        "}"
    )


def apply_raised_toggle_style(
        button,
        checked=False,
        base_color="#4f4f4f",
        hover_color="#5a5a5a",
        pressed_color="#3e3e3e",
        border_color="#4a4a4a",
        side_border_color="#3a3a3a",
        checked_color="#d99200",
        checked_hover_color="#eca91a",
        checked_pressed_color="#ad6500",
        checked_border_color="#6f5200",
        checked_side_border_color="#5a4300",
        text_color="#fff0a0",
        checked_text_color="#1f1f1f",
        compact=False):
    """Style a non-toolbar checkable button without changing its base shape."""
    button.setFlat(False)
    button.setAutoDefault(False)
    button.setDefault(False)
    padding = "2px 10px" if compact else "3px 14px"
    pressed_padding = "3px 10px 1px 10px" if compact else "4px 14px 2px 14px"
    button.setStyleSheet(
        "QPushButton {"
        f"color: {text_color};"
        "}"
        "QPushButton:pressed {"
        "background-color: qlineargradient("
        "x1:0, y1:0, x2:0, y2:1,"
        f"stop:0 {checked_pressed_color},"
        "stop:1 #d88c00);"
        f"color: {checked_text_color};"
        "border-top-color: rgba(255, 255, 255, 0.35);"
        f"border-left-color: {checked_side_border_color};"
        f"border-right-color: {checked_side_border_color};"
        "border-bottom-color: #2f2200;"
        f"padding: {pressed_padding};"
        "}"
        "QPushButton:checked {"
        "background-color: qlineargradient("
        "x1:0, y1:0, x2:0, y2:1,"
        "stop:0 #ffd45a,"
        f"stop:0.50 {checked_hover_color},"
        f"stop:1 {checked_color});"
        f"color: {checked_text_color};"
        f"border: 1px solid {checked_border_color};"
        "border-top-color: rgba(255, 255, 255, 0.65);"
        f"border-left-color: {checked_side_border_color};"
        f"border-right-color: {checked_side_border_color};"
        "border-bottom-color: #433000;"
        f"padding: {padding};"
        "}"
        "QPushButton:checked:hover {"
        "background-color: qlineargradient("
        "x1:0, y1:0, x2:0, y2:1,"
        "stop:0 #ffe07a,"
        "stop:0.55 #f2b832,"
        f"stop:1 {checked_hover_color});"
        "}"
        "QPushButton:checked:pressed {"
        "background-color: qlineargradient("
        "x1:0, y1:0, x2:0, y2:1,"
        f"stop:0 {checked_pressed_color},"
        "stop:1 #d88c00);"
        "border-top-color: rgba(255, 255, 255, 0.35);"
        f"border-left-color: {checked_side_border_color};"
        f"border-right-color: {checked_side_border_color};"
        "border-bottom-color: #2f2200;"
        f"padding: {pressed_padding};"
        "}"
        "QPushButton:focus {"
        "outline: none;"
        "}"
    )


def apply_accent_button_style(
        button, base_color, hover_color, pressed_color, border_color,
        text_color="white"):
    """Style a colored panel action with a raised native-button-like shape."""
    button.setStyleSheet(
        "QPushButton {"
        f"background-color: {base_color}; color: {text_color};"
        f"border: 1px solid {border_color};"
        "border-top-color: rgba(255, 255, 255, 0.42);"
        f"border-bottom: 2px solid {pressed_color};"
        "border-radius: 4px; padding: 1px 10px 3px 10px;"
        "}"
        "QPushButton:hover {"
        f"background-color: {hover_color};"
        "border-top-color: rgba(255, 255, 255, 0.55);"
        "}"
        "QPushButton:pressed {"
        f"background-color: {pressed_color};"
        f"border: 1px solid {border_color};"
        "padding: 2px 10px 2px 10px;"
        "}"
        "QPushButton:checked {"
        f"background-color: {pressed_color};"
        f"border: 1px solid {border_color};"
        "padding: 2px 10px 2px 10px;"
        "}"
    )
