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

from ilastik.core import dataMgr as dataMgrModule
from ilastik.core import ILASTIK_VERSION
import numpy
import traceback

import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import h5py
from ilastik.core.utilities import irange, debug
from ilastik.core.overlayMgr import OverlayItem

from vigra import arraytypes as at
from PyQt4 import QtGui

#from ilastik.core.unsupervised import unsupervisedPCA

class Project(object):
    """
    Import/Export for the whole project, including any data, settings, labels etc.
    """
    def __init__(self, name, labeler, description, dataMgr, labelNames=None, labelColors=None):
        if labelNames is None:
            labelNames = []
        if labelColors is None:
            labelColors = {}     
        self.filename = None
        self.fastRepaint = True
        self.useBorderMargin = False
        self.normalizeData = False
        self.drawUpdateInterval = 300
        self.rgbData = True
        self.name = name
        self.labeler = labeler
        self.description = description
        self.dataMgr = dataMgr
        self.labelNames = labelNames
        self.labelColors = labelColors
        self.trainingMatrix = None
        self.trainingLabels = None
        self.trainingFeatureNames = None

        #self.unsupervisedDecomposer = None # unsupervisedPCA.UnsupervisedPCA() #core.unsupervised.unsupervisedClasses[0]()
        
 
    def saveToDisk(self, fileName = None):
        """ Save the whole project including data, feautues, labels and settings to 
        and hdf5 file with ending ilp """
        try:
            if fileName is not None:
                self.filename = fileName
            else:
                fileName = self.filename
                
            fileHandle = h5py.File(fileName,'w')
            
            fileHandle.create_dataset('ilastikVersion', data=ILASTIK_VERSION)

            projectG = fileHandle.create_group('Project') 
            dataSetG = fileHandle.create_group('DataSets')             
            
            projectG.create_dataset('Name', data=str(self.name))
            projectG.create_dataset('Labeler', data=str(self.labeler))
            projectG.create_dataset('Description', data=str(self.description))
                
            self.dataMgr.serialize(projectG, dataSetG)
            # Save to hdf5 file
            fileHandle.close()
            
            #TODO, integrate somehow into serialization scheme
            self.dataMgr.module["Classification"].exportClassifiers(fileName,'Project/')
            
        except Exception as e:
            print e.message
            traceback.print_exc()
            return False
        return True
    
    @staticmethod
    def loadFromDisk(fileName, featureCache):
        fileHandle = h5py.File(fileName,'r')
        # p = pickle.load(fileHandle)
        
        # extract basic project settings
        projectG = fileHandle['Project']
        dataG = fileHandle['DataSets']
        name = projectG['Name'].value
        labeler = projectG['Labeler'].value 
        description = projectG['Description'].value
        # init dataMgr 
        
        n = len(dataG)
        
        dataMgr = dataMgrModule.DataMgr.deserialize(projectG, dataG)

        
        project = Project( name, labeler, description, dataMgr)
        project.filename = fileName
        
        fileHandle.close()
        return project
        
  

