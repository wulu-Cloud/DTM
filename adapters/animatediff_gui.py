import sys
from PyQt5 import QtWidgets, QtGui, QtCore

class AnimateDiffGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('AnimateDiff Animation Generator')
        self.setGeometry(100, 100, 600, 400)

        # Motion prompt input
        self.prompt_label = QtWidgets.QLabel('Enter Motion Prompt:', self)
        self.prompt_label.move(20, 20)

        self.prompt_input = QtWidgets.QLineEdit(self)
        self.prompt_input.setPlaceholderText('e.g., a cat running')
        self.prompt_input.setGeometry(20, 50, 560, 40)

        # Frame settings
        self.frames_label = QtWidgets.QLabel('Frame Settings:', self)
        self.frames_label.move(20, 100)

        self.frames_input = QtWidgets.QSpinBox(self)
        self.frames_input.setRange(1, 100)
        self.frames_input.setValue(30)
        self.frames_input.setGeometry(20, 130, 100, 40)
        self.frames_label = QtWidgets.QLabel('Number of Frames:', self)
        self.frames_label.move(130, 130)

        # Preview button
        self.preview_button = QtWidgets.QPushButton('Preview', self)
        self.preview_button.setGeometry(20, 180, 100, 40)
        self.preview_button.clicked.connect(self.preview_animation)

        self.show()

    def preview_animation(self):
        # Logic for previewing the animation based on input values
        prompt = self.prompt_input.text()
        frames = self.frames_input.value()
        # Implement your animation preview logic here
        print(f'Previewing animation with prompt: {prompt} and frames: {frames}')

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    ex = AnimateDiffGUI()
    sys.exit(app.exec_())