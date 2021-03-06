import sys, os
from os import path 
import struct
from socket import *  
import numpy as np
import time
import datetime
import threading
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from Ui_TimeDomainPlot import Ui_MainWindow

gSocketHeaderSize = 16
gSocketBodySize = 32 * 1024
gSocketBufSize = gSocketBodySize + gSocketHeaderSize

class UDPSocketClient:
    def __init__(self):
        self.mHost = '192.168.1.6'
        #self.mHost = '127.0.0.1'
        self.mPort = 6000 
        self.mBufSize = gSocketBodySize + gSocketHeaderSize
        self.mAddress = (self.mHost, self.mPort)
        self.mUDPClient = socket(AF_INET, SOCK_DGRAM)
        self.mData = None
        self.mUDPClient.settimeout(5)

    def setBufSize (self,  bufSize):
        self.mBufSize = bufSize
        
    def sendData(self):
        self.mUDPClient.sendto(self.mData,self.mAddress)
        self.mData = None # Clear data after send out

    def receiveData(self):
       self.mData, self.mAddress = self.mUDPClient.recvfrom(gSocketBufSize)
       return self.mData

class RealTimeThread(threading.Thread):  
    def __init__(self, axes, canvas, cha,  timeout, stopforExternalTrigger):  
        super(RealTimeThread, self).__init__()  
        self.axes = axes
        self.canvas = canvas
        self.CHA = mainWindow.radioButton_CHA.isChecked()
        self.timeout = timeout 
        self.data = []
        self.data_ChA = []
        self.data_ChB = []
        self.stopped = False
        self.stopforExternalTrigger = stopforExternalTrigger
        self.sampleRate = mainWindow.getSampleRate()
        self.recordLength = mainWindow.getRecordLength()
        self.volScale = mainWindow.getVoltageScale()
        self.offset = mainWindow.getOffset()     

    def run(self):  
        def bumatoyuanmaSingle(x):
          if (x > 32767): 
             x = x - 65536 
          return x
   
        def parseData(data, length,  withHead):
            data_ChA =[]
            data_ChB = []
            newdata = data
            if (withHead):
               newdata = data[16:]
               #newdata = data # just for testing
            else:
                newdata = data
                
            for pos in range(0, length*1024, 32):
                line = newdata[pos:pos+32]
                newline = ''
                # One line data
                for i in range(0, 32, 2):
                   #print (line[i:i+2])
                    try:
                        newline =  newline + ("%04x" % int(struct.unpack('H',line[i:i+2])[0]))
                    except:
                        #print ("Data Invalid...")
                        newline =  newline + "0000"

                # Get CHA/CHB VALUE BY ABAB...
                for i in range(0,  64,  8):
                    dataA1= newline[i:i+2]
                    dataA2= newline[i+2:i+4]
                    dataA = dataA2 + dataA1
                    dataA = int (dataA,  16)
                    data_ChA.append(bumatoyuanmaSingle(dataA))
                    dataB1 = newline[i+4:i+6]
                    dataB2 = newline[i+6:i+8]
                    dataB = dataB2  + dataB1
                    dataB = int (dataB,  16)
                    data_ChB.append(bumatoyuanmaSingle(dataB))

            #print ("Channel A: Length:", len(data_ChA))
            #print ("Channel B: Length:", len(data_ChB))
            
            return [data_ChA, data_ChB]

        def receiveData():
#            mainWindow.sendCmdWRREG(0x2, 0x28)
#            mainWindow.sendCmdWRREG(0x2, 0x29)
#            time.sleep(1)
#            mainWindow.sendCmdWRREG(0x2, 0x2b)
            mainWindow.sendCmdRAW_AD_SAMPLE(self.recordLength * 4)
            mainWindow.receiveCmdRAW_AD_SAMPLE(self.recordLength * 4)
            return mainWindow.udpSocketClient.mData
                    
        def realtimecapture():
            print ("Start Real Time Capture.......")
            
            frameMode = mainWindow.checkBox_FrameMode.isChecked()


