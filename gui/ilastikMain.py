
#!/usr/bin/env python

# profile with python -m cProfile ilastikMain.py
# python -m cProfile -o profiling.prf  ilastikMain.py
# import pstats
# p = pstats.Stats('fooprof')
# p.sort_statsf('time').reverse_order().print_stats()
# possible sort order: "stdname" "calls" "time" "cumulative". more in p.sort_arg_dic
import threading 
import sys
import numpy
sys.path.append("..")
from PyQt4 import QtCore, QtGui, uic
from core import version, dataMgr, projectMgr, featureMgr, classificationMgr, segmentationMgr, activeLearning, onlineClassifcator
from gui import ctrlRibbon, imgLabel
from Queue import Queue as queue
from collections import deque
import time
from core.utilities import irange, debug


try:
    from vigra import vigranumpycmodule as vm
except ImportError:
    try:
        import vigranumpycmodule as vm
    except ImportError:
        sys.exit("vigranumpycmodule not found!")



class MainWindow(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self)
        self.setGeometry(50, 50, 768, 512)
        self.iconPath = '../../icons/32x32/'
        self.setWindowTitle("Ilastik rev: " + version.getIlastikVersion())
        
        self.createRibbons()
        self.initImageWindows()
        self.createImageWindows()
        self.createFeatures()
        
        self.classificationProcess = None
        self.classificationOnline = None
                
    def createRibbons(self):                     
      
        self.ribbonToolbar = self.addToolBar("ToolBarForRibbons")
        
        self.ribbon = ctrlRibbon.Ribbon(self.ribbonToolbar)
        for ribbon_name, ribbon_group in ctrlRibbon.createRibbons().items():
            tabs = ribbon_group.makeTab()   
            self.ribbon.addTab(tabs, ribbon_group.name)  
        self.ribbonToolbar.addWidget(self.ribbon)
        
        # Wee, this is really ugly... anybody have better ideas for connecting 
        # the signals. This way has no future and is just a worka    round
        
        self.connect(self.ribbon.tabDict['Projects'].itemDict['New'], QtCore.SIGNAL('clicked()'), self.newProjectDlg)
        self.connect(self.ribbon.tabDict['Projects'].itemDict['Save'], QtCore.SIGNAL('clicked()'), self.saveProjectDlg)
        self.connect(self.ribbon.tabDict['Projects'].itemDict['Open'], QtCore.SIGNAL('clicked()'), self.loadProjectDlg)
        self.connect(self.ribbon.tabDict['Projects'].itemDict['Edit'], QtCore.SIGNAL('clicked()'), self.editProjectDlg)
        self.connect(self.ribbon.tabDict['Features'].itemDict['Select'], QtCore.SIGNAL('clicked()'), self.newFeatureDlg)
        self.connect(self.ribbon.tabDict['Features'].itemDict['Compute'], QtCore.SIGNAL('clicked()'), self.featureCompute)
        self.connect(self.ribbon.tabDict['Classification'].itemDict['Train'], QtCore.SIGNAL('clicked()'), self.on_classificationTrain)
        self.connect(self.ribbon.tabDict['Classification'].itemDict['Predict'], QtCore.SIGNAL('clicked()'), self.on_classificationPredict)
        self.connect(self.ribbon.tabDict['Classification'].itemDict['Interactive'], QtCore.SIGNAL('clicked(bool)'), self.on_classificationInteractive)
        self.connect(self.ribbon.tabDict['Classification'].itemDict['Online'], QtCore.SIGNAL('clicked(bool)'), self.on_classificationOnline)
        self.connect(self.ribbon.tabDict['Segmentation'].itemDict['Segment'], QtCore.SIGNAL('clicked(bool)'), self.on_segmentation)
        self.connect(self.ribbon.tabDict['Label'].itemDict['Brushsize'], QtCore.SIGNAL('valueChanged(int)'), self.on_changeBrushSize)
        
        
        #self.connect(self.ribbon.tabDict['Export'].itemDict['Export'], QtCore.SIGNAL('clicked()'), self.debug)
        
        self.ribbon.tabDict['Projects'].itemDict['Edit'].setEnabled(False)
        self.ribbon.tabDict['Projects'].itemDict['Save'].setEnabled(False)
        
        
        #self.ribbon.tabDict['Features'].itemDict['Compute'].setEnabled(False)
        #self.ribbon.tabDict['Classification'].itemDict['Compute'].setEnabled(False)
        
        self.ribbon.setCurrentIndex (0)
          
    def newProjectDlg(self):      
        self.projectDlg = ProjectDlg(self)
    
    def saveProjectDlg(self):
        fileName = QtGui.QFileDialog.getSaveFileName(self, "Save Project", ".", "Project Files (*.ilp)")
        self.project.saveToDisk(str(fileName))
        
    def loadProjectDlg(self):
        fileName = QtGui.QFileDialog.getOpenFileName(self, "Open Project", ".", "Project Files (*.ilp)")
        self.project = projectMgr.Project.loadFromDisk(str(fileName))
        self.ribbon.tabDict['Projects'].itemDict['Edit'].setEnabled(True)
        self.ribbon.tabDict['Projects'].itemDict['Save'].setEnabled(True)
        self.projectModified() 
        
    def editProjectDlg(self):
        if hasattr(self, 'projectDlg'):
            self.projectDlg.show()
            return
        if not hasattr(self, 'project'):
            self.newProjectDlg()
            return
        self.projectDlg = ProjectDlg(self)
        self.projectDlg.updateDlg(self.project)
        self.projectModified()
            
        
    def projectModified(self):
        self.labelWidget.updateProject(self.project)
        
    def newFeatureDlg(self):
        self.newFeatureDlg = FeatureDlg(self)
        
    def initImageWindows(self):
        self.labelDocks = []
        
    def createImageWindows(self):
        label_w = imgLabel.labelWidget(self, ['rgb1.jpg', 'rgb2.tif'])
        
        dock = QtGui.QDockWidget("Ilastik Label Widget", self)
        dock.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea | QtCore.Qt.RightDockWidgetArea | QtCore.Qt.TopDockWidgetArea | QtCore.Qt.LeftDockWidgetArea)
        dock.setWidget(label_w)
        self.labelWidget = label_w  # todo: user defined list of labelwidgets
        
        area = QtCore.Qt.BottomDockWidgetArea
        
        self.addDockWidget(area, dock)
        self.labelDocks.append(dock)
    def createFeatures(self):
        self.featureList = featureMgr.ilastikFeatures
        
    def featureCompute(self):
        self.featureComputation = FeatureComputation(self)
    
    def on_segmentation(self):

        segThreads = []
        seg = []
        for shape, propmap in zip(self.project.dataMgr.dataItemsShapes(), self.project.dataMgr.prediction):
            s = segmentationMgr.LocallyDominantSegmentation2D(shape)
            seg.append(s)
            
            t = threading.Thread(target=s.segment, args=(propmap,))
            segThreads.append(t)
            t.start()         
        
        for cnt, t in irange(segThreads):
            t.join()
            self.project.dataMgr.segmentation[cnt] = seg[cnt].result
        
        self.labelWidget.OverlayMgr.updateSegmentationPixmaps(dict(irange(self.project.dataMgr.segmentation)))
        self.labelWidget.OverlayMgr.setOverlayState('Segmentation')
        
    def on_changeBrushSize(self, rad):
        #if rad / 2 != 0:
        #    rad + 1 
            
        self.labelWidget.setBrushSize(rad)

    def on_classificationTrain(self):
        self.generateTrainingData()
        self.classificationTrain = ClassificationTrain(self)
        
    def on_classificationPredict(self):
        self.classificationPredict = ClassificationPredict(self)
    
    def on_classificationInteractive(self, state):
        if state:
            self.generateTrainingData()
            self.classificationInteractive = ClassificationInteractive(self)
        else:
            self.classificationInteractive.stop()
            
    def on_classificationOnline(self, state):
        if state:
            if not self.classificationOnline:
                self.classificationOnline = ClassificationOnline(self)
            self.classificationOnline.start()
        else:
            self.classificationOnline.stop()
        
    # TODO: This whole function should NOT be here transfer it DataMgr. 
    def generateTrainingData(self):
        trainingMatrices_perDataItem = []
        res_labels = []
        res_names = []
        dataItemNr = 0
        for dataItem in self.project.dataMgr.dataFeatures:
            res_labeledFeatures = []

            if not self.labelWidget.labelForImage.get(dataItemNr, None):
                # No Labels available for that image
                continue
            
            # Extract labelMatrix
            labelmatrix = self.labelWidget.labelForImage[dataItemNr].DrawManagers[0].labelmngr.labelArray
            labeled_indices = labelmatrix.nonzero()[0]
            n_labels = labeled_indices.shape[0]
            nFeatures = 0
            for featureImage, featureString in dataItem:
                # todo: fix hardcoded 2D:
                n = 1   # n: number of feature-values per pixel
                if featureImage.shape.__len__() > 2:
                    n = featureImage.shape[2]
                if n<=1:
                    res_labeledFeatures.append( featureImage.flat[labeled_indices].reshape(1,n_labels) )
                    if dataItemNr == 0:
                        res_names.append( featureString )
                else:
                    for featureDim in xrange(n):
                        res_labeledFeatures.append( featureImage[:,:,featureDim].flat[labeled_indices].reshape(1,n_labels ) )
                        if dataItemNr == 0:
                            res_names.append( featureString + "_%i" %(featureDim))
                nFeatures+=1
            if (dataItemNr==0):
                nFeatures_ofFirstImage = nFeatures
            if nFeatures == nFeatures_ofFirstImage:
                trainingMatrices_perDataItem.append( numpy.concatenate( res_labeledFeatures).T )
                res_labels.append(labelmatrix[labeled_indices])
            else:
                print "feature dimensions don't match (maybe #channels differ?). Skipping image."
            dataItemNr+=1
        trainingMatrix = numpy.concatenate( trainingMatrices_perDataItem )
        self.project.trainingMatrix = trainingMatrix
        self.project.trainingLabels = numpy.concatenate(res_labels)
        self.project.trainingFeatureNames = res_names
        
        debug(trainingMatrix.shape)
        debug(self.project.trainingLabels.shape)
        
