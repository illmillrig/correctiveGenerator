__author__ = 'tmiller'

import maya.api.OpenMaya as om
import maya.cmds as cmds


#----------------------------------------------------------------
# Usage:
# deltas = cgen.createCorrectiveDeltasFromSculpt(cg, shape)
# shape = cgen.createCorrectiveShapeFromDeltas(rest, deltas)
#----------------------------------------------------------------

def createCorrectiveDeltasFromSculpt(correctiveGen, sculpt):
    # expects MDagPath args for worldSpace tranforms queries
    skinCluster = getSkinCluster(correctiveGen.node())
    outMesh = _getSkinOutMeshData(skinCluster)
    outPoints = _getMeshDataPoints(outMesh)

    posePntsX, posePntsY, posePntsZ = _getSmearedPoints(skinCluster)
    smearX, smearY, smearZ = _subtractPoseFromSmearPnts(outPoints, posePntsX, posePntsY, posePntsZ)
    pointMatrices = _createPointMatrices(outPoints, smearX, smearY, smearZ)

    return _computeDeltas(pointMatrices, sculpt)

def createCorrectiveShapeFromDeltas(rest, deltas):
    return _generateShapeFromDeltas(rest, deltas)

def matrixFromList(floatList):
    return om.MMatrix(floatList)

def getSkinCluster(shapeNode):
    fn = om.MFnDependencyNode(shapeNode)
    # what type of object is the shapeNode?
    if shapeNode.hasFn(om.MFn.kMesh):
        inPlug = fn.findPlug("inMesh", True)
    elif shapeNode.hasFn(om.MFn.kNurbsCurve) or shapeNode.hasFn(om.MFn.kNurbsSurface):
        inPlug = fn.findPlug("create", True)
    else:
        return None

    itDg = om.MItDependencyGraph(inPlug, om.MFn.kSkinClusterFilter, om.MItDependencyGraph.kUpstream,
                                 om.MItDependencyGraph.kDepthFirst, om.MItDependencyGraph.kPlugLevel)
    while not itDg.isDone():
        node = itDg.currentNode()
        fn.setObject(node)
        message = fn.findPlug("message", True)
        if not message.isConnected:
            itDg.next()
            continue

        # confirm the set for this skinCluster is also connected to the shapeNode
        connections = message.connectedTo(False, True)
        for i, c in enumerate(connections):
            # if the connected node is not a set
            if not c.node().hasFn(om.MFn.kSet):
                continue

            # if the setMembers attr has no connections
            fn.setObject(c.node())
            setMembersPlug = fn.findPlug("dagSetMembers", True).elementByLogicalIndex(0)
            if not setMembersPlug.isConnected:
                continue

            # find the connected node, is it our shapeNode?
            cons = setMembersPlug.connectedTo(True, False)
            if cons[0].node() == shapeNode:
                return node
        itDg.next()
    return None

def _getSkinInputMeshData(skinCluster):
    fn = om.MFnDependencyNode(skinCluster)
    inData = fn.findPlug("input", True).elementByLogicalIndex(0).child(0)
    return inData.asMObject()

def _getSkinOutMeshData(skinCluster):
    fn = om.MFnDependencyNode(skinCluster)
    outData = fn.findPlug("outputGeometry", True).elementByLogicalIndex(0)
    return outData.asMObject()

def _getMeshDataPoints(meshData):
    fn = om.MFnMesh(meshData)
    return [om.MPoint(pnt) for pnt in fn.getPoints(om.MSpace.kObject)]

def _getSmearedPoints(skinCluster):
    inMesh = _getSkinInputMeshData(skinCluster)
    inPoints = _getMeshDataPoints(inMesh)
    # apply unit offsets to each points before the skinCluster,
    # return the point positions after the skinCluster for each x,y,z offsets
    return _offsetInputPoints(inPoints, skinCluster)

