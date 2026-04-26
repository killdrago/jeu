## FILE: ui/styles.py

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QStyleOptionButton, QPushButton

def set_button_background(color):
    button = QPushButton()
    style = QStyleFactory.create('Fusion')
    style.setLayoutDirection(Qt.RightToLeft)

    # Set the background color for the button
    brush = QBrush(color)
    option = QStyleOptionButton()
    option.initFrom(button)
    style.drawPrimitive(QStyle.PR_BUTTON, option, 'button')

    # Make sure to release the button's resources after use
    del option