class ProjectDlg(QtGui.QDialog):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self)
        # this enables   self.columnPos['File']:
        self.labelCounter = 2
        self.columnPos = {}
        self.labelColor = { 1:QtGui.QColor(QtCore.Qt.red) }
        self.parent = parent
        self.fileList = []
        self.thumbList = []        
        self.initDlg()
        self.on_cmbLabelName_currentIndexChanged(0)
        self.setLabelColorButtonColor(QtGui.QColor(QtCore.Qt.red))
        for i in xrange(self.tableWidget.columnCount()):
            self.columnPos[ str(self.tableWidget.horizontalHeaderItem(i).text()) ] = i
        
    def initDlg(self):
        uic.loadUi('dlgProject.ui', self) 
        self.tableWidget.resizeRowsToContents()
        self.tableWidget.resizeColumnsToContents()
        self.tableWidget.setAlternatingRowColors(True)
        self.tableWidget.setShowGrid(False)
        self.tableWidget.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.tableWidget.verticalHeader().hide()
        self.connect(self.tableWidget, QtCore.SIGNAL("cellPressed(int, int)"), self.updateThumbnail)
        #self.on_cmbLabelName_currentIndexChanged(0)
        self.show()
        

    @QtCore.pyqtSignature("int")
    def on_cmbLabelName_currentIndexChanged(self, nr):
        nr += 1 # 0 is unlabeled !!
        self.txtLabelName.setText(self.cmbLabelName.currentText())
        #col = QtGui.QColor.fromRgb(self.labelColor.get(nr, QtGui.QColor(QtCore.Qt.red).rgb()))
        if not self.labelColor.get(nr,None):
            self.labelColor[nr] = QtGui.QColor(numpy.random.randint(255),numpy.random.randint(255),numpy.random.randint(255))  # default: red
        col = self.labelColor[nr]
        self.setLabelColorButtonColor(col)

    @QtCore.pyqtSignature("")
    def on_btnAddLabel_clicked(self):
        self.cmbLabelName.addItem("Class %d" % self.labelCounter)
        self.cmbLabelName.setCurrentIndex(self.cmbLabelName.count() - 1)
        self.labelCounter += 1
        #self.on_cmbLabelName_currentIndexChanged( self.cmbLabelName.count()-1 )
        
    def setLabelColorButtonColor(self, col):
        self.btnLabelColor.setAutoFillBackground(True)
        fgcol = QtGui.QColor()
        fgcol.setRed(255 - col.red())
        fgcol.setGreen(255 - col.green())
        fgcol.setBlue(255 - col.blue())
        self.btnLabelColor.setStyleSheet("background-color: %s; color: %s" % (col.name(), fgcol.name()))

    @QtCore.pyqtSignature("") 
    def on_btnLabelColor_clicked(self):
        colordlg = QtGui.QColorDialog()
        col = colordlg.getColor()
        labelnr = self.cmbLabelName.currentIndex() + 1
        self.labelColor[labelnr] = col
        self.setLabelColorButtonColor(col)
        
    @QtCore.pyqtSignature("QString")
    def on_txtLabelName_textChanged(self, text):
        self.cmbLabelName.setItemText(self.cmbLabelName.currentIndex(), text)

    @QtCore.pyqtSignature("")
    def updateDlg(self, project):
        self.projectName.setText(project.name)
        self.labeler.setText(project.labeler)
        self.description.setText(project.description)
        
        theFlag = QtCore.Qt.ItemIsEnabled
        flagON = ~theFlag | theFlag 
        flagOFF = ~theFlag
            
        for d in project.dataMgr.dataItems:
            rowCount = self.tableWidget.rowCount()
            self.tableWidget.insertRow(0)
            
            # File Name
            r = QtGui.QTableWidgetItem(d.fileName)
            self.tableWidget.setItem(0, self.columnPos['File'], r)
            
            r = QtGui.QComboBox()
            r.setEditable(True)
            self.tableWidget.setCellWidget(0, self.columnPos['Groups'], r)
            
            # Here comes the cool python "checker" use it for if_than_else in lambdas
            checker = lambda x: x and QtCore.Qt.Checked or QtCore.Qt.Unchecked
            
            # labels
            r = QtGui.QTableWidgetItem()
            r.data(QtCore.Qt.CheckStateRole)
            r.setCheckState(checker(d.hasLabels))
            r.setFlags(r.flags() & flagOFF);
            self.tableWidget.setItem(0, self.columnPos['Labels'], r)
            
            # train
            r = QtGui.QTableWidgetItem()
            r.data(QtCore.Qt.CheckStateRole)
            r.setCheckState(checker(d.isTraining))
            r.setFlags(r.flags() & flagON);
            self.tableWidget.setItem(0, self.columnPos['Train'], r)
            
            # test
            r = QtGui.QTableWidgetItem()
            r.data(QtCore.Qt.CheckStateRole)
            r.setCheckState(checker(d.isTesting))
            r.setFlags(r.flags() & flagON);
            self.tableWidget.setItem(0, self.columnPos['Test'], r)                  
        
        self.cmbLabelName.clear()
        self.labelColor = project.labelColors
        for name in project.labelNames:
            self.cmbLabelName.addItem(name)

        self.update()
        
    @QtCore.pyqtSignature("")     
    def on_addFile_clicked(self):
        
        fileNames = QtGui.QFileDialog.getOpenFileNames(self, "Open Image", ".", "Image Files (*.png *.jpg *.bmp *.tif *.gif);;Multi Spectral Data (*.h5)")
        if fileNames:
            for file_name in fileNames:
                self.fileList.append(file_name)
                rowCount = self.tableWidget.rowCount()
                self.tableWidget.insertRow(0)
                
                theFlag = QtCore.Qt.ItemIsEnabled
                flagON = ~theFlag | theFlag 
                flagOFF = ~theFlag
                
                # file name
                r = QtGui.QTableWidgetItem(file_name)
                self.tableWidget.setItem(0, self.columnPos['File'], r)
                
                # group
                r = QtGui.QComboBox()
                r.setEditable(True)
                self.tableWidget.setCellWidget(0, self.columnPos['Groups'], r)
                
                # labels
                r = QtGui.QTableWidgetItem()
                r.data(QtCore.Qt.CheckStateRole)
                r.setCheckState(QtCore.Qt.Unchecked)
                
                labelsAvailable = dataMgr.DataImpex.checkForLabels(file_name)
                if labelsAvailable:
                    r.setFlags(r.flags() & flagON);
                    
                else:
                    r.setFlags(r.flags() & flagOFF);
                self.tableWidget.setItem(0, self.columnPos['Labels'], r)
                
                # train
                r = QtGui.QTableWidgetItem()
                r.data(QtCore.Qt.CheckStateRole)
                r.setCheckState(QtCore.Qt.Checked)
                r.setFlags(r.flags() & flagON);
                self.tableWidget.setItem(0, self.columnPos['Train'], r)
                
                # test
                r = QtGui.QTableWidgetItem()
                r.data(QtCore.Qt.CheckStateRole)
                r.setCheckState(QtCore.Qt.Checked)
                r.setFlags(r.flags() & flagON);
                self.tableWidget.setItem(0, self.columnPos['Test'], r)
                
                self.initThumbnail(file_name)
                self.tableWidget.setCurrentCell(0, 0)
    
    def on_removeFile_clicked(self):
        row = self.tableWidget.currentRow()
        
        
    def initThumbnail(self, file_name):
        thumb = QtGui.QPixmap(str(file_name))
        thumb = thumb.scaledToWidth(128)
        self.thumbList.append(thumb)
        self.thumbnailImage.setPixmap(self.thumbList[-1])
                    
    def updateThumbnail(self, row=0, col=0):
        self.thumbnailImage.setPixmap(self.thumbList[-row-1]) 
    
    @QtCore.pyqtSignature("")     
    def on_confirmButtons_accepted(self):
        projectName = self.projectName
        labeler = self.labeler
        description = self.description
        self.parent.project = projectMgr.Project(str(projectName.text()), str(labeler.text()), str(description.toPlainText()) , dataMgr.DataMgr())
        self.parent.project.labelColors = self.labelColor
        self.parent.project.labelNames = []
        for i in xrange(self.cmbLabelName.count()):
            self.parent.project.labelNames.append(str(self.cmbLabelName.itemText(i)))
            
        
        rowCount = self.tableWidget.rowCount()
        dataItemList = []
        for k in range(0, rowCount):
            fileName = self.tableWidget.item(k, self.columnPos['File']).text()
            theDataItem = dataMgr.DataItemImage(fileName)
            dataItemList.append(theDataItem)
            
            groups = []
            for i in xrange(self.tableWidget.cellWidget(k, self.columnPos['Groups']).count()):
                groups.append(str(self.tableWidget.cellWidget(k, self.columnPos['Groups']).itemText(i)))
            theDataItem.groupMembership = groups
            
            theDataItem.hasLabels = self.tableWidget.item(k, self.columnPos['Labels']).checkState() == QtCore.Qt.Checked
            theDataItem.isTraining = self.tableWidget.item(k, self.columnPos['Train']).checkState() == QtCore.Qt.Checked
            theDataItem.isTesting = self.tableWidget.item(k, self.columnPos['Test']).checkState() == QtCore.Qt.Checked
            
            
            
            contained = False
            for pr in theDataItem.projects:
                if pr == self.parent.project:
                    contained = true
            if not contained:
                theDataItem.projects.append(self.parent.project)
        
        dataItemList.sort(lambda x,y: cmp(x.fileName, y.fileName))    
        self.parent.project.dataMgr.setDataList(dataItemList) 
        self.parent.ribbon.tabDict['Projects'].itemDict['Edit'].setEnabled(True)
        self.parent.ribbon.tabDict['Projects'].itemDict['Save'].setEnabled(True)
        
        self.parent.projectModified()
        self.close()
        
    
    @QtCore.pyqtSignature("")    
    def on_confirmButtons_rejected(self):
        self.close()