def _detachInputObjectFromSkin(skinCluster):
    fn = om.MFnDependencyNode(skinCluster)
    inDataPlug = fn.findPlug("input", True).elementByLogicalIndex(0).child(0)
    meshPlug = inDataPlug.source()
    if meshPlug.isNull:
        return
    dgMod = om.MDGModifier()
    dgMod.disconnect(meshPlug, inDataPlug)
    dgMod.doIt()
    return om.MPlug(meshPlug)

def _attachInputObjectToSkin(inPlug, skinCluster):
    dgMod = om.MDGModifier()
    fn = om.MFnDependencyNode(skinCluster)
    inDataPlug = fn.findPlug("input", True).elementByLogicalIndex(0).child(0)
    src = inDataPlug.source()
    if not src.isNull:
        dgMod.disconnect(src, inDataPlug)
    dgMod.connect(inPlug, inDataPlug)
    dgMod.doIt()

def _offsetInputPoints(inPoints, skinCluster):
    x = om.MVector(1, 0, 0)
    y = om.MVector(0, 1, 0)
    z = om.MVector(0, 0, 1)
    px = [om.MPoint(p + x) for p in inPoints]
    py = [om.MPoint(p + y) for p in inPoints]
    pz = [om.MPoint(p + z) for p in inPoints]
    return _setSkinInputData(px, skinCluster), _setSkinInputData(py, skinCluster), _setSkinInputData(pz, skinCluster)

def _setSkinInputData(inPoints, skinCluster):
    fn = om.MFnDependencyNode(skinCluster)
    inputPlug = fn.findPlug("input", True).elementByLogicalIndex(0).child(0)
    meshPlug = inputPlug.source()
    if meshPlug.isNull:
        return

    mesh = meshPlug.asMObject()
    fnMesh = om.MFnMesh(mesh)

    # this probably isnt the best way to do this, but it works fine
    fnMesh.copy(mesh)
    fnMesh.setPoints(inPoints, om.MSpace.kObject)
    outMeshPlug = fnMesh.findPlug('outMesh', True)

    source = _detachInputObjectFromSkin(skinCluster)

    dgMod = om.MDGModifier()
    dgMod.connect(outMeshPlug, inputPlug)
    dgMod.doIt()

    posePoints = _getMeshDataPoints(_getSkinOutMeshData(skinCluster))
    _attachInputObjectToSkin(source, skinCluster)

    p = fnMesh.parent(0)

    # I dont know why the api crashes when trying to delete 'p'
    cmds.delete(om.MDagPath.getAPathTo(p).fullPathName())

    return posePoints

def _subtractPoseFromSmearPnts(posePnts, px, py, pz):
    ox = [om.MVector(x - p) for p, x in zip(posePnts, px)]
    oy = [om.MVector(y - p) for p, y in zip(posePnts, py)]
    oz = [om.MVector(z - p) for p, z in zip(posePnts, pz)]
    return ox, oy, oz

def _createPointMatrices(skinnedPosePnts, smearX, smearY, smearZ):
    return [matrixFromList((x[0], x[1], x[2], 0.0,
                            y[0], y[1], y[2], 0.0,
                            z[0], z[1], z[2], 0.0,
                            p[0], p[1], p[2], 1.0)).inverse() for p, x, y, z in zip(skinnedPosePnts, smearX, smearY, smearZ)]

def _computeDeltas(pointMatrices, shape):
    fn = om.MFnMesh(shape)
    shapePoints = fn.getPoints(om.MSpace.kObject)
    return [om.MVector(shapePoint * pointMatrix) for shapePoint, pointMatrix in zip(shapePoints, pointMatrices)]

def _generateShapeFromDeltas(restShape, deltas):
    fn = om.MFnMesh()
    shape = fn.copy(restShape.node())

    #add the deltas to the restShape to create the corrective shape target
    pnts = fn.getPoints(om.MSpace.kObject)
    for i, (p, d) in enumerate(zip(pnts, deltas)):
        pnts[i] = p + d

    fn.setPoints(pnts, om.MSpace.kObject)
    return om.MObject(shape)
