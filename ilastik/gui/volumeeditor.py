#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    Copyright 2010 C Sommer, C Straehle, U Koethe, FA Hamprecht. All rights reserved.
#    
#    Redistribution and use in source and binary forms, with or without modification, are
#    permitted provided that the following conditions are met:
#    
#       1. Redistributions of source code must retain the above copyright notice, this list of
#          conditions and the following disclaimer.
#    
#       2. Redistributions in binary form must reproduce the above copyright notice, this list
#          of conditions and the following disclaimer in the documentation and/or other materials
#          provided with the distribution.
#    
#    THIS SOFTWARE IS PROVIDED BY THE ABOVE COPYRIGHT HOLDERS ``AS IS'' AND ANY EXPRESS OR IMPLIED
#    WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
#    FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE ABOVE COPYRIGHT HOLDERS OR
#    CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
#    CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#    SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
#    ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
#    NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
#    ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#    
#    The views and conclusions contained in the software and documentation are those of the
#    authors and should not be interpreted as representing official policies, either expressed
#    or implied, of their employers.

"""
Dataset Editor Dialog based on PyQt4
"""
import time

try:
    from OpenGL.GL import *
    from OpenGL.GLU import *
except Exception, e:
    print e
    pass

from PyQt4 import QtCore, QtOpenGL
from PyQt4.QtCore import pyqtSignal
import sip
import numpy, qimage2ndarray

import os.path
from collections import deque
import threading

from ilastik.core.volume import DataAccessor

from shortcutmanager import *

from ilastik.gui.quadsplitter import QuadView

import ilastik.gui.exportDialog as exportDialog

from ilastik.gui.iconMgr import ilastikIcons

from ilastik.gui.view3d import OverviewScene

# Local import
#from spyderlib.config import get_icon, get_font

##mixin to enable label access
#class VolumeLabelAccessor():
    #def __init__():
        #self._labels = None

##extend ndarray with _label attribute
#numpy.ndarray.__base__ += (VolumeLabelAccessor, )





def rgb(r, g, b):
    # use qRgb to pack the colors, and then turn the resulting long
    # into a negative integer with the same bitpattern.
    return (QtGui.qRgb(r, g, b) & 0xffffff) - 0x1000000
        

#*******************************************************************************
# P a t c h A c c e s s o r                                                    *
#*******************************************************************************

class PatchAccessor():
    def __init__(self, size_x,size_y, blockSize = 128):
        self._blockSize = blockSize
        self.size_x = size_x
        self.size_y = size_y

        self._cX = int(numpy.ceil(1.0 * size_x / self._blockSize))

        #last blocks can be very small -> merge them with the secondlast one
        self._cXend = size_x % self._blockSize
        if self._cXend < self._blockSize / 3 and self._cXend != 0 and self._cX > 1:
            self._cX -= 1
        else:
            self._cXend = 0

        self._cY = int(numpy.ceil(1.0 * size_y / self._blockSize))

        #last blocks can be very small -> merge them with the secondlast one
        self._cYend = size_y % self._blockSize
        if self._cYend < self._blockSize / 3 and self._cYend != 0 and self._cY > 1:
            self._cY -= 1
        else:
            self._cYend = 0


        self.patchCount = self._cX * self._cY


    def getPatchBounds(self, blockNum, overlap = 0):
        z = int(numpy.floor(blockNum / (self._cX*self._cY)))
        rest = blockNum % (self._cX*self._cY)
        y = int(numpy.floor(rest / self._cX))
        x = rest % self._cX

        startx = max(0, x*self._blockSize - overlap)
        endx = min(self.size_x, (x+1)*self._blockSize + overlap)
        if x+1 >= self._cX:
            endx = self.size_x

        starty = max(0, y*self._blockSize - overlap)
        endy = min(self.size_y, (y+1)*self._blockSize + overlap)
        if y+1 >= self._cY:
            endy = self.size_y


        return [startx,endx,starty,endy]

    def getPatchesForRect(self,startx,starty,endx,endy):
        sx = int(numpy.floor(1.0 * startx / self._blockSize))
        ex = int(numpy.ceil(1.0 * endx / self._blockSize))
        sy = int(numpy.floor(1.0 * starty / self._blockSize))
        ey = int(numpy.ceil(1.0 * endy / self._blockSize))
        
        
        if ey > self._cY:
            ey = self._cY

        if ex > self._cX :
            ex = self._cX

        nums = []
        for y in range(sy,ey):
            nums += range(y*self._cX+sx,y*self._cX+ex)
        
        return nums

        
    

#abstract base class for undo redo stuff
#*******************************************************************************
# S t a t e                                                                    *
#*******************************************************************************

class State():
    def __init__(self):
        pass

    def restore(self):
        pass


#*******************************************************************************
# L a b e l S t a t e                                                          *
#*******************************************************************************

class LabelState(State):
    def __init__(self, title, axis, num, offsets, shape, timeAxis, volumeEditor, erasing, labels, labelNumber):
        self.title = title
        self.time = timeAxis
        self.num = num
        self.offsets = offsets
        self.axis = axis
        self.erasing = erasing
        self.labelNumber = labelNumber
        self.labels = labels
        self.clock = time.clock()
        self.dataBefore = volumeEditor.labelWidget.overlayItem.getSubSlice(self.offsets, self.labels.shape, self.num, self.axis, self.time, 0).copy()
        
    def restore(self, volumeEditor):
        temp = volumeEditor.labelWidget.overlayItem.getSubSlice(self.offsets, self.labels.shape, self.num, self.axis, self.time, 0).copy()
        restore  = numpy.where(self.labels > 0, self.dataBefore, 0)
        stuff = numpy.where(self.labels > 0, self.dataBefore + 1, 0)
        erase = numpy.where(stuff == 1, 1, 0)
        self.dataBefore = temp
        #volumeEditor.labels._data.setSubSlice(self.offsets, temp, self.num, self.axis, self.time, 0)
        volumeEditor.setLabels(self.offsets, self.axis, self.num, restore, False)
        volumeEditor.setLabels(self.offsets, self.axis, self.num, erase, True)
        if volumeEditor.sliceSelectors[self.axis].value() != self.num:
            volumeEditor.sliceSelectors[self.axis].setValue(self.num)
        else:
            #volumeEditor.repaint()
            #repainting is already done automatically by the setLabels function
            pass
        self.erasing = not(self.erasing)          



#*******************************************************************************
# H i s t o r y M a n a g e r                                                  *
#*******************************************************************************

class HistoryManager(QtCore.QObject):
    def __init__(self, parent, maxSize = 3000):
        QtCore.QObject.__init__(self)
        self.volumeEditor = parent
        self.maxSize = maxSize
        self._history = []
        self.current = -1

    def append(self, state):
        if self.current + 1 < len(self._history):
            self._history = self._history[0:self.current+1]
        self._history.append(state)

        if len(self._history) > self.maxSize:
            self._history = self._history[len(self._history)-self.maxSize:len(self._history)]
        
        self.current = len(self._history) - 1

    def undo(self):
        if self.current >= 0:
            self._history[self.current].restore(self.volumeEditor)
            self.current -= 1

    def redo(self):
        if self.current < len(self._history) - 1:
            self._history[self.current + 1].restore(self.volumeEditor)
            self.current += 1
            
    def serialize(self, grp, name='_history'):
        histGrp = grp.create_group(name)
        for i, hist in enumerate(self._history):
            histItemGrp = histGrp.create_group('%04d'%i)
            histItemGrp.create_dataset('labels',data=hist.labels)
            histItemGrp.create_dataset('axis',data=hist.axis)
            histItemGrp.create_dataset('slice',data=hist.num)
            histItemGrp.create_dataset('labelNumber',data=hist.labelNumber)
            histItemGrp.create_dataset('offsets',data=hist.offsets)
            histItemGrp.create_dataset('time',data=hist.time)
            histItemGrp.create_dataset('erasing',data=hist.erasing)
            histItemGrp.create_dataset('clock',data=hist.clock)


    def removeLabel(self, number):
        tobedeleted = []
        for index, item in enumerate(self._history):
            if item.labelNumber != number:
                item.dataBefore = numpy.where(item.dataBefore == number, 0, item.dataBefore)
                item.dataBefore = numpy.where(item.dataBefore > number, item.dataBefore - 1, item.dataBefore)
                item.labels = numpy.where(item.labels == number, 0, item.labels)
                item.labels = numpy.where(item.labels > number, item.labels - 1, item.labels)
            else:
                #if item.erasing == False:
                    #item.restore(self.volumeEditor)
                tobedeleted.append(index - len(tobedeleted))
                if index <= self.current:
                    self.current -= 1

        for val in tobedeleted:
            it = self._history[val]
            self._history.__delitem__(val)
            del it
            
    def clear(self):
        self._history = []

#*******************************************************************************
# V o l u m e U p d a t e                                                      *
#*******************************************************************************

class VolumeUpdate():
    def __init__(self, data, offsets, sizes, erasing):
        self.offsets = offsets
        self._data = data
        self.sizes = sizes
        self.erasing = erasing
    
    def applyTo(self, dataAcc):
        offsets = self.offsets
        sizes = self.sizes
        #TODO: move part of function into DataAccessor class !! e.g. setSubVolume or somethign
        tempData = dataAcc[offsets[0]:offsets[0]+sizes[0],offsets[1]:offsets[1]+sizes[1],offsets[2]:offsets[2]+sizes[2],offsets[3]:offsets[3]+sizes[3],offsets[4]:offsets[4]+sizes[4]].copy()

        if self.erasing == True:
            tempData = numpy.where(self._data > 0, 0, tempData)
        else:
            tempData = numpy.where(self._data > 0, self._data, tempData)
        
        dataAcc[offsets[0]:offsets[0]+sizes[0],offsets[1]:offsets[1]+sizes[1],offsets[2]:offsets[2]+sizes[2],offsets[3]:offsets[3]+sizes[3],offsets[4]:offsets[4]+sizes[4]] = tempData  




#*******************************************************************************
# D u m m y L a b e l W i d g e t                                              *
#*******************************************************************************

class DummyLabelWidget(QtGui.QWidget):
    def __init__(self):
        QtGui.QWidget.__init__(self)
        self.setFixedSize(QtCore.QSize(0,0))
        self.volumeLabels = None
        
    def currentItem(self):
        return None

#*******************************************************************************
# D u m m y O v e r l a y L i s t W i d g e t                                  *
#*******************************************************************************

class DummyOverlayListWidget(QtGui.QWidget):
    def __init__(self,  parent):
        QtGui.QWidget.__init__(self)
        self.volumeEditor = parent
        self.overlays = []


#*******************************************************************************
# V o l u m e E d i t o r                                                      *
#*******************************************************************************

