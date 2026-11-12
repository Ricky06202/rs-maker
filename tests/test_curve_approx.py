"""Regression: fitted NameForge outlines must approximate noisy points.

No FreeCAD installation is required; mocks check the CAD API selection and
the exact-endpoint wiring. A real OpenCascade shape test remains outstanding.
"""
import importlib
import math
import sys
import types
import unittest
from unittest.mock import patch

from freecad.RSMaker.curve_fit import spline_spans


class Vector:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    def distanceToPoint(self, other):
        return math.dist((self.x,self.y,self.z),
                         (other.x,other.y,other.z))


class Edge:
    def __init__(self, a, b):
        self.start, self.end = a, b
        self.Vertexes = [
            types.SimpleNamespace(Point=a),
            types.SimpleNamespace(Point=b),
        ]


class FakeWire:
    def __init__(self, edges):
        self.edges=list(edges)

    def isClosed(self):
        return bool(self.edges) and (
            all(self.edges[i].end.distanceToPoint(
                self.edges[i+1].start)<1e-5
                for i in range(len(self.edges)-1))
            and self.edges[-1].end.distanceToPoint(
                self.edges[0].start)<1e-5)

    def isValid(self):
        return self.isClosed()


class FakeBSpline:
    calls = []

    def __init__(self):
        self.points=[]

    def interpolate(self, **kwargs):
        raise AssertionError("No interpolar todos los puntos de los píxeles")

    def approximate(self, **kwargs):
        self.calls.append(kwargs)
        self.points=kwargs["Points"]

    def toShape(self):
        # OCC approximation can move the endpoints slightly. Connecting
        # segments must bridge that small distance to maintain closed wires.
        first=self.points[0]
        last=self.points[-1]
        return Edge(
            Vector(first.x+.025,first.y,first.z),
            Vector(last.x-.025,last.y,last.z),
        )


class CurveApproxTests(unittest.TestCase):
    def test_tolerance_is_print_safe_and_scales_with_image(self):
        dummy=types.ModuleType("PySide2")
        dummy.QtCore=types.SimpleNamespace()
        dummy.QtGui=types.SimpleNamespace()
        dummy.QtSvg=types.SimpleNamespace()
        with patch.dict(sys.modules,{"PySide2":dummy}):
            lamp=importlib.import_module("freecad.RSMaker.lamp_stencil")
        self.assertLessEqual(lamp._spline_tolerance(4),.20)
        self.assertLess(lamp._spline_tolerance(10),
                        lamp._spline_tolerance(4))
        self.assertGreater(lamp._spline_tolerance(10),0)

    def test_approximate_is_used_and_endpoints_stay_closed(self):
        dummy=types.ModuleType("PySide2")
        dummy.QtCore=types.SimpleNamespace()
        dummy.QtGui=types.SimpleNamespace()
        dummy.QtSvg=types.SimpleNamespace()
        app=types.ModuleType("FreeCAD")
        app.Vector=Vector
        part=types.ModuleType("Part")
        part.BSplineCurve=FakeBSpline
        part.makeLine=lambda a,b:Edge(a,b)
        part.Wire=FakeWire
        def polygon(points):
            return types.SimpleNamespace(
                Edges=[Edge(points[i],points[i+1])
                       for i in range(len(points)-1)])
        part.makePolygon=polygon
        points=[
            (40 + 24*math.cos(2*math.pi*i/40),
             40 + 24*math.sin(2*math.pi*i/40))
            for i in range(40)
        ]
        spans=spline_spans(points,max_points=14)
        FakeBSpline.calls=[]
        with patch.dict(sys.modules,{
                "PySide2":dummy,"FreeCAD":app,"Part":part}):
            lamp=importlib.import_module("freecad.RSMaker.lamp_stencil")
            wire=lamp._spline_wire(spans,90,90,4)
        self.assertTrue(FakeBSpline.calls)
        self.assertTrue(wire.isClosed())
        self.assertTrue(wire.isValid())
        for kwargs in FakeBSpline.calls:
            self.assertEqual(kwargs["Continuity"],"C1")
            self.assertEqual(kwargs["DegMin"],3)
            self.assertLessEqual(kwargs["Tolerance"],.20)


if __name__=="__main__":
    unittest.main()
