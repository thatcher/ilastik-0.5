# -*- coding: utf-8 -*-
#
# Copyright © 2009 Christoph Straehle
# Licensed under the terms of the MIT License
# (see spyderlib/__init__.py for details)

"""
Dataset Editor Dialog based on PyQt4
"""
import math
from OpenGL.GL import *
from OpenGL.GLU import *

from PyQt4 import QtCore, QtGui, QtOpenGL

import vigra, numpy
import qimage2ndarray

# Local import
from spyderlib.config import get_icon, get_font

##mixin to enable label access
#class VolumeLabelAccessor():
    #def __init__():
        #self._labels = None

##extend ndarray with _label attribute
#numpy.ndarray.__base__ += (VolumeLabelAccessor, )


class LabeledVolumeArray(numpy.ndarray):
    def __new__(cls, input_array, labels=None):
        # Input array is an already formed ndarray instance
        # We first cast to be our class type
        obj = numpy.asarray(input_array).view(cls)
        # add the new attribute to the created instance
        obj._labels = labels
        # Finally, we must return the newly created object:
        return obj

    def __array_finalize__(self,obj):
        # reset the attribute from passed original object
        self.info = getattr(obj, '_labels', None)
        # We do not need to return anything



def rgb(r, g, b):
    # use qRgb to pack the colors, and then turn the resulting long
    # into a negative integer with the same bitpattern.
    return (QtGui.qRgb(r, g, b) & 0xffffff) - 0x1000000



class VolumeEditorList(QtCore.QObject):
    editors = None #class variable to hold global editor list

    def __init__(self):
        super(VolumeEditorList, self).__init__()
        self.editors = []


    def append(self, object):
        self.editors.append(object)
        self.emit(QtCore.SIGNAL('appended(int)'), self.editors.__len__() - 1)

    def remove(self, editor):
        for index, item in enumerate(self.editors):
            if item == editor:
                self.emit(QtCore.SIGNAL('removed(int)'), index)
                self.editors.__delitem__(index)

VolumeEditorList.editors = VolumeEditorList()


class DataAccessor():
    def __init__(self, data, channels = 0):
        rgb = 0
        if data.shape[-1] == 3 or channels:
            rgb = 1

        tempShape = data.shape

        self.data = data

        if issubclass(data.__class__, vigra.arraytypes._VigraArray):
            for i in range(len(data.shape)/2):
                #self.data = self.data.swapaxes(i,len(data.shape)-i)
                pass
            self.data = self.data.view(numpy.ndarray)
            #self.data.reshape(tempShape)


        for i in range(5 - (len(data.shape) - rgb)):
            tempShape = (1,) + tempShape
        if not rgb:
            tempShape = tempShape + (1,)

        self.data = self.data.reshape(tempShape)
        self.channels = self.data.shape[-1]

        self.rgb = False
        if data.shape[-1] == 3:
            self.rgb = True




class OverlaySlice():
    def __init__(self, data, color, alpha):
        self.color = color
        self.alpha = alpha

        self.alphaChannel = data

        shape = data.shape
        shape +=(3,)

        self.data = numpy.zeros(shape, 'uint8')
        self.data[:,:,color] = data[:,:]


class VolumeOverlay(QtGui.QListWidgetItem):
    def __init__(self, data, name = "Red Overlay", color = 0, alpha = 0.4):
        super(VolumeOverlay, self).__init__(name)
        self.setTooltip = name
        self.data = data
        self.color = color
        self.alpha = alpha
        self.name = name
        self.visible = True

    def getSlice(self, num, axis):
        shape = ()
        for index, item in enumerate(self.data.shape):
            if index != axis:
                shape += (item,)

        data = None
        if axis is 0:
            data = self.data[num,:,:]
        elif axis is 1:
            data = self.data[:,num,:]
        elif axis is 2:
            data = self.data[:,:,num]
        return OverlaySlice(data, self.color, self.alpha)