class VolumeEditor(QtGui.QWidget):
    changedSlice = pyqtSignal(int,int)
    
    @property
    def useOpenGL(self):
        return self.sharedOpenglWidget is not None
    
    """Array Editor Dialog"""
    def __init__(self, image, parent,  name="", font=None,
                 readonly=False, size=(400, 300), sharedOpenglWidget = None):
        QtGui.QWidget.__init__(self, parent)
        self.ilastik = parent
        self.name = name
        self.grid = None #in 3D mode hold the quad view widget, otherwise remains none
        title = name
        
        #Controls the trade-off of speed and flickering when scrolling through this slice view
        self.fastRepaint = True
        
        self.interactionLog = None
        
        self.labelsAlpha = 1.0

        #Bordermargin settings - they control the blue markers that signal the region from wich the
        #labels are not used for trainig
        self.useBorderMargin = False
        self.borderMargin = 0

        #this setting controls the rescaling of the displayed _data to the full 0-255 range
        self.normalizeData = False

        #this settings controls the timer interval during interactive mode
        #set to 0 to wait for complete brushstrokes !
        self.drawUpdateInterval = 300
        
        self.sharedOpenGLWidget = sharedOpenglWidget
        
        if self.sharedOpenGLWidget is not None:
            print "Enabling OpenGL rendering"
        else:
            print "Disabling OpenGL rendering"
        
        self.embedded = True


        QtGui.QPixmapCache.setCacheLimit(100000)


        if issubclass(image.__class__, DataAccessor):
            self.image = image
        elif issubclass(image.__class__, Volume):
            self.image = image._data
        else:
            self.image = DataAccessor(image)

        self.save_thread = ImageSaveThread(self)
              
        self.selectedTime = 0
        self.selectedChannel = 0

        self.pendingLabels = []

        #self.setAccessibleName(self.name)


        self._history = HistoryManager(self)

        self.drawManager = DrawManager(self)

        self.imageScenes = []
        self.imageScenes.append(ImageScene(self, (self.image.shape[2],  self.image.shape[3], self.image.shape[1]), 0 ,self.drawManager))
        
        if self.image.shape[1] != 1:
            self.overview = OverviewScene(self, self.image.shape[1:4])
            
            self.overview.changedSlice.connect(self.changeSlice)
            self.changedSlice.connect(self.overview.ChangeSlice)
            
            self.imageScenes.append(ImageScene(self, (self.image.shape[1],  self.image.shape[3], self.image.shape[2]), 1 ,self.drawManager))
            self.imageScenes.append(ImageScene(self, (self.image.shape[1],  self.image.shape[2], self.image.shape[3]), 2 ,self.drawManager))
            self.grid = QuadView(self)
            self.grid.addWidget(0, self.imageScenes[2])
            self.grid.addWidget(1, self.imageScenes[0])
            self.grid.addWidget(2, self.imageScenes[1])
            self.grid.addWidget(3, self.overview)
        else:
            self.overview = OverviewSceneDummy(self, self.image.shape[1:4])

        for scene in self.imageScenes:
            self.changedSlice.connect(scene.updateSliceIntersection)
            
        self.viewingLayout = QtGui.QVBoxLayout()
        self.viewingLayout.setContentsMargins(10,2,0,2)
        self.viewingLayout.setSpacing(0)
        
        labelLayout = QtGui.QHBoxLayout()
        labelLayout.setMargin(0)
        labelLayout.setSpacing(5)
        labelLayout.setContentsMargins(0,0,0,0)
        
        self.posLabel = QtGui.QLabel()
        self.pixelValuesLabel = QtGui.QLabel()
        labelLayout.addWidget(self.posLabel)
        labelLayout.addWidget(self.pixelValuesLabel)
        labelLayout.addStretch()
        #self.viewingLayout.addLayout(self.grid)
        if self.image.shape[1] != 1:
            self.viewingLayout.addWidget(self.grid)
            self.grid.setContentsMargins(0,0,10,0)
        else:
            self.viewingLayout.addWidget(self.imageScenes[0])
        self.viewingLayout.addLayout(labelLayout)

        #right side toolbox
        self.toolBox = QtGui.QWidget()
        self.toolBoxLayout = QtGui.QVBoxLayout()
        self.toolBoxLayout.setMargin(5)
        self.toolBox.setLayout(self.toolBoxLayout)
        #self.toolBox.setMaximumWidth(190)
        #self.toolBox.setMinimumWidth(190)

        self.labelWidget = None
        self.setLabelWidget(DummyLabelWidget())

        self.toolBoxLayout.addStretch()

        #Slice Selector Combo Box in right side toolbox
        self.sliceSelectors = []
        sliceSpin = QtGui.QSpinBox()
        sliceSpin.setEnabled(True)
        self.connect(sliceSpin, QtCore.SIGNAL("valueChanged(int)"), self.changeSliceX)
        if self.image.shape[1] > 1 and self.image.shape[2] > 1 and self.image.shape[3] > 1: #only show when needed
            tempLay = QtGui.QHBoxLayout()
            tempLay.addWidget(QtGui.QLabel("<pre>X:</pre>"))
            tempLay.addWidget(sliceSpin, 1)
            self.toolBoxLayout.addLayout(tempLay)
        sliceSpin.setRange(0,self.image.shape[1] - 1)
        self.sliceSelectors.append(sliceSpin)
        

        sliceSpin = QtGui.QSpinBox()
        sliceSpin.setEnabled(True)
        self.connect(sliceSpin, QtCore.SIGNAL("valueChanged(int)"), self.changeSliceY)
        if self.image.shape[1] > 1 and self.image.shape[3] > 1: #only show when needed
            tempLay = QtGui.QHBoxLayout()
            tempLay.addWidget(QtGui.QLabel("<pre>Y:</pre>"))
            tempLay.addWidget(sliceSpin, 1)
            self.toolBoxLayout.addLayout(tempLay)
        sliceSpin.setRange(0,self.image.shape[2] - 1)
        self.sliceSelectors.append(sliceSpin)

        sliceSpin = QtGui.QSpinBox()
        sliceSpin.setEnabled(True)
        self.connect(sliceSpin, QtCore.SIGNAL("valueChanged(int)"), self.changeSliceZ)
        if self.image.shape[1] > 1 and self.image.shape[2] > 1 : #only show when needed
            tempLay = QtGui.QHBoxLayout()
            tempLay.addWidget(QtGui.QLabel("<pre>Z:</pre>"))
            tempLay.addWidget(sliceSpin, 1)
            self.toolBoxLayout.addLayout(tempLay)
        sliceSpin.setRange(0,self.image.shape[3] - 1)
        self.sliceSelectors.append(sliceSpin)
        
        # Check box for slice intersection marks
        sliceIntersectionBox = QtGui.QCheckBox("Slice Intersection")
        sliceIntersectionBox.setEnabled(True)        
        self.toolBoxLayout.addWidget(sliceIntersectionBox)
        for scene in self.imageScenes:
            self.connect(sliceIntersectionBox, QtCore.SIGNAL("stateChanged(int)"), scene.setSliceIntersection)
        sliceIntersectionBox.setCheckState(QtCore.Qt.Checked)

        self.selSlices = []
        self.selSlices.append(0)
        self.selSlices.append(0)
        self.selSlices.append(0)
        
        #Channel Selector Combo Box in right side toolbox
        self.channelLayout = QtGui.QHBoxLayout()
        
        self.channelSpinLabel = QtGui.QLabel("Channel:")
        
        self.channelSpin = QtGui.QSpinBox()
        self.channelSpin.setEnabled(True)
        self.connect(self.channelSpin, QtCore.SIGNAL("valueChanged(int)"), self.setChannel)
        
        self.channelEditBtn = QtGui.QPushButton('Edit channels')
        self.connect(self.channelEditBtn, QtCore.SIGNAL("clicked()"), self.on_editChannels)
        
        
        self.toolBoxLayout.addWidget(self.channelSpinLabel)
        self.channelLayout.addWidget(self.channelSpin)
        self.channelLayout.addWidget(self.channelEditBtn)
        self.toolBoxLayout.addLayout(self.channelLayout)
        
        if self.image.shape[-1] == 1 or self.image.rgb is True: #only show when needed
            self.channelSpin.setVisible(False)
            self.channelSpinLabel.setVisible(False)
            self.channelEditBtn.setVisible(False)
        self.channelSpin.setRange(0,self.image.shape[-1] - 1)


        #Overlay selector
        self.overlayWidget = DummyOverlayListWidget(self)
        self.toolBoxLayout.addWidget( self.overlayWidget)


        self.toolBoxLayout.setAlignment( QtCore.Qt.AlignTop )

        # Make the dialog act as a window and stay on top
        if self.embedded == False:
            pass
            #self.setWindowFlags(self.flags() | QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        #self.setWindowIcon(get_icon('edit.png'))
        self.setWindowTitle(self.tr("Volume") + \
                            "%s" % (" - "+str(title) if str(title) else ""))

        #start viewing in the center of the volume
        self.changeSliceX(numpy.floor((self.image.shape[1] - 1) / 2))
        self.changeSliceY(numpy.floor((self.image.shape[2] - 1) / 2))
        self.changeSliceZ(numpy.floor((self.image.shape[3] - 1) / 2))

        ##undo/redo and other shortcuts
        self.shortcutUndo = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self, self.historyUndo, self.historyUndo) 
        shortcutManager.register(self.shortcutUndo, "Labeling", "History undo")
        
        
        self.shortcutRedo = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+Z"), self, self.historyRedo, self.historyRedo)
        shortcutManager.register(self.shortcutRedo, "Labeling", "History redo")
        
        self.shortcutRedo2 = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Y"), self, self.historyRedo, self.historyRedo)
        shortcutManager.register(self.shortcutRedo2, "Labeling", "History redo")
        
        self.togglePredictionSC = QtGui.QShortcut(QtGui.QKeySequence("Space"), self, self.togglePrediction, self.togglePrediction)
        shortcutManager.register(self.togglePredictionSC, "Overlays", "Invert overlay visibility")
        
        self.shortcutNextLabel = QtGui.QShortcut(QtGui.QKeySequence("l"), self, self.nextLabel, self.nextLabel)
        shortcutManager.register(self.shortcutNextLabel, "Labeling", "Go to next label (cyclic, forward)")
        
        self.shortcutPrevLabel = QtGui.QShortcut(QtGui.QKeySequence("k"), self, self.prevLabel, self.prevLabel )
        shortcutManager.register(self.shortcutPrevLabel, "Labeling", "Go to previous label (cyclic, backwards)")
        
        self.shortcutToggleFullscreenX = QtGui.QShortcut(QtGui.QKeySequence("x"), self, self.toggleFullscreenX, self.toggleFullscreenX )
        shortcutManager.register(self.shortcutToggleFullscreenX, "Navigation", "Enlarge slice view x to full size")
        
        self.shortcutToggleFullscreenY = QtGui.QShortcut(QtGui.QKeySequence("y"), self, self.toggleFullscreenY, self.toggleFullscreenY )
        shortcutManager.register(self.shortcutToggleFullscreenY, "Navigation", "Enlarge slice view y to full size")
        
        self.shortcutToggleFullscreenZ = QtGui.QShortcut(QtGui.QKeySequence("z"), self, self.toggleFullscreenZ, self.toggleFullscreenZ )
        shortcutManager.register(self.shortcutToggleFullscreenZ, "Navigation", "Enlarge slice view z to full size")

        self.shortcutNextChannel = QtGui.QShortcut(QtGui.QKeySequence("q"), self, self.nextChannel, self.nextChannel )
        shortcutManager.register(self.shortcutNextChannel, "Navigation", "Switch to next channel")

        self.shortcutPreviousChannel = QtGui.QShortcut(QtGui.QKeySequence("a"), self, self.previousChannel, self.previousChannel )
        shortcutManager.register(self.shortcutPreviousChannel, "Navigation", "Switch to previous channel")


        for index, scene in enumerate(self.imageScenes):
            scene.shortcutZoomIn = QtGui.QShortcut(QtGui.QKeySequence("+"), scene, scene.zoomIn, scene.zoomIn )
            scene.shortcutZoomIn.setContext(QtCore.Qt.WidgetShortcut)
            
            scene.shortcutZoomOut = QtGui.QShortcut(QtGui.QKeySequence("-"), scene, scene.zoomOut, scene.zoomOut )
            scene.shortcutZoomOut.setContext(QtCore.Qt.WidgetShortcut)
            
            scene.shortcutSliceUp = QtGui.QShortcut(QtGui.QKeySequence("p"), scene, scene.sliceUp, scene.sliceUp )
            scene.shortcutSliceUp.setContext(QtCore.Qt.WidgetShortcut)
            
            scene.shortcutSliceDown = QtGui.QShortcut(QtGui.QKeySequence("o"), scene, scene.sliceDown, scene.sliceDown )
            scene.shortcutSliceDown.setContext(QtCore.Qt.WidgetShortcut)

            scene.shortcutSliceUp2 = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Up"), scene, scene.sliceUp, scene.sliceUp )
            scene.shortcutSliceUp2.setContext(QtCore.Qt.WidgetShortcut)

            scene.shortcutSliceDown2 = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Down"), scene, scene.sliceDown, scene.sliceDown )
            scene.shortcutSliceDown2.setContext(QtCore.Qt.WidgetShortcut)


            scene.shortcutSliceUp10 = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+Up"), scene, scene.sliceUp10, scene.sliceUp10 )
            scene.shortcutSliceUp10.setContext(QtCore.Qt.WidgetShortcut)

            scene.shortcutSliceDown10 = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+Down"), scene, scene.sliceDown10, scene.sliceDown10 )
            scene.shortcutSliceDown10.setContext(QtCore.Qt.WidgetShortcut)

            scene.shortcutBrushSizeUp = QtGui.QShortcut(QtGui.QKeySequence("n"), scene, scene.brushSmaller)
            scene.shortcutBrushSizeUp.setContext(QtCore.Qt.WidgetShortcut)

            scene.shortcutBrushSizeDown = QtGui.QShortcut(QtGui.QKeySequence("m"), scene, scene.brushBigger)
            scene.shortcutBrushSizeDown.setContext(QtCore.Qt.WidgetShortcut)


        #add shortcuts of the imagescenes to the help text szstem
        shortcutManager.register(self.imageScenes[0].shortcutZoomIn, "Navigation", "Zoom in")
        shortcutManager.register(self.imageScenes[0].shortcutZoomOut, "Navigation", "Zoom out")
        shortcutManager.register(self.imageScenes[0].shortcutSliceUp, "Navigation", "Slice up")
        shortcutManager.register(self.imageScenes[0].shortcutSliceDown, "Navigation", "Slice down")
        shortcutManager.register(self.imageScenes[0].shortcutSliceUp2, "Navigation", "Slice up")
        shortcutManager.register(self.imageScenes[0].shortcutSliceDown2, "Navigation", "Slice down")
        shortcutManager.register(self.imageScenes[0].shortcutSliceUp10, "Navigation", "10 slices up")
        shortcutManager.register(self.imageScenes[0].shortcutSliceDown10, "Navigation", "10 slices down")
        shortcutManager.register(self.imageScenes[0].shortcutBrushSizeUp, "Labeling", "Increase brush size")
        shortcutManager.register(self.imageScenes[0].shortcutBrushSizeDown, "Labeling", "Decrease brush size")




        
        self.shortcutUndo.setContext(QtCore.Qt.ApplicationShortcut )
        self.shortcutRedo.setContext(QtCore.Qt.ApplicationShortcut )
        self.shortcutRedo2.setContext(QtCore.Qt.ApplicationShortcut )
        
        self.shortcutUndo.setEnabled(True)
        self.shortcutRedo.setEnabled(True)
        self.shortcutRedo2.setEnabled(True)
        self.togglePredictionSC.setEnabled(True)
        
        self.connect(self, QtCore.SIGNAL("destroyed()"), self.widgetDestroyed)
        
        self.focusAxis =  0

        self.splitter = QtGui.QSplitter()
        self.splitter.setContentsMargins(0,0,0,0)
        
        
        tempWidget = QtGui.QWidget()
        tempWidget.setLayout(self.viewingLayout)
        self.splitter.addWidget(tempWidget)
        
        self.splitter.addWidget(self.toolBox)
        splitterLayout = QtGui.QVBoxLayout()
        splitterLayout.setMargin(0)
        splitterLayout.setSpacing(0)
        splitterLayout.addWidget(self.splitter)
        self.setLayout(splitterLayout)
        
