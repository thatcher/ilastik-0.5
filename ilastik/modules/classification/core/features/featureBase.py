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
import numpy
import ilastik.modules.classification.core.features
import vigra
class FeatureBase(object):
    """
    A Base class for feature plugins, all subclasses of this class
    are automatically loaded and available to the gui if the .py file 
    is in the core/features directory
    """

    name = "Virtual Base Feature"
    author = "HCI, University of Heidelberg"
    homepage = "http://hci.iwr.uni-heidelberg.de"

    groups = ['A', 'B']         #the feature groups in which the feature appears, for example 'Edge', 'Color', etc
    numOutputChannels2d = 1     #convenience attribute, only needed when computeSizeForShape is not reimplemented with custom functionality
    numOutputChannels3d = 1     #convenience attribute, only needed when computeSizeForShape is not reimplemented with custom functionality

    
    def __init__(self, sigma):
        self.sigma = sigma
        self.settings = { }
        self.minContext = sigma*3.5

    def getName(self):
        return self.name + " Sigma " + str(self.sigma)
    
    def getKey(self, c):
        return "Classification/Features/" + self.getName() + "/" + self.getName()+ " Channel " + str(c)

    def settings(self):
        """
        Reimplement this function if you want to display a Dialog where the user can change
        settings related to your feature algorithm.
        settings should be saved to the self.settings hash if you want to use the
        provided serialization and deserialization facilities
        """
        pass

    def compute(self, data):
        """
        arguments: data is a 3D numpy.ndarray
        result: numpy ndarray of shape: (data.shape + (numOutputChannels,))

        you plugin must reimplement this function, or the compute2d and compute3d functions.
        """
        if data.shape[0] > 1:
            res = self.compute3d(data)
            if len(res.shape) == 3:
                return res.reshape(res.shape + (1,))
            else:
                return res
        else:
            res = self.compute2d(data[0,:])
            if len(res.shape) == 2:
                res.shape = (1,) + res.shape + (1,)
            else:
                res.shape =  (1,) + res.shape
            return res

    def compute2d(self, data):
        pass

    def compute3d(self, data):
        pass


    def computeSizeForShape(self, shape, selectedChannels=None):
        if selectedChannels is None:
            numChannels = shape[-1]
        else:
            numChannels = len(selectedChannels)
        
        if shape[1] > 1:
            return self.__class__.numOutputChannels3d * numChannels
        else:
            return self.__class__.numOutputChannels2d * numChannels
        
    def applyToAllChannels(self, data, func, *args):
        result = []
        for channel in range(data.shape[-1]):
            t=data[...,channel].squeeze()
            
            tres = func(t, *args)
            if len(tres.shape) != len(data.shape):
                tres.shape = tres.shape + (1,)
            result.append(tres)
        return numpy.concatenate(result, axis=-1)
    
    def applySliceBySlice(self, data, func, *args):
        result=[]
        for channel in range(data.shape[-1]):
            #print "INTO SLICE BY SLICE", data.shape
            for slice in range(data.shape[-2]):
                tres = func(data[...,slice,channel].view(numpy.ndarray), *args).view(numpy.ndarray)
                #print tres.shape, "UUUUUUUUUUUUUUUUU"
        if len(tres.shape) != len(data.shape):
                tres.shape = tres.shape + (1,)
        result.append(tres)
        return numpy.concatenate(result,axis=1)
    
    
    def reshapeBeforeApply(self,factor,data,func,*args):
        result = []
        if range(data.shape[-1])>1 or range(data.shape[0])>1: raise
        
        temp=data[1,:,:,:,1]
        
        oldshape=data.shape
        newshape=tuple([x*factor for x in oldshape])
        temp=vigra.sampling.resizeVolumeSplineInterpolation(temp.astype('float32').view(numpy.ndarray),newshape)
        tres = func(data[...], *args)
        tres=vigra.sampling.resizeVolumeSplineInterpolation(tres.astype('float32').view(numpy.ndarray),oldshape)
        tres.shape = (1,)+tres.shape + (1,)
        result.append(tres)
        return numpy.concatenate(result, axis=-1)
    
    def serialize(self, h5grp):
        h5grp.create_dataset('name',data=self.name)
        h5grp.create_dataset('class',data=self.__class__.__name__)
        h5grp.create_dataset('sigma',data=self.sigma)
        h5grp.create_dataset('number of 2d channels',data=self.__class__.numOutputChannels2d)
        h5grp.create_dataset('number of 3d channels',data=self.__class__.numOutputChannels3d)
        h5grp.create_dataset('groups',data=','.join(self.groups))

    @classmethod
    def deserialize(cls, h5grp):
        # _name = h5grp['name']
        _class = h5grp['class']
        _sigma = h5grp['sigma']

        return eval('ilastik.modules.classification.core.features.standardFeatures.' + _class.value + '(' + str(_sigma.value) + ')')

    def __str__(self):
        return self.name