class FeatureDlg(QtGui.QDialog):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self)
        self.parent = parent
        self.initDlg()
        
    def initDlg(self):
        uic.loadUi('dlgFeature.ui', self) 
        for featureItem in self.parent.featureList:
            self.featureList.insertItem(self.featureList.count() + 1, QtCore.QString(featureItem.__str__()))        
        
        for k, groupName in irange(featureMgr.ilastikFeatureGroups.groupNames):
            rc = self.featureTable.rowCount()
            self.featureTable.insertRow(rc)
        self.featureTable.setVerticalHeaderLabels(featureMgr.ilastikFeatureGroups.groupNames)
        
        for k, scaleName in irange(featureMgr.ilastikFeatureGroups.groupScaleNames):
            rc = self.featureTable.columnCount()
            self.featureTable.insertColumn(rc)
        self.featureTable.setHorizontalHeaderLabels(featureMgr.ilastikFeatureGroups.groupScaleNames)
        
        self.featureTable.resizeRowsToContents()
        self.featureTable.resizeColumnsToContents()
        for c in range(self.featureTable.columnCount()):
            self.featureTable.horizontalHeader().resizeSection(c, 54)#(0, QtGui.QHeaderView.Stretch)

        self.featureTable.verticalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.featureTable.setShowGrid(False)
        
        
        for r in range(self.featureTable.rowCount()):
            for c in range(self.featureTable.columnCount()):
                item = QtGui.QTableWidgetItem()
                if featureMgr.ilastikFeatureGroups.selection[r][c]:
                    item.setIcon(QtGui.QIcon(self.parent.iconPath + "categories/preferences-system.png"))
                self.featureTable.setItem(r,c,item)
        self.setStyleSheet("selection-background-color: qlineargradient(x1: 0, y1: 0, x2: 0.5, y2: 0.5, stop: 0 #BBBBDD, stop: 1 white)")
        self.show()
    
    def on_featureTable_itemSelectionChanged(self):  
        sel = self.featureTable.selectedItems()
        sel_flag = False
        for i in sel:
            if i.icon().isNull():
                sel_flag = True
        
        if sel_flag:
            for i in sel:
                icon = QtGui.QIcon(self.parent.iconPath + "categories/preferences-system.png")
                i.setIcon(icon)
                featureMgr.ilastikFeatureGroups.selection[i.row()][i.column()] = True  
                           
        else:
            for i in sel:
                icon = QtGui.QIcon()
                i.setIcon(icon)   
                featureMgr.ilastikFeatureGroups.selection[i.row()][i.column()] = False     
        
    @QtCore.pyqtSignature("")     
    def on_confirmButtons_accepted(self):  
        self.parent.project.featureMgr = featureMgr.FeatureMgr()

        featureSelectionList = []
        for k in range(0, self.featureList.count()):
            if self.featureList.item(k).isSelected():
                featureSelectionList.append(self.parent.featureList[k])
        
        featureSelectionList = featureMgr.ilastikFeatureGroups.createList()
        self.parent.project.featureMgr.setFeatureItems(featureSelectionList)
        self.close()
        #self.parent.projectModified()
        
    @QtCore.pyqtSignature("")    
    def on_confirmButtons_rejected(self):
        self.close()