# Replace it in the start command
#            mainWindow.sendCmdWRREG(0x2, 0x28)
#            mainWindow.sendCmdWRREG(0x2, 0x29)
#            time.sleep(1)

            # Start to read data
            mainWindow.sendCmdWRREG(0x2, 0x2b)

            if (frameMode == False):
                receiveTimes = int (self.recordLength*mainWindow.getFrameNumber() / 8)
                while not self.stopped:
                    self.data_ChA = []
                    self.data_ChB = []
                    if receiveTimes <= 1:
                        data = receiveData()
                        #print ("Receive Total Length:",  len(data))
                        if data:
                            data = parseData(data, self.recordLength * 4 ,  True )
                            self.data_ChA = data[0]
                            self.data_ChB = data[1]
                    else:
                        for loop in range(0, receiveTimes):
                            data = receiveData()
                            if data:
                                data = parseData(data, 32,  True )
                                self.data_ChA = self.data_ChA + data[0]
                                self.data_ChB = self.data_ChB + data[1]
                            
                    if (mainWindow.radioButton_CHA.isChecked()): 
                        on_draw(self.axes, self.canvas, self.data_ChA)
                    else: 
                        on_draw(self.axes, self.canvas, self.data_ChB)
                
                    if self.stopforExternalTrigger == True:
                        self.stop()
    #                    mainWindow.externalTriggerThread.stop()
    #                    mainWindow.on_pushButton_Stop_TimeDomain_clicked()
                    
                if self.stopped:
                    mainWindow.lastChAData = []
                    mainWindow.lastChAData.append(self.data_ChA )
                    mainWindow.lastChBData = []
                    mainWindow.lastChBData.append(self.data_ChB)
                    
            elif (frameMode == True):
                receiveTimes = int (self.recordLength / 8)
                frameNum = mainWindow.getFrameNumber();
                data_ChA_List = []
                data_ChB_List = []
                
                while not self.stopped:
                    for frameIndex in range(0,  frameNum):
                        self.data_ChA = []
                        self.data_ChB = []
                        if receiveTimes <= 1:
                            data = receiveData()
                            #print ("Receive Total Length:",  len(data))
                            if data:
                                data = parseData(data, self.recordLength * 4 ,  True )
                                self.data_ChA = data[0]
                                self.data_ChB = data[1]
                                data_ChA_List.append(self.data_ChA)
                                data_ChB_List.append(self.data_ChB)
                        else:
                            for loop in range(0, receiveTimes):
                                data = receiveData()
                                if data:
                                    data = parseData(data, 32,  True )
                                    self.data_ChA = self.data_ChA + data[0]
                                    self.data_ChB = self.data_ChB + data[1]
                            
                            data_ChA_List.append(self.data_ChA)
                            data_ChB_List.append(self.data_ChB)
                            
                        if (mainWindow.radioButton_CHA.isChecked()): 
                            on_draw(self.axes, self.canvas, self.data_ChA)
                        else: 
                            on_draw(self.axes, self.canvas, self.data_ChB)

                    if self.stopforExternalTrigger == True:
                        self.stop()
  
                if self.stopped:
                    mainWindow.lastChAData = data_ChA_List 
                    mainWindow.lastChBData = data_ChB_List  
  
        def on_draw( axes, canvas, data):
                # clear the axes and redraw the plot anew
                axes.clear() 
                #axes.set_title('Signal')
                axes.set_xlabel('Time(μs)')
                axes.set_ylabel('Voltage')
                
                self.sampleRate = mainWindow.getSampleRate()
                #self.recordLength = mainWindow.getRecordLength()
                self.volScale = mainWindow.getVoltageScale()
                self.offset = mainWindow.getOffset()
                timespan = self.recordLength*1024/self.sampleRate # in us
                x = np.linspace(0, timespan, self.recordLength*1024)  
                #x = np.linspace(-self.sampleRate*1e6/2, self.sampleRate*1e6/2, self.recordLength*1024)  
                normalLimY = self.volScale * 10;
                axes.set_ylim(-normalLimY/2 + self.offset, normalLimY/2 + self.offset )
                ymajorLocator = MultipleLocator(self.volScale) 
                yminorLocator = MultipleLocator(self.volScale/2) 
                axes.yaxis.set_major_locator(ymajorLocator)
                axes.yaxis.set_minor_locator(yminorLocator)
                axes.grid(True)
                
                #print ("Plot X Length: ",  self.recordLength*1024)
                #print ("Plot Data Length: ",  len(data))
                axes.plot(x, data)
                canvas.draw()

        now = datetime.datetime.now()
        startTime = now.strftime('%Y-%m-%d-%H-%M-%S')
        subthread = threading.Thread(target=realtimecapture)
        subthread.setDaemon(True)  
        subthread.start()  
        
    def stop(self): 
        print ("Stop Real Time Thread...")
        self.stopped = True  

    def isStopped(self):  
        return self.stopped  

