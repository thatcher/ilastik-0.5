import numpy
from ilastik.core.overlays import thresholdOverlay
import vigra

#*******************************************************************************
# d u m m y O v e r l a y                                                      *
#*******************************************************************************

class dummyOverlay:
    def __init__(self, data, color):
        self._data = data
        self._data = self._data.reshape(self._data.shape+(1,))
        self.color = color


#*******************************************************************************
# S y n a p s e F i l t e r A n d S e g m e n t o r                            *
#*******************************************************************************

class SynapseFilterAndSegmentor(object):
    def __init__(self, parent = None, labelnum = None, cc_overlay = None, input_overlay = None):
        self.parent = parent
        self.labelnum = labelnum
        activeImage = self.parent._activeImage
        self.labels = activeImage.overlayMgr["Classification/Labels"]
        self.cc = cc_overlay
        self.thres = input_overlay
        print self.cc.shape
        self.ndim = 3 if cc_overlay.shape[1]>1 else 2
        self.goodsizes = []
        
    
    def computeSizes(self):
        candidates = self.objectsSlow3d(self.cc[0, :, :, :, 0])
        print "n candidates", len(candidates)
        #print "ndim", self.ndim
        #print "label size", self.labels.shape
        
        index = (0, 0, 0)
        for key, value in candidates.iteritems():
            for i in range(len(value[0])):
                if self.ndim==3:
                    index = (0, value[0][i], value[1][i], value[2][i], 0)
                else:
                    index = (0, 0, value[0][i], value[1][i], 0)
                if self.labels[index]==self.labelnum+1:
                    self.goodsizes.append(len(value[0]))
                    break
        return candidates, self.goodsizes
        
    def objectsSlow3d(self, cc):
        #returns a dictionary, where the key is the point "intensity" (i.e. connected component number)
        #and the value is a list of point coordinates [[x], [y], [z]]
        objs = {}

        nzindex = numpy.nonzero(cc)
        for i in range(len(nzindex[0])):
            value = cc[nzindex[0][i], nzindex[1][i], nzindex[2][i]]
            if value > 0:
                if value not in objs:
                    objs[value] = [[], [], []]
                objs[value][0].append(nzindex[0][i])
                objs[value][1].append(nzindex[1][i])
                objs[value][2].append(nzindex[2][i])
                
        return objs
    
    def computeReferenceObjects(self):
        threshref = [0.5, 0.5]
        self.thres.setThresholds(threshref)
        accessor = thresholdOverlay.MultivariateThresholdAccessor(self.thres)
        data = numpy.asarray(accessor[0, :, :, :, 0], dtype='uint8')
        data = data.swapaxes(0, 2).view()
        cc = vigra.analysis.labelVolumeWithBackground(data, 6, 2)
        cc = cc.swapaxes(0, 2).view()
        objs_ref = self.objectsSlow3d(cc)
        return objs_ref
    
    def filterObjects(self, objsbig, objsref, mingoodsize, maxgoodsize):
        goodobjs = []
        bboxes = []
        print "filtering, min good size: ", mingoodsize, "max good size:", maxgoodsize
        for key, value in objsbig.iteritems():
            if len(value[0])>0.1*mingoodsize and len(value[0])<10*maxgoodsize:
                goodobjs.append(value)
                bboxes.append([numpy.amin(value[0]), numpy.amin(value[1]), numpy.amin(value[2]), numpy.amax(value[0]), numpy.amax(value[1]), numpy.amax(value[2])])
                                        
        goodobjsref = []
        bboxesref = []
    
        for key, value in objsref.iteritems():
            if len(value[0])>0.1*mingoodsize and len(value[0])<10*maxgoodsize:
                goodobjsref.append(value)
                bboxesref.append([numpy.amin(value[0]), numpy.amin(value[1]), numpy.amin(value[2]), numpy.amax(value[0]), numpy.amax(value[1]), numpy.amax(value[2])])
        #print "after size filtering, with user threshold ", len(goodobjs), ", with ref. threshold ", len(goodobjsref)
        found = False
        foundlist = []
        objs_final = []
        for i, big in enumerate(bboxesref):
            #print "in loop"
            found = False
            for small in bboxes:
                if big[0]>small[3] or small[0]>big[3] or big[1]>small[4] or small[1]>big[4] or big[2]>small[5] or small[2]>big[5]:
                    continue
                else:
                    found = True
                    break            
            if found == True:
                objs_final.append(goodobjsref[i])
        print "total synapses found: ", len(objs_final)        
        return objs_final
        