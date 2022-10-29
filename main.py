import sys
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import queue
import numpy as np
import serial 

plt.ion()

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5 import uic
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtMultimedia import QAudioDeviceInfo, QAudio, QCameraInfo


class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)
        fig.tight_layout()

class MainGuiWindow(QtWidgets.QMainWindow):
    def __init__(self):
        self.arduino = serial.Serial(port='/dev/ttyACM0', baudrate=38400, timeout=.1)
        QtWidgets.QMainWindow.__init__(self)
        self.ui = uic.loadUi('design.ui', self)
        self.resize(888, 600)
        self.threadpool = QtCore.QThreadPool()
        self.canvas = MplCanvas(self, width=5, height=4, dpi=100)
        self.ui.verticalLayout.addWidget(self.canvas)
        self.reference_plot = None

        data = None
        while (data := self.arduino.readline().decode('utf-8').replace('\n', '').replace('\r', '')) != 'Readings:':
            pass

        self.plotdata = np.random.uniform(0.0, 1.0, size=(1, 1))
        self.interval = 300
        self.phase = 0

        self.update_plot()
        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.interval) #msec
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

    def update_plot(self):
        self.phase += 100
        self.plotdata = np.append(self.plotdata, np.random.uniform(0.0, 1.0, size=(1, 1)), axis=0)
        data = self.plotdata
        plot_refs = self.canvas.axes.plot(data, color=(0,1,0.29))
        self.reference_plot = plot_refs[0]				
        self.canvas.draw()

    def read_serial(self):
        reading = ''
        while self.arduino.readline().decode('utf-8') != 'first:':
            pass
        while len(reading := self.arduino.readline()) == 0:
            pass
        print(reading)

        return (reading)

app = QtWidgets.QApplication(sys.argv)
win = MainGuiWindow()
win.show()
sys.exit(app.exec_())