# For exteranl Trigger Type
class ExternalTriggerThread(threading.Thread):  
    def __init__(self):  
        super(ExternalTriggerThread, self).__init__()  
        self.stopped = False
        self.internalRealTimeThread = None

    def run(self):      
        def triggerMonitor():
            print ("Start External Trigger Thread.......")
            while not self.stopped:
                
                    
                # Read register....
                mainWindow.sendCmdWRREG(0x2, 0x28)
                mainWindow.sendCmdWRREG(0x2, 0x29)
                time.sleep(1)
        
                currentDataLength = mainWindow.readExternalTriggerDataCount()
                print ("Current Data Length:",  currentDataLength)
                
                #currentDataLength = mainWindow.getRecordLength() *1024*mainWindow.getFrameNumber()
                # Read Data
                # FrameNum*RecordLength*1024
                if (mainWindow.getRecordLength() *1024*mainWindow.getFrameNumber() <= currentDataLength):
                    # start RealTimeThread
                    self.internalRealTimeThread = RealTimeThread(mainWindow.axes, mainWindow.canvas, mainWindow.radioButton_CHA.isChecked(), 1.0,  True)
                    self.internalRealTimeThread.setDaemon(True)
                    self.internalRealTimeThread.start()
                    #times = 1
                    while (not self.internalRealTimeThread.isStopped()):
                        time.sleep(0.5)
                
                # Wait for 500ms
                time.sleep(0.5)

        subthread = threading.Thread(target=triggerMonitor)
        subthread.setDaemon(True)  
        subthread.start()  
        
    def stop(self): 
        print ("Stop External Trigger Thread...")
        self.stopped = True  

    def isStopped(self):  
        return self.stopped  