class OverlayListView(QtGui.QListWidget):
    def __init__(self,parent = None):
        super(OverlayListView, self).__init__(parent)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.connect(self, QtCore.SIGNAL("customContextMenuRequested(QPoint)"), self.onContext)
        self.overlays = []

    def addOverlay(self, overlay):
        self.overlays.append(overlay)
        self.addItem(overlay)

    def onContext(self, pos):
        index = self.indexAt(pos)

        if not index.isValid():
           return

        item = self.itemAt(pos)
        name = item.text()

        menu = QtGui.QMenu(self)

        removeAction = menu.addAction("Remove")
        if item.visible is True:
            toggleHideAction = menu.addAction("Hide")
        else:
            toggleHideAction = menu.addAction("Show")

        action = menu.exec_(QtGui.QCursor.pos())
        if action == removeAction:
            self.overlays.remove(item)
            it = self.takeItem(index.row())
            del it
        elif action == toggleHideAction:
            item.visible = not(item.visible)


class VolumeLabelDescription():
    def __init__(self, name,number, color):
        self.number = number
        self.name = name
        self.color = color

class VolumeLabels():
    def __init__(self, data = None):
        self.data = data
        self.descriptions = [] #array of VolumeLabelDescriptions

class LabelListItem(QtGui.QListWidgetItem):
    def __init__(self, name , number, color):
        super(LabelListItem, self).__init__(name)
        self.number = number
        self.color = color
        self.curColor = self.color
        self.visible = True

    def toggleVisible(self):
        self.visible = not(self.visible)
        if self.visible == True:
            self.curColor = self.color
        else:
            self.curColor = QtGui.QColor.fromRgb(0,0,0)

    def setColor(self, color):
        self.color = color
        self.toggleVisible()
        self.toggleVisible()


class LabelListView(QtGui.QListWidget):
    def __init__(self,parent = None):
        super(LabelListView, self).__init__(parent)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.connect(self, QtCore.SIGNAL("customContextMenuRequested(QPoint)"), self.onContext)
        self.colorTab = []
        self.items = []
        self.volumeEditor = parent
        self.initFromMgr(parent.labels)

    def initFromMgr(self, volumelabel):
        self.volumeLabel = volumelabel
        for index, item in enumerate(volumelabel.descriptions):
            li = LabelListItem(item.name,item.number, QtGui.QColor.fromRgb(item.color))
            self.addItem(li)
            self.items.append(li)
        self.buildColorTab()


    def addLabel(self, labelName, labelNumber, color):
        description = VolumeLabelDescription(labelName, labelNumber, color)        
        self.volumeLabel.descriptions.append(description)
        
        label =  LabelListItem(labelName, labelNumber, color)
        self.items.append(label)
        self.addItem(label)
        self.buildColorTab()

    def buildColorTab(self):
        self.colorTab = []
        for i in range(256):
            self.colorTab.append(QtGui.QColor.fromRgb(0,0,0).rgb())

        for index,item in enumerate(self.items):
            self.colorTab[item.number] = item.curColor.rgb()


    def onContext(self, pos):
        index = self.indexAt(pos)

        if not index.isValid():
           return

        item = self.itemAt(pos)
        name = item.text()

        menu = QtGui.QMenu(self)

        removeAction = menu.addAction("Remove")
        if item.visible is True:
            toggleHideAction = menu.addAction("Hide")
        else:
            toggleHideAction = menu.addAction("Show")

        action = menu.exec_(QtGui.QCursor.pos())
        if action == removeAction:
            self.volumeLabel.description.delitem(index.row())
            self.labels.remove(item)
            it = self.takeItem(index.row())
            del it
        elif action == toggleHideAction:
            item.toggleVisible()

        self.buildColorTab()






