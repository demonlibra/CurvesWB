# -*- coding: utf-8 -*-

__title__ = "Interpolate"
__author__ = "Christophe Grellier (Chris_G)"
__license__ = "LGPL 2.1"
__doc__ = "Interpolate a set of points."

import FreeCAD
import FreeCADGui
import Part
import _utils

TOOL_ICON = _utils.iconsPath() + '/interpolate.svg'
debug = _utils.debug
#debug = _utils.doNothing


# ********************************************************
# **** Part.BSplineCurve.interpolate() documentation *****
# ********************************************************

#Replaces this B-Spline curve by interpolating a set of points.
#The function accepts keywords as arguments.

#interpolate(Points = list_of_points) 

#Optional arguments :

#PeriodicFlag = bool (False) : Sets the curve closed or opened.
#Tolerance = float (1e-6) : interpolating tolerance

#Parameters : knot sequence of the interpolated points.
#If not supplied, the function defaults to chord-length parameterization.
#If PeriodicFlag == True, one extra parameter must be appended.

#EndPoint Tangent constraints :

#InitialTangent = vector, FinalTangent = vector
#specify tangent vectors for starting and ending points 
#of the BSpline. Either none, or both must be specified.

#Full Tangent constraints :

#Tangents = list_of_vectors, TangentFlags = list_of_bools
#Both lists must have the same length as Points list.
#Tangents specifies the tangent vector of each point in Points list.
#TangentFlags (bool) activates or deactivates the corresponding tangent.
#These arguments will be ignored if EndPoint Tangents (above) are also defined.

#Note : Continuity of the spline defaults to C2. However, if periodic, or tangents 
#are supplied, the continuity will drop to C1.

class Interpolate:
    def __init__(self, obj , source):
        ''' Add the properties '''
        debug("\nInterpolate class Init\n")
        obj.addProperty("App::PropertyLinkSubList",    "PointList",      "General",    "Point list to interpolate").PointList = source
        obj.addProperty("App::PropertyBool",           "Periodic",       "General",    "Set the curve closed").Periodic = False
        obj.addProperty("App::PropertyFloat",          "Tolerance",      "General",    "Interpolation tolerance").Tolerance = 1e-7
        obj.addProperty("App::PropertyBool",           "CustomTangents", "General",    "User specified tangents").CustomTangents = False
        obj.addProperty("App::PropertyBool",           "DetectAligned",  "General",    "interpolate 3 aligned points with a line").DetectAligned = True
        obj.addProperty("App::PropertyBool",           "Polygonal",      "General",    "interpolate with a degree 1 polygonal curve").Polygonal = False
        obj.addProperty("App::PropertyFloatList",      "Parameters",     "Parameters", "Parameters of interpolated points")
        obj.addProperty("App::PropertyEnumeration",    "Parametrization","Parameters", "Parametrization type").Parametrization=["ChordLength","Centripetal","Uniform","Custom"]
        obj.addProperty("App::PropertyVectorList",     "Tangents",       "General",   "Tangents at interpolated points")
        obj.addProperty("App::PropertyBoolList",       "TangentFlags",   "General",   "Activation flag of tangents")
        obj.Proxy = self
        self.obj = obj
        obj.Parametrization = "ChordLength"
        obj.setEditorMode("CustomTangents", 2)

    def setTolerance(self, obj):
        try:
            l = obj.PointObject.Shape.BoundBox.DiagonalLength
            obj.ApproxTolerance = l / 10000.0
        except:
            obj.ApproxTolerance = 0.001

    def getPoints( self, obj):
        vl = _utils.getShape(obj, "PointList", "Vertex")
        return([v.Point for v in vl]) 

    def detect_aligned_pts(self, fp, pts):
        tol = .99
        tans = fp.Tangents
        flags = [False]*len(pts) #list(fp.TangentFlags)
        for i in range(len(pts)-2):
            v1 = pts[i+1]-pts[i]
            v2 = pts[i+2]-pts[i+1]
            l1 = v1.Length
            l2 = v2.Length
            v1.normalize()
            v2.normalize()
            if v1.dot(v2) > tol:
                debug("aligned points detected : %d - %d - %d"%(i,i+1,i+2))
                tans[i] = v1.multiply(l1/3.0)
                tans[i+2] = v2.multiply(l2/3.0)
                tans[i+1] = (v1+v2).multiply(min(l1,l2)/6.0)
                flags[i] = True
                flags[i+1] = True
                flags[i+2] = True
        fp.Tangents = tans
        fp.TangentFlags = flags
        

    def execute(self, obj):
        debug("* Interpolate : execute *")
        pts = self.getPoints( obj)
        if obj.Polygonal:
            if obj.Periodic:
                pts.append(pts[0])
            poly = Part.makePolygon(pts)
            bs = poly.approximate(1e-8,obj.Tolerance,999,1)
            obj.Shape = bs.toShape()
        else:
            bs = Part.BSplineCurve()
            bs.interpolate(Points=pts, PeriodicFlag=obj.Periodic, Tolerance=obj.Tolerance, Parameters=obj.Parameters)
            if not (len(obj.Tangents) == len(pts) and len(obj.TangentFlags) == len(pts)) or obj.DetectAligned:
                if obj.Periodic:
                    obj.Tangents = [bs.tangent(p)[0] for p in obj.Parameters[0:-1]]
                else:
                    obj.Tangents = [bs.tangent(p)[0] for p in obj.Parameters]
                obj.TangentFlags = [True]*len(pts)
            if obj.CustomTangents or obj.DetectAligned:
                if obj.DetectAligned:
                    self.detect_aligned_pts(obj, pts)
                bs.interpolate(Points=pts, PeriodicFlag=obj.Periodic, Tolerance=obj.Tolerance, Parameters=obj.Parameters, Tangents=obj.Tangents, TangentFlags=obj.TangentFlags) #, Scale=False)
        obj.Shape = bs.toShape()

    def setParameters(self, obj, val):
        # Computes a knot Sequence for a set of points
        # fac (0-1) : parameterization factor
        # fac=0 -> Uniform / fac=0.5 -> Centripetal / fac=1.0 -> Chord-Length
        pts = self.getPoints( obj)
        if obj.Periodic: # we need to add the first point as the end point
            pts.append(pts[0])
        params = [0]
        for i in range(1,len(pts)):
            p = pts[i].sub(pts[i-1])
            pl = pow(p.Length,val)
            params.append(params[-1] + pl)
        m = float(max(params))
        obj.Parameters = [p/m for p in params]

    def touch_parametrization(self, fp):
        p = fp.Parametrization
        fp.Parametrization = p
            
    def onChanged(self, fp, prop):
        #print fp
        if not fp.PointList:
            return

        if prop == "Parametrization":
            debug("Approximate : Parametrization changed\n")
            if fp.Parametrization == "Custom":
                fp.setEditorMode("Parameters", 0)
            else:
                fp.setEditorMode("Parameters", 2)
                if fp.Parametrization == "ChordLength":
                    self.setParameters(fp, 1.0)
                elif fp.Parametrization == "Centripetal":
                    self.setParameters(fp, 0.5)
                elif fp.Parametrization == "Uniform":
                    self.setParameters(fp, 0.0)
        if prop == "Polygonal":
            if fp.Polygonal:
                fp.setEditorMode("CustomTangents", 2)
                fp.setEditorMode("DetectAligned", 2)
                fp.setEditorMode("Parameters", 2)
                fp.setEditorMode("Parametrization", 2)
                fp.setEditorMode("Tangents", 2)
                fp.setEditorMode("TangentFlags", 2)
            else:
                fp.setEditorMode("CustomTangents", 0)
                fp.setEditorMode("DetectAligned", 0)
                fp.setEditorMode("Parameters", 0)
                fp.setEditorMode("Parametrization", 0)
                fp.setEditorMode("Tangents", 0)
                fp.setEditorMode("TangentFlags", 0)
        if prop in ["Periodic","PointList"]:
            self.touch_parametrization(fp)
        if prop == "Parameters":
            self.execute(fp)

    def onDocumentRestored(self, fp):
        fp.setEditorMode("CustomTangents", 2)
        self.touch_parametrization(fp)

    def __getstate__(self):
        out = {"name": self.obj.Name}
        return(out)

    def __setstate__(self,state):
        self.obj = FreeCAD.ActiveDocument.getObject(state["name"])
        return(None)