class FeatureComputation(object):
    def __init__(self, parent):
        self.parent = parent
        self.featureCompute()
    
    def featureCompute(self):
        self.myTimer = QtCore.QTimer()
        self.parent.connect(self.myTimer, QtCore.SIGNAL("timeout()"), self.updateFeatureProgress)
        
        numberOfJobs = self.parent.project.featureMgr.prepareCompute(self.parent.project.dataMgr)  
        self.initFeatureProgress(numberOfJobs)
        self.parent.project.featureMgr.triggerCompute()
        self.myTimer.start(200) 
        
    def initFeatureProgress(self, numberOfJobs):
        statusBar = self.parent.statusBar()
        self.myFeatureProgressBar = QtGui.QProgressBar()
        self.myFeatureProgressBar.setMinimum(0)
        self.myFeatureProgressBar.setMaximum(numberOfJobs)
        self.myFeatureProgressBar.setFormat(' Features... %p%')
        statusBar.addWidget(self.myFeatureProgressBar)
        statusBar.show()
    
    def updateFeatureProgress(self):
        val = self.parent.project.featureMgr.getCount() 
        self.myFeatureProgressBar.setValue(val)
        if not self.parent.project.featureMgr.featureProcess.is_alive():
            self.myTimer.stop()
            self.terminateFeatureProgressBar()
            self.parent.project.featureMgr.joinCompute(self.parent.project.dataMgr)
            
    def terminateFeatureProgressBar(self):
        self.parent.statusBar().removeWidget(self.myFeatureProgressBar)
        self.parent.statusBar().hide()
        
    def featureShow(self, item):
        pass