class VolumeEditor(QtGui.QWidget):
    """Array Editor Dialog"""
    def __init__(self, image, name="", font=None,
                 readonly=False, size=(400, 300), labels = None ):
        super(VolumeEditor, self).__init__()
        self.name = name
        title = name

        if hasattr(image, '_labels'):
            self.labels = image._labels
        elif labels is not None:
            self.labels = labels
        else:
            self.labels = VolumeLabels()

        self.editor_list = VolumeEditorList.editors

        self.linkedTo = None

        self.selAxis = 0
        self.selSlice = 0

        self.image = image

        self.ownIndex = self.editor_list.editors.__len__()
        #self.setAccessibleName(self.name)

        self.layout = QtGui.QHBoxLayout()
        self.setLayout(self.layout)

        self.grid = QtGui.QGridLayout()

        self.imageScenes = []
        self.imageScenes.append(ImageScene(self, image.shape[1:3], 0))
        self.imageScenes.append(ImageScene( self, (image.shape[0], image.shape[2]) , 1))
        self.imageScenes.append(ImageScene(self, image.shape[0:2], 2))
        self.grid.addWidget(self.imageScenes[2], 0, 0)
        self.grid.addWidget(self.imageScenes[0], 0, 1)
        self.grid.addWidget(self.imageScenes[1], 1, 0)

        #enable opengl acceleration
        for index, item in enumerate(self.imageScenes):
            #item.setViewport(QtOpenGL.QGLWidget())
            pass


        self.overview = OverviewScene(self)
        self.grid.addWidget(self.overview, 1, 1)

        self.gridWidget = QtGui.QWidget()
        self.gridWidget.setLayout(self.grid)
        self.layout.addWidget(self.gridWidget)

        #right side toolbox
        self.toolBox = QtGui.QWidget()
        self.toolBoxLayout = QtGui.QVBoxLayout()
        self.toolBox.setLayout(self.toolBoxLayout)
        self.toolBox.setMaximumWidth(100)
        self.toolBox.setMinimumWidth(100)

        #Link to ComboBox
        self.editor_list.append(self)
        self.connect(self.editor_list, QtCore.SIGNAL("appended(int)"), self.linkComboAppend)
        self.connect(self.editor_list, QtCore.SIGNAL("removed(int)"), self.linkComboRemove)

        self.linkCombo = QtGui.QComboBox()
        self.linkCombo.setEnabled(True)
        self.linkCombo.addItem("None")
        for index, item in enumerate(self.editor_list.editors):
            self.linkCombo.addItem(item.name)
        self.connect(self.linkCombo, QtCore.SIGNAL("currentIndexChanged(int)"), self.linkToOther)
        self.toolBoxLayout.addWidget(QtGui.QLabel("Link to:"))
        self.toolBoxLayout.addWidget(self.linkCombo)

        #Slice Selector Combo Box in right side toolbox
        self.sliceSelectors = []
        sliceSpin = QtGui.QSpinBox()
        sliceSpin.setEnabled(True)
        self.connect(sliceSpin, QtCore.SIGNAL("valueChanged(int)"), self.changeSliceX)
        self.toolBoxLayout.addWidget(QtGui.QLabel("Slice 0:"))
        self.toolBoxLayout.addWidget(sliceSpin)
        sliceSpin.setRange(0,self.image.shape[0] - 1)
        self.sliceSelectors.append(sliceSpin)

        sliceSpin = QtGui.QSpinBox()
        sliceSpin.setEnabled(True)
        self.connect(sliceSpin, QtCore.SIGNAL("valueChanged(int)"), self.changeSliceY)
        self.toolBoxLayout.addWidget(QtGui.QLabel("Slice 1:"))
        self.toolBoxLayout.addWidget(sliceSpin)
        sliceSpin.setRange(0,self.image.shape[1] - 1)
        self.sliceSelectors.append(sliceSpin)

        sliceSpin = QtGui.QSpinBox()
        sliceSpin.setEnabled(True)
        self.connect(sliceSpin, QtCore.SIGNAL("valueChanged(int)"), self.changeSliceZ)
        self.toolBoxLayout.addWidget(QtGui.QLabel("Slice 2:"))
        self.toolBoxLayout.addWidget(sliceSpin)
        sliceSpin.setRange(0,self.image.shape[2] - 1)
        self.sliceSelectors.append(sliceSpin)


        maxShape = max(image.shape[0], image.shape[1])
        maxShape = max(maxShape, image.shape[2])

        self.maxSlices = []
        self.maxSlices.append((self.image.shape[0] - 1))
        self.maxSlices.append((self.image.shape[1] - 1))
        self.maxSlices.append((self.image.shape[2] - 1))

        self.selSlices = []
        self.selSlices.append(0)
        self.selSlices.append(0)
        self.selSlices.append(0)


        #Overlay selector
        self.addOverlayButton = QtGui.QPushButton("Add Overlay")
        self.connect(self.addOverlayButton, QtCore.SIGNAL("pressed()"), self.addOverlay)
        self.toolBoxLayout.addWidget(self.addOverlayButton)

        self.overlayView = OverlayListView()
        self.toolBoxLayout.addWidget( self.overlayView)

        #Label selector
        self.addLabelButton = QtGui.QPushButton("Add Label")
        self.connect(self.addLabelButton, QtCore.SIGNAL("pressed()"), self.addLabel)
        self.toolBoxLayout.addWidget(self.addLabelButton)

        self.labelView = LabelListView(self)

        self.toolBoxLayout.addWidget( self.labelView)


        self.toolBoxLayout.setAlignment( QtCore.Qt.AlignTop )

        self.layout.addWidget(self.toolBox)

        # Make the dialog act as a window and stay on top
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.setWindowIcon(get_icon('edit.png'))
        self.setWindowTitle(self.tr("Volume") + \
                            "%s" % (" - "+str(title) if str(title) else ""))

        #start viewing in the center of the volume
        self.changeSliceX(numpy.floor((self.image.shape[0] - 1) / 2))
        self.changeSliceY(numpy.floor((self.image.shape[1] - 1) / 2))
        self.changeSliceZ(numpy.floor((self.image.shape[2] - 1) / 2))

    def addOverlay(self):
        overlays = []
        for index, item in enumerate(self.editor_list.editors):
            overlays.append(item.name)
        itemName, ok  = QtGui.QInputDialog.getItem(self,"Add Overlay", "Overlay:", overlays, 0, False)
        itemIndex = -1
        if ok is True:
            for index, item in enumerate(self.editor_list.editors):
                if item.name == itemName:
                    ov = VolumeOverlay(item.image, item.name)
                    self.overlayView.addOverlay(ov)
        self.repaint()


    def addLabel(self):
        name, ok = QtGui.QInputDialog.getText(self, 'Add Label', 'Enter Label name:')
        if ok:
            number, ok = QtGui.QInputDialog.getInteger(self, 'Add Label', 'Enter label number:')
            if ok and number != 0:
                color = QtGui.QColorDialog.getColor()
                self.labelView.addLabel(name, number, color)


    def get_copy(self):
        """Return modified text"""
        return unicode(self.edit.toPlainText())

    def changeSliceX(self, num):
        self.changeSlice(num, 0)

    def changeSliceY(self, num):
        self.changeSlice(num, 1)

    def changeSliceZ(self, num):
        self.changeSlice(num, 2)

    def changeSlice(self, num, axis):
        tempImage = None
        tempLabels = None
        tempoverlays = []
        self.sliceSelectors[axis].setValue(num)

        for index, item in enumerate(self.overlayView.overlays):
            tempoverlays.append(item.getSlice(num,axis))

        if axis is 0:
            tempImage = self.image[num,:,:]
            if self.labels.data is not None:
                tempLabels = self.labels.data[num,:,:]
        elif axis is 1:
            tempImage = self.image[:,num,:]
            if self.labels.data is not None:
                tempLabels = self.labels.data[:,num,:]
        elif axis is 2:
            tempImage = self.image[:,:,num]
            if self.labels.data is not None:
                tempLabels = self.labels.data[:,:,num]

        self.selSlices[axis] = num
        self.imageScenes[axis].display(tempImage, tempoverlays, tempLabels)
        self.overview.display(axis)
        self.emit(QtCore.SIGNAL('changedSlice(int, int)'), num, axis)