class ViewProviderInterpolate:
    def __init__(self,vobj):
        vobj.Proxy = self
       
    def getIcon(self):
        return (TOOL_ICON)

    def attach(self, vobj):
        self.Object = vobj.Object
  
    def setEdit(self,vobj,mode):
        return False
    
    def unsetEdit(self,vobj,mode):
        return

    def __getstate__(self):
        return({"name": self.Object.Name})

    def __setstate__(self,state):
        self.Object = FreeCAD.ActiveDocument.getObject(state["name"])
        return(None)

    #def claimChildren(self):
        #return [self.Object.PointObject]
        
    #def onDelete(self, feature, subelements):
        #try:
            #self.Object.PointObject.ViewObject.Visibility=True
        #except Exception as err:
            #App.Console.PrintError("Error in onDelete: " + err.message)
        #return(True)

class interpolate:
    def parseSel(self, selectionObject):
        verts = list()
        for obj in selectionObject:
            if obj.HasSubObjects:
                for n in obj.SubElementNames:
                    if 'Vertex' in n:
                        verts.append((obj.Object,[n]))
            else:
                for i in range(len(obj.Object.Shape.Vertexes)):
                    verts.append((obj.Object,"Vertex%d"%(i+1)))
        if verts:
            return(verts)
        else:
            FreeCAD.Console.PrintMessage("\nPlease select an object that has at least 2 vertexes")
            return(None)

    def Activated(self):
        s = FreeCADGui.Selection.getSelectionEx()
        try:
            ordered = FreeCADGui.activeWorkbench().Selection
            if ordered:
                s = ordered
        except AttributeError:
            pass
        source = self.parseSel(s)
        if not source:
            return(False)
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython","Interpolation_Curve") #add object to document
        Interpolate(obj,source)
        ViewProviderInterpolate(obj.ViewObject)
        FreeCAD.ActiveDocument.recompute()
            
    def GetResources(self):
        return {'Pixmap' : TOOL_ICON, 'MenuText': 'Interpolate', 'ToolTip': 'Interpolate points with a BSpline curve'}

FreeCADGui.addCommand('Interpolate', interpolate())



