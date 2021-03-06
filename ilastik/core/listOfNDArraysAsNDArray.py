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

# Helper class that behaves like an ndarray, but consists of an array of ndarrays
#*******************************************************************************
# L i s t O f N D A r r a y s A s N D A r r a y                                *
#*******************************************************************************

class ListOfNDArraysAsNDArray:
    """
    Helper class that behaves like an ndarray, but consists of an array of ndarrays
    """

    def __init__(self, ndarrays):
        self.ndarrays = ndarrays
        self.dtype = ndarrays[0].dtype
        self.shape = (len(ndarrays),) + ndarrays[0].shape
        for idx, it in enumerate(ndarrays):
            if it.dtype != self.dtype or self.shape[1:] != it.shape:
                print "########### ERROR ListOfNDArraysAsNDArray all array items should have same dtype and shape (array: ", self.dtype, self.shape, " item : ",it.dtype, it.shape , ")"
        #Yes, this is horrible. But otherwise we have to copy.
        if len(self.ndarrays)==1 and self.ndarrays[0].flat is not None:
            self.flat = self.ndarrays[0].flat
            
    def __getitem__(self, key):
        return self.ndarrays[key[0]][tuple(key[1:])]

    def __setitem__(self, key, data):
        self.ndarrays[key[0]][tuple(key[1:])] = data
        print "##########ERROR ######### : ListOfNDArraysAsNDArray not implemented"
   
    def flatten(self):
        if len(self.ndarrays)==1:
            return self.ndarrays[0].flatten()
        else:
            print "##########ERROR ######### : ListOfNDArraysAsNDArray not implemented"       