#         Tried to resolve ugly splitter handle problem fro windows
#         Still it does not look good
#        http://stackoverflow.com/questions/2545577/qsplitter-becoming-undistinguishable-between-qwidget-and-qtabwidget
#        sHandle = self.splitter.handle(1)
#        v = QtGui.QVBoxLayout(sHandle)
#        v.setSpacing(5)
#        v.setMargin(5)
#        
#        l = QtGui.QFrame(sHandle)
#        l.setFrameShape(QtGui.QFrame.VLine)
#        l.setFrameShadow(QtGui.QFrame.Sunken)
#        
#        v.addWidget(l)
#        
#        sHandle.setLayout(v)
        
        self.updateGeometry()
        self.update()
        if self.grid:
            self.grid.update()

    def toggleFullscreenX(self):
        self.maximizeSliceView(0)
    
    def toggleFullscreenY(self):
        self.maximizeSliceView(1)
        
    def toggleFullscreenZ(self):
        self.maximizeSliceView(2)
        
    def nextChannel(self):
        self.channelSpin.setValue(self.selectedChannel + 1)

    def previousChannel(self):
        self.channelSpin.setValue(self.selectedChannel - 1)

    def toggleFullscreen3D(self):
        v = [self.imageScenes[i].isVisible() for i in range(3)]
        
        if any(v):
            for i in range(3):
                self.imageScenes[i].setVisible(False)
        else:
            for i in range(3):
                self.imageScenes[i].setVisible(True)

    def maximizeSliceView(self, axis):
        if axis == 2:
            self.grid.toggleMaximized(0)
        if axis == 1:
            self.grid.toggleMaximized(2)
        if axis == 0:
            self.grid.toggleMaximized(1)
    
    def nextLabel(self):
        self.labelWidget.nextLabel()
        
    def prevLabel(self):
        self.labelWidget.nextLabel()

    def onLabelSelected(self):
        print "onLabelSelected() Warning: am i used anymore?"
#        if self.labelWidget.currentItem() is not None:
#            self.drawManager.setBrushColor(self.labelWidget.currentItem().color)
#            for i in range(3):
#                self.imageScenes[i].crossHairCursor.setColor(self.labelWidget.currentItem().color)

    def onOverlaySelected(self, index):
        if self.labelWidget.currentItem() is not None:
            pass

    def focusNextPrevChild(self, forward = True):
        if forward is True:
            self.focusAxis += 1
            if self.focusAxis > 2:
                self.focusAxis = 0
        else:
            self.focusAxis -= 1
            if self.focusAxis < 0:
                self.focusAxis = 2
                
        if len(self.imageScenes) > 2:
            self.imageScenes[self.focusAxis].setFocus()
        return True
        
    def widgetDestroyed(self):
        pass
    
    def cleanUp(self):
        QtGui.QApplication.processEvents()
        print "VolumeEditor: cleaning up "
        for index, s in enumerate( self.imageScenes ):
            s.cleanUp()
            s.close()
            s.deleteLater()
        self.imageScenes = []
        self.save_thread.stopped = True
        self.save_thread.imagePending.set()
        self.save_thread.wait()
        QtGui.QApplication.processEvents()
        print "finished saving thread"


    def on_editChannels(self):
        from ilastik.gui.channelEditDialog import EditChannelsDialog 
        
        dlg = EditChannelsDialog(self.ilastik.project.dataMgr.selectedChannels, self.ilastik.project.dataMgr[0]._dataVol._data.shape[-1], self)
        
        result = dlg.exec_()
        if result is not None:
            self.ilastik.project.dataMgr.selectedChannels = result

    def togglePrediction(self):
        for index,  item in enumerate(self.overlayWidget.overlays):
            item.visible = not(item.visible)
            s = None
            if item.visible:
                s = QtCore.Qt.Checked
            else:
                s = QtCore.Qt.Unchecked
            self.overlayWidget.overlayListWidget.item(index).setCheckState(s)
        self.repaint()
        

    def setLabelsAlpha(self, num):
        print "####################### function not used anymore"
        
    def getPendingLabels(self):
        temp = self.pendingLabels
        self.pendingLabels = []
        return temp

    def historyUndo(self):
        self._history.undo()

    def historyRedo(self):
        self._history.redo()

    def addOverlay(self, visible, data, name, color, alpha, colorTab = None):
        ov = VolumeOverlay(data,name, color, alpha, colorTab, visible)
        self.overlayWidget.addOverlay(ov)

    def addOverlayObject(self, ov):
        self.overlayWidget.addOverlay(ov)
        
    def repaint(self):
        for i in range(3):
            tempImage = None
            tempLabels = None
            tempoverlays = []   
            for index, item in enumerate(reversed(self.overlayWidget.overlays)):
                if item.visible:
                    tempoverlays.append(item.getOverlaySlice(self.selSlices[i],i, self.selectedTime, item.channel)) 
            if len(self.overlayWidget.overlays) > 0:
                tempImage = self.overlayWidget.getOverlayRef("Raw Data")._data.getSlice(self.selSlices[i], i, self.selectedTime, self.overlayWidget.getOverlayRef("Raw Data").channel)
            else:
                tempImage = None
#            if self.labelWidget.volumeLabels is not None:
#                if self.labelWidget.volumeLabels.data is not None:
#                    tempLabels = self.labelWidget.volumeLabels.data.getSlice(self.selSlices[i],i, self.selectedTime, 0)
            if len(self.imageScenes) > i:
                self.imageScenes[i].displayNewSlice(tempImage, tempoverlays, fastPreview = False)

    def on_saveAsImage(self):
        sliceOffsetCheck = False
        if self.image.shape[1]>1:
            #stack z-view is stored in imageScenes[2], for no apparent reason
            sliceOffsetCheck = True
        timeOffsetCheck = self.image.shape[0]>1
        formatList = QtGui.QImageWriter.supportedImageFormats()
        formatList = [x for x in formatList if x in ['png', 'tif']]
        expdlg = exportDialog.ExportDialog(formatList, timeOffsetCheck, sliceOffsetCheck, None, parent=self.ilastik)
        expdlg.exec_()
        try:
            tempname = str(expdlg.path.text()) + "/" + str(expdlg.prefix.text())
            filename = str(QtCore.QDir.convertSeparators(tempname))
            self.save_thread.start()
            stuff = (filename, expdlg.timeOffset, expdlg.sliceOffset, expdlg.format)
            self.save_thread.queue.append(stuff)
            self.save_thread.imagePending.set()
            
        except:
            pass
        
    def setLabelWidget(self,  widget):
        """
        Public interface function for setting the labelWidget toolBox
        """
        if self.labelWidget is not None:
            self.toolBoxLayout.removeWidget(self.labelWidget)
            self.labelWidget.close()
            del self.labelWidget
        self.labelWidget = widget
        self.connect(self.labelWidget, QtCore.SIGNAL("itemSelectionChanged()"), self.onLabelSelected)
        self.toolBoxLayout.insertWidget( 0, self.labelWidget)
        if isinstance(widget, DummyLabelWidget):
            oldMargins = list(self.toolBoxLayout.getContentsMargins())
            oldMargins[1] = 0
            self.toolBoxLayout.setContentsMargins(oldMargins[0],oldMargins[1],oldMargins[2],oldMargins[3])
    
    def setOverlayWidget(self,  widget):
        """
        Public interface function for setting the overlayWidget toolBox
        """
        if self.overlayWidget is not None:
            self.toolBoxLayout.removeWidget(self.overlayWidget)
            self.overlayWidget.close()
            del self.overlayWidget
        self.overlayWidget = widget
        self.connect(self.overlayWidget , QtCore.SIGNAL("selectedOverlay(int)"), self.onOverlaySelected)
        self.toolBoxLayout.insertWidget( 1, self.overlayWidget)        
        self.ilastik.project.dataMgr[self.ilastik._activeImageNumber].overlayMgr.ilastik = self.ilastik


    def get_copy(self):
        """Return modified text"""
        return unicode(self.edit.toPlainText())

    def setRgbMode(self, mode):
        """
        change display mode of 3-channel images to either rgb, or 3-channels
        mode can bei either  True or False
        """
        if self.image.shape[-1] == 3:
            self.image.rgb = mode
            self.channelSpin.setVisible(not mode)
            self.channelSpinLabel.setVisible(not mode)

    def setUseBorderMargin(self, use):
        self.useBorderMargin = use
        self.setBorderMargin(self.borderMargin)

    def setFastRepaint(self, fastRepaint):
        self.fastRepaint = fastRepaint

    def setBorderMargin(self, margin):
        #print "******** setBorderMargin", margin
        if margin != self.borderMargin:
            for imgScene in self.imageScenes:
                imgScene.__borderMarginIndicator__(margin)
            
        self.borderMargin = margin
        
        for imgScene in self.imageScenes:
            if imgScene.border is not None:
                imgScene.border.setVisible(self.useBorderMargin)
            
        self.repaint()


    def changeSliceX(self, num):
        self.changeSlice(num, 0)

    def changeSliceY(self, num):
        self.changeSlice(num, 1)

    def changeSliceZ(self, num):
        self.changeSlice(num, 2)

    def setChannel(self, channel):
        if len(self.overlayWidget.overlays) > 0:
            ov = self.overlayWidget.getOverlayRef("Raw Data")
            if ov.shape[-1] == self.image.shape[-1]:
                self.overlayWidget.getOverlayRef("Raw Data").channel = channel
            
        self.selectedChannel = channel
        for i in range(3):
            self.changeSlice(self.selSlices[i], i)

    def setTime(self, time):
        self.selectedTime = time
        for i in range(3):
            self.changeSlice(self.selSlices[i], i)

    def updateTimeSliceForSaving(self, time, num, axis):
        self.imageScenes[axis].thread.freeQueue.clear()
        if self.sliceSelectors[axis].value() != num:
            #this will emit the signal and change the slice
            self.sliceSelectors[axis].setValue(num)
        elif self.selectedTime!=time:
            #if only the time is changed, we don't want to update all 3 slices
            self.selectedTime = time
            self.changeSlice(num, axis)
        else:
            #no need to update, just save the current image
            self.imageScenes[axis].thread.freeQueue.set()

    def changeSlice(self, num, axis):

        if self.interactionLog is not None:
            self.interactionLog.append("%f: changeSlice(axis,number) %d,%d" % (time.clock(),axis,num))
        self.selSlices[axis] = num
        tempImage = None
        tempLabels = None
        tempoverlays = []
        #This bloody call is recursive, be careful!
        self.sliceSelectors[axis].setValue(num)

        for index, item in enumerate(reversed(self.overlayWidget.overlays)):
            if item.visible:
                tempoverlays.append(item.getOverlaySlice(num,axis, self.selectedTime, item.channel)) 
        
        if len(self.overlayWidget.overlays) > 0:
            tempImage = self.overlayWidget.getOverlayRef("Raw Data")._data.getSlice(num, axis, self.selectedTime, self.selectedChannel)
        else:
            tempImage = None            

        self.selSlices[axis] = num
        if len(self.imageScenes) > axis:
            self.imageScenes[axis].sliceNumber = num
            self.imageScenes[axis].displayNewSlice(tempImage, tempoverlays)
        
        #print "VolumeEditor.changedSlice(%s, %d)" % (num, axis)
        self.changedSlice.emit(num, axis)

    def closeEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        keys = QtGui.QApplication.keyboardModifiers()
        k_ctrl = (keys == QtCore.Qt.ControlModifier)
        
        if k_ctrl is True:        
            if event.delta() > 0:
                scaleFactor = 1.1
            else:
                scaleFactor = 0.9
            self.imageScenes[0].doScale(scaleFactor)
            self.imageScenes[1].doScale(scaleFactor)
            self.imageScenes[2].doScale(scaleFactor)

    def setLabels(self, offsets, axis, num, labels, erase):
        """
        offsets: labels is a 2D matrix in the image plane perpendicular to axis, which is offset from the origin
                 of the slice by the 2D offsets verctor
        axis:    the axis (x=0, y=1 or z=2 which is perpendicular to the image plane
        num:     position of the image plane perpendicular to axis on which the 'labels' were drawn
        labels   2D matrix of new labels
        erase    boolean whether we are erasing or not. This changes how we interprete the update defined through
                 'labels'
        """
        
        if axis == 0:
            offsets5 = (self.selectedTime,num,offsets[0],offsets[1],0)
            sizes5 = (1,1,labels.shape[0], labels.shape[1],1)
        elif axis == 1:
            offsets5 = (self.selectedTime,offsets[0],num,offsets[1],0)
            sizes5 = (1,labels.shape[0],1, labels.shape[1],1)
        else:
            offsets5 = (self.selectedTime,offsets[0],offsets[1],num,0)
            sizes5 = (1,labels.shape[0], labels.shape[1],1,1)
        
        vu = VolumeUpdate(labels.reshape(sizes5),offsets5, sizes5, erase)
        vu.applyTo(self.labelWidget.overlayItem)
        self.pendingLabels.append(vu)

        patches = self.imageScenes[axis].patchAccessor.getPatchesForRect(offsets[0], offsets[1],offsets[0]+labels.shape[0], offsets[1]+labels.shape[1])

        tempImage = None
        tempLabels = None
        tempoverlays = []
        for index, item in enumerate(reversed(self.overlayWidget.overlays)):
            if item.visible:
                tempoverlays.append(item.getOverlaySlice(self.selSlices[axis],axis, self.selectedTime, 0))

        if len(self.overlayWidget.overlays) > 0:
            tempImage = self.overlayWidget.getOverlayRef("Raw Data")._data.getSlice(num, axis, self.selectedTime, self.selectedChannel)
        else:
            tempImage = None            

        self.imageScenes[axis].updatePatches(patches, tempImage, tempoverlays)

        self.emit(QtCore.SIGNAL('newLabelsPending()'))
            
    def pushLabelsToLabelWidget(self):
        newLabels = self.getPendingLabels()
        self.labelWidget.labelMgr.newLabels(newLabels)
            
            
    def getVisibleState(self):
        #TODO: ugly, make nicer
        vs = [self.selectedTime, self.selSlices[0], self.selSlices[1], self.selSlices[2], self.selectedChannel]
        return vs



    def show(self):
        QtGui.QWidget.show(self)



