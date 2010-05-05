import numpy
import sys
from Queue import Queue as queue
from copy import copy
import os
import h5py
import h5py as tables # TODO: exchange tables with h5py
from core.utilities import irange, debug, irangeIfTrue

import vigra
at = vigra.arraytypes
    

class DataItemBase():
    """
    Data Base class, serves as an interface for the specialized data structures, e.g. images, multispectral, volume etc.  
    """
    #3D: important
    def __init__(self, fileName):
        self.fileName = str(fileName)
        self.hasLabels = False
        self.isTraining = True
        self.isTesting = False
        self.groupMember = []
        self.projects = []
        
        self.data = None
        self.labels = None
        self.dataKind = None
        self.dataType = []
        self.dataDimensions = 0
        self.thumbnail = None
        self.shape = ()
        self.channelDescription = []
        self.channelUsed = []
        
    def shape(self):
        if self.dataKind in ['rgb', 'multi', 'gray']:
            return self.shape[0:2]
        
    def loadData(self):
        self.data = "This is not an Image..."
    
    def unpackChannels(self):
        if self.dataKind in ['rgb']:
            return [ self.data[:,:,k] for k in range(0,3) ]
        elif self.dataKind in ['multi']:
            return [ self.data[:,:,k] for k in irangeIfTrue(self.channelUsed)]
        elif self.dataKind in ['gray']:
            return [ self.data ]   

class DataItemImage(DataItemBase):
    def __init__(self, fileName):
        DataItemBase.__init__(self, fileName) 
        self.dataDimensions = 2
        self.overlayImage = None
       
    def loadData(self):
        fBase, fExt = os.path.splitext(self.fileName)
        if fExt == '.h5':
            self.data, self.channelDescription, self.labels, self.overlayImage = DataImpex.loadMultispectralData(self.fileName)
            
        else:
            self.data = DataImpex.loadImageData(self.fileName)
            self.labels = at.ScalarImage(self.data.shape[0:2],at.uint8)
        #print "Shape after Loading and width",self.data.shape, self.data.width
        self.extractDataAttributes()
    
    def extractDataAttributes(self):
        self.dataType = self.data.dtype
        self.shape = self.data.shape
        if len(self.data.shape) == 3:
            if self.data.shape[2] == 3:
                self.dataKind = 'rgb'
                self.channelDescription = ['Red','Green','Blue']
                self.channelUsed = [True] * len(self.channelDescription)
            elif self.data.shape[2] > 3:
                self.dataKind = 'multi'
                self.channelUsed = [True] * len(self.channelDescription)
                # self.channelDescription have been set by load Method
        elif len(self.data.shape) == 2:
            self.dataKind = 'gray'
            self.channelDescription = ['Intensities']
            self.channelUsed = [True]
    
    @classmethod
    def initFromArray(cls, dataArray, originalFileName):
        obj = cls(originalFileName)
        obj.data = dataArray
        obj.extractDataAttributes()
        return obj
        
    
            
    def unLoadData(self):
        # TODO: delete permanently here for better garbage collection
        self.data = None
        
class DataItemVolume(DataItemBase):
    #3D: important
    def __init__(self, fileName):
        DataItemBase.__init__(self, fileName) 
       
    def loadData(self):
        self.data = vigra.impex.readVolume(self.fileName)
        self.dataDimensions = 3
        self.dataType = self.data.dtype
        if len(self.data.shape) == 4:
            if self.data.shape[3] == 3:
                self.dataKind = 'rgb'
            elif self.data.shape[3] > 3:
                self.dataKind = 'multi'
        elif len(self.data.shape) == 3:
            self.dataKind = 'gray'
            
    def unLoadData(self):
        # TODO: delete permanently here for better garbage collection
        self.data = None
    
        
