# -*- coding: utf-8 -*-
import numpy, vigra
import random

from ilastik.gui.ribbons.ilastikTabBase import IlastikTabBase

from PyQt4 import QtGui, QtCore

from ilastik.gui.iconMgr import ilastikIcons

from ilastik.gui.overlaySelectionDlg import OverlaySelectionDialog
from ilastik.gui.overlayWidget import OverlayWidget
from ilastik.core.overlayMgr import OverlayItem
from ilastik.core.volume import DataAccessor
import ilastik.gui.volumeeditor as ve
                    
                    
class AutoSegmentationTab(IlastikTabBase, QtGui.QWidget):
    name = 'Auto Segmentation'
    position = 2
    moduleName = "Automatic_Segmentation"
    
    def __init__(self, parent=None):
        IlastikTabBase.__init__(self, parent)
        QtGui.QWidget.__init__(self, parent)
        
        self._initContent()
        self._initConnects()
        self.weights = None
        
    def on_activation(self):
        if self.ilastik.project is None:
            return
        ovs = self.ilastik._activeImage.module[self.__class__.moduleName].getOverlayRefs()
        if len(ovs) == 0:
            raw = self.ilastik._activeImage.overlayMgr["Raw Data"]
            if raw is not None:
                ovs.append(raw.getRef())
                        
        self.ilastik.labelWidget._history.volumeEditor = self.ilastik.labelWidget

        overlayWidget = OverlayWidget(self.ilastik.labelWidget, self.ilastik.project.dataMgr)
        self.ilastik.labelWidget.setOverlayWidget(overlayWidget)
        
        self.ilastik.labelWidget.setLabelWidget(ve.DummyLabelWidget())
    
    def on_deActivation(self):
        pass
    
    def _initContent(self):
        tl = QtGui.QHBoxLayout()
        
        self.btnChooseWeights = QtGui.QPushButton(QtGui.QIcon(ilastikIcons.Select),'Choose Border Probability Overlay')
        self.btnSegment = QtGui.QPushButton(QtGui.QIcon(ilastikIcons.Play),'Segment')
        #self.btnSegmentorsOptions = QtGui.QPushButton(QtGui.QIcon(ilastikIcons.System),'Segmentors Options')
        
        self.btnChooseWeights.setToolTip('Choose the input overlay that contains border probabilities')
        self.btnSegment.setToolTip('Segment the image')
        #self.btnSegmentorsOptions.setToolTip('Select a segmentation plugin and change settings')
        
        tl.addWidget(self.btnChooseWeights)
        tl.addWidget(self.btnSegment)
        tl.addStretch()
        #tl.addWidget(self.btnSegmentorsOptions)
        
        self.setLayout(tl)
        
    def _initConnects(self):
        self.connect(self.btnChooseWeights, QtCore.SIGNAL('clicked()'), self.on_btnChooseWeights_clicked)
        self.connect(self.btnSegment, QtCore.SIGNAL('clicked()'), self.on_btnSegment_clicked)
        #self.connect(self.btnSegmentorsOptions, QtCore.SIGNAL('clicked()'), self.on_btnSegmentorsOptions_clicked)
        
        
    def on_btnChooseWeights_clicked(self):
        dlg = OverlaySelectionDialog(self.ilastik,  singleSelection = True)
        answer = dlg.exec_()
        
        if len(answer) > 0:
            overlay = answer[0]
            self.parent.labelWidget.overlayWidget.addOverlayRef(overlay.getRef())
            
            volume = overlay._data[0,:,:,:,0]
            print numpy.max(volume),  numpy.min(volume)
    
            #real_weights = numpy.zeros(volume.shape + (3,))        
            
            borderIndicator = QtGui.QInputDialog.getItem(self.ilastik, "Select border indicator type", "Select the border probability type : \n (Normal: bright pixels mean high border probability, Inverted: dark pixels mean high border probability) ",  ["Normal",  "Inverted"],  editable = False)
            borderIndicator = str(borderIndicator[0])
            
            weights = self.parent.project.dataMgr.Automatic_Segmentation.invertPotential()
            weights = self.parent.project.dataMgr.Automatic_Segmentation.normalizePotential()

            self.weights = weights
            
        
    def on_btnSegment_clicked(self):
        
        if self.weights is not None:
            self.parent.project.dataMgr.Automatic_Segmentation.computeResults(self.weights)
            self.parent.project.dataMgr.Automatic_Segmentation.finalizeResults()
            
            self.parent.labelWidget.repaint()
        
    def on_btnSegmentorsOptions_clicked(self):
        pass
        #dialog = AutoSegmentorSelectionDlg(self.parent)
        #answer = dialog.exec_()
        #if answer != None:
        #    self.parent.project.autoSegmentor = answer
        #    self.parent.project.autoSegmentor.setupWeights(self.parent.project.dataMgr[self.parent._activeImageNumber].autoSegmentationWeights)