#*******************************************************************************
# D r a w M a n a g e r                                                        *
#*******************************************************************************

class DrawManager(QtCore.QObject):
    def __init__(self, parent):
        QtCore.QObject.__init__(self)
        self.volumeEditor = parent
        self.shape = None
        self.brushSize = 3
        #self.initBoundingBox()
        self.penVis = QtGui.QPen(QtCore.Qt.white, 3, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        self.penDraw = QtGui.QPen(QtCore.Qt.white, 3, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        self.penDraw.setColor(QtCore.Qt.white)
        self.pos = None
        self.erasing = False
        self.lines = []
        self.scene = QtGui.QGraphicsScene()

    def copy(self):
        """
        make a shallow copy of DrawManager - needed for python 2.5 compatibility
        """
        cp = DrawManager(self.parent)
        cp.volumeEditor = self.volumeEditor
        cp.shape = self.shape
        cp.brushSize = self.brushSize
        cp.penVis = self.penVis
        cp.penDraw = self.penDraw
        cp.pos = self.pos
        cp.erasing = self.erasing
        cp.lines = self.lines
        cp.scene = self.scene
        return cp

    def initBoundingBox(self):
        self.leftMost = self.shape[0]
        self.rightMost = 0
        self.topMost = self.shape[1]
        self.bottomMost = 0

    def growBoundingBox(self):
        self.leftMost = max(0,self.leftMost - self.brushSize -1)
        self.topMost = max(0,self.topMost - self.brushSize -1 )
        self.rightMost = min(self.shape[0],self.rightMost + self.brushSize + 1)
        self.bottomMost = min(self.shape[1],self.bottomMost + self.brushSize + 1)

    def toggleErase(self):
        self.erasing = not(self.erasing)
        self.updateCrossHair()

    def setErasing(self):
        self.erasing = True
        self.updateCrossHair()
    
    def disableErasing(self):
        self.erasing = False
        self.updateCrossHair()

    def updateCrossHair(self):
        if self.erasing == True:
            color = QtGui.QColor("black") 
        else:
            color = self.volumeEditor.labelWidget.currentItem().color
        
        for i in self.volumeEditor.imageScenes:
            i.crossHairCursor.setColor(color)

    def setBrushSize(self, size):
        for i in self.volumeEditor.imageScenes:
            i.crossHairCursor.setBrushSize(size)
        
        self.brushSize = size
        self.penVis.setWidth(size)
        self.penDraw.setWidth(size)
        
    def getBrushSize(self):
        return self.brushSize
        
    def setBrushColor(self, color):
        self.penVis.setColor(color)
        
    def getCurrentPenPixmap(self):
        pixmap = QtGui.QPixmap(self.brushSize, self.brushSize)
        if self.erasing == True or not self.volumeEditor.labelWidget.currentItem():
            self.penVis.setColor(QtCore.Qt.black)
        else:
            self.penVis.setColor(self.volumeEditor.labelWidget.currentItem().color)
                    
        painter = QtGui.QPainter(pixmap)
        painter.setPen(self.penVis)
        painter.drawPoint(QtGui.Q)

    def beginDraw(self, pos, shape):
        self.shape = shape
        self.initBoundingBox()
        self.scene.clear()
        if self.erasing == True or not self.volumeEditor.labelWidget.currentItem():
            self.penVis.setColor(QtCore.Qt.black)
        else:
            self.penVis.setColor(self.volumeEditor.labelWidget.currentItem().color)
        self.pos = QtCore.QPointF(pos.x()+0.0001, pos.y()+0.0001)
        
        line = self.moveTo(pos)
        return line

    def endDraw(self, pos):
        self.moveTo(pos)
        self.growBoundingBox()

        tempi = QtGui.QImage(self.rightMost - self.leftMost, self.bottomMost - self.topMost, QtGui.QImage.Format_ARGB32_Premultiplied) #TODO: format
        tempi.fill(0)
        painter = QtGui.QPainter(tempi)
        
        self.scene.render(painter, QtCore.QRectF(0,0, self.rightMost - self.leftMost, self.bottomMost - self.topMost),
            QtCore.QRectF(self.leftMost, self.topMost, self.rightMost - self.leftMost, self.bottomMost - self.topMost))
        
        oldLeft = self.leftMost
        oldTop = self.topMost
        return (oldLeft, oldTop, tempi) #TODO: hackish, probably return a class ??

    def dumpDraw(self, pos):
        res = self.endDraw(pos)
        self.beginDraw(pos, self.shape)
        return res


    def moveTo(self, pos):    
        lineVis = QtGui.QGraphicsLineItem(self.pos.x(), self.pos.y(),pos.x(), pos.y())
        lineVis.setPen(self.penVis)
        
        line = QtGui.QGraphicsLineItem(self.pos.x(), self.pos.y(),pos.x(), pos.y())
        line.setPen(self.penDraw)
        self.scene.addItem(line)

        self.pos = pos
        x = pos.x()
        y = pos.y()
        #update bounding Box :
        if x > self.rightMost:
            self.rightMost = x
        if x < self.leftMost:
            self.leftMost = x
        if y > self.bottomMost:
            self.bottomMost = y
        if y < self.topMost:
            self.topMost = y
        return lineVis

#*******************************************************************************
# I m a g e S a v e T h r e a d                                                *
#*******************************************************************************

class ImageSaveThread(QtCore.QThread):
    def __init__(self, parent):
        QtCore.QThread.__init__(self, None)
        self.ve = parent
        self.queue = deque()
        self.imageSaved = threading.Event()
        self.imageSaved.clear()
        self.imagePending = threading.Event()
        self.imagePending.clear()
        self.stopped = False
        self.previousSlice = None
        
    def run(self):
        while not self.stopped:
            self.imagePending.wait()
            while len(self.queue)>0:
                stuff = self.queue.pop()
                if stuff is not None:
                    filename, timeOffset, sliceOffset, format = stuff
                    if self.ve.image.shape[1]>1:
                        axis = 2
                        self.previousSlice = self.ve.sliceSelectors[axis].value()
                        for t in range(self.ve.image.shape[0]):
                            for z in range(self.ve.image.shape[3]):                   
                                self.filename = filename
                                if (self.ve.image.shape[0]>1):
                                    self.filename = self.filename + ("_time%03i" %(t+timeOffset))
                                self.filename = self.filename + ("_z%05i" %(z+sliceOffset))
                                self.filename = self.filename + "." + format
                        
                                #only change the z slice display
                                self.ve.imageScenes[axis].thread.queue.clear()
                                self.ve.imageScenes[axis].thread.freeQueue.wait()
                                self.ve.updateTimeSliceForSaving(t, z, axis)
                                
                                
                                self.ve.imageScenes[axis].thread.freeQueue.wait()
        
                                self.ve.imageScenes[axis].saveSlice(self.filename)
                    else:
                        axis = 0
                        for t in range(self.ve.image.shape[0]):                 
                            self.filename = filename
                            if (self.ve.image.shape[0]>1):
                                self.filename = self.filename + ("_time%03i" %(t+timeOffset))
                            self.filename = self.filename + "." + format
                            self.ve.imageScenes[axis].thread.queue.clear()
                            self.ve.imageScenes[axis].thread.freeQueue.wait()
                            self.ve.updateTimeSliceForSaving(t, self.ve.selSlices[0], axis)                              
                            self.ve.imageScenes[axis].thread.freeQueue.wait()
                            self.ve.imageScenes[axis].saveSlice(self.filename)
            self.imageSaved.set()
            self.imagePending.clear()
            if self.previousSlice is not None:
                self.ve.sliceSelectors[axis].setValue(self.previousSlice)
                self.previousSlice = None
            

#*******************************************************************************
# I m a g e S c e n e R e n d e r T h r e a d                                  *
#*******************************************************************************

class ImageSceneRenderThread(QtCore.QThread):
    def __init__(self, parent):
        QtCore.QThread.__init__(self, None)
        self.imageScene = parent
        self.patchAccessor = parent.patchAccessor
        self.volumeEditor = parent.volumeEditor
        #self.queue = deque(maxlen=1) #python 2.6
        self.queue = deque() #python 2.5
        self.outQueue = deque()
        self.dataPending = threading.Event()
        self.dataPending.clear()
        self.newerDataPending = threading.Event()
        self.newerDataPending.clear()
        self.freeQueue = threading.Event()
        self.freeQueue.clear()
        self.stopped = False
        #if self.imageScene.openglWidget is not None:
        #    self.contextPixmap = QtGui.QPixmap(2,2)
        #    self.context = QtOpenGL.QGLContext(self.imageScene.openglWidget.context().format(), self.contextPixmap)
        #    self.context.create(self.imageScene.openglWidget.context())
        #else:
        #    self.context = None
    
    def run(self):
        #self.context.makeCurrent()

        while not self.stopped:
            self.emit(QtCore.SIGNAL('finishedQueue()'))
            self.dataPending.wait()
            self.newerDataPending.clear()
            self.freeQueue.clear()
            while len(self.queue) > 0:
                stuff = self.queue.pop()
                if stuff is not None:
                    nums, origimage, overlays , min, max  = stuff
                    for patchNr in nums:
                        if self.newerDataPending.isSet():
                            self.newerDataPending.clear()
                            break
                        bounds = self.patchAccessor.getPatchBounds(patchNr)

                        if self.imageScene.openglWidget is None:
                            p = QtGui.QPainter(self.imageScene.scene.image)
                            p.translate(bounds[0],bounds[2])
                        else:
                            p = QtGui.QPainter(self.imageScene.imagePatches[patchNr])
                        
                        p.eraseRect(0,0,bounds[1]-bounds[0],bounds[3]-bounds[2])

                        #add overlays
                        for index, origitem in enumerate(overlays):
                            p.setOpacity(origitem.alpha)
                            itemcolorTable = origitem.colorTable
                            
                            
                            itemdata = origitem._data[bounds[0]:bounds[1],bounds[2]:bounds[3]]
                            
                            origitemColor = None
                            if isinstance(origitem.color,  long) or isinstance(origitem.color,  int):
                                origitemColor = QtGui.QColor.fromRgba(long(origitem.color))
                            else:
                                origitemColor = origitem.color
                                 
                            # if itemdata is uint16
                            # convert it for displayporpuse
                            if itemcolorTable is None and itemdata.dtype == numpy.uint16:
                                print '*** Normalizing your data for display purpose'
                                print '*** I assume you have 12bit data'
                                itemdata = (itemdata*255.0/4095.0).astype(numpy.uint8)
                            
                            if itemcolorTable != None:         
                                if itemdata.dtype != 'uint8':
                                    """
                                    if the item is larger we take the values module 256
                                    since QImage supports only 8Bit Indexed images
                                    """
                                    olditemdata = itemdata              
                                    itemdata = numpy.ndarray(olditemdata.shape, 'float32')
                                    #print "moduo", olditemdata.shape, olditemdata.dtype
                                    if olditemdata.dtype == 'uint32':
                                        itemdata[:] = numpy.right_shift(numpy.left_shift(olditemdata,24),24)[:]
                                    elif olditemdata.dtype == 'uint64':
                                        itemdata[:] = numpy.right_shift(numpy.left_shift(olditemdata,56),56)[:]
                                    elif olditemdata.dtype == 'int32':
                                        itemdata[:] = numpy.right_shift(numpy.left_shift(olditemdata,24),24)[:]
                                    elif olditemdata.dtype == 'int64':
                                        itemdata[:] = numpy.right_shift(numpy.left_shift(olditemdata,56),56)[:]
                                    elif olditemdata.dtype == 'uint16':
                                        itemdata[:] = numpy.right_shift(numpy.left_shift(olditemdata,8),8)[:]
                                    else:
                                        #raise TypeError(str(olditemdata.dtype) + ' <- unsupported image _data type (in the rendering thread, you know) ')
                                        # TODO: Workaround: tried to fix the problem
                                        # with the segmentation display, somehow it arrieves
                                        # here in float32
                                        print TypeError(str(olditemdata.dtype) + ': unsupported dtype of overlay in ImageSceneRenderThread.run()')
                                        continue
                                   
                                if len(itemdata.shape) > 2 and itemdata.shape[2] > 1:
                                    image0 = qimage2ndarray.array2qimage(itemdata.swapaxes(0,1), normalize=False)
                                else:
                                    image0 = qimage2ndarray.gray2qimage(itemdata.swapaxes(0,1), normalize=False)
                                    image0.setColorTable(itemcolorTable[:])
                                
                            else:
                                if origitem.min is not None and origitem.max is not None:
                                    normalize = (origitem.min, origitem.max)
                                else:
                                    normalize = False
                                
                                                                
                                if origitem.autoAlphaChannel is False:
                                    if len(itemdata.shape) == 3 and itemdata.shape[2] == 3:
                                        image1 = qimage2ndarray.array2qimage(itemdata.swapaxes(0,1), normalize)
                                        image0 = image1
                                    else:
                                        tempdat = numpy.zeros(itemdata.shape[0:2] + (3,), 'float32')
                                        tempdat[:,:,0] = origitemColor.redF()*itemdata[:]
                                        tempdat[:,:,1] = origitemColor.greenF()*itemdata[:]
                                        tempdat[:,:,2] = origitemColor.blueF()*itemdata[:]
                                        image1 = qimage2ndarray.array2qimage(tempdat.swapaxes(0,1), normalize)
                                        image0 = image1
                                else:
                                    image1 = qimage2ndarray.array2qimage(itemdata.swapaxes(0,1), normalize)
                                    image0 = QtGui.QImage(itemdata.shape[0],itemdata.shape[1],QtGui.QImage.Format_ARGB32)#qimage2ndarray.array2qimage(itemdata.swapaxes(0,1), normalize=False)
                                    image0.fill(origitemColor.rgba())
                                    image0.setAlphaChannel(image1)
                            p.drawImage(0,0, image0)

                        p.end()
                        self.outQueue.append(patchNr)
                        
#                        if self.imageScene.scene.tex > -1:
#                            self.context.makeCurrent()    
#                            glBindTexture(GL_TEXTURE_2D,self.imageScene.scene.tex)
#                            b = self.imageScene.patchAccessor.getPatchBounds(patchNr,0)
#                            glTexSubImage2D(GL_TEXTURE_2D, 0, b[0], b[2], b[1]-b[0], b[3]-b[2], GL_RGB, GL_UNSIGNED_BYTE, ctypes.c_void_p(self.imageScene.imagePatches[patchNr].bits().__int__()))
#                            
#                        self.outQueue.clear()
                                       

            self.dataPending.clear()


#*******************************************************************************
# C r o s s H a i r C u r s o r                                                *
#*******************************************************************************

class CrossHairCursor(QtGui.QGraphicsItem) :
    modeYPosition  = 0
    modeXPosition  = 1
    modeXYPosition = 2
    
    def boundingRect(self):
        return QtCore.QRectF(0,0, self.width, self.height)
    def __init__(self, width, height):
        QtGui.QGraphicsItem.__init__(self)
        
        self.width = width
        self.height = height
        
        self.penDotted = QtGui.QPen(QtCore.Qt.red, 2, QtCore.Qt.DotLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        self.penDotted.setCosmetic(True)
        
        self.penSolid = QtGui.QPen(QtCore.Qt.red, 2)
        self.penSolid.setCosmetic(True)
        
        self.x = 0
        self.y = 0
        self.brushSize = 0
        
        self.mode = self.modeXYPosition
    
    def setColor(self, color):
        self.penDotted = QtGui.QPen(color, 2, QtCore.Qt.DotLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        self.penDotted.setCosmetic(True)
        self.penSolid  = QtGui.QPen(color, 2)
        self.penSolid.setCosmetic(True)
        self.update()
    
    def showXPosition(self, x, y):
        """only mark the x position by displaying a line f(y) = x"""
        self.setVisible(True)
        self.mode = self.modeXPosition
        self.setPos(x, y - int(y))
        
    def showYPosition(self, y, x):
        """only mark the y position by displaying a line f(x) = y"""
        self.setVisible(True)
        self.mode = self.modeYPosition
        self.setPos(x - int(x), y)
        
    def showXYPosition(self, x,y):
        """mark the (x,y) position by displaying a cross hair cursor
           including a circle indicating the current brush size"""
        self.setVisible(True)
        self.mode = self.modeXYPosition
        self.setPos(x,y)
    
    def paint(self, painter, option, widget=None):
        painter.setPen(self.penDotted)
        
        if self.mode == self.modeXPosition:
            painter.drawLine(QtCore.QPointF(self.x+0.5, 0), QtCore.QPointF(self.x+0.5, self.height))
        elif self.mode == self.modeYPosition:
            painter.drawLine(QtCore.QPointF(0, self.y), QtCore.QPointF(self.width, self.y))
        else:            
            painter.drawLine(QtCore.QPointF(0.0,self.y), QtCore.QPointF(self.x -0.5*self.brushSize, self.y))
            painter.drawLine(QtCore.QPointF(self.x+0.5*self.brushSize, self.y), QtCore.QPointF(self.width, self.y))

            painter.drawLine(QtCore.QPointF(self.x, 0), QtCore.QPointF(self.x, self.y-0.5*self.brushSize))
            painter.drawLine(QtCore.QPointF(self.x, self.y+0.5*self.brushSize), QtCore.QPointF(self.x, self.height))

            painter.setPen(self.penSolid)
            painter.drawEllipse(QtCore.QPointF(self.x, self.y), 0.5*self.brushSize, 0.5*self.brushSize)
        
    def setPos(self, x, y):
        self.x = x
        self.y = y
        self.update()
        
    def setBrushSize(self, size):
        self.brushSize = size
        self.update()

#*******************************************************************************
# S l i c e I n t e r s e c t i o n M a r k e r                                *
#*******************************************************************************

class SliceIntersectionMarker(QtGui.QGraphicsItem) :
    
    def boundingRect(self):
        return QtCore.QRectF(0,0, self.width, self.height)
    
    def __init__(self, width, height):
        QtGui.QGraphicsItem.__init__(self)
        
        self.width = width
        self.height = height
              
        self.penX = QtGui.QPen(QtCore.Qt.red, 2)
        self.penX.setCosmetic(True)
        
        self.penY = QtGui.QPen(QtCore.Qt.green, 2)
        self.penY.setCosmetic(True)
        
        self.x = 0
        self.y = 0
        
        self.isVisible = False

    def setPosition(self, x, y):
        self.x = x
        self.y = y
        self.update()
        
    def setPositionX(self, x):
        self.setPosition(x, self.y)
        
    def setPositionY(self, y):
        self.setPosition(self.x, y)  
   
    def setColor(self, colorX, colorY):
        self.penX = QtGui.QPen(colorX, 2)
        self.penX.setCosmetic(True)
        self.penY = QtGui.QPen(colorY, 2)
        self.penY.setCosmetic(True)
        self.update()
        
    def setVisibility(self, state):
        if state == True:
            self.isVisible = True
        else:
            self.isVisible = False
        self.update()
    
    def paint(self, painter, option, widget=None):
        if self.isVisible:
            painter.setPen(self.penY)
            painter.drawLine(QtCore.QPointF(0.0,self.y), QtCore.QPointF(self.width, self.y))
            
            painter.setPen(self.penX)
            painter.drawLine(QtCore.QPointF(self.x, 0), QtCore.QPointF(self.x, self.height))
        
    def setPos(self, x, y):
        self.x = x
        self.y = y
        self.update()
        
#*******************************************************************************
# I m a g e G r a p h i c s I t e m                                            *
#*******************************************************************************

class ImageGraphicsItem(QtGui.QGraphicsItem):
    def __init__(self, image):
        QtGui.QGraphicsItem.__init__(self)
        self.image = image

    def paint(self,painter, options, widget):
        painter.setClipRect( options.exposedRect )
        painter.drawImage(0,0,self.image)

    def boundingRect(self):
        return QtCore.QRectF(self.image.rect())


#*******************************************************************************
# C u s t o m G r a p h i c s S c e n e                                        *
#*******************************************************************************

class CustomGraphicsScene( QtGui.QGraphicsScene):#, QtOpenGL.QGLWidget):
    def __init__(self,parent,widget,image):
        QtGui.QGraphicsScene.__init__(self)
        #QtOpenGL.QGLWidget.__init__(self)
        self._widget = widget
        self.imageScene = parent
        self.image = image
        self.images = []
        self.bgColor = QtGui.QColor(QtCore.Qt.black)
        self.tex = -1

            
    def drawBackground(self, painter, rect):
        #painter.fillRect(rect,self.bgBrush)
        if self._widget != None:

            self._widget.context().makeCurrent()
            
            glClearColor(self.bgColor.redF(),self.bgColor.greenF(),self.bgColor.blueF(),1.0)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            if self.tex > -1:
                #self._widget.drawTexture(QtCore.QRectF(self.image.rect()),self.tex)
                d = painter.device()
                dc = sip.cast(d,QtOpenGL.QGLFramebufferObject)

                rect = QtCore.QRectF(self.image.rect())
                tl = rect.topLeft()
                br = rect.bottomRight()
                
                #flip coordinates since the texture is flipped
                #this is due to qimage having another representation thatn OpenGL
                rect.setCoords(tl.x(),br.y(),br.x(),tl.y())
                
                #switch corrdinates if qt version is small
                painter.beginNativePainting()
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
                dc.drawTexture(rect,self.tex)
                painter.endNativePainting()

        else:
            painter.setClipRect(rect)
            painter.drawImage(0,0,self.image)
        



#*******************************************************************************
# I m a g e S c e n e                                                          *
#*******************************************************************************
#TODO: ImageScene should not care/know about what axis it is!
class ImageScene(QtGui.QGraphicsView):
    #axisColor = [QtGui.QColor("red"), QtGui.QColor("green"), QtGui.QColor("blue")]
    axisColor = [QtGui.QColor(255,0,0,255), QtGui.QColor(0,255,0,255), QtGui.QColor(0,0,255,255)]
    
    def __borderMarginIndicator__(self, margin):
        print "__borderMarginIndicator__()", margin
        """
        update the border margin indicator (left, right, top, bottom)
        to reflect the new given margin
        """
        self.margin = margin
        if self.border:
            self.scene.removeItem(self.border)
        borderPath = QtGui.QPainterPath()
        borderPath.setFillRule(QtCore.Qt.WindingFill)
        borderPath.addRect(0,0, margin, self.imShape[1])
        borderPath.addRect(0,0, self.imShape[0], margin)
        borderPath.addRect(self.imShape[0]-margin,0, margin, self.imShape[1])
        borderPath.addRect(0,self.imShape[1]-margin, self.imShape[0], margin)
        self.border = QtGui.QGraphicsPathItem(borderPath)
        brush = QtGui.QBrush(QtGui.QColor(0,0,255))
        brush.setStyle( QtCore.Qt.Dense7Pattern )
        self.border.setBrush(brush)
        self.border.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        self.border.setZValue(200)
        self.scene.addItem(self.border)
        
    def __init__(self, parent, imShape, axis, drawManager):
        """
        imShape: 3D shape of the block that this slice view displays.
                 first two entries denote the x,y extent of one slice,
                 the last entry is the extent in slice direction
        """
        QtGui.QGraphicsView.__init__(self)
        self.imShape = imShape[0:2]
        self.drawManager = drawManager
        self.tempImageItems = []
        self.volumeEditor = parent
        self.axis = axis
        self.sliceNumber = 0
        self.sliceExtent = imShape[2]
        self.drawing = False
        self.view = self
        self.image = QtGui.QImage(imShape[0], imShape[1], QtGui.QImage.Format_RGB888) #Format_ARGB32
        self.border = None
        self.allBorder = None
        self.factor = 1.0
        
        #for panning
        self.lastPanPoint = QtCore.QPoint()
        self.dragMode = False
        self.deltaPan = QtCore.QPointF(0,0)
        self.x = 0.0
        self.y = 0.0
        
        self.min = 0
        self.max = 255
        
        self.openglWidget = None
        ##enable OpenGL acceleratino
        if self.volumeEditor.sharedOpenGLWidget is not None:
            self.openglWidget = QtOpenGL.QGLWidget(shareWidget = self.volumeEditor.sharedOpenGLWidget)
            self.setViewport(self.openglWidget)
            self.setViewportUpdateMode(QtGui.QGraphicsView.FullViewportUpdate)
            


        self.scene = CustomGraphicsScene(self, self.openglWidget, self.image)

        # oli todo
        if self.volumeEditor.image.shape[1] > 1:
            grviewHudLayout = QtGui.QVBoxLayout(self)
            tempLayout = QtGui.QHBoxLayout()
            self.fullScreenButton = QtGui.QPushButton()
            self.fullScreenButton.setIcon(QtGui.QIcon(QtGui.QPixmap(ilastikIcons.AddSelx22)))
            self.fullScreenButton.setStyleSheet("background-color: white; border: 2px solid " + self.axisColor[self.axis].name() +"; border-radius: 4px;")
            self.connect(self.fullScreenButton, QtCore.SIGNAL('clicked()'), self.imageSceneFullScreen)
            tempLayout.addWidget(self.fullScreenButton)
            tempLayout.addStretch()
            grviewHudLayout.addLayout(tempLayout)
            grviewHudLayout.addStretch()
        
        
        if self.openglWidget is not None:
            self.openglWidget.context().makeCurrent()
            self.scene.tex = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D,self.scene.tex)
            glTexImage2D(GL_TEXTURE_2D, 0,GL_RGB, self.scene.image.width(), self.scene.image.height(), 0, GL_RGB, GL_UNSIGNED_BYTE, ctypes.c_void_p(self.scene.image.bits().__int__()))
            
        self.view.setScene(self.scene)
        self.scene.setSceneRect(0,0, imShape[0],imShape[1])
        self.view.setSceneRect(0,0, imShape[0],imShape[1])
        self.scene.bgColor = QtGui.QColor(QtCore.Qt.white)
        if os.path.isfile('gui/backGroundBrush.png'):
            self.scene.bgBrush = QtGui.QBrush(QtGui.QImage('gui/backGroundBrush.png'))
        else:
            self.scene.bgBrush = QtGui.QBrush(QtGui.QColor(QtCore.Qt.black))
        #self.setBackgroundBrush(brushImage)
        self.view.setRenderHint(QtGui.QPainter.Antialiasing, False)
        #self.view.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, False)

        self.patchAccessor = PatchAccessor(imShape[0],imShape[1],64)
        #print "PatchCount :", self.patchAccessor.patchCount

        self.imagePatches = range(self.patchAccessor.patchCount)
        for i,p in enumerate(self.imagePatches):
            b = self.patchAccessor.getPatchBounds(i, 0)
            self.imagePatches[i] = QtGui.QImage(b[1]-b[0], b[3] -b[2], QtGui.QImage.Format_RGB888)

        self.pixmap = QtGui.QPixmap.fromImage(self.image)
        self.imageItem = QtGui.QGraphicsPixmapItem(self.pixmap)
        
        #self.setStyleSheet("QWidget:!focus { border: 2px solid " + self.axisColor[self.axis].name() +"; border-radius: 4px; }\
        #                    QWidget:focus { border: 2px solid white; border-radius: 4px; }")
        
        if self.axis is 0:
            self.view.rotate(90.0)
            self.view.scale(1.0,-1.0)
        
        #on right mouse press, the customContextMenuRequested() signal is
        #_automatically_ emitted, no need to call onContext explicitly
        #self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        #self.connect(self, QtCore.SIGNAL("customContextMenuRequested(QPoint)"), self.onContext)

        self.setMouseTracking(True)

        #indicators for the biggest filter mask's size
        #marks the area where labels should not be placed
        # -> the margin top, left, right, bottom
        self.margin = 0
        # -> the complete 2D slice is marked
        brush = QtGui.QBrush(QtGui.QColor(0,0,255))
        brush.setStyle( QtCore.Qt.DiagCrossPattern )
        allBorderPath = QtGui.QPainterPath()
        allBorderPath.setFillRule(QtCore.Qt.WindingFill)
        allBorderPath.addRect(0, 0, imShape[0], imShape[1])
        self.allBorder = QtGui.QGraphicsPathItem(allBorderPath)
        self.allBorder.setBrush(brush)
        self.allBorder.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        self.scene.addItem(self.allBorder)
        self.allBorder.setVisible(False)
        self.allBorder.setZValue(99)

        self.ticker = QtCore.QTimer(self)
        self.connect(self.ticker, QtCore.SIGNAL("timeout()"), self.tickerEvent)
        #label updates while drawing, needed for interactive segmentation
        self.drawTimer = QtCore.QTimer(self)
        self.connect(self.drawTimer, QtCore.SIGNAL("timeout()"), self.updateLabels)
        
        # invisible cursor to enable custom cursor
        self.hiddenCursor = QtGui.QCursor(QtCore.Qt.BlankCursor)
        
        # For screen recording BlankCursor dont work
        #self.hiddenCursor = QtGui.QCursor(QtCore.Qt.ArrowCursor)
        
        self.thread = ImageSceneRenderThread(self)
        self.connect(self.thread, QtCore.SIGNAL('finishedPatch(int)'),self.redrawPatch)
        self.connect(self.thread, QtCore.SIGNAL('finishedQueue()'), self.renderingThreadFinished)
        self.thread.start()
        
        #self.connect(self, QtCore.SIGNAL("destroyed()"),self.cleanUp)


        self.crossHairCursor = CrossHairCursor(self.image.width(), self.image.height())
        self.crossHairCursor.setZValue(100)
        self.scene.addItem(self.crossHairCursor)
        self.crossHairCursor.setBrushSize(self.drawManager.brushSize)

        self.sliceIntersectionMarker = SliceIntersectionMarker(self.image.width(), self.image.height())
        self.sliceIntersectionMarker.setPos(23, 42);
        if self.axis == 0:
            self.sliceIntersectionMarker.setColor(self.axisColor[1], self.axisColor[2])
        elif self.axis == 1:
            self.sliceIntersectionMarker.setColor(self.axisColor[0], self.axisColor[2])
        elif self.axis == 2:
            self.sliceIntersectionMarker.setColor(self.axisColor[0], self.axisColor[1])
                    
        self.scene.addItem(self.sliceIntersectionMarker)

        self.tempErase = False

    def imageSceneFullScreen(self):
        if self.volumeEditor.imageScenes[0] == self.fullScreenButton.parent():
            self.volumeEditor.toggleFullscreenX()
        if self.volumeEditor.imageScenes[1] == self.fullScreenButton.parent():
            self.volumeEditor.toggleFullscreenY()
        if self.volumeEditor.imageScenes[2] == self.fullScreenButton.parent():
            self.volumeEditor.toggleFullscreenZ()

    def setImageSceneFullScreenLabel(self):
        self.allVisible = True
        a = range(3)
        for i in a:
            if not self.volumeEditor.imageScenes[i].isVisible():
                self.allVisible = False
                break
        if self.allVisible:
            self.fullScreenButton.setIcon(QtGui.QIcon(QtGui.QPixmap(ilastikIcons.AddSelx22)))
        else:
            self.fullScreenButton.setIcon(QtGui.QIcon(QtGui.QPixmap(ilastikIcons.RemSelx22)))

    def setSliceIntersection(self, state):
        if state == QtCore.Qt.Checked:
            self.sliceIntersectionMarker.setVisibility(True)
        else:
            self.sliceIntersectionMarker.setVisibility(False)
            
    def updateSliceIntersection(self, num, axis):
        if self.axis == 0:
            if axis == 1:
                self.sliceIntersectionMarker.setPositionX(num)
            elif axis == 2:
                self.sliceIntersectionMarker.setPositionY(num)
            else:
                return
        elif self.axis == 1:
            if axis == 0:
                self.sliceIntersectionMarker.setPositionX(num)
            elif axis == 2:
                self.sliceIntersectionMarker.setPositionY(num)
            else:
                return
        elif self.axis == 2:
            if axis == 0:
                self.sliceIntersectionMarker.setPositionX(num)
            elif axis == 1:
                self.sliceIntersectionMarker.setPositionY(num)
            else:
                return
        
    def changeSlice(self, delta):
        if self.drawing == True:
            self.endDraw(self.mousePos)
            self.drawing = True
            self.drawManager.beginDraw(self.mousePos, self.imShape)

        self.volumeEditor.sliceSelectors[self.axis].stepBy(delta)
        if self.volumeEditor.interactionLog is not None:
            lm = "%f: changeSlice(axis, num) %d, %d" % (time.clock(), self.axis, self.volumeEditor.sliceSelectors[self.axis].value())
            self.volumeEditor.interactionLog.append(lm)

    def sliceUp(self):
        self.changeSlice(1)
        
    def sliceUp10(self):
        self.changeSlice(10)

    def sliceDown(self):
        self.changeSlice(-1)

    def sliceDown10(self):
        self.changeSlice(-10)

    def brushSmaller(self):
        b = self.drawManager.brushSize
        if b > 1:
            self.drawManager.setBrushSize(b-1)
            self.crossHairCursor.setBrushSize(b-1)
        
    def brushBigger(self):
        b = self.drawManager.brushSize
        if b < 61:
            self.drawManager.setBrushSize(b+1)
            self.crossHairCursor.setBrushSize(b+1)

    def cleanUp(self):
        #print "stopping ImageSCeneRenderThread", str(self.axis)
        self.thread.stopped = True
        self.thread.dataPending.set()
        self.thread.wait()
        
        self.ticker.stop()
        self.drawTimer.stop()
        del self.drawTimer
        del self.ticker
        
        print "finished thread"

    def updatePatches(self, patchNumbers ,image, overlays = ()):
        stuff = [patchNumbers,image, overlays, self.min, self.max]
        #print patchNumbers
        if patchNumbers is not None:
            self.thread.queue.append(stuff)
            self.thread.dataPending.set()

    def displayNewSlice(self, image, overlays = (), fastPreview = True):
        self.thread.queue.clear()
        self.thread.newerDataPending.set()

        fastPreview = fastPreview and self.volumeEditor.fastRepaint
        
        #if we are in opengl 2d render mode, quickly update the texture without any overlays
        #to get a fast update on slice change
        if image is not None:
            #TODO: This doing something twice (see below)
            if fastPreview is True and self.volumeEditor.sharedOpenGLWidget is not None and len(image.shape) == 2:
                self.volumeEditor.sharedOpenGLWidget.context().makeCurrent()
                t = self.scene.tex
                ti = qimage2ndarray.gray2qimage(image.swapaxes(0,1), normalize = self.volumeEditor.normalizeData)
    
                if not t > -1:
                    self.scene.tex = glGenTextures(1)
                    glBindTexture(GL_TEXTURE_2D,self.scene.tex)
                    glTexImage2D(GL_TEXTURE_2D, 0,GL_RGB, ti.width(), ti.height(), 0, GL_LUMINANCE, GL_UNSIGNED_BYTE, ctypes.c_void_p(ti.bits().__int__()))
                else:
                    glBindTexture(GL_TEXTURE_2D,self.scene.tex)
                    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, ti.width(), ti.height(), GL_LUMINANCE, GL_UNSIGNED_BYTE, ctypes.c_void_p(ti.bits().__int__()))
                
                self.viewport().repaint()
    
            if self.volumeEditor.normalizeData:
                self.min = numpy.min(image)
                self.max = numpy.max(image)
            else:
                self.min = 0
                self.max = 255
        ########### 
        #TODO: This doing something twice (see above)
        self.updatePatches(range(self.patchAccessor.patchCount), image, overlays)
        
    def saveSlice(self, filename):
        print "Saving in ", filename, "slice #", self.sliceNumber, "axis", self.axis
        result_image = QtGui.QImage(self.scene.image.size(), self.scene.image.format())
        p = QtGui.QPainter(result_image)
        for patchNr in range(self.patchAccessor.patchCount):
            bounds = self.patchAccessor.getPatchBounds(patchNr)
            if self.openglWidget is None:
                p.drawImage(0, 0, self.scene.image)
            else:
                p.drawImage(bounds[0], bounds[2], self.imagePatches[patchNr])
        p.end()
        #horrible way to transpose an image. but it works.
        transform = QtGui.QTransform()
        transform.rotate(90)
        result_image = result_image.mirrored()
        result_image = result_image.transformed(transform)
        result_image.save(QtCore.QString(filename))

    def display(self, image, overlays = ()):
        self.thread.queue.clear()
        self.updatePatches(range(self.patchAccessor.patchCount),image, overlays)

    def renderingThreadFinished(self):
        #only proceed if htere is no new _data already in the rendering thread queue
        if not self.thread.dataPending.isSet():
            #if, in slicing direction, we are within the margin of the image border
            #we set the border overlay indicator to visible

            self.allBorder.setVisible((self.sliceNumber < self.margin or self.sliceExtent - self.sliceNumber < self.margin) and self.sliceExtent > 1 and self.volumeEditor.useBorderMargin)
            # print "renderingThreadFinished()", self.volumeEditor.useBorderMargin, self.volumeEditor.borderMargin    

            #if we are in opengl 2d render mode, update the texture
            if self.openglWidget is not None:
                self.volumeEditor.sharedOpenGLWidget.context().makeCurrent()
                for patchNr in self.thread.outQueue:
                    t = self.scene.tex
                    #self.scene.tex = -1
                    if t > -1:
                        #self.openglWidget.deleteTexture(t)
                        pass
                    else:
                        #self.scene.tex = self.openglWidget.bindTexture(self.scene.image, GL_TEXTURE_2D, GL_RGBA)
                        self.scene.tex = glGenTextures(1)
                        glBindTexture(GL_TEXTURE_2D,self.scene.tex)
                        glTexImage2D(GL_TEXTURE_2D, 0,GL_RGB, self.scene.image.width(), self.scene.image.height(), 0, GL_RGB, GL_UNSIGNED_BYTE, ctypes.c_void_p(self.scene.image.bits().__int__()))
                        
                    glBindTexture(GL_TEXTURE_2D,self.scene.tex)
                    b = self.patchAccessor.getPatchBounds(patchNr,0)
                    glTexSubImage2D(GL_TEXTURE_2D, 0, b[0], b[2], b[1]-b[0], b[3]-b[2], GL_RGB, GL_UNSIGNED_BYTE, ctypes.c_void_p(self.imagePatches[patchNr].bits().__int__()))
            else:
                # TODO: What is going on down here??
                """
                t = self.scene.tex
                #self.scene.tex = -1
                if t > -1:
                    #self.openglWidget.deleteTexture(t)
                    pass
                else:
                    #self.scene.tex = self.openglWidget.bindTexture(self.scene.image, GL_TEXTURE_2D, GL_RGBA)
                    self.scene.tex = glGenTextures(1)
                    glBindTexture(GL_TEXTURE_2D,self.scene.tex)
                    glTexImage2D(GL_TEXTURE_2D, 0,GL_RGB, self.scene.image.width(), self.scene.image.height(), 0, GL_RGB, GL_UNSIGNED_BYTE, ctypes.c_void_p(self.scene.image.bits().__int__()))
                    
                #glBindTexture(GL_TEXTURE_2D,self.scene.tex)
                #glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.scene.image.width(), self.scene.image.height(), GL_RGB, GL_UNSIGNED_BYTE, ctypes.c_void_p(self.scene.image.bits().__int__()))
                """
                    
            self.thread.outQueue.clear()
            #if all updates have been rendered remove tempitems
            if self.thread.queue.__len__() == 0:
                for index, item in enumerate(self.tempImageItems):
                    self.scene.removeItem(item)
                self.tempImageItems = []

            #update the scene, and the 3d overvie
        #print "updating slice view ", self.axis
        self.viewport().repaint() #update(QtCore.QRectF(self.image.rect()))
        self.volumeEditor.overview.display(self.axis)
        self.thread.freeQueue.set()
        
    def redrawPatch(self, patchNr):
        if self.thread.stopped is False:
            pass
#            patch = self.thread.imagePatches[patchNr]
#            if self.textures[patchNr] < 0 :
#                t = self.openglWidget.bindTexture(patch)
#                self.textures[patchNr] = t
#            else:
#                t_old = self.textures[patchNr]
#
#                t_new = self.openglWidget.bindTexture(patch)
#                self.textures[patchNr] = t_new
#
#                self.openglWidget.deleteTexture(t_old)

#            bounds = self.patchAccessor.getPatchBounds(patchNr)
#            p = QtGui.QPainter(self.scene.image)
#            p.drawImage(bounds[0],bounds[2],self.thread.imagePatches[patchNr])
#            p.end()

            #self.scene.update(bounds[0],bounds[2],bounds[1]-bounds[0],bounds[3]-bounds[2])
        
    def updateLabels(self):
        result = self.drawManager.dumpDraw(self.mousePos)
        image = result[2]
        ndarr = qimage2ndarray.rgb_view(image)
        labels = ndarr[:,:,0]
        labels = labels.swapaxes(0,1)
        number = self.volumeEditor.labelWidget.currentItem().number
        labels = numpy.where(labels > 0, number, 0)
        ls = LabelState('drawing', self.axis, self.volumeEditor.selSlices[self.axis], result[0:2], labels.shape, self.volumeEditor.selectedTime, self.volumeEditor, self.drawManager.erasing, labels, number)
        self.volumeEditor._history.append(ls)        
        self.volumeEditor.setLabels(result[0:2], self.axis, self.volumeEditor.sliceSelectors[self.axis].value(), labels, self.drawManager.erasing)
        
    
    def beginDraw(self, pos):
        if self.volumeEditor.interactionLog is not None:
            lm = "%f: endDraw()" % (time.clock())
            self.volumeEditor.interactionLog.append(lm)        
        self.mousePos = pos
        self.drawing  = True
        line = self.drawManager.beginDraw(pos, self.imShape)
        line.setZValue(99)
        self.tempImageItems.append(line)
        self.scene.addItem(line)

        if self.volumeEditor.drawUpdateInterval > 0:
            self.drawTimer.start(self.volumeEditor.drawUpdateInterval) #update labels every some ms
        self.volumeEditor.labelWidget.ensureLabelOverlayVisible()
        
    def endDraw(self, pos):
        if self.volumeEditor.interactionLog is not None:
            lm = "%f: endDraw()" % (time.clock())
            self.volumeEditor.interactionLog.append(lm)        
        self.drawTimer.stop()
        result = self.drawManager.endDraw(pos)
        image = result[2]
        ndarr = qimage2ndarray.rgb_view(image)
        labels = ndarr[:,:,0]
        labels = labels.swapaxes(0,1)
        number = self.volumeEditor.labelWidget.currentItem().number
        labels = numpy.where(labels > 0, number, 0)
        ls = LabelState('drawing', self.axis, self.volumeEditor.selSlices[self.axis], result[0:2], labels.shape, self.volumeEditor.selectedTime, self.volumeEditor, self.drawManager.erasing, labels, number)
        self.volumeEditor._history.append(ls)        
        self.volumeEditor.setLabels(result[0:2], self.axis, self.volumeEditor.sliceSelectors[self.axis].value(), labels, self.drawManager.erasing)
        self.volumeEditor.pushLabelsToLabelWidget()
        self.drawing = False


    def wheelEvent(self, event):
        keys = QtGui.QApplication.keyboardModifiers()
        k_alt = (keys == QtCore.Qt.AltModifier)
        k_ctrl = (keys == QtCore.Qt.ControlModifier)

        self.mousePos = self.mapToScene(event.pos())
        grviewCenter  = self.mapToScene(self.viewport().rect().center())

        if event.delta() > 0:
            if k_alt is True:
                self.changeSlice(10)
            elif k_ctrl is True:
                scaleFactor = 1.1
                self.doScale(scaleFactor)
            else:
                self.changeSlice(1)
        else:
            if k_alt is True:
                self.changeSlice(-10)
            elif k_ctrl is True:
                scaleFactor = 0.9
                self.doScale(scaleFactor)
            else:
                self.changeSlice(-1)
        if k_ctrl is True:
            mousePosAfterScale = self.mapToScene(event.pos())
            offset = self.mousePos - mousePosAfterScale
            newGrviewCenter = grviewCenter + offset
            self.centerOn(newGrviewCenter)
            self.mouseMoveEvent(event)

    def zoomOut(self):
        self.doScale(0.9)

    def zoomIn(self):
        self.doScale(1.1)

    def doScale(self, factor):
        self.factor = self.factor * factor
        if self.volumeEditor.interactionLog is not None:
            lm = "%f: zoomFactor(factor) %f" % (time.clock(), self.factor)
            self.volumeEditor.interactionLog.append(lm)        
        self.view.scale(factor, factor)


    def tabletEvent(self, event):
        self.setFocus(True)
        
        if not self.volumeEditor.labelWidget.currentItem():
            return
        
        self.mousePos = mousePos = self.mapToScene(event.pos())
        
        x = mousePos.x()
        y = mousePos.y()
        if event.pointerType() == QtGui.QTabletEvent.Eraser or QtGui.QApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
            self.drawManager.setErasing()
        elif event.pointerType() == QtGui.QTabletEvent.Pen and QtGui.QApplication.keyboardModifiers() != QtCore.Qt.ShiftModifier:
            self.drawManager.disableErasing()
        if self.drawing == True:
            if event.pressure() == 0:
                self.endDraw(mousePos)
                self.volumeEditor.changeSlice(self.volumeEditor.selSlices[self.axis], self.axis)
            else:
                if self.drawManager.erasing:
                    #make the brush size bigger while erasing
                    self.drawManager.setBrushSize(int(event.pressure()*10))
                else:
                    self.drawManager.setBrushSize(int(event.pressure()*7))
        if self.drawing == False:
            if event.pressure() > 0:
                self.beginDraw(mousePos)
                
                
        self.mouseMoveEvent(event)

    #TODO oli
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MidButton:
            self.lastPanPoint = event.pos()
            self.crossHairCursor.setVisible(False)
            self.dragMode = True
            if self.ticker.isActive():
                self.deltaPan = QtCore.QPointF(0, 0)
        if not self.volumeEditor.labelWidget.currentItem():
            return
        
        if event.buttons() == QtCore.Qt.LeftButton:
            #don't draw if flicker the view
            if self.ticker.isActive():
                return
            if QtGui.QApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
                self.drawManager.setErasing()
                self.tempErase = True
            mousePos = self.mapToScene(event.pos())
            self.beginDraw(mousePos)
            
        if event.buttons() == QtCore.Qt.RightButton:
            #make sure that we have the cursor at the correct position
            #before we call the context menu
            self.mouseMoveEvent(event)
            self.onContext(event.pos())
            
    #TODO oli
    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MidButton:
            releasePoint = event.pos()
            
            self.lastPanPoint = releasePoint
            self.dragMode = False
            self.ticker.start(20)
        if self.drawing == True:
            mousePos = self.mapToScene(event.pos())
            self.endDraw(mousePos)
        if self.tempErase == True:
            self.drawManager.disableErasing()
            self.tempErase = False

    #TODO oli
    def panning(self):
        hBar = self.horizontalScrollBar()
        vBar = self.verticalScrollBar()
        vBar.setValue(vBar.value() - self.deltaPan.y())
        if self.isRightToLeft():
            hBar.setValue(hBar.value() + self.deltaPan.x())
        else:
            hBar.setValue(hBar.value() - self.deltaPan.x())
        
        
    #TODO oli
    def deaccelerate(self, speed, a=1, maxVal=64):
        x = self.qBound(-maxVal, speed.x(), maxVal)
        y = self.qBound(-maxVal, speed.y(), maxVal)
        ax ,ay = self.setdeaccelerateAxAy(speed.x(), speed.y(), a)
        if x > 0:
            x = max(0.0, x - a*ax)
        elif x < 0:
            x = min(0.0, x + a*ax)
        if y > 0:
            y = max(0.0, y - a*ay)
        elif y < 0:
            y = min(0.0, y + a*ay)
        return QtCore.QPointF(x, y)

    #TODO oli
    def qBound(self, minVal, current, maxVal):
        return max(min(current, maxVal), minVal)
    
    def setdeaccelerateAxAy(self, x, y, a):
        x = abs(x)
        y = abs(y)
        if x > y:
            if y > 0:
                ax = int(x / y)
                if ax != 0:
                    return ax, 1
            else:
                return x/a, 1
        if y > x:
            if x > 0:
                ay = int(y/x)
                if ay != 0:
                    return 1, ay
            else:
                return 1, y/a
        return 1, 1

    #TODO oli
    def tickerEvent(self):
        if self.deltaPan.x() == 0.0 and self.deltaPan.y() == 0.0 or self.dragMode == True:
            self.ticker.stop()
            cursor = QtGui.QCursor()
            mousePos = self.mapToScene(self.mapFromGlobal(cursor.pos()))
            x = mousePos.x()
            y = mousePos.y()
            self.crossHairCursor.showXYPosition(x, y)
        else:
            self.deltaPan = self.deaccelerate(self.deltaPan)
            self.panning()

    #TODO oli
    def updateInfoLabels(self, posX, posY, posZ, colorValues):
        self.volumeEditor.posLabel.setText("<b>x:</b> %03i  <b>y:</b> %03i  <b>z:</b> %03i" % (posX, posY, posZ))
        if isinstance(colorValues, numpy.ndarray):
            self.volumeEditor.pixelValuesLabel.setText("<b>R:</b> %03i  <b>G:</b> %03i  <b>B:</b> %03i" % (colorValues[0], colorValues[1], colorValues[2]))
        else:
            self.volumeEditor.pixelValuesLabel.setText("<b>Gray:</b> %03i" %int(colorValues))
    
    def coordinateUnderCursor(self):
        """returns the coordinate that is defined by hovering with the mouse
           over one of the slice views. It is _not_ the coordinate as defined
           by the three slice views"""
        
        posX = posY = posZ = -1
        if self.axis == 0:
            posY = self.x
            posZ = self.y
            posX = self.volumeEditor.selSlices[0]
        elif self.axis == 1:
            posY = self.volumeEditor.selSlices[1]
            posZ = self.y
            posX = self.x
        else:
            posY = self.y
            posZ = self.volumeEditor.selSlices[2]
            posX = self.x
        return (posX, posY, posZ)
    
    #TODO oli
    def mouseMoveEvent(self,event):
        if self.dragMode == True:
            self.deltaPan = QtCore.QPointF(event.pos() - self.lastPanPoint)
            self.panning()
            self.lastPanPoint = event.pos()
            return
        if self.ticker.isActive():
            return
            
        self.mousePos = mousePos = self.mousePos = self.mapToScene(event.pos())
        x = self.x = mousePos.x()
        y = self.y = mousePos.y()
        #posX = 0
        #posY = 0
        #posZ = 0
        if x > 0 and x < self.image.width() and y > 0 and y < self.image.height() and len(self.volumeEditor.overlayWidget.overlays) > 0:
            
            #should we hide the cursor only when entering once ? performance?
            #self.setCursor(self.hiddenCursor)
            
            self.crossHairCursor.showXYPosition(x,y)
            #self.crossHairCursor.setPos(x,y)
            
            (posX, posY, posZ) = self.coordinateUnderCursor()
            
            if self.axis == 0:
                colorValues = self.volumeEditor.overlayWidget.getOverlayRef("Raw Data").getOverlaySlice(posX, 0, time=0, channel=0)._data[x,y]
                self.updateInfoLabels(posX, posY, posZ, colorValues)
                if len(self.volumeEditor.imageScenes) > 2:
                    yView = self.volumeEditor.imageScenes[1].crossHairCursor
                    zView = self.volumeEditor.imageScenes[2].crossHairCursor
                    yView.setVisible(False)
                    zView.showYPosition(x, y)
            elif self.axis == 1:
                colorValues = self.volumeEditor.overlayWidget.getOverlayRef("Raw Data").getOverlaySlice(posY, 1, time=0, channel=0)._data[x,y]
                self.updateInfoLabels(posX, posY, posZ, colorValues)
                xView = self.volumeEditor.imageScenes[0].crossHairCursor
                zView = self.volumeEditor.imageScenes[2].crossHairCursor
                
                zView.showXPosition(x, y)
                xView.setVisible(False)
            else:
                colorValues = self.volumeEditor.overlayWidget.getOverlayRef("Raw Data").getOverlaySlice(posZ, 2, time=0, channel=0)._data[x,y]
                self.updateInfoLabels(posX, posY, posZ, colorValues)
                xView = self.volumeEditor.imageScenes[0].crossHairCursor
                yView = self.volumeEditor.imageScenes[1].crossHairCursor
                
                xView.showXPosition(y, x)
                yView.showXPosition(x, y)
        else:
            self.unsetCursor()
                
        
        if self.drawing == True:
            line = self.drawManager.moveTo(mousePos)
            line.setZValue(99)
            self.tempImageItems.append(line)
            self.scene.addItem(line)


    def mouseDoubleClickEvent(self, event):
        mousePos = self.mapToScene(event.pos())
        x = mousePos.x()
        y = mousePos.y()
        
          
        if self.axis == 0:
            self.volumeEditor.changeSlice(x, 1)
            self.volumeEditor.changeSlice(y, 2)
        elif self.axis == 1:
            self.volumeEditor.changeSlice(x, 0)
            self.volumeEditor.changeSlice(y, 2)
        elif self.axis ==2:
            self.volumeEditor.changeSlice(x, 0)
            self.volumeEditor.changeSlice(y, 1)

    def onContext(self, pos):
        if type(self.volumeEditor.labelWidget) == DummyLabelWidget: return
        self.volumeEditor.labelWidget.onImageSceneContext(self, pos)

    def onContextSetLabel(self, i):
        self.volumeEditor.labelWidget.listWidget.selectionModel().setCurrentIndex(i, QtGui.QItemSelectionModel.ClearAndSelect)
        self.drawManager.updateCrossHair()

#*******************************************************************************
# O v e r v i e w S c e n e D u m m y                                          *
#*******************************************************************************

class OverviewSceneDummy(QtGui.QWidget):
    def __init__(self, parent, shape):
        QtGui.QWidget.__init__(self)
        pass
    
    def display(self, axis):
        pass

    def redisplay(self):
        pass
    
#*******************************************************************************
# O v e r v i e w S c e n e O l d                                              *
#*******************************************************************************

class OverviewSceneOld(QtOpenGL.QGLWidget):
    def __init__(self, parent, shape):
        QtOpenGL.QGLWidget.__init__(self, shareWidget = parent.sharedOpenGLWidget)
        self.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        self.sceneShape = shape
        self.volumeEditor = parent
        self.images = parent.imageScenes
        self.sceneItems = []
        self.initialized = False
        self.tex = []
        self.tex.append(-1)
        self.tex.append(-1)
        self.tex.append(-1)
        if self.volumeEditor.sharedOpenGLWidget is None:
            self.setVisible(False)

    def display(self, axis):
        if self.volumeEditor.sharedOpenGLWidget is not None:  
            if self.initialized is True:
                #self.initializeGL()
                self.makeCurrent()
                self.paintGL(axis)
                self.swapBuffers()
            
    def redisplay(self):
        if self.volumeEditor.sharedOpenGLWidget is not None:
            if self.initialized is True:
                for i in range(3):
                    self.makeCurrent()
                    self.paintGL(i)
                self.swapBuffers()        

    def paintGL(self, axis = None):
        if self.volumeEditor.sharedOpenGLWidget is not None:
            '''
            Drawing routine
            '''
            pix0 = self.images[0].pixmap
            pix1 = self.images[1].pixmap
            pix2 = self.images[2].pixmap
    
            maxi = max(pix0.width(),pix1.width())
            maxi = max(maxi, pix2.width())
            maxi = max(maxi, pix0.height())
            maxi = max(maxi, pix1.height())
            maxi = max(maxi, pix2.height())
    
            ratio0w = 1.0 * pix0.width() / maxi
            ratio1w = 1.0 * pix1.width() / maxi
            ratio2w = 1.0 * pix2.width() / maxi
    
            ratio0h = 1.0 * pix0.height() / maxi
            ratio1h = 1.0 * pix1.height() / maxi
            ratio2h = 1.0 * pix2.height() / maxi
           
            glMatrixMode(GL_MODELVIEW)
    
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            glLoadIdentity()
    
            glRotatef(30,1.0,0.0,0.0)
    
            glTranslatef(0,-3,-5)        # Move Into The Screen
    
            glRotatef(-30,0.0,1.0,0.0)        # Rotate The Cube On X, Y & Z
    
            #glRotatef(180,1.0,0.0,1.0)        # Rotate The Cube On X, Y & Z
    
            glPolygonMode( GL_FRONT_AND_BACK, GL_LINE ) #wireframe mode
    
            glBegin(GL_QUADS)            # Start Drawing The Cube
    
            glColor3f(1.0,0.0,1.0)            # Set The Color To Violet
            
            glVertex3f( ratio2w, ratio1h,-ratio2h)        # Top Right Of The Quad (Top)
            glVertex3f(-ratio2w, ratio1h,-ratio2h)        # Top Left Of The Quad (Top)
            glVertex3f(-ratio2w, ratio1h, ratio2h)        # Bottom Left Of The Quad (Top)
            glVertex3f( ratio2w, ratio1h, ratio2h)        # Bottom Right Of The Quad (Top)
    
            glVertex3f( ratio2w,-ratio1h, ratio2h)        # Top Right Of The Quad (Bottom)
            glVertex3f(-ratio2w,-ratio1h, ratio2h)        # Top Left Of The Quad (Bottom)
            glVertex3f(-ratio2w,-ratio1h,-ratio2h)        # Bottom Left Of The Quad (Bottom)
            glVertex3f( ratio2w,-ratio1h,-ratio2h)        # Bottom Right Of The Quad (Bottom)
    
            glVertex3f( ratio2w, ratio1h, ratio2h)        # Top Right Of The Quad (Front)
            glVertex3f(-ratio2w, ratio1h, ratio2h)        # Top from PyQt4 import QtCore, QtGui, QtOpenGLLeft Of The Quad (Front)
            glVertex3f(-ratio2w,-ratio1h, ratio2h)        # Bottom Left Of The Quad (Front)
            glVertex3f( ratio2w,-ratio1h, ratio2h)        # Bottom Right Of The Quad (Front)
    
            glVertex3f( ratio2w,-ratio1h,-ratio2h)        # Bottom Left Of The Quad (Back)
            glVertex3f(-ratio2w,-ratio1h,-ratio2h)        # Bottom Right Of The Quad (Back)
            glVertex3f(-ratio2w, ratio1h,-ratio2h)        # Top Right Of The Quad (Back)
            glVertex3f( ratio2w, ratio1h,-ratio2h)        # Top Left Of The Quad (Back)
    
            glVertex3f(-ratio2w, ratio1h, ratio2h)        # Top Right Of The Quad (Left)
            glVertex3f(-ratio2w, ratio1h,-ratio2h)        # Top Left Of The Quad (Left)
            glVertex3f(-ratio2w,-ratio1h,-ratio2h)        # Bottom Left Of The Quad (Left)
            glVertex3f(-ratio2w,-ratio1h, ratio2h)        # Bottom Right Of The Quad (Left)
    
            glVertex3f( ratio2w, ratio1h,-ratio2h)        # Top Right Of The Quad (Right)
            glVertex3f( ratio2w, ratio1h, ratio2h)        # Top Left Of The Quad (Right)
            glVertex3f( ratio2w,-ratio1h, ratio2h)        # Bottom Left Of The Quad (Right)
            glVertex3f( ratio2w,-ratio1h,-ratio2h)        # Bottom Right Of The Quad (Right)
            glEnd()                # Done Drawing The Quad
    
    
            curCenter = -(( 1.0 * self.volumeEditor.selSlices[2] / self.sceneShape[2] ) - 0.5 )*2.0*ratio1h
            if axis is 2:
                self.tex[2] = self.images[2].scene.tex
            if self.tex[2] != -1:
                glBindTexture(GL_TEXTURE_2D,self.tex[2])
                
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
                glPolygonMode( GL_FRONT_AND_BACK, GL_FILL ) #solid drawing mode

                glBegin(GL_QUADS) #horizontal quad (e.g. first axis)
                glColor3f(1.0,1.0,1.0)            # Set The Color To White
                glTexCoord2d(0.0, 0.0)
                glVertex3f( -ratio2w,curCenter, -ratio2h)        # Top Right Of The Quad
                glTexCoord2d(1.0, 0.0)
                glVertex3f(+ ratio2w,curCenter, -ratio2h)        # Top Left Of The Quad
                glTexCoord2d(1.0, 1.0)
                glVertex3f(+ ratio2w,curCenter, + ratio2h)        # Bottom Left Of The Quad
                glTexCoord2d(0.0, 1.0)
                glVertex3f( -ratio2w,curCenter, + ratio2h)        # Bottom Right Of The Quad
                glEnd()


                glPolygonMode( GL_FRONT_AND_BACK, GL_LINE ) #wireframe mode
                glBindTexture(GL_TEXTURE_2D,0) #unbind texture

                glBegin(GL_QUADS)
                glColor3f(0.0,0.0,1.0)            # Set The Color To Blue, Z Axis
                glVertex3f( ratio2w,curCenter, ratio2h)        # Top Right Of The Quad (Bottom)
                glVertex3f(- ratio2w,curCenter, ratio2h)        # Top Left Of The Quad (Bottom)
                glVertex3f(- ratio2w,curCenter,- ratio2h)        # Bottom Left Of The Quad (Bottom)
                glVertex3f( ratio2w,curCenter,- ratio2h)        # Bottom Right Of The Quad (Bottom)
                glEnd()
    
    
    
    
    
    
    
            curCenter = (( (1.0 * self.volumeEditor.selSlices[0]) / self.sceneShape[0] ) - 0.5 )*2.0*ratio2w
    
            if axis is 0:
                self.tex[0] = self.images[0].scene.tex
            if self.tex[0] != -1:
                glBindTexture(GL_TEXTURE_2D,self.tex[0])


                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
                glPolygonMode( GL_FRONT_AND_BACK, GL_FILL ) #solid drawing mode

                glBegin(GL_QUADS)
                glColor3f(0.8,0.8,0.8)            # Set The Color To White
                glTexCoord2d(1.0, 0.0)
                glVertex3f(curCenter, ratio0h, ratio0w)        # Top Right Of The Quad (Left)
                glTexCoord2d(0.0, 0.0)
                glVertex3f(curCenter, ratio0h, - ratio0w)        # Top Left Of The Quad (Left)
                glTexCoord2d(0.0, 1.0)
                glVertex3f(curCenter,- ratio0h,- ratio0w)        # Bottom Left Of The Quad (Left)
                glTexCoord2d(1.0, 1.0)
                glVertex3f(curCenter,- ratio0h, ratio0w)        # Bottom Right Of The Quad (Left)
                glEnd()

                glPolygonMode( GL_FRONT_AND_BACK, GL_LINE ) #wireframe mode
                glBindTexture(GL_TEXTURE_2D,0) #unbind texture

                glBegin(GL_QUADS)
                glColor3f(1.0,0.0,0.0)            # Set The Color To Red,
                glVertex3f(curCenter, ratio0h, ratio0w)        # Top Right Of The Quad (Left)
                glVertex3f(curCenter, ratio0h, - ratio0w)        # Top Left Of The Quad (Left)
                glVertex3f(curCenter,- ratio0h,- ratio0w)        # Bottom Left Of The Quad (Left)
                glVertex3f(curCenter,- ratio0h, ratio0w)        # Bottom Right Of The Quad (Left)
                glEnd()
    
    
            curCenter = (( 1.0 * self.volumeEditor.selSlices[1] / self.sceneShape[1] ) - 0.5 )*2.0*ratio2h
    
    
            if axis is 1:
                self.tex[1] = self.images[1].scene.tex
            if self.tex[1] != -1:
                glBindTexture(GL_TEXTURE_2D,self.tex[1])
    
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
                glPolygonMode( GL_FRONT_AND_BACK, GL_FILL ) #solid drawing mode

                glBegin(GL_QUADS)
                glColor3f(0.6,0.6,0.6)            # Set The Color To White
                glTexCoord2d(1.0, 0.0)
                glVertex3f( ratio1w,  ratio1h, curCenter)        # Top Right Of The Quad (Front)
                glTexCoord2d(0.0, 0.0)
                glVertex3f(- ratio1w, ratio1h, curCenter)        # Top Left Of The Quad (Front)
                glTexCoord2d(0.0, 1.0)
                glVertex3f(- ratio1w,- ratio1h, curCenter)        # Bottom Left Of The Quad (Front)
                glTexCoord2d(1.0, 1.0)
                glVertex3f( ratio1w,- ratio1h, curCenter)        # Bottom Right Of The Quad (Front)
                glEnd()

                glPolygonMode( GL_FRONT_AND_BACK, GL_LINE ) #wireframe mode
                glBindTexture(GL_TEXTURE_2D,0) #unbind texture
                glBegin(GL_QUADS)
                glColor3f(0.0,1.0,0.0)            # Set The Color To Green
                glVertex3f( ratio1w,  ratio1h, curCenter)        # Top Right Of The Quad (Front)
                glVertex3f(- ratio1w, ratio1h, curCenter)        # Top Left Of The Quad (Front)
                glVertex3f(- ratio1w,- ratio1h, curCenter)        # Bottom Left Of The Quad (Front)
                glVertex3f( ratio1w,- ratio1h, curCenter)        # Bottom Right Of The Quad (Front)
                glEnd()
    
            glFlush()

    def resizeGL(self, w, h):
        '''
        Resize the GL window
        '''

        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(40.0, 1.0, 1.0, 30.0)

    def initializeGL(self):
        '''
        Initialize GL
        '''

        # set viewing projection
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClearDepth(1.0)

        glDepthFunc(GL_LESS)                # The Type Of Depth Test To Do
        glEnable(GL_DEPTH_TEST)                # Enables Depth Testing
        glShadeModel(GL_SMOOTH)                # Enables Smooth Color Shading
        glEnable(GL_TEXTURE_2D)
        glLineWidth( 2.0 );

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(40.0, 1.0, 1.0, 30.0)
        
        self.initialized = True

#class OverviewScene2(QtGui.QGraphicsView):
#    def __init__(self, images):
#        QtGui.QGraphicsView.__init__(self)
#        self.scene = QtGui.QGraphicsScene(self)
##        self.scene.setSceneRect(0,0, imShape[0],imShape[1])
#        self.setScene(self.scene)
#        self.setRenderHint(QtGui.QPainter.Antialiasing)
#        self.images = images
#        self.sceneItems = []
#
#    def display(self):
#        for index, item in enumerate(self.sceneItems):
#            self.scene.removeItem(item)
#            del item
#        self.sceneItems = []
#        self.sceneItems.append(QtGui.QGraphicsPixmapItem(self.images[0].pixmap))
#        self.sceneItems.append(QtGui.QGraphicsPixmapItem(self.images[1].pixmap))
#        self.sceneItems.append(QtGui.QGraphicsPixmapItem(self.images[2].pixmap))
#        for index, item in enumerate(self.sceneItems):
#            self.scene.addItem(item)

def test():
    """Text editor demo"""
    app = QtGui.QApplication([""])

    im = (numpy.random.rand(1024,1024)*255).astype(numpy.uint8)
    im[0:10,0:10] = 255
    
    dialog = VolumeEditor(im)
    dialog.show()
    app.exec_()
    del app

    app = QtGui.QApplication([""])

    im = (numpy.random.rand(128,128,128)*255).astype(numpy.uint8)
    im[0:10,0:10,0:10] = 255

    dialog = VolumeEditor(im)
    dialog.show()
    app.exec_()


#*******************************************************************************
# i f   _ _ n a m e _ _   = =   " _ _ m a i n _ _ "                            *
#*******************************************************************************

if __name__ == "__main__":
    test()