class ClassificationTrain(object):
    def __init__(self, parent):
        self.parent = parent
        self.start()
        
    def start(self):               
        self.classificationTimer = QtCore.QTimer()
        self.parent.connect(self.classificationTimer, QtCore.SIGNAL("timeout()"), self.updateClassificationProgress)      
        numberOfJobs = 10                 
        self.initClassificationProgress(numberOfJobs)
        
        # Get Train Data
        F = self.parent.project.trainingMatrix
        L = self.parent.project.trainingLabels
        featLabelTupel = queue()
        featLabelTupel.put((F,L))
       
        self.classificationProcess = classificationMgr.ClassifierTrainThread(numberOfJobs, featLabelTupel)
        self.classificationProcess.start()
        self.classificationTimer.start(200) 

    def initClassificationProgress(self, numberOfJobs):
        statusBar = self.parent.statusBar()
        self.myClassificationProgressBar = QtGui.QProgressBar()
        self.myClassificationProgressBar.setMinimum(0)
        self.myClassificationProgressBar.setMaximum(numberOfJobs)
        self.myClassificationProgressBar.setFormat(' Training... %p%')
        statusBar.addWidget(self.myClassificationProgressBar)
        statusBar.show()
    
    def updateClassificationProgress(self):
        val = self.classificationProcess.count
        self.myClassificationProgressBar.setValue(val)
        if not self.classificationProcess.is_alive():
            self.classificationTimer.stop()
            self.classificationProcess.join()
            self.finalize()
            self.terminateClassificationProgressBar()
            
    def finalize(self):
        self.parent.project.classifierList = self.classificationProcess.classifierList
                      
    def terminateClassificationProgressBar(self):
        self.parent.statusBar().removeWidget(self.myClassificationProgressBar)
        self.parent.statusBar().hide()

