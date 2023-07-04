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
        # Setting up Arduino
        if 'linux' in sys.platform:
            target_port = ''
            for port in serial.tools.list_ports.comports():
                if 'ttyACM' in port.description:
                    target_port = port.description
                    break
            self.arduino = serial.Serial(port='/dev/{}'.format(target_port.description), baudrate=38400, timeout=.1)
        elif 'win' in sys.platform:
            target_port = ''
            for port in serial.tools.list_ports.comports():
                if 'Arduino Uno' in port.description:
                    target_port = port.name
            self.arduino = serial.Serial(port=target_port, baudrate=38400, timeout=.1)

        # Setting Up Qt
        QtWidgets.QMainWindow.__init__(self)
        self.ui = uic.loadUi('design.ui', self)
        self.threadpool = QtCore.QThreadPool()
        self.canvas = MplCanvas(self, width=5, height=4, dpi=100)
        self.ui.verticalLayout.addWidget(self.canvas)
        self.reference_plot = None

        # Resetting Arduino
        self.reset_arduino()

        # Queue
        self.q = queue.Queue(maxsize=40)
        self.plotdata = np.array([])
        self.plotTimeData = np.array([])
        self.interval = 100
        self.phase = 0

        # Connecting Start Button
        self.pushButton.clicked.connect(self.start_timer)
        self.timerInput.setPlaceholderText("В минутах")             

    # Timers
    def start_timer(self):
        try:
            input_timer = float(self.timerInput.toPlainText())
            if input_timer <= 0:
                return
        except:
            return

        self.timerInput.setReadOnly(True)

        self.timer_duration = input_timer * 60

        self.start_worker()

        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.interval) #msec
        self.timer.timeout.connect(self.update_state)
        self.timer.start()

        self.main_timer = QtCore.QTimer()
        self.main_timer.setInterval(int(self.timer_duration * 1000))
        self.main_timer.setSingleShot(True)
        self.main_timer.timeout.connect(self.timeout)
        self.main_timer.start()

    def timeout(self):
        self.timerInput.setReadOnly(False)
        self.timer.stop()

    def reset_arduino(self):
        while self.arduino.readline().decode('utf-8').replace('\n', '').replace('\r', '') != 'Readings:':
            pass

    # Updates timerInput and plot
    def update_state(self):
        unprocessed_remaining_time = self.main_timer.remainingTime() / 1000
        remaining_time = 0

        if unprocessed_remaining_time > 100:
            remaining_time = str(int(round(unprocessed_remaining_time / 60))) + " м"
        else:
            remaining_time = str(round(unprocessed_remaining_time, 1)) + " с"

        self.timerInput.setPlainText(remaining_time)
        self.timerInput.setAlignment(QtCore.Qt.AlignCenter)              

        try:
            self.plotdata = np.append(self.plotdata, self.q.get_nowait(), axis=0)
            self.plotTimeData = np.append(self.plotTimeData, [self.timer_duration - self.main_timer.remainingTime() / 1000], axis=0)
        except:
            pass
        plot_refs = self.canvas.axes.plot(self.plotTimeData, self.plotdata, color=(0,0,0))
        self.reference_plot = plot_refs[0]				
        self.canvas.draw()

    # Reads new values from Arduino
    def read_serial(self):
        while True:
            reading = ''
            # SKips first line of text
            while self.arduino.readline().decode('utf-8').replace('\n', '').replace('\r', '') != 'first:':
                pass
            # Reads each line erasing \n and \r until a value with length not 0 is met
            while len(reading := self.arduino.readline().decode('utf-8').replace('\n', '').replace('\r', '')) == 0:
                pass
            self.q.put([float(reading)*10])

    # Non blocking functions
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

# Main
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = MainGuiWindow()
    app.setStyleSheet(qdarktheme.load_stylesheet())
    win.show()
    sys.exit(app.exec_())
