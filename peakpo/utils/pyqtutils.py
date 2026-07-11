from qtpy import QtCore, QtGui, QtWidgets


def undo_button_press(buttonObj, released_text='Released',
                      pressed_text='Pressed'):
    """
    recover checkable pushButton status when error occurs

    :param buttonObj: pyqt4 pushButton object
    :param released_text: text label of the button when released
    :param pressed_text: text label of the button when pressed
    """
    if buttonObj.isChecked():
        buttonObj.setChecked(False)
        buttonObj.setText(released_text)
    else:
        buttonObj.setChecked(True)
        buttonObj.setText(pressed_text)
    return


class SpinBoxFixStyle(QtWidgets.QProxyStyle):
    """
    Copied from https://stackoverflow.com/questions/40746350/why-qspinbox-jumps-twice-the-step-value
    To fix the SpinBox button problem.  This fixes SpinBoxes issuing events
    twice.
    """

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QtWidgets.QStyle.SH_SpinBox_KeyPressAutoRepeatRate:
            return 5**10
        elif hint == QtWidgets.QStyle.SH_SpinBox_ClickAutoRepeatRate:
            return 5**10
        elif hint == QtWidgets.QStyle.SH_SpinBox_ClickAutoRepeatThreshold:
            # You can use only this condition to avoid the auto-repeat,
            # but better safe than sorry ;-)
            return 5**10
        else:
            return super().styleHint(hint, option, widget, returnData)

    def subControlRect(self, cc, option, sc, widget=None):
        if cc != QtWidgets.QStyle.CC_SpinBox:
            return super().subControlRect(cc, option, sc, widget)

        rect = QtCore.QRect(option.rect)
        if option.buttonSymbols == QtWidgets.QAbstractSpinBox.NoButtons:
            if sc == QtWidgets.QStyle.SC_SpinBoxEditField:
                return rect.adjusted(2, 0, -2, 0)
            if sc in (
                QtWidgets.QStyle.SC_SpinBoxUp,
                QtWidgets.QStyle.SC_SpinBoxDown,
            ):
                return QtCore.QRect()
            return super().subControlRect(cc, option, sc, widget)

        button_width = min(24, max(12, rect.width() // 4))
        half_height = rect.height() // 2
        if option.direction == QtCore.Qt.RightToLeft:
            button_x = rect.left()
            edit_rect = rect.adjusted(button_width, 0, 0, 0)
        else:
            button_x = rect.right() - button_width + 1
            edit_rect = rect.adjusted(0, 0, -button_width, 0)

        if sc == QtWidgets.QStyle.SC_SpinBoxEditField:
            return edit_rect
        if sc == QtWidgets.QStyle.SC_SpinBoxUp:
            return QtCore.QRect(
                button_x, rect.top(), button_width, half_height)
        if sc == QtWidgets.QStyle.SC_SpinBoxDown:
            return QtCore.QRect(
                button_x, rect.top() + half_height,
                button_width, rect.height() - half_height)
        return super().subControlRect(cc, option, sc, widget)


class CheckboxIndicatorStyle(QtWidgets.QProxyStyle):
    """Draw checkboxes as a bordered square with an inset checked core."""

    ACCENT_FILL = "#bfbfbf"
    ACCENT_FILL_HOVER = "#d0d0d0"
    ACCENT_BORDER = "#5a5a5a"
    ACCENT_BORDER_HOVER = "#707070"
    ACCENT_OFF_FILL = "#2b2b2b"
    ACCENT_OFF_FILL_HOVER = "#333333"
    ACCENT_DISABLED_BORDER = "rgba(90, 90, 90, 0.45)"
    ACCENT_DISABLED_FILL = "rgba(191, 191, 191, 0.35)"
    ACCENT_DISABLED_OFF_FILL = "#262626"

    def drawPrimitive(self, element, option, painter, widget=None):
        if element != QtWidgets.QStyle.PE_IndicatorCheckBox:
            return super().drawPrimitive(element, option, painter, widget)
        if not isinstance(widget, QtWidgets.QCheckBox):
            return super().drawPrimitive(element, option, painter, widget)

        rect = QtCore.QRect(option.rect).adjusted(0, 0, -1, -1)
        if rect.isEmpty():
            return

        enabled = bool(option.state & QtWidgets.QStyle.State_Enabled)
        checked = bool(
            option.state & (QtWidgets.QStyle.State_On | QtWidgets.QStyle.State_NoChange)
        )
        hovered = bool(option.state & QtWidgets.QStyle.State_MouseOver)
        radius = 2.0

        border_color = QtGui.QColor(
            self.ACCENT_BORDER if enabled else self.ACCENT_DISABLED_BORDER
        )
        if hovered and enabled:
            border_color = QtGui.QColor(self.ACCENT_BORDER_HOVER)
        fill_color = QtGui.QColor(
            self.ACCENT_FILL if enabled else self.ACCENT_DISABLED_FILL
        )
        if hovered and enabled:
            fill_color = QtGui.QColor(self.ACCENT_FILL_HOVER)
        off_fill_color = QtGui.QColor(
            self.ACCENT_OFF_FILL if enabled else self.ACCENT_DISABLED_OFF_FILL
        )
        if hovered and enabled:
            off_fill_color = QtGui.QColor(self.ACCENT_OFF_FILL_HOVER)
        inset = 2 if checked else 1

        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        outer = QtCore.QRectF(rect)
        inner = outer.adjusted(inset, inset, -inset, -inset)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(border_color)
        painter.drawRoundedRect(outer, radius, radius)
        painter.setBrush(fill_color if checked else off_fill_color)
        painter.drawRoundedRect(inner, max(0.5, radius - inset), max(0.5, radius - inset))
        painter.restore()


def align_spinbox_right(spinbox):
    spinbox.setAlignment(
        QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
        QtCore.Qt.AlignVCenter)


def align_all_spinboxes_right(root):
    for spinbox in root.findChildren(QtWidgets.QAbstractSpinBox):
        align_spinbox_right(spinbox)