class ClassificationInteractive(object):
    def __init__(self, parent):
        self.parent = parent
        self.stopped = False
        self.trainingQueue = deque(maxlen=1)
        #self.lock = threading.Lock()
        
        self.parent.labelWidget.connect(self.parent.labelWidget, QtCore.SIGNAL('newLabelsPending'), self.updateTrainingQueue)
        self.interactiveTimer = QtCore.QTimer()
        self.parent.connect(self.interactiveTimer, QtCore.SIGNAL("timeout()"), self.updateLabelWidget)      
        self.temp_cnt = 0
        self.start()
        self.interactiveTimer.start(500)
        #self.tmp_count = 0
        #self.resultLock = threading.Lock()
        
    def updateTrainingQueue(self):
        self.parent.generateTrainingData()
        F = self.parent.project.trainingMatrix
        L = self.parent.project.trainingLabels   

        self.trainingQueue.append((F,L))

    def updateLabelWidget(self):  
        predictIndex = self.parent.labelWidget.activeImage
        displayClassNr = self.parent.labelWidget.activeLabel  
#        try:
#            image = self.classificationInteractive.result[predictIndex].pop()
#        except IndexError:
#            time.sleep(0.01)
#            return
        viewPredictions = {}
        for i, predict in irange(self.classificationInteractive.result):
            try:
                viewPredictions[i]=predict.pop()
            except IndexError:
                pass

        self.parent.labelWidget.OverlayMgr.updatePredictionsPixmaps(viewPredictions)
        self.parent.labelWidget.OverlayMgr.setOverlayState('Prediction')


    def initInteractiveProgressBar(self):
        statusBar = self.parent.statusBar()
        self.myInteractionProgressBar = QtGui.QProgressBar()
        self.myInteractionProgressBar.setMinimum(0)
        self.myInteractionProgressBar.setMaximum(0)
        statusBar.addWidget(self.myInteractionProgressBar)
        statusBar.show()
        
    def terminateClassificationProgressBar(self):
        self.parent.statusBar().removeWidget(self.myInteractionProgressBar)
        self.parent.statusBar().hide()
        
    def start(self):
        
        F = self.parent.project.trainingMatrix
        L = self.parent.project.trainingLabels
        
        self.trainingQueue.append((F,L))
        
        (predictDataList, dummy) = self.parent.project.dataMgr.buildFeatureMatrix()
        
        
        numberOfClasses = len(self.parent.project.labelNames)
        numberOfClassifiers=6
        treeCount=6
        self.classificationInteractive = classificationMgr.ClassifierInteractiveThread(self.trainingQueue, predictDataList, self.parent.labelWidget, numberOfClasses, numberOfClassifiers, treeCount )
        self.initInteractiveProgressBar()
               
        self.classificationInteractive.start()
    def stop(self):
        self.interactiveTimer.stop()
        self.classificationInteractive.stopped = True
        
        self.classificationInteractive.join()
        self.finalize()
        
        self.terminateClassificationProgressBar()
    
    def finalize(self):
        self.parent.project.classifierList = list(self.classificationInteractive.classifierList)
        
        # TODO[CSo] Here we need another Thread, would be nice to reuse ClassificationPredict
        # self.classificationInteractive.finishPredictions()
        
        self.parent.project.dataMgr.prediction = map(lambda x:x.pop(), self.classificationInteractive.resultList)
        