class DataMgr():
    """
    Manages Project structure and associated files, e.g. images volumedata
    """
    #TODO: does not unload data, maybe implement some sort of reference counting if memory scarceness manifests itself
    
    def __init__(self, dataItems=None):
        if dataItems is None:
            dataItems = []            
        self.setDataList(dataItems)
        self.dataFeatures = [None] * len(dataItems)
        self.prediction = [None] * len(dataItems)
        self.segmentation = [None] * len(dataItems)
        self.labels = {}
        
    def setDataList(self, dataItems):
        self.dataItems = dataItems
        self.dataItemsLoaded = [False] * len(dataItems)
        self.segmentation = [None] * len(dataItems)
        self.prediction = [None] * len(dataItems)
        self.uncertainty = [None] * len(dataItems)
        
    def append(self, dataItem):
        self.dataItems.append(dataItem)
        self.dataItemsLoaded.append(False)
        self.segmentation.append(None)
        self.prediction.append(None)
        self.uncertainty.append(None)
        
        
    def getDataList(self):
        return self.dataItems
        
    def dataItemsShapes(self):     
        return map(DataItemBase.shape, self)
        
        
    def __getitem__(self, ind):
        if not self.dataItemsLoaded[ind]:
            self.dataItems[ind].loadData()
            self.dataItemsLoaded[ind] = True
        return self.dataItems[ind]
    
    def __setitem__(self, ind, val):
        self.dataItems[ind] = val
        self.dataItemsLoaded[ind] = True
    
    def getIndexFromFileName(self, fileName):
        for k, dataItem in irange(self.dataItems):
            if fileName == dataItem.fileName:
                return k
        return False
    
    def remove(self, dataItemIndex):
        del self.dataItems[dataItemIndex]
        del self.dataItemsLoaded[dataItemIndex]
        del self.segmentation[dataItemIndex]
        del self.prediction[dataItemIndex]
        del self.uncertainty[dataItemIndex]
    
    def clearDataList(self):
        self.dataItems = []
        self.dataFeatures = []
        self.labels = {}
    
    def __len__(self):
        return len(self.dataItems)
    
    def buildFeatureMatrix(self):
        self.featureMatrixList = [] 
        for dataFeatures in self.dataFeatures:
            fTuple = []
            for features in dataFeatures:
                f = features[0]
                fSize = f.shape[0] * f.shape[1] 
                if len(f.shape) == 2:
                    f = f.reshape(fSize,1)
                else:
                    f = f.reshape(fSize,f.shape[2])    
                fTuple.append(f)
            self.featureMatrixList.append( numpy.concatenate(fTuple,axis=1) )
        return self.featureMatrixList
    
    def buildTrainingMatrix(self):  
        #3D: extremely important, make the dimensionality test of 
        #returned feature image depend upon the dimensionality of the data
        res_labels = [] 
        res_names = []
        res_features = []
        for dataInd , dataFeatures in irange(self.dataFeatures):
            res_features_tmp = []
            #labels = at.ScalarImage(self.dataItems[dataInd].labels).flatten() 
            labels = self.dataItems[dataInd].labels.flatten() 
            label_inds = labels.nonzero()[0]
            labels = labels[label_inds]      
            nLabels = label_inds.shape[0]

            for featureImage, featureString, c_ind in dataFeatures:
                n = 1   # n: number of feature-values per pixel
                if featureImage.ndim > 2: #3D: fails with 3D data !!!
                                          #this checks the dimensionality of the feature, should be adapted for 3d
                    n = featureImage.shape[2]
                if n == 1:
                    res_features_tmp.append(featureImage.flat[label_inds].reshape(1, nLabels))
                    res_names.append(featureString)
                else:
                    for featureDim in xrange(n):
                        res_features_tmp.append(featureImage[:, :, featureDim].flat[label_inds].reshape(1, nLabels))
                        res_names.append(featureString + "_%i" % (featureDim))

            res_features.append(numpy.concatenate(res_features_tmp).T)
            res_labels.append(labels)
        
        return numpy.concatenate(res_features), numpy.concatenate(res_labels), res_names
    
    def export2Hdf5(self, fileName):
        for imageIndex, dataFeatures in irange(self.dataFeatures):
            groupName = os.path.split(self[imageIndex].fileName)[-1]
            groupName, dummy = os.path.splitext(groupName)
            F = {}
            F_name = {}
            prefix = 'Channel'
            for feat, f_name, channel_ind in dataFeatures:
                if not F.has_key('%s%03d' % (prefix,channel_ind)):
                    F['%s%03d' % (prefix,channel_ind)] = []
                if not F_name.has_key('%s%03d' % (prefix,channel_ind)):
                    F_name['%s%03d' % (prefix,channel_ind)] = []
                
                if len(feat.shape) == 2:
                    feat.shape = feat.shape +  (1,)
                    
                F['%s%03d' % (prefix,channel_ind)].append(feat)
                F_name['%s%03d' % (prefix,channel_ind)].append(f_name)
                
            F_res = {}
            for f in F:
                F_res[f] = numpy.concatenate(F[f], axis=2)
            
            P = self.prediction[imageIndex]
            if P is not None:
                F_res['Prediction'] = P.reshape(self[imageIndex].shape[0:2] +(-1,))
            
            
            
            L = {}
            L['Labels'] = self[imageIndex].labels
             
                
            DataImpex.exportFeatureLabel2Hdf5(F_res, L, fileName, groupName)
            print "Object saved to disk: %s" % fileName
        
        

