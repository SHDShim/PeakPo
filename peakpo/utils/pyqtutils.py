

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
