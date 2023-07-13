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
import pandas as pd

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

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi, layout='tight')
        self.axes = fig.add_subplot(111, ylabel='Вес на датчик, г', xlabel='Время, с')
        self.axes.grid()
        self.axes.set_ylim(ymin=0, ymax=500)

        super(MplCanvas, self).__init__(fig)

class MainGuiWindow(QtWidgets.QMainWindow):
    def __init__(self):
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

        for i in range(row_count):
            for j in range(column_count):
                self.ui.tableWidget.setItem(i, j, QTableWidgetItem('---'))

        # Data
        self.q = queue.Queue(maxsize=40)
        self.plotData = np.array([])
        self.plotTimeData = np.array([])
        self.timer_duration = 0

        # Setup
        self.interval = 90
        self.phase = 0
        self.xlimit = self.timer_duration
        self.ylimit = 500
        self.xintervals = [0, self.xlimit]
        self.yintervals = [0, self.ylimit]

        self.tenzo_max = 0
        self.running = False

        self.ui.spinBoxY.setMaximum(500)
        self.ui.spinBoxY.setValue(int(self.ylimit))

        # Connecting
        self.startButton.clicked.connect(self.start_timer)
        # self.saveButton.clicked.connect(self.open_save_menu)
        self.calibrate_button.clicked.connect(self.reset_arduino)
        self.ui.no_timer_button.clicked.connect(self.turn_on_without_timer)
        self.ui.with_timer_button.clicked.connect(self.turn_on_with_timer)
        self.ui.calculate_button.clicked.connect(self.calculate_vars)

        self.ui.action_save_image.triggered.connect(self.save_plot)
        self.ui.action_save_excel.triggered.connect(self.save_excel)

        self.ui.spinBoxX.valueChanged.connect(self.change_graph_limits)
        self.ui.spinBoxY.valueChanged.connect(self.change_graph_limits)

        # self.ui.moveLeft.clicked.connect(self.moveGraphLeft)
        self.ui.moveRight.clicked.connect(self.moveGraphRight)
        # self.ui.moveTop.clicked.connect(self.moveGraphTop)
        # self.ui.moveBot.clicked.connect(self.moveGraphBot)

        self.timerInput.setPlaceholderText("")
        # self.zoomIn.clicked.connect(self.zoom_in)
        # self.zoomOut.clicked.connect(self.zoom_out)
        # self.moveLeft.clicked.connect(self.move_left)
        # self.moveRight.clicked.connect(self.move_right)

        # Setting up Arduino
        self.is_arduino_connected = False

        self.arduino_check_timer = QtCore.QTimer()
        self.arduino_check_timer.setInterval(400) #msec
        self.arduino_check_timer.timeout.connect(self.check_is_arduino_connected)
        self.arduino_check_timer.start()

    def connect_arduino(self):
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

    def check_is_arduino_connected(self):
        try:
            self.connect_arduino()
            self.is_arduino_connected = True
            self.reset_arduino()
        except:
            try:
                self.arduino.write(b' ') # Check is open
            except:
                self.is_arduino_connected = False

        if self.is_arduino_connected:
            self.startButton.setEnabled(True)
            self.ui.label.setText("Подключено")
        else:
            self.startButton.setEnabled(False)
            self.ui.label.setText("Не подключено")

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
        # self.saveButton.setEnabled(False)
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
        self.xlimit = self.timer_duration
        self.ui.spinBoxX.setValue(int(self.xlimit))
        self.xintervals[1] = self.xlimit

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
            self.ui.spinBoxX.setMaximum(int(self.timer_duration))
        else:
            pass
            
        # Initialize graph with zeros
        self.plotData = np.append(self.plotData, [0], axis=0)
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
        # self.saveButton.setEnabled(True)
        self.ui.radioButton.setEnabled(True)
        self.ui.radioButton_2.setEnabled(True)
        self.ui.with_timer_button.setEnabled(True)
        self.ui.no_timer_button.setEnabled(True)
        self.ui.radioButton.setChecked(True)
        self.ui.with_timer_button.setChecked(True)

        self.tenzo_max = 0
        
    def set_xticks(self):
        self.canvas.axes.set_xlim(xmin=self.xintervals[0], xmax=self.xintervals[1] + 1)
        ticker_obj = ticker.MaxNLocator('auto', integer=True)
        self.canvas.axes.set_xticks(ticker_obj.tick_values(self.xintervals[0], self.xintervals[1]))
    
    def reset_graph(self):
        self.plotData = np.array([])
        self.plotTimeData = np.array([])
        self.canvas.axes.clear()

        self.canvas.axes.grid()
        self.canvas.axes.set_ylim(ymin=0, ymax=self.ylimit)
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
            self.plotData = np.append(self.plotData, queue_result, axis=0)
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

        self.set_xticks()
        self.canvas.axes.set_ylim(ymin=self.yintervals[0], ymax=self.yintervals[1])

        plot_refs = self.canvas.axes.plot(self.plotTimeData, self.plotData, color=(0,0,0), linewidth=0.8)
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
        try:
            option = QtWidgets.QFileDialog.Options()
            file = QtWidgets.QFileDialog.getSaveFileName(self, "Сохранить как", "Изображение.jpeg", "Изображения (*.png *.jpg *.bmp *.jpeg)", options=option)
            self.canvas.print_jpeg(file[0])
        except:
            return

    def save_excel(self):
        try:
            option = QtWidgets.QFileDialog.Options()
            file = QtWidgets.QFileDialog.getSaveFileName(self, "Сохранить как", "Результат.xlsx", "Excel Файлы (*.xlsx)", options=option)

            full_graph = np.stack((self.plotTimeData, self.plotData))
            df = pd.DataFrame(full_graph)

            df.to_excel(file[0], index=False)
        except:
            return
        
    def calculate_vars(self):
        r0 = float(self.ui.r0.text())
        rk = float(self.ui.rk.text())
        f0 = float(self.ui.f0.text())
        p1 = float(self.ui.p1.text())

        m1 = round(r0 * f0, 3)
        fk = round(m1 / rk, 3)
        ktr = round((fk/p1)/rk, 3)

        self.ui.fk.setText(str(fk))
        self.ui.m1.setText(str(m1))
        self.ui.ktr.setText(str(ktr))

    def change_graph_limits(self):
        self.xlimit = self.ui.spinBoxX.value()
        self.ylimit = self.ui.spinBoxY.value()
        self.xintervals = [0, self.xlimit]
        self.yintervals = [0, self.ylimit]

        self.canvas.draw()
        self.set_xticks()
        self.canvas.axes.set_ylim(ymin=self.yintervals[0], ymax=self.yintervals[1])

    def moveGraphLeft(self):
        self.xintervals[0] -= 10
        self.xintervals[1] -= 10
        
        self.set_xticks()

    def moveGraphRight(self):
        self.xintervals[0] += 10
        self.xintervals[1] += 10
        
        self.set_xticks()

    def moveGraphTop(self):
        self.yintervals[0] += 10
        self.yintervals[1] += 10
        self.canvas.axes.set_ylim(ymin=self.yintervals[0], ymax=self.yintervals[1])

    def moveGraphBot(self):
        self.yintervals[0] -= 10
        self.yintervals[1] -= 10
        self.canvas.axes.set_ylim(ymin=self.yintervals[0], ymax=self.yintervals[1])

class StopDialog(QtWidgets.QDialog):
    def __init__(self, accept, reject):
        super().__init__()

        self.setWindowTitle("Предупреждение")

        QBtn = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel

        self.buttonBox = QtWidgets.QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(accept)
        self.buttonBox.rejected.connect(reject)

        self.layout = QtWidgets.QVBoxLayout()
        message = QtWidgets.QLabel("Вы преждевременно остановите испытание. Продолжить?")
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

# Main
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = MainGuiWindow()
    app.setStyleSheet(qdarktheme.load_stylesheet()) # Dark Theme
    win.show()
    sys.exit(app.exec_())