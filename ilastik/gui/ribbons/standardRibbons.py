# -*- coding: utf-8 -*-

from PyQt4 import QtGui, QtCore

from ilastik.gui.ribbons.ilastikTabBase import IlastikTabBase, TabButton
from ilastik.gui.iconMgr import ilastikIcons
from ilastik.gui.overlaySelectionDlg import OverlaySelectionDialog
from ilastik.gui.overlayWidget import OverlayWidget
from ilastik.core.overlayMgr import OverlayItem

#*******************************************************************************
# C o n n e c t e d C o m p o n e n t s T a b                                  *
#*******************************************************************************

class ConnectedComponentsTab(IlastikTabBase, QtGui.QWidget):
    name = "Connected Components"
    def __init__(self, parent=None):
        IlastikTabBase.__init__(self, parent)
        QtGui.QWidget.__init__(self, parent)
        
        self._initContent()
        self._initConnects()
        
    def on_activation(self):
        if self.ilastik.project is None:
            return
        ovs = self.ilastik._activeImage._dataVol.backgroundOverlays
        if len(ovs) == 0:
            raw = self.ilastik._activeImage.overlayMgr["Raw Data"]
            if raw is not None:
                ovs.append(raw.getRef())
                        
        overlayWidget = OverlayWidget(self.ilastik.labelWidget, self.ilastik.project.dataMgr)
        self.ilastik.labelWidget.setOverlayWidget(overlayWidget)
        
        
        #create background overlay
        ov = OverlayItem(self.ilastik._activeImage._dataVol.background._data, color=0, alpha=1.0, colorTable = self.ilastik._activeImage._dataVol.background.getColorTab(), autoAdd = True, autoVisible = True, linkColorTable = True)
        self.ilastik._activeImage.overlayMgr["Connected Components/Background"] = ov
        ov = self.ilastik._activeImage.overlayMgr["Connected Components/Background"]
        
        self.ilastik.labelWidget.setLabelWidget(BackgroundWidget(self.ilastik.project.backgroundMgr, self.ilastik._activeImage._dataVol.background, self.ilastik.labelWidget, ov))    
    
    def on_deActivation(self):
        if self.ilastik.project is None:
            return
        self.ilastik._activeImage._dataVol.background._history = self.ilastik.labelWidget._history

        if self.ilastik._activeImage._dataVol.background._history is not None:
            self.ilastik.labelWidget._history = self.ilastik._activeImage._dataVol.background._history
        
    def _initContent(self):
        tl = QtGui.QHBoxLayout()
        tl.setMargin(0)
        
        self.btnInputOverlay = TabButton('Select Overlay', ilastikIcons.Select)
        self.btnCC           = TabButton('CC', ilastikIcons.System)
        self.btnCCBack       = TabButton('CC with background', ilastikIcons.System)
        self.btnCCOptions    = TabButton('Options', ilastikIcons.System)
        
        self.btnInputOverlay.setToolTip('Select an overlay for connected components search')
        self.btnCC.setToolTip('Run connected componets on the selected overlay')
        self.btnCCBack.setToolTip('Run connected components with background')
        self.btnCCOptions.setToolTip('Set options')
        
        self.btnInputOverlay.setEnabled(True)
        self.btnCC.setEnabled(False)
        self.btnCCBack.setEnabled(False)
        self.btnCCOptions.setEnabled(True)
        
        tl.addWidget(self.btnInputOverlay)
        tl.addWidget(self.btnCC)
        tl.addWidget(self.btnCCBack)
        tl.addStretch()
        tl.addWidget(self.btnCCOptions)
        
        self.setLayout(tl)
        
    def _initConnects(self):
        self.connect(self.btnInputOverlay, QtCore.SIGNAL('clicked()'), self.on_btnInputOverlay_clicked)
        self.connect(self.btnCC, QtCore.SIGNAL('clicked()'), self.on_btnCC_clicked)
        self.connect(self.btnCCBack, QtCore.SIGNAL('clicked()'), self.on_btnCCBack_clicked)
        #self.connect(self.btnCCOptions, QtCore.SIGNAL('clicked()'), self.on_btnCCOptions_clicked)
        
        
    def on_btnInputOverlay_clicked(self):
        dlg = OverlaySelectionDialog(self.ilastik,  singleSelection = True)
        answer = dlg.exec_()
        
        if len(answer) > 0:
            overlay = answer[0]
            self.parent.labelWidget.overlayWidget.addOverlayRef(overlay.getRef())
            print overlay.key
            self.parent.project.dataMgr.connCompBackgroundKey = overlay.key
            
        self.btnCC.setEnabled(True)
        self.btnCCBack.setEnabled(True)
        
    def on_btnCC_clicked(self):
        self.parent.on_connectComponents(background = False)
    def on_btnCCBack_clicked(self):
        self.parent.on_connectComponents(background = True)

        
        
    
    
    