class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)

        self.dpi = 100
        self.signalframe = self.widget_Signal_TimeDomain
        self.figure = Figure((11.3, 6.3), dpi=self.dpi)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(self.signalframe)
        self.axes = self.figure.add_subplot(111)
        #self.axes.set_title('Signal')
        self.axes.set_xlabel('Time(μs)')
        self.axes.set_ylabel('Voltage')
        #plt.subplots_adjust(left=0.2, bottom=0.2, right=0.8, top=0.8, hspace=0.2, wspace=0.3)
        
        timespan = self.getRecordLength()*1024/self.getSampleRate() # in us
        x = np.linspace(0, timespan, self.getRecordLength()*1024)  
        normalLimY = self.getVoltageScale() * 10;
        self.axes.set_ylim(-normalLimY/2 + self.getOffset(), normalLimY/2 + self.getOffset() )
        ymajorLocator = MultipleLocator(self.getVoltageScale()) 
        yminorLocator = MultipleLocator(self.getVoltageScale()/2) 
        self.axes.yaxis.set_major_locator(ymajorLocator)
        self.axes.yaxis.set_minor_locator(yminorLocator)
        self.axes.grid(True)
        
        
        self.figure.tight_layout()# Adjust spaces
        #self.NavToolbar = NavigationToolbar(self.canvas, self.signalframe)
        #self.addToolBar(QtCore.Qt.RightToolBarArea, NavigationToolbar(self.canvas, self.signalframe))
        self.toolbar = NavigationToolbar(self.canvas, self.signalframe)
        self.toolbar.hide()
        
        # Button slots
        self.pushButton_Home.clicked.connect(self.home)
        self.pushButton_Back.clicked.connect(self.back)
        self.pushButton_Forward.clicked.connect(self.forward)
        self.pushButton_Pan.clicked.connect(self.pan)
        self.pushButton_Zoom.clicked.connect(self.zoom)
        self.pushButton_SavePic.clicked.connect(self.savepic)
        
        # Init Socket
        self.udpSocketClient = UDPSocketClient()
        
        # Init Length
        self.sendCmdRecordLength(1)
        
        self.sendCmdWRREG(0x2,  0x20)
        self.sendCmdWRREG(0x2,  0x28)
        
        # Read sampleRate
        value = self.readCmdSampleRate()
        if value > 5:
            value = 0
        self.comboBox_SampleRate.setCurrentIndex(value)
        
        self.frameNum = self.getFrameNumber()
        
        # The last data
        self.lastChAData = []
        self.lastChBData = []
        
        self.realTimeThread = None
        self.externalTriggerThread = None

    def home(self):
        self.toolbar.home()
    def back(self):
        self.toolbar.back()
    def forward(self):
        self.toolbar.forward ()
    def zoom(self):
        self.toolbar.zoom()
    def pan(self):
        self.toolbar.pan()
    def savepic(self):
        self.toolbar.save_figure()

    def sendcommand(self, cmdid, status, msgid, len, type, offset, apiversion, pad, CRC16,  cmdData):
          cmdid=struct.pack('H',htons(cmdid))
          status=struct.pack('H',htons(status))
          msgid=struct.pack('H',htons(msgid))
          len=struct.pack('H',htons(len))
          type=struct.pack('H',htons(type))
          offset=struct.pack('H',htons(offset))
          apiversion=struct.pack('B',apiversion) # 1 Byte unsigned char
          pad=struct.pack('B',pad) # 1 Byte unsigned char
          CRC16=struct.pack('H',htons(CRC16)) # 2 Byte unsigned short
          cmdHeader = cmdid + status + msgid + len + type + offset + apiversion + pad + CRC16
          
          if (cmdData != None):
              self.udpSocketClient.mData = cmdHeader + cmdData
          else:
              self.udpSocketClient.mData = cmdHeader
          
          self.udpSocketClient.sendData()
       
    def sendCmdTriggerType(self,  value): 
        value = value << 2
        regAddr= 0x2 # 0x2, Bit[2], 0: Auot, 1: External
        regValue=value
        currentValue = self.readCmdTriggerType()
        
        currentValue = currentValue | value
        self.sendCmdWRREG(regAddr,  currentValue)