#        for i in range(256):
#            col = QtGui.QColor(classColor.red(), classColor.green(), classColor.blue(), i * opasity)
#            image.setColor(i, col.rgba())

    def unlink(self):
        if self.linkedTo is not None:
            self.disconnect(self.editor_list.editors[self.linkedTo], QtCore.SIGNAL("changedSlice(int, int)"), self.changeSlice)
            self.linkedTo = None

    def linkToOther(self, index):
        self.unlink()
        if index > 0 and index != self.ownIndex + 1:
            other = self.editor_list.editors[index-1]
            self.connect(other, QtCore.SIGNAL("changedSlice(int, int)"), self.changeSlice)
            self.linkedTo = index - 1
        else:
            self.linkCombo.setCurrentIndex(0)

    def linkComboAppend(self, index):
        self.linkCombo.addItem( self.editor_list.editors[index].name )

    def linkComboRemove(self, index):
        if self.linkedTo == index:
            self.linkCombo.setCurrentIndex(0)
            self.linkedTo = None
        if self.linkedTo > index:
            self.linkedTo = self.linkedTo - 1
        if self.ownIndex > index:
            self.ownIndex = self.ownIndex - 1
            self.linkCombo.removeItem(index + 1)

    def closeEvent(self, event):
        self.disconnect(self.editor_list, QtCore.SIGNAL("appended(int)"), self.linkComboAppend)
        self.disconnect(self.editor_list, QtCore.SIGNAL("removed(int)"), self.linkComboRemove)
        self.unlink()
        self.editor_list.remove(self)
        event.accept()

    def wheelEvent(self, event):
        if event.delta() > 0:
            scaleFactor = 1.1
        else:
            scaleFactor = 0.9
        self.imageScenes[0].doScale(scaleFactor)
        self.imageScenes[1].doScale(scaleFactor)
        self.imageScenes[2].doScale(scaleFactor)

    def setLabels(self, axis, labels, erase):
        num = self.sliceSelectors[axis].value()

        if self.labels.data is None:
            self.labels.data = numpy.zeros(self.image.shape[0:3],'uint8')

        tempLabels = None
        
        if axis is 0:
            tempLabels = self.labels.data[num,:,:]
        elif axis is 1:
            tempLabels = self.labels.data[:,num,:]
        elif axis is 2:
            tempLabels = self.labels.data[:,:,num]

        if erase == True:
            tempLabels = numpy.where(labels > 0, 0, tempLabels)
        else:
            tempLabels = numpy.where(labels > 0, labels, tempLabels)

        if axis is 0:
            self.labels.data[num,:,:] = tempLabels[:,:]
        elif axis is 1:
            self.labels.data[:,num,:] = tempLabels[:,:]
        elif axis is 2:
            self.labels.data[:,:,num] = tempLabels[:,:]

    def show(self):
        super(VolumeEditor, self).show()
        return  self.labels



