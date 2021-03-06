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

#import vigra.lasvm as lasvm
import numpy
import math
import time

try:
    import vigra
except ImportError:
    sys.exit("vigra module not found!")

#*******************************************************************************
# O n l i n e C l a s s i f i e r                                              *
#*******************************************************************************

class OnlineClassifier():
    def __init__(self):
        self.predSets={}
        pass
    def start(self,features,labels,ids):
        pass
    def addData(self,features,labels,ids):
        pass
    def removeData(self,ids):
        pass
    def fastLearn(self):
        pass
    def improveSolution(self):
        pass
    def addPredictionSet(self,features,id):
        self.predSets[id]=features
    def predict(self,id):
        pass

#*******************************************************************************
# C u m u l a t i v e O n l i n e C l a s s i f i e r                          *
#*******************************************************************************

class CumulativeOnlineClassifier(OnlineClassifier):
#*******************************************************************************
# f o r                                                                        *
#*******************************************************************************

    """Base class for all online classifiers, which can not unlearn and need to be shown the data from the last around every round"""
    def __init__(self):
        self.labels=None
        self.features=None
        self.ids=None
        OnlineClassifier.__init__(self)

    def start(self,features,labels,ids):
        self.features=features
        self.labels=labels
        self.ids=ids

    def addData(self,features,labels,ids):
        self.features=numpy.append(self.features,features,axis=0)
        self.labels=numpy.append(self.labels,labels)
        self.ids=numpy.append(self.ids,ids)

    def removeData(self,ids):
        indexes=ids
        for i in xrange(len(indexes)):
            for j in xrange(len(indexes)):
                if self.ids[j]==indexes[i]:
                    indexes[i]=j
                    break
            raise RuntimeError('removing a non existing example from online learner')
        #remove all those selected things
        self.ids=numpy.delete(self.ids,indexes)
        self.labels=numpy.delete(self.labels,indexes)
        self.features=numpy.delete(self.features,indexes,axis=0)

#*******************************************************************************
# O n l i n e R F                                                              *
#*******************************************************************************

class OnlineRF(CumulativeOnlineClassifier):
    def __init__(self,tree_count=100):
        CumulativeOnlineClassifier.__init__(self)
        self.rf=None
        self.tree_count=tree_count
        self.learnedRange=0
        self.predOnlineSets={}
        self.relearnId=0;

    def start(self,features,labels,ids):
        CumulativeOnlineClassifier.start(self,features,labels.astype(numpy.uint32),ids)
        self.startRF()

    def startRF(self):
        self.rf=vigra.classification.RandomForest_new(treeCount=self.tree_count,prepare_online_learning=True)
        self.rf.learnRF(self.features,self.labels);
        self.learnedRange=len(self.labels.flatten())

    def addData(self,features,labels,ids):
        CumulativeOnlineClassifier.addData(self,features,labels.astype(numpy.uint32),ids)

    def removeData(self,ids):
        CumulativeOnlineClassifier.removeData(self,ids)
        self.learnedRange=0

    def fastLearn(self):
        #learn everything not learned so far
        if(self.learnedRange==0):
            self.startRF()
        else:
            self.rf.onlineLearn(self.features,self.labels,self.learnedRange)
        self.learnedRange=len(self.labels.flatten())

    def improveSolution(self):
        self.rf.reLearnTree(self.features,self.labels,self.relearnId)
        for p in self.predOnlineSets.values():
            p.invalidateTree(self.relearnId)
        self.relearnId=(self.relearnId +1) % self.tree_count
        pass

    def addPredictionSet(self,features,id):
        OnlineClassifier.addPredictionSet(self,features,id)
        self.predOnlineSets[id]=vigra.classification.RF_OnlinePredictionSet(features,self.tree_count)

    def predict(self,id):
        return self.rf.predictProbabilities(self.predSets[id])
    def fastPredict(self,id):
        return self.rf.predictProbabilities(self.predOnlineSets[id])



#*******************************************************************************
# O n l i n e L a S v m                                                        *
#*******************************************************************************

