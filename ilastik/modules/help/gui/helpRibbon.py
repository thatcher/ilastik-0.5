import numpy, vigra
import random

from ilastik.gui.ribbons.ilastikTabBase import IlastikTabBase

from PyQt4 import QtGui, QtCore

from ilastik.gui.iconMgr import ilastikIcons

from ilastik.gui.overlaySelectionDlg import OverlaySelectionDialog
from ilastik.gui.overlayWidget import OverlayWidget
from ilastik.gui.shortcutmanager import shortcutManager

class HelpTab(IlastikTabBase, QtGui.QWidget):
    name = 'Help'
    def __init__(self, parent=None):
        IlastikTabBase.__init__(self, parent)
        QtGui.QWidget.__init__(self, parent)
        
        self._initContent()
        self._initConnects()
        
    def on_activation(self):
        print 'Changed to Tab: ', self.__class__.name
       
    def on_deActivation(self):
        print 'Left Tab ', self.__class__.name
        
    def _initContent(self):

        tl = QtGui.QHBoxLayout()      
        self.btnShortcuts = QtGui.QPushButton(QtGui.QIcon(ilastikIcons.Help),'Shortcuts')
      
        self.btnShortcuts.setToolTip('Show a list of ilastik shortcuts')
        
        tl.addWidget(self.btnShortcuts)
        tl.addStretch()
        
        self.setLayout(tl)
        #self.shortcutManager = shortcutManager()
        
    def _initConnects(self):
        self.connect(self.btnShortcuts, QtCore.SIGNAL('clicked()'), self.on_btnShortcuts_clicked)
        
    def on_btnShortcuts_clicked(self):
        shortcutManager.showDialog()