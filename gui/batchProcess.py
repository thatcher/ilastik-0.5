# -*- coding: utf-8 -*-
"""
Created on Mon Mar 22 09:33:57 2010

@author: - 
"""


import os, glob
import vigra
import numpy

import numpy
import sys

import vigra
import getopt
import h5py
import glob

from PyQt4 import QtCore, QtGui, uic

import sys
sys.path.append( os.path.join(os.getcwd(), '..') )

import volumeeditor as ve

from core import dataMgr
from core import classificationMgr as cm

class BatchProcess(QtGui.QDialog):
    def __init__(self, parent):
        QtGui.QWidget.__init__(self)
        self.ilastik = parent
        self.setMinimumWidth(400)
        self.layout = QtGui.QVBoxLayout()
        self.setLayout(self.layout)

        tempLayout = QtGui.QHBoxLayout()
        self.path = QtGui.QLineEdit("")
        self.connect(self.path, QtCore.SIGNAL("textChanged(QString)"), self.pathChanged)
        self.pathButton = QtGui.QPushButton("Select")
        self.connect(self.pathButton, QtCore.SIGNAL('clicked()'), self.slotDir)
        tempLayout.addWidget(self.path)
        tempLayout.addWidget(self.pathButton)
        self.layout.addWidget(QtGui.QLabel("Path to Image Stack:"))
        self.layout.addLayout(tempLayout)


        tempLayout = QtGui.QHBoxLayout()
        self.cancelButton = QtGui.QPushButton("Cancel")
        self.connect(self.cancelButton, QtCore.SIGNAL('clicked()'), self.reject)
        self.okButton = QtGui.QPushButton("Ok")
        self.okButton.setEnabled(False)
        self.connect(self.okButton, QtCore.SIGNAL('clicked()'), self.accept)
        self.loadButton = QtGui.QPushButton("Process")
        self.connect(self.loadButton, QtCore.SIGNAL('clicked()'), self.slotProcess)
        tempLayout.addStretch()
        tempLayout.addWidget(self.cancelButton)
        tempLayout.addWidget(self.okButton)
        tempLayout.addWidget(self.loadButton)
        self.layout.addStretch()
        self.layout.addLayout(tempLayout)
        
        
        self.logger = QtGui.QPlainTextEdit()
        self.logger.setVisible(False)
        self.layout.addWidget(self.logger)        
        self.image = None
        
        
        self.dataMgr = dataMgr.DataMgr()
        
        


    def pathChanged(self, text):
        list = glob.glob(str(self.path.text()) )


    def slotDir(self):
        path = self.path.text()
        filename = QtGui.QFileDialog.getExistingDirectory(self, "Image Stack Directory", path)
        self.path.setText(filename + "/*")

    def slotProcess(self):
        pattern = self.path.text()
        self.process(str(pattern))
    
    def process(self, pattern):
        self.logger.clear()
        self.logger.setVisible(True)
  
        #loop over provided images an put them in the hdf5
        z = 0
        allok = True
        for filename in sorted(glob.glob(pattern), key = str.lower):
            di = dataMgr.DataItemImage(filename)
            di.loadData()
            self.dataMgr.append(di)
            
            self.ilastik.project.featureMgr.prepareCompute(self.dataMgr)  
            self.ilastik.project.featureMgr.triggerCompute()
            self.ilastik.project.featureMgr.joinCompute(self.dataMgr)
            
            
            self.dataMgr.buildFeatureMatrix()
            
            self.dataMgr.classifiers = self.ilastik.project.dataMgr.classifiers

            classificationPredict = cm.ClassifierPredictThread(self.dataMgr)
            classificationPredict.start()
            classificationPredict.wait()            
            
            
            #save results
            try:
                f = h5py.File(filename + '_processed', 'w')
                g = f.create_group("volume")        
                self.dataMgr[0].dataVol.data.serialize(g, 'data')
                da = ve.DataAccessor(self.dataMgr[0].prediction, channels = True)
                da.serialize(g, 'prediction')
                f.close()
                self.logger.insertPlainText(".")
            except Exception as e:
                print "######Exception"
                print e
                allok = False
                self.logger.appendPlainText("Error processing file " + filename + ", " + str(e))
                self.logger.appendPlainText("")                
            
            
            self.dataMgr.clearDataList()
            self.logger.repaint()
            
        if allok:
            self.logger.appendPlainText("Batch processing finished")            
            self.okButton.setEnabled(True)
        
    def exec_(self):
        if super(BatchProcess, self).exec_() == QtGui.QDialog.Accepted:
            return  self.image
        else:
            return None
       
def test():
    """Text editor demo"""
    import numpy
    app = QtGui.QApplication([""])
    
    dialog = BatchProcess()
    print dialog.show()
    app.exec_()


if __name__ == "__main__":
    test()