from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from power_controller import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("PowerController_IP")
    app.setOrganizationName("PowerController")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
