#!/usr/bin/python

import faulthandler; faulthandler.enable()

import sys, glob, queue, time
from threading import Thread, Event
from PyQt5.QtCore import QTime, QTimer
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QThread
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt 

from QTimage import ImageSource, ImageSequence, imageSeq
from tcam import TCam 

# async worker to start image source
# send signal with new ImageSource ref
class SourceStarter(QThread):

    signal = pyqtSignal(ImageSource)

    def __init__(self):
        QThread.__init__(self)

    def run(self):
        #print("SourceStarter: entry")
        # explicitly invalidate previous ref
        # so that it is garbage collected
        self.src = None
        # create new source instance and get temp ref
        self.src = ImageSource(name='ImageSource')
        #print("SourceStarter: ImageSource instance created")
        # wait until source initialization is complete
        while (not self.src.isInitialized()):
            print("SourceStarter: waiting for ImageSource to init")
            pass
        # run source
        self.src.start()
        # tell gui thread about new source
        self.signal.emit(self.src)
        #print("SourceStarter: exit")

class ImageSink(QLabel):

    def __init__(self):
        super().__init__()
        self.setAutoFillBackground(False)
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("LightGray"))
        self.setPalette(palette)
        self.setWindowTitle("ImageSink")
        # timer for elapsed time
        self.wallTime = QTime()
        self.wallTime.start()
        self.nImages = 0.01

    def getStats(self):
        sec = (self.wallTime.elapsed() * 0.001)
        n = self.nImages
        self.wallTime.restart()
        self.nImages = 0.01
        #print('getStats: %d frames, %f sec, %f fps' % (n, sec, n/sec))
        s = "% 3.1f fps" % (n/sec)
        return(s)

    @pyqtSlot(QPixmap)
    def updateImage(self, pixmap: QPixmap):
        pm = pixmap.scaled(self.width(), self.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(pm);
        self.nImages += 1

class FramePlayer(QMainWindow):
    connected = False
    
    def __init__(self):
        super().__init__()
        self.app_quit_flag = False
        self.paused = False        
        self.camConnected = False
        self.ip_addr = "192.168.4.1"
        #create null instance
        self.cam = 0
        
        self.initUI()

    def initUI(self):
        # set main window defaults, initial size/pos
        QToolTip.setFont(QFont('SansSerif', 10))
        scrn = QDesktopWidget().availableGeometry()
        scrn.setHeight(scrn.height()//3)
        scrn.setWidth(scrn.width()//3)
        self.resize(scrn.width(),scrn.height())
        self.setWindowTitle('PyQt5 FramePlayer')
        frame = self.frameGeometry()
        center = QDesktopWidget().availableGeometry().center()
        frame.moveCenter(center)
        self.move(frame.topLeft())

        # create layouts
        mainLayout = QVBoxLayout()
        btnLayout = QHBoxLayout()

        # set main layout as central widget
        cw = QWidget()
        cw.setLayout(mainLayout)
        self.setCentralWidget(cw)

        # create image sink and source
        self.imageSink = ImageSink()
        mainLayout.addWidget(self.imageSink)
        self.imageSource = 0  # begin with invalid ref

        # create buttons
        
        # create rate spinner
        self.rate = QSpinBox(self)
        self.rate.setRange(1,60)
        self.rate.setValue(9)
        self.rate.valueChanged.connect(self.fpsChanged)
    
        self.connectbtn = QPushButton('Connect', self)
        self.connectbtn.clicked.connect(self.connectClicked)
        
    #    self.useCameraImages = True
        self.useCameraImages = False
    #    self.srcBtn = QPushButton('Cam', self)
        self.srcBtn = QPushButton('Jpg', self)
        self.srcBtn.clicked.connect(self.srcBtnClicked)

        self.startBtn = QPushButton('Start', self)
        self.startBtn.clicked.connect(self.startBtnClicked)
        
        self.pauseBtn = QPushButton('Pause', self)
        self.pauseBtn.clicked.connect(self.pauseBtnClicked)
        self.pauseBtn.setEnabled(False)

        self.stopBtn = QPushButton('Stop', self)
        self.stopBtn.clicked.connect(self.stopBtnClicked)
        # disable stop button
        self.stopBtn.setEnabled(False)
        
        self.infoBtn = QPushButton('Help', self)
        self.infoBtn.clicked.connect(self.infoBtnClicked)

        self.quitBtn = QPushButton('Quit', self)
        self.quitBtn.clicked.connect(self.quitBtnClicked)


        # add stats, slider, and buttons to layout
        self.stats = QLabel('30 fps')
        btnLayout.addWidget(self.stats)
        btnLayout.addSpacing(50)
        btnLayout.addWidget(QLabel('fps'))
        btnLayout.addWidget(self.rate)
        btnLayout.addStretch(1)
    
    #
    #    btnLayout.addSpacing(btnSpacing)
        btnLayout.addWidget(self.connectbtn)    
    #
    
        btnLayout.addWidget(self.srcBtn)
        btnLayout.addWidget(self.startBtn)
        btnLayout.addWidget(self.pauseBtn)
        btnLayout.addWidget(self.stopBtn)
        btnLayout.addWidget(self.infoBtn)
        btnLayout.addWidget(self.quitBtn)
        mainLayout.addLayout(btnLayout)

        # animate stats
        self.timer = QTimer()
        self.timer.start()
        self.timer.timeout.connect(self.showStats)
        self.timer.start(777) 

    def showStats(self) :
        self.stats.setText(self.imageSink.getStats())

    def fpsChanged(self):
        fps = self.rate.value()
        #print('fps changed %d' % fps)
        if (isinstance(self.imageSource,ImageSource)):
            self.imageSource.setRate(fps)

    def infoBtnClicked(self):
        #print('info button clicked')
        QMessageBox.information(self, 
            'Info',
            'Preloads 100 or so .png files to memory, and plays '
            'them in a loop. You can adjust the frame rate with '
            'the spin box.', 
            QMessageBox.Ok)

#        self.camConnected = False
#        self.ip_addr = "192.168.4.1"
#        #create null instance
#        self.cam = 0       


    def connectClicked(self):
        print("connect clicked")
        
        #if self.camConnected:
         
        if self.camConnected == True:
            print("connected, disconnecting")
            self.camConnected = False
            self.setWindowTitle('PyQt5 T-Cam Viewer')
            self.connectbtn.setText("Connect")            
            self.cam.shutdown()
            #destroy instance
            self.cam = 0
        else:
            print("connecting")
            self.cam = TCam()
            self.ip_addr = "192.168.4.1"
            stat = self.cam.connect(self.ip_addr)
            if stat["status"] == "connected":
                print("Connected to ip =", self.ip_addr)
                self.camConnected = True
                self.setWindowTitle('PyQt5 T-Cam Viewer ' + self.ip_addr)
                self.connectbtn.setText("Disconnect")
            else:
                print("Could not connect to", ip_addr)
                cam.shutdown()
                self.camConnected = False
                #destroy instance
                self.cam = 0    

    '''
    def dummy(self):
        print('hello')            
    '''

    def getClicked(self):
        print("get clicked")
        self.imageSource.getImage(self)


    def startBtnClicked(self):
        #print('start button clicked')
        # QMessageBox.information(self, 
        #     'Start',
        #     'Start button clicked.', 
        #     QMessageBox.Ok)

        # stop source if running
        self.stopSource()
        # clear displayed frame
        self.imageSink.clear()
        # disable buttons while starting
        self.disableButtons()
        # show hourglass mouse cursor while starting
        busy  = Qt.CursorShape.BusyCursor
        QApplication.setOverrideCursor(busy)
        # create and start worker thread
        self.starterThread = SourceStarter()
        # connect signal to slot
        self.starterThread.signal.connect(self.sourceStarted)
        # run it
        self.starterThread.start()
        
    def pauseBtnClicked(self):
        if self.paused == False:
#if (isinstance(self.imageSource,ImageSource)):
            self.imageSource.pause()
            self.pauseBtn.setText('Resume')
            self.paused = True
        else:
            self.imageSource.resume()
            self.pauseBtn.setText('Pause')
            self.paused = False

    @pyqtSlot(ImageSource)
    def sourceStarted(self, srcRef: ImageSource):
        # save new ImageSource ref
        self.imageSource = srcRef
        # connect ImageSink slot to ImageSource signal
        self.imageSource.signal.connect(self.imageSink.updateImage)
        # set source fps
        self.fpsChanged()
        # enable buttons except start & src button
        self.enableButtons()
        self.startBtn.setEnabled(False)
        self.srcBtn.setEnabled(False)
        # restore normal mouse cursor
        arrow = Qt.CursorShape.ArrowCursor
        QApplication.setOverrideCursor(arrow)

    def disableButtons(self):
        self.startBtn.setEnabled(False)
        self.pauseBtn.setEnabled(False)
        self.stopBtn.setEnabled(False)
        self.quitBtn.setEnabled(False)
        self.infoBtn.setEnabled(False)
        self.srcBtn.setEnabled(False)

    def enableButtons(self):
        self.startBtn.setEnabled(True)
        self.pauseBtn.setEnabled(True)
        self.stopBtn.setEnabled(True)
        self.quitBtn.setEnabled(True)
        self.infoBtn.setEnabled(True)
        self.srcBtn.setEnabled(True)

    def stopBtnClicked(self):
        #print('button clicked')
        # QMessageBox.information(self, 
        #     'Stop',
        #     'Stop button clicked.', 
        #     QMessageBox.Ok)
        self.stopSource()
        # disable stop start src buttons
        self.stopBtn.setEnabled(False)
        self.startBtn.setEnabled(True)
        self.pauseBtn.setEnabled(False)
        self.srcBtn.setEnabled(True)


    # called on Quit button clicked
    def quitBtnClicked(self):
        print('quit clicked')
        '''
        reply = QMessageBox.question(self, 
            'Quit',
            'Quit, are you sure?', QMessageBox.Yes |
            QMessageBox.No, QMessageBox.No)
        '''
        reply = True
        
        #if reply == QMessageBox.Yes:
        if True:
            print('quit confirmed')
            self.app_quit_flag = True
            self.stopSource()
            self.close()
        else:
            print('quit canceled')
            self.app_quit_flag = False

    def srcBtnClicked(self):
        #print('src button clicked')
        cam = self.useCameraImages
        if cam:
            txt = 'Jpg'
            cam = False
        else:
            txt = 'Cam'
            cam = True
		# select source of images
        imageSeq.selectSource(cam)
        self.useCameraImages = cam
        self.srcBtn.setText(txt)

    def stopSource(self):
        if (isinstance(self.imageSource, ImageSource)):
            # stop source thread
            self.imageSource.stop()
            self.imageSource.quit() # QThread reqmt
            self.imageSource.wait() # QThread reqmt
            # explicitly invalidate ref 
			# to allow garbage collection
            self.imageSource = 0
        else:
            #print("FramePlayer stopSource - no instance of ImageSource ")
            pass


    # called on main window "X" closer clicked
    def closeEvent(self, event):
        print('main window closed')
        if self.app_quit_flag :
            event.accept()
            return
        '''
        reply = QMessageBox.question(self, 
            'Message',
            'Quit, are you sure?', QMessageBox.Yes |
            QMessageBox.No, QMessageBox.No)
        '''
        
        #if reply != QMessageBox.Yes:
        if False:
            print('quit canceled')
            self.app_quit_flag = False
            event.ignore()
        else:
            print('quit confirmed')
            self.app_quit_flag = True
            self.stopSource()
            event.accept()

def main():
    app = QApplication(sys.argv)
    w = FramePlayer()
    w.show()
    result = app.exec_()
    sys.exit(result)


if __name__ == '__main__':
    main()

