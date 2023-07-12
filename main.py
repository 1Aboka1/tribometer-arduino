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
import traceback

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
from PyQt5.QtWidgets import QTableWidgetItem
import qdarktheme

ylim = 1000

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi, layout='tight')
        self.axes = fig.add_subplot(111, ylabel='Вес на датчик, г', xlabel='Время, с')
        self.axes.grid()
        self.axes.set_ylim(ymin=0, ymax=ylim)

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

        # Setting up Qt
        title = 'Трибометр'

        QtWidgets.QMainWindow.__init__(self)
        self.ui = uic.loadUi('design.ui', self)
        self.threadpool = QtCore.QThreadPool()
        self.setWindowTitle(title)

        self.canvas_width = 12
        self.canvas_height = 8
        self.canvas_dpi = 100

        # Setting up graph
        self.canvas = MplCanvas(self, width=12, height=8, dpi=100)
        self.ui.verticalLayout.addWidget(self.canvas)
        self.reference_plot = None
        self.ui.radioButton.setChecked(True)
        self.ui.with_timer_button.setChecked(True)

        # Setting up table
        row_count = 2
        column_count = 2

        self.ui.tableWidget.setRowCount(row_count)
        self.ui.tableWidget.setColumnCount(column_count)

        self.ui.tableWidget.setHorizontalHeaderLabels(['Текущее значение', 'Максимум'])
        self.ui.tableWidget.setVerticalHeaderLabels(['Тензодатчик', 'Unknown'])

        self.ui.tableWidget.setReadOnly(True)

        for i in range(row_count):
            for j in range(column_count):
                self.ui.tableWidget.setItem(i, j, QTableWidgetItem('---'))

        # Data
        self.q = queue.Queue(maxsize=40)
        self.plotdata = np.array([])
        self.plotTimeData = np.array([])

        # Setup
        self.interval = 100
        self.phase = 0
        self.intervals = [0, 0] # For zoom in and out
        self.tenzo_max = 0
        self.running = False

        # Connecting Buttons
        self.startButton.clicked.connect(self.start_timer)
        self.saveButton.clicked.connect(self.save_plot)
        self.calibrate_button.clicked.connect(self.reset_arduino)
        self.ui.no_timer_button.clicked.connect(self.turn_on_without_timer)
        self.ui.with_timer_button.clicked.connect(self.turn_on_with_timer)

        self.timerInput.setPlaceholderText("")
        # self.zoomIn.clicked.connect(self.zoom_in)
        # self.zoomOut.clicked.connect(self.zoom_out)
        # self.moveLeft.clicked.connect(self.move_left)
        # self.moveRight.clicked.connect(self.move_right)

        # Resetting Arduino
        self.reset_arduino()

    def turn_on_without_timer(self):
        self.ui.timerInput.setEnabled(False)
        self.ui.radioButton.setEnabled(False)
        self.ui.radioButton_2.setEnabled(False)

    def turn_on_with_timer(self):
        self.timerInput.setEnabled(True)
        self.ui.radioButton.setEnabled(True)
        self.ui.radioButton_2.setEnabled(True)

    def disabling_widgets_at_start(self):
        self.timerInput.setReadOnly(True)
        self.startButton.setText("Остановить испытание")
        self.saveButton.setEnabled(False)
        self.ui.radioButton.setEnabled(False)
        self.ui.radioButton_2.setEnabled(False)
        self.ui.with_timer_button.setEnabled(False)
        self.ui.no_timer_button.setEnabled(False)
        self.startButton.clicked.disconnect()
        self.startButton.clicked.connect(self.stop_dialog)

    def timer_duration_calculation(self):
        try:
            input_timer = float(self.timerInput.text())
            if input_timer <= 0.1:
                return
        except:
            return
        
        if self.ui.radioButton.isChecked(): # Minutes is checked
            self.timer_duration = input_timer * 60
        else:
            self.timer_duration = input_timer

    # Timers
    def start_timer(self):
        self.reset_graph()
        if self.ui.with_timer_button.isChecked():
            self.timer_duration_calculation()
        else:
            self.timer_duration = 1000

        self.disabling_widgets_at_start()

        self.running = True
        self.q = queue.Queue(maxsize=40)        
        self.reference_plot = None

        if self.ui.with_timer_button.isChecked():
            self.set_xticks()
        else:
            pass

        # Initialize graph with zeros
        self.plotdata = np.append(self.plotdata, [0], axis=0)
        self.plotTimeData = np.append(self.plotTimeData, [0], axis=0)

        self.start_worker()

        # Timer for updating the plot
        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.interval) #msec
        self.timer.timeout.connect(self.update_state)
        self.timer.start()

        # Timer from the user input
        self.main_timer = QtCore.QTimer()
        self.main_timer.setInterval(int(self.timer_duration * 1000))
        self.main_timer.setSingleShot(True)
        self.main_timer.timeout.connect(self.timeout)
        self.main_timer.start()

    def timeout(self):
        self.running = False

        self.timerInput.setReadOnly(False)
        self.startButton.setText("Начать испытание")
        self.startButton.clicked.disconnect()
        self.startButton.clicked.connect(self.start_timer)
        
        self.q = queue.Queue(maxsize=40)
        self.timer.stop()
        self.timerInput.setText('0')
        self.timerInput.setEnabled(True)
        self.saveButton.setEnabled(True)
        self.ui.radioButton.setEnabled(True)
        self.ui.radioButton_2.setEnabled(True)
        self.ui.with_timer_button.setEnabled(True)
        self.ui.no_timer_button.setEnabled(True)
        self.ui.radioButton.setChecked(True)
        self.ui.with_timer_button.setChecked(True)

        self.tenzo_max = 0
        
    def set_xticks(self):
        self.canvas.axes.set_xlim(xmin=0, xmax=self.timer_duration + 1)
        ticker_obj = ticker.MaxNLocator('auto', integer=True)
        self.canvas.axes.set_xticks(ticker_obj.tick_values(0, self.timer_duration))
        self.intervals = [0, self.timer_duration + 1]
    
    def reset_graph(self):
        self.plotdata = np.array([])
        self.plotTimeData = np.array([])
        self.canvas.axes.clear()

        self.canvas.axes.grid()
        self.canvas.axes.set_ylim(ymin=0, ymax=ylim)
        self.canvas.axes.set_ylabel('Вес на датчик, г')
        self.canvas.axes.set_xlabel('Время, с')

    def stop_dialog(self):
        self.dlg = StopDialog(self.accept, self.reject)

        self.dlg.exec()
    
    def accept(self):
        self.timeout()
        
        self.startButton.clicked.disconnect()
        self.startButton.clicked.connect(self.start_timer)
        
        self.dlg.close()
    
    def reject(self):
        self.dlg.close()

    def reset_arduino(self):
        self.arduino.write(b'R')
        result = ''
        while 'first:' not in result:
            unprocessed_result = self.arduino.readline().decode('utf-8')
            result = unprocessed_result.replace('\n', '').replace('\r', '')
            print(result)

    # Updates timerInput
    def update_timer_input(self):
        unprocessed_remaining_time = self.main_timer.remainingTime() / 1000
        remaining_time = 0

        if unprocessed_remaining_time > 100:
            remaining_time = str(int(round((unprocessed_remaining_time) / 60))) + " м"
        else:
            remaining_time = str(round(unprocessed_remaining_time, 1)) + " с"

        self.timerInput.setText(remaining_time)
        self.timerInput.setAlignment(QtCore.Qt.AlignCenter)  

    # Updates timerInput and plot
    def update_state(self):
        time_stamp = self.timer_duration - self.main_timer.remainingTime() / 1000
        self.update_timer_input()

        try:    
            queue_result = self.q.get_nowait()
            self.plotdata = np.append(self.plotdata, queue_result, axis=0)
            self.plotTimeData = np.append(self.plotTimeData, [time_stamp], axis=0)
            # print(time_stamp)
            # print(queue_result)

            # Setting to table
            self.ui.tableWidget.setItem(0, 0, QTableWidgetItem(str(queue_result[0]) + ' г'))
            if queue_result[0] > self.tenzo_max:
                self.tenzo_max = queue_result[0]
                self.ui.tableWidget.setItem(0, 1, QTableWidgetItem(str(queue_result[0]) + ' г'))
        except Exception:
            pass
            
        # print(self.plotdata)
        # print(self.plotTimeData)
        # print('-----\n')

        plot_refs = self.canvas.axes.plot(self.plotTimeData, self.plotdata, color=(0,0,0), linewidth=0.8)
        self.reference_plot = plot_refs[0]				
        self.canvas.draw()

    # Reads new values from Arduino
    def read_serial(self):
        while self.running == True:
            reading = ''
            # SKips first line of text
            while reading := self.arduino.readline().decode('utf-8').replace('\n', '').replace('\r', '') != 'first:':
                # print(reading)
                pass
            # Reads each line erasing \n and \r until a value with length not 0 is met
            while len(reading := self.arduino.readline().decode('utf-8').replace('\n', '').replace('\r', '')) == 0:
                # print(reading)
                pass
            try:
                self.q.put([float(reading)*10])
            except:
                print('Error reading serial')

    # Non blocking functions
    def start_worker(self):
        worker = Worker(self.start_stream)
        self.threadpool.start(worker)

    def start_stream(self):
        self.read_serial()

    # Saving
    def save_plot(self):
        self.canvas.print_jpeg("graphs/image.jpeg")