class DataImpex(object):
    """
    Data Import/Export class 
    """
    @staticmethod
    def loadMultispectralData(fileName):
        h5file = h5py.File(fileName,'r')       
        try:
            if 'data' in h5file.listnames():
                data = at.Image(h5file['data'].value, at.float32)
            else:
                print 'No "data"-field contained in: %s ' % fileName
                return -1
            
            if 'labels' in h5file.listnames():
                labels = at.ScalarImage(h5file['labels'].value, at.uint8)
            else:
                print 'No "labels"-field contained in: %s ' % fileName
                labels = at.ScalarImage(data.shape[0:2], at.uint8)
            
            if 'channelNames' in h5file.listnames():
                channelNames = h5file['channelNames'].value
                channelNames = map(str,channelNames[:,0])
            else:
                print 'No "channelNames"-field contained in: %s ' % fileName
                channelNames = map(str, range(data.shape[2]))
            if 'overlayImage' in h5file.listnames():
                overlayImage = at.Image(h5file['overlayImage'].value)
            else:
                print 'No "overlayImage"-field contained in: %s ' % fileName
                overlayImage = None
                               
        except Exception as e:
            print "Error while reading H5 File %s " % fileName
            print e
        finally:
            h5file.close()
            
        return (data, channelNames, labels, overlayImage)
    
    @staticmethod
    def loadImageData(fileName):
        # I have to do a cast to at.Image which is useless in here, BUT, when i py2exe it,
        # the result of vigra.impex.readImage is numpy.ndarray? I don't know why... (see featureMgr compute)
        data = at.Image(vigra.impex.readImage(fileName))
        return data
    
    @staticmethod    
    def _exportFeatureLabel2Hdf5(features, labels, h5file, h5group):
        try:
            h5group = h5file.createGroup(h5file.root, h5group, 'Some Title')
        except tables.NodeError as ne:
            print ne
            print "_exportFeatureLabel2Hdf5: Overwriting"
            h5file.removeNode(h5file.root, h5group, recursive=True)
            h5group = h5file.createGroup(h5file.root, h5group, 'Some Title')
        
        cnt = 0
        for key in features:
            val = features[key]    
            #print val.flags
            tmp = h5file.createArray(h5group, key, val, "Description")
            
            tmp._v_attrs.order = cnt
            tmp._v_attrs.type = 'INPUT'
            tmp._v_attrs.scale = 'ORDINAL'
            tmp._v_attrs.domain = 'REAL'
            tmp._v_attrs.dimension = 2
            tmp._v_attrs.missing_label = 0
            cnt += 1
        
        for key in labels:
            val = labels[key]
            print val.flags
            print '***************'
            val = val.T
            print val.flags
            tmp = h5file.createArray(h5group, key  , val.T,  "Description")
            
            tmp._v_attrs.order = cnt
            tmp._v_attrs.type= 'OUTPUT'
            tmp._v_attrs.scale = 'NOMINAL'
            tmp._v_attrs.domain = numpy.array(range(int(val.max())+1))
            tmp._v_attrs.dimension = 2
            tmp._v_attrs.missing_label = 0
            cnt += 1    
            
    @staticmethod
    def exportFeatureLabel2Hdf5(features, labels, hFilename, h5group):
        if os.path.isfile(hFilename):
            mode = 'a'
        else:
            mode = 'w'
        h5file = tables.openFile(hFilename, mode = mode, title = "Ilastik File Version")
        
        try:
            DataImpex._exportFeatureLabel2Hdf5(features, labels, h5file, h5group)
        except Exception as e:
            print e
        finally:
            h5file.close() 
    
    @staticmethod
    def checkForLabels(fileName):
        fileName = str(fileName)
        fBase, fExt = os.path.splitext(fileName)
        if fExt != '.h5':
            return 0
               
        h5file = h5py.File(fileName,'r')       
        try:
            # Data sets below root are asumed to be data, labels and featureDescriptor
            if 'labels' in h5file.listnames():
                labels = h5file['labels'].value
                res = len(numpy.unique(labels)) - 1
                del labels
            else:
                res = 0
        except Exception as e:
            print "Error while reading H5 File %s " % fileName
            print e
        finally:
            h5file.close()
        return res
    
class channelMgr(object):
    def __init__(self, dataMgr):
        self.dataMgr = dataMgr
        self.compoundChannels = {'rgb':{},'gray':{},'multi':{}}
        
        self.registerCompoundChannels('rgb', 'TrueColor', self.compoundSelectChannelFunctor, [0,1,2]) 
        self.registerCompoundChannels('gray', 'Intensities', self.compoundSelectChannelFunctor, [0,1,2])
        self.registerCompoundChannels('multi', 'Channel:', self.compoundSelectChannelFunctor, 0)
        
    def channelConcatenation(self, dataInd, channelList):
        if self.dataMgr[dataInd].dataKind == 'gray':
            res = self.dataMgr[dataInd].data
        else:
            res = self.dataMgr[dataInd].data[:,:, channelList]
        return res
    
    def getDefaultDisplayImage(self, dataInd):
        if self.dataMgr[dataInd].dataKind == 'gray':
            res = channelConcatenation(self, dataInd, channelList)
        elif self.dataMgr[dataInd].dataKind == 'rgb':
            res = channelConcatenation(self, dataInd, [0,1,2])
        elif self.dataMgr[dataInd].dataKind == 'multi':
            res = channelConcatenation(self, dataInd, [0]) 
        return res 
    
    def registerCompoundChannels(self, dataKind, compoundName, compundFunctor, compundArg):
        self.compoundChannels[dataKind][compoundName] = lambda x,compundArg=compundArg:compundFunctor(x, compundArg)
    
    def compoundSelectChannelFunctor(self, data, selectionList):
        if data.ndim == 3:
            return data[:,:,selectionList]
        else:
            return data
        
        
        
        
    
    
        
        
        
        
        

                    
                    
                    
                
        
        


        
