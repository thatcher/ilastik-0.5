import numpy
import sys

try:
    from vigra import vigranumpycmodule as vm
except ImportError:
    try:
        import vigranumpycmodule as vm
    except ImportError:
        sys.exit("vigranumpycmodule not found!")

class DataItemBase():
    def __init__(self, fileName):
        self.fileName = str(fileName)
        self.hasLabels = False
        self.isTraining = True
        self.isTesting = False
        self.groupMember = []
        self.projects = []
        
        self.data = None
        self.labels = []
        self.dataKind = None
        self.dataType = None
        self.dataDimensions = 0
        self.thumbnail = None
        
    def loadData(self):
        self.data = "This is not an Image..."
    
    def unpackChannels(self):
        if self.dataKind in ['rgb']:
            return [ self.data[:,:,k] for k in range(0,3) ]
        elif self.dataKind in ['multi']:
            return [ self.data[:,:,k] for k in range(0, self.data.shape[2]) ]
        elif self.dataKind in ['gray']:
            return [ self.data ]   

class DataItemImage(DataItemBase):
    def __init__(self, fileName):
        DataItemBase.__init__(self, fileName) 
        self.dataDimensions = 2
       
    def loadData(self):
        self.data = vm.readImage(self.fileName)
        self.data = self.data.swapaxes(0,1)
        self.dataType = self.data.dtype
        if len(self.data.shape) == 3:
            if self.data.shape[2] == 3:
                self.dataKind = 'rgb'
            elif self.data.shape[2] > 3:
                self.dataKind = 'multi'
        elif len(self.data.shape) == 2:
            self.dataKind = 'gray'
            
    def unLoadData(self):
        # TODO: delete permanently here for better garbage collection
        self.data = None
class DataItemVolume(DataItemBase):
    def __init__(self, fileName):
        DataItemBase.__init__(self, fileName) 
       
    def loadData(self):
        self.data = vm.readVolume(self.fileName)
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
    def __init__(self, dataItems=[]):
        self.setDataList(dataItems)
        self.dataFeatures = []
        self.labels = [None] * len(dataItems)
        self.prediction = [None] * len(dataItems)
        
    def setDataList(self, dataItems):
        self.dataItems = dataItems
        self.dataItemsLoaded = [False] * len(dataItems)
        
    def __getitem__(self, ind):
        if not self.dataItemsLoaded[ind]:
            self.dataItems[ind].loadData()
            self.dataItemsLoaded[ind] = True
        return self.dataItems[ind]
    
    def clearDataList(self):
        self.dataItems = []
        self.dataFeatures = []
        self.labels = [None] * len(self.dataItems)
    
    def __len__(self):
        return len(self.dataItems)
        
        


        