#    def receiveCmdTriggerType(self): 
#        global gSocketBodySize
#        gSocketBodySize = 8
#        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
#        mainWindow.udpSocketClient.receiveData() # Do nothing
    
    def readCmdTriggerType(self): 
        print ("readCmdTriggerType ")
        self.sendCmdRDREG(0x02,  0x00)
        data = self.udpSocketClient.receiveData()
        value = int(struct.unpack('L',data[20:24])[0])
        return value
        
    def readExternalTriggerDataCount(self): 
        self.sendCmdRDREG(0x10,  0x00)
        data = self.udpSocketClient.receiveData()
        data = data[20:24]
        lowValue = ntohl(int(struct.unpack('L',data)[0]))
        #print (hex(lowValue))
        self.sendCmdRDREG(0x12,  0x00)
        data = self.udpSocketClient.receiveData()
        data = data[20:24]
        highValue =ntohl(int(struct.unpack('L',data)[0]))
        #print (hex(highValue))
        value = highValue << 16 | lowValue
        return value
        #return 1024
    
    def sendCmdSampleRate(self, value): 
        global gSocketBodySize
        gSocketBodySize = 4
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        cmdData  =  struct.pack('L', htonl(value)) 
        self.sendcommand(0x5a09,0x0000,0x5a09,0x0004,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
        mainWindow.udpSocketClient.receiveData() # Do nothing
        
    def readCmdSampleRate(self): 
        global gSocketBodySize
        gSocketBodySize = 4
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        # Len is not cared
        self.sendcommand(0x5a0a,0x0000,0x5a0a,0x0004,0x0000,0x0000,0x00,0x00,0x0000, None )
        data = self.udpSocketClient.receiveData()
        value = int(struct.unpack('L',data[16:20])[0])
        return value
        
    def sendCmdRecordLength(self,  length): 
        #recordLength = self.getRecordLength()
        regAddr= 0x8
        regValue= length
        self.sendCmdWRREG(regAddr,  regValue)

    def receiveCmdRecordLength(self): 
        global gSocketBodySize
        gSocketBodySize = 8
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        self.udpSocketClient.receiveData() # Do nothing
   
    def sendCmdRAW_AD_SAMPLE(self,  length):
        #print (sys._getframe().f_code.co_name)        
        global gSocketBodySize
        gSocketBodySize = length*1024
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        len = 0 #self.getRecordLength()
        self.sendcommand(0x5a04,0x0000,0x5a04,len,0x0000,0x0000,0x00,0x00,0x0000, None)
          
    def receiveCmdRAW_AD_SAMPLE(self,  length):
        global gSocketBodySize
        gSocketBodySize =  length*1024
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        mainWindow.udpSocketClient.receiveData()
    
    def sendCmdFramNum(self,  frameNum):
        if (frameNum <= 2**16-1):
            regAddr= 0x4
            regValue= frameNum
            self.sendCmdWRREG(regAddr,  regValue)
        else:
             # Low
            regAddr= 0x4
            regValue= frameNum & (2**16-1)
            self.sendCmdWRREG(regAddr,  regValue)
            # High
            regAddr= 0x6
            regValue= frameNum >> 16
            self.sendCmdWRREG(regAddr,  regValue)

    def sendCmdWRREG(self,  regAddress,  regValue):
        #print (sys._getframe().f_code.co_name)
        global gSocketBodySize
        gSocketBodySize = 8
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        cmdData  =  struct.pack('L', htonl(regAddress)) +  struct.pack('L', htonl(regValue))
        self.sendcommand(0x5a02,0x0000,0x5a02,0x0008,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
        self.udpSocketClient.receiveData() # Do nothing
        
    def sendCmdRDREG(self,  regAddress,  regValue):
        #print (sys._getframe().f_code.co_name)
        global gSocketBodySize
        gSocketBodySize = 8
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        cmdData  =  struct.pack('L', htonl(regAddress)) +  struct.pack('L', htonl(regValue))
        self.sendcommand(0x5a01,0x0000,0x5a01,0x0008,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
    
    
    
    def getTriggerType(self):
        index = self.comboBox_TriggerDomain.currentIndex()
        return int(index)
        
    def getSampleRate(self):
        index = self.comboBox_SampleRate.currentText()
        return int(index)
        
    def getRecordLength(self):
        index = self.comboBox_RecordLength.currentIndex()
        return 2**index
        
    def getVoltageScale(self):
        volScale = 200
        volScaleStr = self.lineEdit_VolScale.text()
        volScale = 200
        if (('-' )  == volScaleStr or "" == volScaleStr):
            volScale = 200
        else:
            volScale = int(volScaleStr) 
                
        return volScale
        
    def getOffset(self):
        offset = 0
        offsetStr = self.lineEdit_Offset.text();
        if (('-' )  == offsetStr or "" == offsetStr):
            offset = 0
        else:
            offset = int(offsetStr) 
                
        return offset
        
    def getFrameNumber(self):
        if (self.checkBox_FrameMode.isChecked() and self.checkBox_FrameMode.isEnabled()):
            return int(self.lineEdit_FrameNum.text())
        else:
            return 1
    
    @pyqtSlot()
    def on_pushButton_Stop_TimeDomain_clicked(self):
        """
        Slot documentation goes here.
        """
        if self.realTimeThread != None:
            self.realTimeThread.stop()
        if self.externalTriggerThread != None:
            self.externalTriggerThread.stop()
            
        self.pushButton_Start_TimeDomain.setEnabled(True)
        self.pushButton_Stop_TimeDomain.setEnabled(False)
        self.pushButton_Save_TimeDomain.setEnabled(True)
        self.comboBox_RecordLength.setEnabled(True)
        self.comboBox_SampleRate.setEnabled(True)
        self.comboBox_TriggerDomain.setEnabled(True)
    
    @pyqtSlot()
    def on_pushButton_Start_TimeDomain_clicked(self):
        """
        Slot documentation goes here.
        """
        self.pushButton_Start_TimeDomain.setEnabled(False)
        self.pushButton_Stop_TimeDomain.setEnabled(True)
        self.pushButton_Save_TimeDomain.setEnabled(False)
        self.comboBox_RecordLength.setEnabled(False)
        self.comboBox_SampleRate.setEnabled(False)
        self.comboBox_TriggerDomain.setEnabled(False)
        
        # Start to capture...
        self.sendCmdWRREG(0x2, 0x28)
        self.sendCmdWRREG(0x2, 0x29)
        time.sleep(1)
        
        if self.getTriggerType() == 0: # Auto Trigger Type
            self.realTimeThread = RealTimeThread(self.axes, self.canvas, self.radioButton_CHA.isChecked(), 1.0,  False)
            self.realTimeThread.setDaemon(True)
            self.realTimeThread.start()
        elif self.getTriggerType() == 1: # External Trigger Type
            self.externalTriggerThread = ExternalTriggerThread()
            self.externalTriggerThread.setDaemon(True)
            self.externalTriggerThread.start()  
    
    @pyqtSlot()
    def on_pushButton_Save_TimeDomain_clicked(self):
        """
        Slot documentation goes here.
        """
        # Write into file
        now = datetime.datetime.now()
        currentTime = now.strftime('%Y-%m-%d-%H-%M-%S') 
        if (len(self.lastChAData) == 1):
            FileName_CHA = "ChA-" + currentTime + ".txt"
            File_CHA=open(FileName_CHA,'w')
            FileName_CHB = "ChB-" + currentTime + ".txt"
            File_CHB=open(FileName_CHB,'w')
            
            for pos in range(0, len(self.lastChAData[0])):
                File_CHA.write(str(self.lastChAData[0][pos]))
                File_CHA.write('\n')
                File_CHB.write(str(self.lastChBData[0][pos]))
                File_CHB.write('\n')
                
            File_CHA.close()
            File_CHB.close()
        else:
            for fileIndex in range(0,  len(self.lastChAData)):
                FileName_CHA = "ChA-" + currentTime + "-" + str(fileIndex + 1) + ".txt"
                File_CHA=open(FileName_CHA,'w')
                FileName_CHB = "ChB-" + currentTime + "-" + str(fileIndex + 1) + ".txt"
                File_CHB=open(FileName_CHB,'w')
                
                for pos in range(0, len(self.lastChAData[fileIndex])):
                    File_CHA.write(str(self.lastChAData[fileIndex][pos]))
                    File_CHA.write('\n')
                    File_CHB.write(str(self.lastChBData[fileIndex][pos]))
                    File_CHB.write('\n')
                    
                File_CHA.close()
                File_CHB.close()
            
        
        # Do not clear it
        #self.lastChAData = []
        #self.lastChBData = []
        
    @pyqtSlot(int)
    def on_comboBox_TriggerDomain_currentIndexChanged(self, index):
        
        self.sendCmdTriggerType(index)
        
        # Enable/Disable Frame Mode
        if index == 1:
            self.checkBox_FrameMode.setEnabled(True)
            self.label_FrameNum.setEnabled(True)
            self.lineEdit_FrameNum.setEnabled(True)
        else:
            self.checkBox_FrameMode.setEnabled(False)
            self.label_FrameNum.setEnabled(False)
            self.lineEdit_FrameNum.setEnabled(False)

    @pyqtSlot(int)
    def on_comboBox_SampleRate_currentIndexChanged(self, index):
        if index > -1:
            self.sendCmdSampleRate(index)
        
    @pyqtSlot(int)
    def on_comboBox_RecordLength_currentIndexChanged(self, index):
        self.sendCmdRecordLength(2**index)
  
    @pyqtSlot()
    def on_lineEdit_FrameNum_editingFinished(self):
        self.frameNum = int(self.lineEdit_FrameNum.text())
        self.sendCmdFramNum(self.frameNum);

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