class OnlineLaSvm(OnlineClassifier):
    def __init__(self,cacheSize=3000):
        OnlineClassifier.__init__(self)
        self.cacheSize=cacheSize
        self.svm=None
        #mpl.interactive(True)
        #mpl.use('WXAgg')

    def start(self,features,labels,ids):
        # TODO Cast to float64!
        self.linindepThresh=0.0
        self.improveRuns=0
        self.maxPredSVs=200
        #self.svm=lasvm.laSvmMultiParams(1.0,features.shape[1],1.0,0.001,self.cacheSize,True)
        self.addData(features,labels,ids)
        self.svm.startGuessParameters()
        print numpy.min(features.flatten())
        print numpy.max(features.flatten())
        self.fastLearn()
        self.numFeatures=features.shape[1]
        f=open('./g_run.txt','w')
        f_v=open('./var_run.txt','w')
        f_n=open('./num_sv_run.txt','w')
        f.close()
        f_v.close()
        f_n.close()
        #pylab.figure()

    def addPredictionSet(self,features,id):
        self.predSets[id]=lasvm.SVM_PredSet(features)

    def addData(self,features,labels,ids):
        # TODO Cast to float64!
        features = features
        labels = labels
        labels=labels*2-3;
        if(self.svm==None):
            raise RuntimeError("run \"start\" before addData")
        self.svm.addData(features,labels,ids)

    def removeData(self,ids):
        if self.svm==None:
            raise RuntimeError("run \"start\" first")
        self.svm.removeData(ids)

    def fastLearn(self):
        if self.svm==None:
            raise RuntimeError("run \"start\" first")
        print "Begin fast learn"
        self.svm.fastLearn(2,1,True)
        self.svm.finish(True)
        print "End fast learn"

    def improveSolution(self):
        t0=time.time()
        self.svm.sig_a=1.5
        self.svm.sig_b=-1.5
        self.svm.enableLindepThreshold(0.0)
        self.svm.ReFindPairs(False)
        self.svm.finish(True)
        while(time.time()<t0+0.25):
            self.improveRuns=self.improveRuns+1
            if self.svm==None:
                raise RuntimeError("run \"start\" first")
            print "Begin improving solution"
            self.svm.optimizeKernelStep(0,False,True)
            print "Done improving solution"
            f=open('g_run.txt','a')
            f_v=open('./var_run.txt','a')
            f_n=open('./sv_num_run.txt','a')
            f_n.write(repr(self.maxPredSVs)+"\n")
            
            for i in xrange(self.numFeatures):
                if(self.svm.gamma(i)>math.exp(-100)):
                    f.write(repr(math.log(self.svm.gamma(i))))
                else:
                    f.write(repr(-100))
                f_v.write(repr(self.svm.variance(i)))
                if i==self.numFeatures-1:
                    f.write("\n")
                    f_v.write("\n")
                else:
                    f.write("\t")
                    f_v.write("\t")
            f.close()
            f_v.close()
            f_n.close()
        self.svm.enableLindepThreshold(0.01)
        self.svm.ReFindPairs(True)
        self.svm.finish(True)

    def predict(self,id):
        while(self.improveRuns<20):
            self.improveSolution()
        print "Begin predict"
        pred=self.svm.predictF(self.predSets[id]);
        print "End predict"
        pred=(pred>0.0)
        pred=(pred.astype(numpy.int32)*2)-1
        pred=pred.reshape((pred.shape[0],1))
        return numpy.append(1.0-(pred+1)/2,(pred+1)/2.0,axis=1)

    def fastPredict(self,id):
        while(self.improveRuns<20):
            self.improveSolution()
        #adjust svs
        print "*****************************"
        print "I want no more than",self.maxPredSVs,"support vectors"
        print "*****************************"
        self.maxPredSVs=int(self.maxPredSVs)
        if(self.maxPredSVs<self.svm.getAlphas().shape[0]*0.9):
            print "Decreasing threshold"
            self.linindepThresh=self.svm.GetOptimalLinIndepTreshold(int(self.maxPredSVs))
            self.linindepThresh=min(0.9,self.linindepThresh)
            #self.svm.enableLindepThreshold(self.linindepThresh)
            #self.svm.ReFindPairs(True)
            self.svm.finish(True)
        if(self.maxPredSVs>self.svm.getAlphas().shape[0]*1.1):
            print "Increasing threshold"
            self.linindepThresh=self.linindepThresh+0.05
            #self.svm.enableLindepThreshold(self.linindepThresh)
            #self.svm.ReFindPairs(False)
            self.svm.finish(True)
            


        t0=time.time()
        print "Begin fast predict"
        #pred=self.svm.predictFRangedSingleCoverTree(self.predSets[id],0.5,0.1,True)
        pred=self.svm.predictF(self.predSets[id])
        print "End fast predict"
        needed_time=time.time()-t0
        print "needed_time",needed_time
        print "svs",self.svm.getAlphas().shape[0]
        print needed_time
        print "Before",self.maxPredSVs
        self.maxPredSVs=max(1.0/needed_time*self.svm.getAlphas().shape[0],30)
        print "After",self.maxPredSVs


        pred[pred>1.0]=1.0
        pred[pred<-1.0]=-1.0
        pred=(pred+1.0)/2.0
        print numpy.min(pred.flatten())
        print numpy.max(pred.flatten())
        pred=pred.reshape((pred.shape[0],1))


        #self.svm.enableLindepThreshold(0.01)
        #self.svm.ReFindPairs(False)
        return numpy.concatenate((1.0-pred, pred), axis=1)
        




