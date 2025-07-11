import sys
from PyQt5.QtWidgets import QApplication
from ui.main_window import FrostedCompiler

if __name__ == '__main__':
    app = QApplication(sys.argv)
    compiler = FrostedCompiler()
    compiler.show()
    sys.exit(app.exec_())