class ClassificationOnline(object):
    def __init__(self, parent):
        print "Online Classification initialized"
        self.parent = parent
        self.parent.generateTrainingData()
        
        features = self.parent.project.trainingMatrix
        labels = self.parent.project.trainingLabels  
        predictionList, dummy = self.parent.project.dataMgr.buildFeatureMatrix()
        ids = numpy.zeros( (len(labels),) )
        self.OnlineThread = classificationMgr.ClassifierOnlineThread(features, labels, ids, predictionList, self.predictionUpdatedCallBack)
        self.parent.labelWidget.connect(self.parent.labelWidget, QtCore.SIGNAL('newLabelsPending'), self.updateTrainingData)
        
    def start(self):
        print "Online Classification started"
        self.OnlineThread.start()
        
    def stop(self):
        print "Online Classification stopped"
        self.OnlineThread.stopped = True
        self.OnlineThread.commandQueue.put((None,None,None,'stop'))
        self.OnlineThread.join()
        self.OnlineThread = None
    
    def predictionUpdatedCallBack(self):
        #self.labelWidget.emit(QtCore.SIGNAL('newLabelsPending'))
        pass
    
    def updateTrainingData(self):
        
        self.parent.generateTrainingData()
        features = self.parent.project.trainingMatrix
        labels = self.parent.project.trainingLabels 
        ids = numpy.zeros( (len(labels),) )
        
        self.OnlineThread.commandQueue.put((features, labels, ids, 'learn'))
        
        
        
        
    
