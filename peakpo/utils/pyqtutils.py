from PyQt5 import QtWidgets


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
