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

class StackLoader(QtGui.QDialog):
    def __init__(self):
        QtGui.QWidget.__init__(self)
        self.setMinimumWidth(400)
        self.layout = QtGui.QVBoxLayout()
        self.setLayout(self.layout)

        tempLayout = QtGui.QHBoxLayout()
        self.path = QtGui.QLineEdit("")
        self.pathButton = QtGui.QPushButton("Select")
        self.connect(self.pathButton, QtCore.SIGNAL('clicked()'), self.slotDir)
        tempLayout.addWidget(self.path)
        tempLayout.addWidget(self.pathButton)
        self.layout.addWidget(QtGui.QLabel("Path to Image Stack:"))
        self.layout.addLayout(tempLayout)


        tempLayout = QtGui.QHBoxLayout()
        self.offsetX = QtGui.QSpinBox()
        self.offsetX.setRange(0,10000)
        self.offsetY = QtGui.QSpinBox()
        self.offsetY.setRange(0,10000)
        self.offsetZ = QtGui.QSpinBox()
        self.offsetZ.setRange(0,10000)
        tempLayout.addWidget( self.offsetX)
        tempLayout.addWidget( self.offsetY)
        tempLayout.addWidget( self.offsetZ)
        self.layout.addWidget(QtGui.QLabel("Offsets:"))
        self.layout.addLayout(tempLayout)
        
        tempLayout = QtGui.QHBoxLayout()
        self.sizeX = QtGui.QSpinBox()
        self.sizeX.setRange(0,10000)
        self.sizeY = QtGui.QSpinBox()
        self.sizeY.setRange(0,10000)
        self.sizeZ = QtGui.QSpinBox()
        self.sizeZ.setRange(0,10000)
        tempLayout.addWidget( self.sizeX)
        tempLayout.addWidget( self.sizeY)
        tempLayout.addWidget( self.sizeZ)
        self.layout.addWidget(QtGui.QLabel("Dimensions:"))
        self.layout.addLayout(tempLayout)

        tempLayout = QtGui.QHBoxLayout()
        self.invert = QtGui.QCheckBox()
        tempLayout.addWidget(self.invert)
        tempLayout.addWidget(QtGui.QLabel("Invert Colors?"))
        tempLayout.addStretch()
        self.layout.addLayout(tempLayout) 

        tempLayout = QtGui.QHBoxLayout()
        self.normalize = QtGui.QCheckBox()
        tempLayout.addWidget(self.normalize)
        tempLayout.addWidget(QtGui.QLabel("Normalize?"))
        tempLayout.addStretch()
        self.layout.addLayout(tempLayout) 


        tempLayout = QtGui.QHBoxLayout()
        self.downsample = QtGui.QCheckBox()
        tempLayout.addWidget(self.downsample)
        tempLayout.addWidget(QtGui.QLabel("Downsample To:"))
        tempLayout.addStretch()
        self.layout.addLayout(tempLayout)

        tempLayout = QtGui.QHBoxLayout()
        self.downX = QtGui.QSpinBox()
        self.downX.setRange(0,10000)
        self.downY = QtGui.QSpinBox()
        self.downY.setRange(0,10000)
        self.downZ = QtGui.QSpinBox()
        self.downZ.setRange(0,10000)
        tempLayout.addWidget( self.downX)
        tempLayout.addWidget( self.downY)
        tempLayout.addWidget( self.downZ)
        self.layout.addLayout(tempLayout)
    
        
        tempLayout = QtGui.QHBoxLayout()
        self.alsoSave = QtGui.QCheckBox()
        tempLayout.addWidget(self.alsoSave)
        tempLayout.addWidget(QtGui.QLabel("also save to Destination File:"))
        tempLayout.addStretch()
        self.layout.addLayout(tempLayout) 

        tempLayout = QtGui.QHBoxLayout()
        self.fileButton = QtGui.QPushButton("Select")
        self.connect(self.fileButton, QtCore.SIGNAL('clicked()'), self.slotFile)
        self.file = QtGui.QLineEdit("")
        tempLayout.addWidget(self.file)
        tempLayout.addWidget(self.fileButton)
        self.layout.addLayout(tempLayout)        
        
        
        
        tempLayout = QtGui.QHBoxLayout()
        self.cancelButton = QtGui.QPushButton("Cancel")
        self.connect(self.cancelButton, QtCore.SIGNAL('clicked()'), self.close)
        self.okButton = QtGui.QPushButton("Load")
        self.connect(self.okButton, QtCore.SIGNAL('clicked()'), self.slotLoad)
        tempLayout.addWidget(self.cancelButton)
        tempLayout.addWidget(self.okButton)
        self.layout.addLayout(tempLayout)
                
        self.image = None


    def slotDir(self):
        path = self.path.text()
        filename = QtGui.QFileDialog.getExistingDirectory(self, "Image Stack Directory", path)
        self.path.setText(filename + "/*")
        list = glob.glob(str(self.path.text()) )
        self.sizeX.setValue(len(list))
        temp = vigra.impex.readImage(list[0])
        self.sizeY.setValue(temp.shape[0])
        self.sizeZ.setValue(temp.shape[1])

    def slotFile(self):
        filename= QtGui.QFileDialog.getSaveFileName(self, "Save to File", "*.h5")
        self.file.setText(filename)

    def slotLoad(self):
        offsets = (self.offsetX.value(),self.offsetY.value(),self.offsetZ.value())
        shape = (self.sizeX.value(),self.sizeY.value(),self.sizeZ.value())
        destShape = None
        if self.downsample.checkState() > 0:
            destShape = (self.downX.value(),self.downY.value(),self.downZ.value())
        filename = str(self.file.text())
        if self.alsoSave.checkState() == 0:
            filename = None
        normalize = self.normalize.checkState() > 0
        invert = self.invert.checkState() > 0
        self.load(str(self.path.text()), offsets, shape, destShape, filename, normalize, invert)
    
    def load(self, pattern,  offsets, shape, destShape = None, destfile = None, normalize = False, invert = False):
           
        self.image = numpy.zeros(shape, 'float32')
    
        #loop over provided images an put them in the hdf5
        z = 0
        for filename in sorted(glob.glob(pattern), key = str.lower):
            if z >= offsets[0] and z < offsets[0] + shape[0]:
                try:
                    img_data = vigra.impex.readImage(filename)
                    if invert:
                        self.image[z-offsets[0],:,:] = 255 - img_data[offsets[1]:offsets[1]+shape[1], offsets[2]:offsets[2]+shape[2]]
                    else:
                        self.image[z-offsets[0],:,:] = img_data[offsets[1]:offsets[1]+shape[1], offsets[2]:offsets[2]+shape[2]]
                except:
                    print "######ERROR loading File ", filename 
            z = z + 1
                 
        if destShape is not None:
            result = vigra.sampling.resizeVolumeSplineInterpolation(self.image.view(vigra.Volume),destShape)
            self.image = result
        else:
            destShape = shape
        
        if normalize:
            maximum = numpy.max(self.image)
            minimum = numpy.min(self.image)
            self.image = self.image * (255.0 / (maximum - minimum)) - minimum

                    
        self.image = self.image.reshape(1,destShape[0],destShape[1],destShape[2],1)
        if destfile != None :
            f = h5py.File(destfile, 'w')
            g = f.create_group("volume")        
            g.create_dataset("data",data = self.image)
            f.close()
        super(StackLoader, self).accept()
        
    def exec_(self):
        super(StackLoader, self).exec_()
        return  self.image
       
def test():
    """Text editor demo"""
    import numpy
    from spyderlib.utils.qthelpers import qapplication
    app = qapplication()
    
    dialog = StackLoader()
    print dialog.show()
    app.exec_()


if __name__ == "__main__":
    test()