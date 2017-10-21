__author__ = 'tmiller'

import maya.cmds as cmds
import maya.OpenMayaUI as mui
import maya.api.OpenMaya as om2

from Qt import QtGui, QtCore, QtWidgets

import correctiveGenerator as cgen


def showUI():
    global _correctiveGenUI
    try:
        _correctiveGenUI.close()
        _correctiveGenUI.deleteLater()
    except NameError: pass
    _correctiveGenUI = CorrectiveGeneratorUI()
    _correctiveGenUI.show()


class CorrectiveGeneratorUI(QtWidgets.QDialog):
    style = """
    QLineEdit{
        background-color: rgb(50,50,50);
    }
    QLabel{
        color: rgb(100,100,100);
    }
    QPushButton#uiCreateCorrectiveBTN{
        background-color: rgb(150,50,20);
    }
    """
    def __init__(self, parent=None):
        if parent is None:
            import shiboken2
            parent = shiboken2.wrapInstance(long(mui.MQtUtil.mainWindow()), QtWidgets.QMainWindow)

        super(CorrectiveGeneratorUI, self).__init__(parent)
        self.setWindowTitle("CSG")
        icon = QtGui.QIcon(":blendShape.png")
        self.setWindowIcon(icon)

        # Corrective Object (skinned mesh)
        self.uiCorrectiveGenEDT = None
        self.uiCorrectiveGenFromSelectionBTN = None

        # Rest shape (don't assume intermediate object is the rest, let's be explicit)
        self.uiRestEDT = None
        self.uiRestFromSelectionBTN = None

        # create button, assume the sculpt is selected
        self.uiCreateBTN = None

        self.initWidgets()
        self.initConnections()

        self.setStyleSheet(self.style)
        self.resize(self.sizeHint())

    def initWidgets(self):
        lay = QtWidgets.QGridLayout()
        lay.setContentsMargins(4,4,4,4)

        icon = QtGui.QIcon(":selectByObject.png")

        genLay = QtWidgets.QGridLayout()
        genLabel = QtWidgets.QLabel(" Generator Object")
        self.uiCorrectiveGenEDT = QtWidgets.QLineEdit("CorrectiveGen")
        self.uiCorrectiveGenFromSelectionBTN = QtWidgets.QPushButton(icon, "")
        self.uiCorrectiveGenFromSelectionBTN.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Minimum)
        genLay.addWidget(genLabel)
        genLay.addWidget(self.uiCorrectiveGenEDT, 1, 0)
        genLay.addWidget(self.uiCorrectiveGenFromSelectionBTN, 1, 1)
        lay.addItem(genLay)

        restLay = QtWidgets.QGridLayout()
        restLabel = QtWidgets.QLabel(" Rest Object")
        self.uiRestEDT = QtWidgets.QLineEdit("Rest")
        self.uiRestFromSelectionBTN = QtWidgets.QPushButton(icon, "")
        self.uiRestFromSelectionBTN.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Minimum)
        restLay.addWidget(restLabel)
        restLay.addWidget(self.uiRestEDT, 1, 0)
        restLay.addWidget(self.uiRestFromSelectionBTN, 1, 1)
        lay.addItem(restLay)

        self.uiCreateBTN = QtWidgets.QPushButton("Create Corrective")
        self.uiCreateBTN.setObjectName("uiCreateCorrectiveBTN")
        self.uiCreateBTN.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        lay.addWidget(self.uiCreateBTN)

        self.setLayout(lay)

    def initConnections(self):
        self.uiCreateBTN.clicked.connect(self.create)
        self.uiCorrectiveGenFromSelectionBTN.clicked.connect(lambda : self.populateEditFromSceneSelection(self.uiCorrectiveGenEDT))
        self.uiRestFromSelectionBTN.clicked.connect(lambda : self.populateEditFromSceneSelection(self.uiRestEDT))

    @staticmethod
    def populateEditFromSceneSelection(lineEdit):
        sel = cmds.ls(sl=True)
        if not sel:
            raise RuntimeError("Nothing Selected")
        lineEdit.setText(str(sel[0]))

    def create(self):
        sel = om2.MGlobal.getActiveSelectionList()
        if sel.isEmpty():
            raise RuntimeError("No Sculpt Object Selected")

        # confirm the correctiveGen and the rest shape exist
        if not cmds.ls(self.uiCorrectiveGenEDT.text()):
            raise RuntimeError("Can't find Corrective Generator object")

        if not cmds.ls(self.uiRestEDT.text()):
            raise RuntimeError("Can't find Rest object")

        # add the correctiveGenerator and the rest shape to the selectionList
        sel.add(self.uiCorrectiveGenEDT.text())
        sel.add(self.uiRestEDT.text())

        sculpt = sel.getDagPath(0)
        correctiveGen = sel.getDagPath(1)
        rest = sel.getDagPath(2)

        sculpt.extendToShape()
        correctiveGen.extendToShape()
        rest.extendToShape()

        deltas = cgen.createCorrectiveDeltasFromSculpt(correctiveGen, sculpt)
        shape = cgen.createCorrectiveShapeFromDeltas(rest, deltas)
