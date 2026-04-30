"""Entry point for SAGAN GUI."""
import sys

from PyQt5.QtWidgets import QApplication
from sagan_gui.main import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('SAGAN GUI')
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
