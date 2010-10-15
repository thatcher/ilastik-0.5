# -*- coding: utf-8 -*-
import vigra
import gc
from ilastik.gui.ribbons.ilastikTabBase import IlastikTabBase
from PyQt4 import QtGui, QtCore
from ilastik.gui.iconMgr import ilastikIcons

import ilastik.gui
from projectDialog import ProjectDlg, ProjectSettingsDlg
from ilastik.core import projectMgr
from ilastik.gui.overlayWidget import OverlayWidget
from ilastik.gui import volumeeditor as ve

class ProjectTab(IlastikTabBase, QtGui.QWidget):
    name = 'Project'
    position = 0
    moduleName = "Project"
    
    def __init__(self, parent=None):
        IlastikTabBase.__init__(self, parent)
        QtGui.QWidget.__init__(self, parent)
        self._initContent()
        self._initConnects()
        
    def on_activation(self):
        if self.ilastik.project is None:
            self.ilastik.setTabBusy(True)
            return
        ovs = self.ilastik._activeImage.module[self.__class__.moduleName].getOverlayRefs()
        if len(ovs) == 0:
            raw = self.ilastik._activeImage.overlayMgr["Raw Data"]
            if raw is not None:
                ovs.append(raw.getRef())
        
        self.ilastik.labelWidget._history.volumeEditor = self.ilastik.labelWidget

        overlayWidget = OverlayWidget(self.ilastik.labelWidget, self.ilastik._activeImage.overlayMgr,  ovs)
        self.ilastik.labelWidget.setOverlayWidget(overlayWidget)
        
        self.ilastik.labelWidget.setLabelWidget(ve.DummyLabelWidget())
    
    def on_deActivation(self):
        pass
        
    def _initContent(self):
        tl = QtGui.QHBoxLayout()
        
        self.btnNew = QtGui.QPushButton(QtGui.QIcon(ilastikIcons.New),'New')
        self.btnOpen = QtGui.QPushButton(QtGui.QIcon(ilastikIcons.Open),'Open')
        self.btnSave = QtGui.QPushButton(QtGui.QIcon(ilastikIcons.Save),'Save')
        self.btnEdit = QtGui.QPushButton(QtGui.QIcon(ilastikIcons.Edit),'Edit')
        self.btnOptions = QtGui.QPushButton(QtGui.QIcon(ilastikIcons.Edit),'Options')
        
        self.btnNew.setToolTip('Create new project')
        self.btnOpen.setToolTip('Open existing project')
        self.btnSave.setToolTip('Save current project to file')
        self.btnEdit.setToolTip('Edit current project')
        self.btnOptions.setToolTip('Edit ilastik options')
        
        tl.addWidget(self.btnNew)
        tl.addWidget(self.btnOpen)
        tl.addWidget(self.btnSave)
        tl.addWidget(self.btnEdit)
        tl.addStretch()
        tl.addWidget(self.btnOptions)
        
        self.btnSave.setEnabled(False)
        self.btnEdit.setEnabled(False)
        self.btnOptions.setEnabled(False)
        
        self.setLayout(tl)
        
    def _initConnects(self):
        self.connect(self.btnNew, QtCore.SIGNAL('clicked()'), self.on_btnNew_clicked)
        self.connect(self.btnOpen, QtCore.SIGNAL('clicked()'), self.on_btnOpen_clicked)
        self.connect(self.btnSave, QtCore.SIGNAL('clicked()'), self.on_btnSave_clicked)
        self.connect(self.btnEdit, QtCore.SIGNAL('clicked()'), self.on_btnEdit_clicked)
        self.connect(self.btnOptions, QtCore.SIGNAL('clicked()'), self.on_btnOptions_clicked)
        
    # Custom Callbacks
    def on_btnNew_clicked(self):
        self.parent.projectDlg = ProjectDlg(self.parent)
        if self.parent.projectDlg.exec_() == QtGui.QDialog.Accepted:
            self.btnSave.setEnabled(True)
            self.btnEdit.setEnabled(True)
            self.btnOptions.setEnabled(True)
            self.parent.updateFileSelector()
            self.parent._activeImageNumber = 0
            self.ilastik.setTabBusy(False)
            
    def on_btnSave_clicked(self):
        fileName = QtGui.QFileDialog.getSaveFileName(self, "Save Project", ilastik.gui.LAST_DIRECTORY, "Project Files (*.ilp)")
        fn = str(fileName)
        if len(fn) > 4:
            if fn[-4:] != '.ilp':
                fn = fn + '.ilp'
            if self.parent.project.saveToDisk(fn):
                QtGui.QMessageBox.information(self.parent, 'Success', "The project has been saved successfully to:\n %s" % str(fileName), QtGui.QMessageBox.Ok)
                
            ilastik.gui.LAST_DIRECTORY = QtCore.QFileInfo(fn).path()
    
    def on_btnOpen_clicked(self):
        fileName = QtGui.QFileDialog.getOpenFileName(self, "Open Project", ilastik.gui.LAST_DIRECTORY, "Project Files (*.ilp)")
        if str(fileName) != "":
            labelWidget = None
            #if self.parent.project is not None:
            #    if len(self.parent.project.dataMgr) > self.parent._activeImageNumber:
            #        labelWidget = weakref.ref(self.parent.project.dataMgr[self.parent._activeImageNumber])#.featureBlockAccessor)
            self.parent.project = projectMgr.Project.loadFromDisk(str(fileName), self.parent.featureCache)
            self.btnSave.setEnabled(True)
            self.btnEdit.setEnabled(True)
            self.btnOptions.setEnabled(True)
            self.parent.changeImage(0)
            self.parent.updateFileSelector()
            self.ilastik.setTabBusy(False)
            ilastik.gui.LAST_DIRECTORY = QtCore.QFileInfo(fileName).path()
            gc.collect()
            if labelWidget is not None:
                if labelWidget() is not None:
                    refs =  gc.get_referrers(labelWidget())
                    for i,r in enumerate(refs):
                        print type(r)
                        print "##################################################################"
                        print r
   
    def on_btnEdit_clicked(self):
        self.parent.projectDlg = ProjectDlg(self.parent, False)
        self.parent.projectDlg.updateDlg(self.parent.project)
        self.parent.projectModified()
        
    def on_btnOptions_clicked(self):
        tmp = ProjectSettingsDlg(self.ilastik, self.ilastik.project)
        tmp.exec_()