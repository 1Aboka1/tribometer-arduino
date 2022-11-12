import sys
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import queue
import numpy as np
import serial.tools.list_ports
import serial

matplotlib.rcParams.update(
    {
        'text.usetex': False,
        'font.family': 'stixgeneral',
        'mathtext.fontset': 'stix',
    }
)
plt.ion()

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5 import uic
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtMultimedia import QAudioDeviceInfo, QAudio, QCameraInfo
import qdarktheme

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi, layout='tight')
        self.axes = fig.add_subplot(111, ylabel='Вес на датчик, г', xlabel='Время, с')
        self.axes.grid()
        super(MplCanvas, self).__init__(fig)

class MainGuiWindow(QtWidgets.QMainWindow):
    def __init__(self):
        if 'linux' in sys.platform:
            target_port = ''
            for port in serial.tools.list_ports.comports():
                if 'ttyACM' in port.description:
                    target_port = port
                    break
            self.arduino = serial.Serial(port='/dev/{}'.format(target_port.description), baudrate=38400, timeout=.1)
        elif 'win' in sys.platform:
            self.arduino = serial.Serial(port='/dev/ttyACM1', baudrate=38400, timeout=.1)
        QtWidgets.QMainWindow.__init__(self)
        self.ui = uic.loadUi('design.ui', self)
        self.threadpool = QtCore.QThreadPool()
        self.canvas = MplCanvas(self, width=5, height=4, dpi=100)
        self.ui.verticalLayout.addWidget(self.canvas)
        self.reference_plot = None

        while self.arduino.readline().decode('utf-8').replace('\n', '').replace('\r', '') != 'Readings:':
            pass

        self.q = queue.Queue(maxsize=20)
        self.plotdata = np.array([])
        self.plotTimeData = np.array([])
        self.interval = 100
        self.phase = 0

        self.start_worker()
        self.main_timer = QtCore.QTimer()
        self.timer_duration = 12
        self.main_timer.setInterval(self.timer_duration * 1000)
        self.main_timer.timeout.connect(self.timeout)
        self.main_timer.start()

        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.interval) #msec
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

    def timeout(self):
        self.timer.stop()

    def reset_arduino(self):
        while self.arduino.readline().decode('utf-8').replace('\n', '').replace('\r', '') != 'Readings:':
            pass

    def update_plot(self):
        try:
            self.plotdata = np.append(self.plotdata, self.q.get_nowait(), axis=0)
            self.plotTimeData = np.append(self.plotTimeData, [self.timer_duration - self.main_timer.remainingTime() / 1000], axis=0)
        except:
            pass
        plot_refs = self.canvas.axes.plot(self.plotTimeData, self.plotdata, color=(0,0,0))
        self.reference_plot = plot_refs[0]				
        self.canvas.draw()

    def read_serial(self):
        while True:
            reading = ''
            while self.arduino.readline().decode('utf-8').replace('\n', '').replace('\r', '') != 'first:':
                pass
            while len(reading := self.arduino.readline().decode('utf-8').replace('\n', '').replace('\r', '')) == 0:
                pass
            self.q.put([float(reading)*10])

    def start_worker(self):
        worker = Worker(self.start_stream)
        self.threadpool.start(worker)

    def start_stream(self):
        self.read_serial()

class Worker(QtCore.QRunnable):
	def __init__(self, function, *args, **kwargs):
		super(Worker, self).__init__()
		self.function = function
		self.args = args
		self.kwargs = kwargs

	@pyqtSlot()
	def run(self):
		self.function(*self.args, **self.kwargs)

app = QtWidgets.QApplication(sys.argv)
win = MainGuiWindow()
app.setStyleSheet(qdarktheme.load_stylesheet())
win.show()
sys.exit(app.exec_())