class ClassificationPredict(object):
    def __init__(self, parent):
        self.parent = parent
        self.start()
    
    def start(self):               
        self.classificationTimer = QtCore.QTimer()
        self.parent.connect(self.classificationTimer, QtCore.SIGNAL("timeout()"), self.updateClassificationProgress)      
        
        (self.featureQueue, self.featureQueue_dataIndices) = self.parent.project.dataMgr.buildFeatureMatrix()
        
        numberOfJobs = len(self.featureQueue) * len(self.parent.project.classifierList)
        
        self.initClassificationProgress(numberOfJobs)
        self.classificationPredict = classificationMgr.ClassifierPredictThread(self.parent.project.classifierList, self.featureQueue, self.featureQueue_dataIndices)
        self.classificationPredict.start()
        self.classificationTimer.start(200) 

    def initClassificationProgress(self, numberOfJobs):
        statusBar = self.parent.statusBar()
        self.myClassificationProgressBar = QtGui.QProgressBar()
        self.myClassificationProgressBar.setMinimum(0)
        self.myClassificationProgressBar.setMaximum(numberOfJobs)
        self.myClassificationProgressBar.setFormat(' Prediction... %p%')
        statusBar.addWidget(self.myClassificationProgressBar)
        statusBar.show()
    
    def updateClassificationProgress(self):
        val = self.classificationPredict.count
        self.myClassificationProgressBar.setValue(val)
        if not self.classificationPredict.is_alive():
            self.classificationTimer.stop()

            self.classificationPredict.join()
            self.finalize()           
            
            self.terminateClassificationProgressBar()
            

            displayImage = self.parent.labelWidget.activeImage
            predictions = dict(irange(self.classificationPredict.predictionList))
            self.parent.labelWidget.OverlayMgr.updatePredictionsPixmaps(predictions)
            self.parent.labelWidget.OverlayMgr.showOverlayPixmapByState()
            
    def finalize(self):
        self.parent.project.dataMgr.prediction = self.classificationPredict.predictionList
        
    def terminateClassificationProgressBar(self):
        self.parent.statusBar().removeWidget(self.myClassificationProgressBar)
        self.parent.statusBar().hide()
    



if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    mainwindow = MainWindow()  
    mainwindow.show() 
    sys.exit(app.exec_())
