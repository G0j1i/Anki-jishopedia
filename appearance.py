from PyQt5.QtWidgets import QWidget, QLabel, QRadioButton, QVBoxLayout, QHBoxLayout
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

class AppearanceMenu(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Appearance Settings")
        self.setGeometry(100, 100, 300, 200)

        main_layout = QVBoxLayout()

        # Auto theme section
        auto_layout = QVBoxLayout()
        auto_img = QLabel()
        auto_img.setPixmap(QPixmap(":/icons/Auto.svg"))
        auto_img.setAlignment(Qt.AlignCenter)
        auto_layout.addWidget(auto_img)

        self.auto_radio = QRadioButton("Auto")
        self.auto_radio.setEnabled(False)  # Disable the button
        auto_layout.addWidget(self.auto_radio)

        coming_soon_label = QLabel("Coming soon.")
        coming_soon_label.setAlignment(Qt.AlignCenter)
        auto_layout.addWidget(coming_soon_label)

        # Add other radio buttons here
        # Example:
        light_radio = QRadioButton("Light")
        dark_radio = QRadioButton("Dark")
        main_layout.addWidget(light_radio)
        main_layout.addWidget(dark_radio)

        main_layout.addLayout(auto_layout)
        self.setLayout(main_layout)