class StopDialog(QtWidgets.QDialog):
    def __init__(self, accept, reject):
        super().__init__()

        self.setWindowTitle("Предупреждение")

        QBtn = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel

        self.buttonBox = QtWidgets.QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(accept)
        self.buttonBox.rejected.connect(reject)

        self.layout = QtWidgets.QVBoxLayout()
        message = QtWidgets.QLabel("Вы преждевременно остановить испытание. Продолжить?")
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

class Worker(QtCore.QRunnable):
	def __init__(self, function, *args, **kwargs):
		super(Worker, self).__init__()
		self.function = function
		self.args = args
		self.kwargs = kwargs

	@pyqtSlot()
	def run(self):
		self.function(*self.args, **self.kwargs)

class GraphManipulation():
    def __init__(self, intervals, max_value):
        self.intervals = intervals
        self.max = max_value
        self.coef = 1

    def interval_check(self):
        if self.intervals == [0, 0]:
            return
        temp = (len(str(self.max)) - 1) * 5

    def zoom_in(self):
        self.interval_check()

    def zoom_out(self):
        self.interval_check()

    def move_left(self):
        self.interval_check()

    def move_right(self):
        self.interval_check()

# Main
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = MainGuiWindow()
    app.setStyleSheet(qdarktheme.load_stylesheet()) # Dark Theme
    win.show()
    sys.exit(app.exec_())
