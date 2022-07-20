# resolution of IR camera frame 160 x 120
# external IR camera transfer rate 9 fps via TCP
# camera data is json

import base64
##from palettes import ironblack_palette
##from PIL import Image as im
import json
import numpy as np
import argparse
import sys

from threading import Thread, Event
import glob, time
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtCore import QByteArray

#from tcam import TCam 

from ironblack import ironblack_palette

maxImages = 200

class ImageSequence():

    srcImages = []

    def __init__(self, name=None):
        super().__init__()
        self.loaded = False
        # True = use tCam json data, else jpgs
        #self.tCam = True
        self.tCam = False
        #Do we need this here
        self.connected = False

    def selectSource(self, cam):
        if (self.tCam != cam):
            self.tCam = cam
            self.loaded = False

    def load(self):
        if self.loaded:
            return
        self.srcImages = []
        if self.tCam:
            self.loadCamImages()
        else:
            self.loadJpgImages()

    def loadCamImages(self):
        names = []
        # load images from tmjsn file
        file = 'pi0_5sec_heating.tmjsn'
        #file = 'tCam-imagehand.tmjsn'
        #print(f"Reading camera image file {file}")
        with open(file, 'r') as f:
            json_str = f.read()

        #print("Getting radiometric data")
        camFrames = json_str.split(chr(3))
        nFrames = 0
        for frame in camFrames:
            try:
                img = json.loads(frame)
                dimg = base64.b64decode(img["radiometric"])
            except json.decoder.JSONDecodeError:    
                print("json decode error ignored")
                next
            except KeyError:
                print("key error ignored")
                next
            mv = memoryview(dimg).cast("H")
            #print("Computing image min/max for mapping to palette")
            imgmin = 65535
            imgmax = 0

            for i in mv.tolist():
                if i < imgmin:
                    imgmin = i
                if i > imgmax:
                    imgmax = i

            delta = imgmax - imgmin
            #print(f"Max val is {imgmax}, Min val is {imgmin}, Delta is {delta}")

            # now form the 8 bit range from the min and delta.  This allows us 
            # to bracket the 16 bit data into an 8 bit range, and then use the 
            # 8 bits to look up the palette data for the pixel value.
            transformed = []
            for i in mv:
                val = int((i - imgmin) * 255 / delta)

                if val > 255:
                    transformed.append(ironblack_palette[255])
                else:
                    transformed.append(ironblack_palette[val])

            # Convert to a PPM image
            #print("Displaying image")
            a = np.zeros((120, 160, 3), np.uint8)
            for r in range(0, 120):
                for c in range(0, 160):
                    a[r, c] = transformed[(r * 160) + c]

            # create PPM preamble in QByteArray
            # see http://netpbm.sourceforge.net/doc/ppm.html
            ppm_pre = "P6  160  120  255\n "
            qb = QByteArray()
            qb.append(bytes(ppm_pre, "utf-8"))
            # append the raw data
            qb.append(a.tobytes())
            # create QPixmap
            pm = QPixmap()
            pm.loadFromData(qb, "PPM")
            # add to buffer list
            self.srcImages.append(pm)
            self.loaded = True

    def loadJpgImages(self):
        # load images from jpg files
        names = []
        for filename in glob.glob("frm/frm_???.png"):
            names.append(filename)
        names.sort()
        while len(names) > maxImages:
            names.pop()
        for filename in names:
            pm = QPixmap()
            #print(f"Reading file {filename}")
            pm.load(filename)
            self.srcImages.append(pm)
            self.loaded = True
    
 
# static instance
imageSeq = ImageSequence()

class ImageSource(QThread):
    # signal to send new frame
    signal = pyqtSignal(QPixmap)

    def __init__(self, name=None):
        super().__init__()
        self.initComplete = False
        self.frameEvent = Event()
        self.stopEvent = Event()
        self.paused = False
        self.images = []
        self.imageIndex = 0
        self.loadImages()
        self.nImages = len(self.images)
        self.loopCalSec = 0.99
        self.updater = None
        self.fps = 30
        self.minFps = 1
        self.maxFps = 120
        self.initComplete = True
        
        self.ip = "192.168.4.1"
        self.connected = False
        #self.cam = TCam()


    def  isInitialized(self):
        return self.initComplete
        

    def setRate(self, fps):
        if (fps >= self.minFps and fps <= self.maxFps):
            self.fps = fps      

    def pause(self):
        if not self.paused:
            self.paused = True
            print('ImageSource paused')

    def resume(self):           
        if self.paused:
            self.paused = False
            print('ImageSource resumed')


    def stop(self):
        #print('ImageSource stopping (set stopEvent)')
        self.stopEvent.set()


    def loadImages(self):
        imageSeq.load()
        self.images = imageSeq.srcImages
        print("ImageSource loaded %d images" % len(self.images))

    
    def run(self):
        print('ImageSource started') 
        self.stopEvent.clear()
        print("  fps {0}, loopCalSec {1} frame period {2} ".format(
            self.fps, self.loopCalSec,self.loopCalSec/self.fps))
        while not self.stopEvent.wait(self.loopCalSec/self.fps):
            #print(f"ImageSource: frame {self.imageIndex}")
            if self.paused == True:
                continue
            pixmap = self.images[self.imageIndex]
            # send new frame to gui
            self.signal.emit(pixmap)
            self.imageIndex += 1
            if self.imageIndex >= self.nImages:
                self.imageIndex = 0
        print('ImageSource stopped')
    
