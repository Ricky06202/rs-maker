"""Regression tests for filled-black icon/silhouette artwork.

The original user image is not committed: these reproduce its topology with
synthetic eye counters and thick black artwork. Tests run without FreeCAD.
"""
import importlib
import sys
import types
import unittest
from unittest.mock import patch

from freecad.RSMaker import stencil_core as core


def rect(mask,w,x0,y0,x1,y1,value=1):
    for y in range(y0,y1):
        for x in range(x0,x1):
            mask[y*w+x]=value


class SolidBlackArtworkTests(unittest.TestCase):
    def test_filled_icon_is_not_mistaken_for_ink_linework(self):
        w=h=100
        outer=bytearray(w*h)
        rect(outer,w,15,12,85,87)
        ink=bytearray(outer)
        rect(ink,w,27,25,48,50,0)  # white eye window
        rect(ink,w,55,25,76,50,0)
        rect(ink,w,34,32,42,43,1)  # black pupil island
        rect(ink,w,62,32,70,43,1)
        style,density=core.classify_artwork(ink,outer,w,h)
        self.assertEqual(style,"silhouette")
        self.assertGreater(density,.62)

    def test_line_illustration_keeps_line_art_behavior(self):
        w=h=100
        envelope=bytearray(w*h)
        rect(envelope,w,9,9,91,91)
        ink=bytearray(w*h)
        for y in range(9,91):
            rect(ink,w,9,y,11,y+1)
            rect(ink,w,89,y,91,y+1)
        for x in range(9,91):
            ink[9*w+x]=1
            ink[90*w+x]=1
        style,density=core.classify_artwork(ink,envelope,w,h)
        self.assertEqual(style,"lineart")
        self.assertLess(density,.62)

    def test_tiny_raster_specks_are_not_cad_perforations(self):
        w=h=40
        cut=bytearray(w*h)
        cut[8*w+8]=1
        cut[10*w+10]=1
        rect(cut,w,16,16,28,28)
        preserved,removed=core.clean_tiny_cutouts(cut,w,h,4)
        self.assertEqual(removed,2)
        self.assertEqual(sum(preserved),12*12)

    def test_worker_keeps_black_body_and_cuts_eyes(self):
        dummy=types.ModuleType("PySide2")
        dummy.QtCore=types.SimpleNamespace()
        dummy.QtGui=types.SimpleNamespace()
        dummy.QtSvg=types.SimpleNamespace()
        w=h=84
        art_w=74
        art_h=64
        ink=bytearray(art_w*art_h)
        outer=bytearray(art_w*art_h)
        rect(outer,art_w,8,4,66,58)
        ink[:]=outer
        rect(ink,art_w,19,15,36,36,0)
        rect(ink,art_w,43,15,60,36,0)
        rect(ink,art_w,24,20,31,30,1)
        rect(ink,art_w,48,20,55,30,1)
        prepared=dict(scale=1,w=w,h=h,margin=5,top_of_band=66,
                      art_w=art_w,art_h=art_h,
                      cached=(bytes(ink),bytes(outer)),
                      text_w=74,text_h=10,letters=bytearray(74*10))
        cfg=types.SimpleNamespace(bridge_width=1.6,
                                  quality_mode="fast",compute_backend="cpu")
        with patch.dict(sys.modules,{"PySide2":dummy}):
            lamp=importlib.import_module("freecad.RSMaker.lamp_stencil")
            meta=lamp.build_masks(cfg,prepared)
        self.assertEqual(meta["artwork"]["style"],"silhouette")
        self.assertEqual(len(core.connected_components(
            meta["front_mask"],w,h)),1)
        self.assertEqual(len(core.connected_components(
            meta["rear_mask"],w,h)),1)
        # Figure is translated so the bottom overlaps the title plaque.
        overlap=max(round(5.0*prepared["scale"]),
                    round(cfg.bridge_width*prepared["scale"]*2.5))
        dy=prepared["top_of_band"]+overlap-prepared["margin"]-57
        y0=prepared["margin"]+dy
        x0=prepared["margin"]
        # Black face remains material; white eyes become through-cutouts.
        face=meta["front_mask"]
        self.assertEqual(face[(y0+44)*w+(x0+38)],1)
        self.assertEqual(face[(y0+24)*w+(x0+22)],0)
        self.assertEqual(face[(y0+24)*w+(x0+47)],0)
        # Pupil centers stay printable, tied by existing support bridges.
        self.assertEqual(face[(y0+24)*w+(x0+27)],1)
        self.assertEqual(face[(y0+24)*w+(x0+51)],1)

if __name__=="__main__":
    unittest.main()