class DrawManager(QtCore.QObject):
    def __init__(self, parent, shape):
        self.parent = parent
        self.shape = shape
        self.brushSize = 3
        self.penVis = QtGui.QPen(QtCore.Qt.white, 3, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        self.penDraw = QtGui.QPen(QtCore.Qt.white, 3, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        self.penDraw.setColor(QtCore.Qt.white)
        self.createNewImage()
        self.pos = None
        self.erasing = False

    def createNewImage(self):
        self.image = QtGui.QImage(self.shape[0], self.shape[1],QtGui.QImage.Format_ARGB32_Premultiplied) #TODO: format
        self.image.fill(0)

    def toggleErase(self):
        self.erasing = not(self.erasing)

    def setBrushSize(self, size):
        self.brushSize = size
        self.penVis.setWidth(size)
        self.penDraw.setWidth(size)

    def beginDraw(self, pos):
        if self.erasing == True:
            self.penVis.setColor(QtCore.Qt.black)
        else:
            self.penVis.setColor(self.parent.labelView.currentItem().color)
        self.painter = QtGui.QPainter(self.image)
        self.painter.setClipRegion(QtGui.QRegion(0,0,self.shape[0],self.shape[1]))
        self.painter.setClipping(True)
        self.painter.setPen(self.penDraw)
        self.pos = pos
        line = self.moveTo(pos)
        return line

    def endDraw(self, pos):
        self.moveTo(pos)
        self.painter.end()
        tempi = self.image
        self.createNewImage()
        return tempi

    def moveTo(self, pos):
        self.painter.drawLine(self.pos.x(), self.pos.y(),pos.x(), pos.y())
        line = QtGui.QGraphicsLineItem(self.pos.x(), self.pos.y(),pos.x(), pos.y())
        line.setPen(self.penVis)
        self.pos = pos
        return line



class ImageScene( QtGui.QGraphicsView):
    def __init__(self, parent, imShape, axis):
        QtGui.QGraphicsView.__init__(self)
        self.drawManager = DrawManager(parent, imShape)
        self.tempImageItems = []
        self.volumeEditor = parent
        self.axis = axis
        self.drawing = False
        self.view = self
        self.scene = QtGui.QGraphicsScene(self.view)
        self.scene.setSceneRect(0,0, imShape[0],imShape[1])
        self.view.setScene(self.scene)
        #self.setViewport(QtOpenGL.QGLWidget())
        self.view.setRenderHint(QtGui.QPainter.Antialiasing, False)
        self.view.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, False)
        self.imageItem = None
        self.pixmap = None
        self.image = None
        if self.axis is 0:
            self.setStyleSheet("QWidget { border: 2px solid red; border-radius: 4px; }")
            self.view.rotate(90.0)
            self.view.scale(1.0,-1.0)
        if self.axis is 1:
            self.setStyleSheet("QWidget { border: 2px solid green; border-radius: 4px; }")
        if self.axis is 2:
            self.setStyleSheet("QWidget { border: 2px solid blue; border-radius: 4px; }")
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.connect(self, QtCore.SIGNAL("customContextMenuRequested(QPoint)"), self.onContext)

        #cross chair
        pen = QtGui.QPen(QtCore.Qt.red, 2, QtCore.Qt.DotLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        self.setMouseTracking(True)
        
        # Fixed pen width
        pen.setCosmetic(True)
        self.linex = QtGui.QGraphicsLineItem()
        self.liney = QtGui.QGraphicsLineItem()
        self.linex.setZValue(100)

        self.linex.setPen(pen)
        self.liney.setPen(pen)
        self.liney.setZValue(100)
        self.scene.addItem(self.linex)
        self.scene.addItem(self.liney)



    def display(self, image, overlays = [], labels = None):
        if self.imageItem is not None:
            self.scene.removeItem(self.imageItem)
            del self.imageItem
            del self.pixmap
            del self.image
            self.imageItem = None

        for index, item in enumerate(self.tempImageItems):
            self.scene.removeItem(item)

        self.tempImageItems = []



        self.image = qimage2ndarray.array2qimage(image.swapaxes(0,1), normalize=False)

        self.image = self.image.convertToFormat(QtGui.QImage.Format_ARGB32_Premultiplied)
        
        #add overlays
        for index, item in enumerate(overlays):
            p = QtGui.QPainter(self.image)
            #p.begin(self.pixmap)
            #p.setBrush(QtGui.QColor(255, 255, 255, 255))
            p.setOpacity(item.alpha)

            imageO = qimage2ndarray.array2qimage(item.data.swapaxes(0,1), normalize=False)
            alphaChan = item.alphaChannel

            #image = image.convertToFormat(QtGui.QImage.Format_ARGB32_Premultiplied)
            mask = imageO.createMaskFromColor(QtGui.QColor(0,0,0).rgb(),QtCore.Qt.MaskOutColor) #QtGui.QBitmap.fromImage(
            imageO.setAlphaChannel(qimage2ndarray.gray2qimage(alphaChan.swapaxes(0,1), False))
            #pixmapi = QtGui.QPixmap.fromImage(imageO)
            #pixmapi.setMask(mask)
#            pixmap.fill(QtCore.Qt.transparent)
##            p.fillRect(0,0, pixmapi.width(), pixmapi.height(),QtGui.QBrush(QtGui.QColor(0, 0, 0, 255)))

            p.drawImage(imageO.rect(), imageO)
            #p.drawPixmap(pixmapi.rect(),pixmapi)

            ##p.drawRect(0, 0, pixmap.width(), pixmap.height())
            p.end()
            del p

        if labels is not None:
            p1 = QtGui.QPainter(self.image)
            #p1.setOpacity(0.99)
            image0 = qimage2ndarray.gray2qimage(labels.swapaxes(0,1), False)

            image0.setColorTable(self.volumeEditor.labelView.colorTab)
            mask = image0.createMaskFromColor(QtGui.QColor(0,0,0).rgb(),QtCore.Qt.MaskOutColor) #QtGui.QBitmap.fromImage(
            #alphaChan = numpy.where(labels > 0, 255, 0)
            #mask = qimage2ndarray.gray2qimage(alphaChan, False)
            image0.setAlphaChannel(mask)
            p1.drawImage(image0.rect(), image0)
            p1.end()
            del p1


        self.pixmap = QtGui.QPixmap.fromImage(self.image)

        self.imageItem = QtGui.QGraphicsPixmapItem(self.pixmap)

        self.scene.addItem(self.imageItem)
        
        self.view.repaint()        
        


    def wheelEvent(self, event):
        keys = QtGui.QApplication.keyboardModifiers()
        k_alt = (keys == QtCore.Qt.AltModifier)
        k_ctrl = (keys == QtCore.Qt.ControlModifier)

        if event.delta() > 0:
            if k_alt is True:
                self.volumeEditor.sliceSelectors[self.axis].stepBy(10)
            elif k_ctrl is True:
                scaleFactor = 1.1
                self.doScale(scaleFactor)
            else:
                self.volumeEditor.sliceSelectors[self.axis].stepUp()
        else:
            if k_alt is True:
                self.volumeEditor.sliceSelectors[self.axis].stepBy(-10)
            elif k_ctrl is True:
                scaleFactor = 0.9
                self.doScale(scaleFactor)
            else:
                self.volumeEditor.sliceSelectors[self.axis].stepDown()

    def doScale(self, factor):
        self.view.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton:
            if self.volumeEditor.labelView.currentItem() is not None:
                self.drawing  = True
                mousePos = self.mapToScene(event.pos())
#                self.drawManager.setColor(self.volumeEditor.labelView.currentItem().curColor)
                line = self.drawManager.beginDraw(mousePos)
                self.tempImageItems.append(line)
                self.scene.addItem(line)
        elif event.buttons() == QtCore.Qt.RightButton:
            self.onContext(event.pos())

    def mouseReleaseEvent(self, event):
        if self.drawing == True:
            mousePos = self.mapToScene(event.pos())
            image = self.drawManager.endDraw(mousePos)
            ndarr = qimage2ndarray.rgb_view(image)
            labels = ndarr[:,:,0]
            labels = labels.swapaxes(0,1)
            number = self.volumeEditor.labelView.currentItem().number
            labels = numpy.where(labels > 0, number, 0)
            self.volumeEditor.setLabels(self.axis, labels, self.drawManager.erasing)
            self.drawing = False

    def mouseMoveEvent(self,event):
        mousePos = self.mapToScene(event.pos())
        x = mousePos.x()
        y = mousePos.y()

        if x > 0 and x < self.image.width() and y > 0 and y < self.image.height():
            self.linex.setLine(0,y,self.image.width(),y)
            self.liney.setLine(x,0,x,self.image.height())
        
        if event.buttons() == QtCore.Qt.LeftButton and self.drawing == True:
            line = self.drawManager.moveTo(mousePos)
            self.tempImageItems.append(line)
            self.scene.addItem(line)


    def onContext(self, pos):
        menu = QtGui.QMenu(self)
        labeling = menu.addMenu("Labeling")
        toggleEraseA = None
        if self.drawManager.erasing == True:
            toggleEraseA = labeling.addAction("Enable Labelmode")
        else:
            toggleEraseA = labeling.addAction("Enable Eraser")
        brushM = labeling.addMenu("Brush size")
        brush1 = brushM.addAction("1")
        brush3 = brushM.addAction("3")
        brush5 = brushM.addAction("5")
        brush10 = brushM.addAction("10")

        action = menu.exec_(QtGui.QCursor.pos())
        if action == toggleEraseA:
            self.drawManager.toggleErase()
        elif action == brush1:
            self.drawManager.setBrushSize(1)
        elif action == brush3:
            self.drawManager.setBrushSize(3)
        elif action == brush5:
            self.drawManager.setBrushSize(5)
        elif action == brush10:
            self.drawManager.setBrushSize(10)


class OverviewScene(QtOpenGL.QGLWidget):
    '''
    Widget for drawing two spirals.
    '''

    def __init__(self, parent):
        QtOpenGL.QGLWidget.__init__(self)
        self.parent = parent
        self.images = parent.imageScenes
        self.sceneItems = []
        self.initialized = False
        self.tex = []
        self.tex.append(0)
        self.tex.append(0)
        self.tex.append(0)

    def display(self, axis):
        if self.initialized is True:
            #self.initializeGL()
            self.makeCurrent()
            if self.tex[axis] is not 0:
                self.deleteTexture(self.tex[axis])
            self.paintGL(axis)
            self.swapBuffers()

    def paintGL(self, axis = None):
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


        curCenter = -(( 1.0 * self.parent.selSlices[2] / self.parent.maxSlices[2] ) - 0.5 )*2.0*ratio1h
        if axis is 2 or self.tex[2] is 0:
            self.tex[2] = self.bindTexture(self.images[2].image, GL_TEXTURE_2D, GL_RGB)
        else:
            glBindTexture(GL_TEXTURE_2D,self.tex[2])
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glPolygonMode( GL_FRONT_AND_BACK, GL_FILL ) #solid drawing mode

        glBegin(GL_QUADS) #horizontal quad (e.g. first axis)
        glColor3f(1.0,1.0,1.0)            # Set The Color To White
        glTexCoord2d(0.0, 1.0)
        glVertex3f( -ratio2w,curCenter, -ratio2h)        # Top Right Of The Quad
        glTexCoord2d(1.0, 1.0)
        glVertex3f(+ ratio2w,curCenter, -ratio2h)        # Top Left Of The Quad
        glTexCoord2d(1.0, 0.0)
        glVertex3f(+ ratio2w,curCenter, + ratio2h)        # Bottom Left Of The Quad
        glTexCoord2d(0.0, 0.0)
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







        curCenter = (( (1.0 * self.parent.selSlices[0]) / self.parent.maxSlices[0] ) - 0.5 )*2.0*ratio2w

        if axis is 0 or self.tex[0] is 0:
            self.tex[0] = self.bindTexture(self.images[0].image, GL_TEXTURE_2D, GL_RGB)
        else:
            glBindTexture(GL_TEXTURE_2D,self.tex[0])


        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glPolygonMode( GL_FRONT_AND_BACK, GL_FILL ) #solid drawing mode

        glBegin(GL_QUADS)
        glColor3f(0.8,0.8,0.8)            # Set The Color To White
        glTexCoord2d(1.0, 1.0)
        glVertex3f(curCenter, ratio0h, ratio0w)        # Top Right Of The Quad (Left)
        glTexCoord2d(0.0, 1.0)
        glVertex3f(curCenter, ratio0h, - ratio0w)        # Top Left Of The Quad (Left)
        glTexCoord2d(0.0, 0.0)
        glVertex3f(curCenter,- ratio0h,- ratio0w)        # Bottom Left Of The Quad (Left)
        glTexCoord2d(1.0, 0.0)
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


        curCenter = (( 1.0 * self.parent.selSlices[1] / self.parent.maxSlices[1] ) - 0.5 )*2.0*ratio2h


        if axis is 1 or self.tex[1] is 0:
            self.tex[1] = self.bindTexture(self.images[1].image, GL_TEXTURE_2D, GL_RGB)
        else:
            glBindTexture(GL_TEXTURE_2D,self.tex[1])

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glPolygonMode( GL_FRONT_AND_BACK, GL_FILL ) #solid drawing mode

        glBegin(GL_QUADS)
        glColor3f(0.6,0.6,0.6)            # Set The Color To White
        glTexCoord2d(1.0, 1.0)
        glVertex3f( ratio1w,  ratio1h, curCenter)        # Top Right Of The Quad (Front)
        glTexCoord2d(0.0, 1.0)
        glVertex3f(- ratio1w, ratio1h, curCenter)        # Top Left Of The Quad (Front)
        glTexCoord2d(0.0, 0.0)
        glVertex3f(- ratio1w,- ratio1h, curCenter)        # Bottom Left Of The Quad (Front)
        glTexCoord2d(1.0, 0.0)
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

class OverviewScene2(QtGui.QGraphicsView):
    def __init__(self, images):
        QtGui.QGraphicsView.__init__(self)
        self.scene = QtGui.QGraphicsScene(self)
#        self.scene.setSceneRect(0,0, imShape[0],imShape[1])
        self.setScene(self.scene)
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.images = images
        self.sceneItems = []

    def display(self):
        for index, item in enumerate(self.sceneItems):
            self.scene.removeItem(item)
            del item
        self.sceneItems = []
        self.sceneItems.append(QtGui.QGraphicsPixmapItem(self.images[0].pixmap))
        self.sceneItems.append(QtGui.QGraphicsPixmapItem(self.images[1].pixmap))
        self.sceneItems.append(QtGui.QGraphicsPixmapItem(self.images[2].pixmap))
        for index, item in enumerate(self.sceneItems):
            self.scene.addItem(item)

def test():
    """Text editor demo"""
    import numpy
    from spyderlib.utils.qthelpers import qapplication
    app = qapplication()

    im = (numpy.random.rand(128,64,32)*255).astype(numpy.uint8)
    im[0:10,0:10,0:10] = 255

    dialog = VolumeEditor(im)
    dialog.show()
    app.exec_()

if __name__ == "__main__":
    test()
