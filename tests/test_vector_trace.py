"""Specialized line-art vectorization and rear-envelope regression tests."""
import unittest

from freecad.RSMaker import stencil_core as core
from freecad.RSMaker import vector_trace as tracer


def rect(mask,w,x0,y0,x1,y1,value=1):
    for y in range(y0,y1):
        for x in range(x0,x1):
            mask[y*w+x]=value


class LineArtVectorizationTests(unittest.TestCase):
    def test_subpixel_donut_has_outer_and_real_hole(self):
        w=h=84
        mask=bytearray(w*h)
        rect(mask,w,4,4,80,80)
        rect(mask,w,25,25,59,59,0)
        traced=tracer.subpixel_contours(mask,w,h,tolerance=.30)
        self.assertEqual(len(traced),2)
        self.assertEqual(sum(core.polygon_area(r)>0 for r in traced),1)
        self.assertEqual(sum(core.polygon_area(r)<0 for r in traced),1)
        self.assertTrue(any(abs(x-round(x))>1e-3 for ring in traced
                            for x,y in ring),
                        "Las curvas tienen que tener coordenadas subpíxel")
        self.assertTrue(all(-1<=x<=w+1 and -1<=y<=h+1
                            for ring in traced for x,y in ring))

    def test_boundary_rectangle_has_closed_outer_ring(self):
        # The caption plate touches the side/bottom image edges.
        w,h=115,92
        mask=bytearray(w*h)
        rect(mask,w,0,55,w,h)
        rings=tracer.subpixel_contours(mask,w,h,tolerance=.2)
        self.assertEqual(len(rings),1)
        self.assertGreater(core.polygon_area(rings[0]),0)
        self.assertGreater(len(rings[0]),3)

    def test_curved_figure_preserves_counters(self):
        w=h=122
        mask=bytearray(w*h)
        for y in range(h):
            for x in range(w):
                if (x-60)**2+(y-60)**2<46**2:
                    mask[y*w+x]=1
                if (x-60)**2+(y-60)**2<20**2:
                    mask[y*w+x]=0
        traced,method=tracer.trace_or_fallback(mask,w,h,"high")
        self.assertEqual(method,"subpíxel")
        self.assertEqual(len(traced),2)
        self.assertTrue(any(core.polygon_area(p)>0 for p in traced))
        self.assertTrue(any(core.polygon_area(p)<0 for p in traced))

    def test_tiny_hole_uses_only_local_polygon_fallback(self):
        w=h=115
        mask=bytearray(w*h)
        rect(mask,w,5,5,110,110)
        rect(mask,w,30,30,80,80,0)
        mask[91*w+90]=0  # A 1-pixel counter, too small for Gaussian tracing.
        old=core.contours(mask,w,h,tolerance=.52,min_area=.5)
        self.assertEqual(len(old),3)
        result,method=tracer.trace_or_fallback(mask,w,h,"high")
        self.assertEqual(len(result),3)
        self.assertTrue(method.startswith("subpíxel mixto"))
        self.assertEqual(sum(core.polygon_area(r)>0 for r in result),1)
        self.assertEqual(sum(core.polygon_area(r)<0 for r in result),2)

    def test_fast_mode_keeps_lightweight_polygons(self):
        w=h=55
        mask=bytearray(w*h)
        rect(mask,w,3,3,52,52)
        _,method=tracer.trace_or_fallback(mask,w,h,"fast")
        self.assertEqual(method,"rápido")

    def test_rear_is_not_inferred_from_front_bridges(self):
        # Artwork + plaque: a diagonal cut-out region must not be covered
        # merely because an unrelated front-only stroke surrounds it.
        w=h=90
        envelope=bytearray(w*h)
        rect(envelope,w,0,65,w,h)
        rect(envelope,w,36,14,58,73)
        rear=core.solid_rear_envelope(envelope,w,h)
        front=bytearray(envelope)
        # Draw a diagonal stencil bridge that makes a triangular exterior
        # pocket between left side of character and upper caption plate.
        for i in range(20):
            front[(45+i)*w+16+i]=1
        front=core.repair_diagonal_contacts(front,w,h)[0]
        self.assertEqual(len(core.connected_components(rear,w,h)),1)
        self.assertEqual(rear[58*w+15],0)
        self.assertEqual(rear[58*w+28],0)
        self.assertEqual(rear[70*w+50],1)
        self.assertEqual(rear,core.solid_rear_envelope(envelope,w,h))


if __name__=="__main__":
    unittest.main()
