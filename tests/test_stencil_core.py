"""Standalone tests: stencil holes and no-floating-letter guarantees."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from freecad.RSMaker import stencil_core as st


def rect(mask,w,x1,y1,x2,y2,value=1):
    for y in range(y1,y2):
        for x in range(x1,x2):
            mask[y*w+x]=value


class StencilTests(unittest.TestCase):
    def test_fill_holes(self):
        w,h=34,28
        m=bytearray(w*h)
        rect(m,w,4,4,30,24)
        rect(m,w,11,10,22,18,0)
        self.assertFalse(m[14*w+15])
        filled=st.fill_holes(m,w,h)
        self.assertTrue(filled[14*w+15])
        self.assertFalse(filled[0])

    def test_hollow_O_keeps_center_printable(self):
        w,h=90,70
        full=bytearray(w*h)
        rect(full,w,3,3,87,67)
        letters=bytearray(w*h)
        rect(letters,w,27,12,63,59)
        rect(letters,w,37,23,53,49,0)
        plate=bytearray(v and not letters[i] for i,v in enumerate(full))
        self.assertEqual(len(st.connected_components(plate,w,h)),2)
        connected,bridges,removed=st.connect_islands(plate,full,w,h,2,1)
        self.assertEqual(bridges,1)
        self.assertEqual(removed,0)
        self.assertEqual(len(st.connected_components(connected,w,h)),1)
        self.assertTrue(any(connected[y*w+32] for y in range(25,45)))
        self.assertFalse(connected[18*w+45])

    def test_nested_islands_connect_at_any_detail(self):
        # Three enclosed material rings: an outer body and two islands.
        # The second island can only be reached by passing through the first.
        # The original BFS stopped at that island, incorrectly claiming
        # the drawing was too detailed to support.
        for size in (80, 240):
            with self.subTest(size=size):
                w=h=size
                envelope=bytearray([1])*(w*h)
                material=bytearray(w*h)

                def ring(a,b,thick):
                    rect(material,w,a,a,b,b)
                    rect(material,w,a+thick,a+thick,b-thick,b-thick,0)

                ring(2,size-2,max(2,size//80))
                ring(size//6,size-size//6,max(2,size//80))
                ring(size//3,size-size//3,max(2,size//80))
                self.assertEqual(len(st.connected_components(material,w,h)),3)
                result,bridges,removed=st.connect_islands(
                    material,envelope,w,h,bridge_radius=2,min_island=2)
                self.assertEqual((bridges,removed),(2,0))
                self.assertEqual(len(st.connected_components(result,w,h)),1)
                self.assertFalse(result[(size//2)*w+size//2],
                                 "El centro calado debe permanecer abierto")

    def test_unreachable_islands_have_actionable_error(self):
        # Totally disconnected silhouette sections cannot be repaired using
        # only internal aperture bridges. The error must identify that case.
        w=h=40
        envelope=bytearray(w*h)
        material=bytearray(w*h)
        rect(envelope,w,2,2,12,12)
        rect(envelope,w,29,29,39,39)
        rect(material,w,2,2,12,12)
        rect(material,w,29,29,39,39)
        with self.assertRaisesRegex(ValueError,"fuera de la silueta"):
            st.connect_islands(material,envelope,w,h,2,2)

    def test_remove_tiny_loose_specks(self):
        w=h=40
        envelope=bytearray(w*h)
        rect(envelope,w,0,0,40,40)
        front=bytearray(w*h)
        rect(front,w,0,0,20,40)
        front[25*w+30]=1
        out,bridges,removed=st.connect_islands(front,envelope,w,h,1,2)
        self.assertEqual((bridges,removed),(0,1))
        self.assertFalse(out[25*w+30])

    def test_diagonal_contact_repaired_without_detaching_islands(self):
        w=h=45
        material=bytearray(w*h)
        rect(material,w,2,2,43,43)
        rect(material,w,10,10,35,35,0)
        # A pinched letter counter, with diagonally touching borders.
        material[10*w+10]=1
        material[11*w+11]=1
        fixed,count=st.repair_diagonal_contacts(material,w,h)
        self.assertGreaterEqual(count,1)
        self.assertEqual(len(st.connected_components(fixed,w,h)),1)
        # Pixel-level boundaries should no longer have checkerboard crossings.
        for y in range(h-1):
            for x in range(w-1):
                i=y*w+x
                a,b,c,d=fixed[i],fixed[i+1],fixed[i+w],fixed[i+w+1]
                self.assertFalse(a and d and not b and not c)
                self.assertFalse(b and c and not a and not d)
        rings=st.contours(fixed,w,h,tolerance=.85)
        self.assertTrue(rings)

    def test_proportional_resize_keeps_ratio(self):
        ratio = 160 / 170
        width, height = st.proportional_size(220, 170, ratio, "width")
        self.assertAlmostEqual(width / height, ratio, places=3)
        width2, height2 = st.proportional_size(width, 300, ratio, "height")
        self.assertAlmostEqual(width2 / height2, ratio, places=3)
        self.assertNotEqual(width2, width)

    def test_proportional_resize_clamps_to_both_limits(self):
        width, height = st.proportional_size(430, 90, 2.5, "height")
        self.assertAlmostEqual(width / height, 2.5, places=2)
        self.assertLessEqual(width, 430)
        self.assertLessEqual(height, 430)
        width, height = st.proportional_size(430, 100, 2.5, "width")
        self.assertLessEqual(width, 430)
        self.assertAlmostEqual(width / height, 2.5, places=2)

    def test_suggest_dimensions_monotonic_complexity(self):
        w=h=64
        simple=bytearray(w*h)
        for y in range(14,50):
            for x in range(14,50):
                simple[y*w+x]=1
        intricate=bytearray(w*h)
        for y in range(14,50):
            for x in range(14,50):
                intricate[y*w+x]=int(x%2==0 or y%2==0)
        a=st.suggest_dimensions(simple,w,h)
        b=st.suggest_dimensions(intricate,w,h)
        self.assertGreaterEqual(b["height"], a["height"])

    def test_quality_profiles_are_progressive_and_bounded(self):
        modes=["fast","balanced","high"]
        values=[st.quality_settings(mode,160,170) for mode in modes]
        self.assertLess(values[0]["scale"], values[1]["scale"])
        self.assertLess(values[1]["scale"], values[2]["scale"])
        for mode in modes:
            settings=st.quality_settings(mode,430,430)
            pixels=(round(430*settings["scale"])**2)
            self.assertLess(pixels,st.QUALITY_MODES[mode]["max_pixels"]*1.01)
        with self.assertRaises(ValueError):
            st.quality_settings("unsafe",150,150)

    def test_spline_spans_keep_closed_loops_and_sharp_corners(self):
        from freecad.RSMaker.curve_fit import sharp_corners, spline_spans
        square=[(4,4),(50,4),(50,50),(4,50)]
        self.assertEqual(len(sharp_corners(square)),4)
        parts=spline_spans(square)
        self.assertEqual(len(parts),4)
        self.assertEqual(sum(len(segment)-1 for segment in parts),len(square))
        for i,segment in enumerate(parts):
            self.assertEqual(segment[-1],parts[(i+1)%len(parts)][0])

    def test_smoothing_does_not_change_sharp_spikes_or_shift_supports(self):
        from math import hypot
        from freecad.RSMaker.curve_fit import smooth_ring, spline_spans
        points=[(1,1),(30,1),(32,11),(34,12),(36,13),
                (38,14),(40,15),(42,16),(30,35),(1,35)]
        smoothed=smooth_ring(points,iterations=3)
        self.assertEqual(smoothed[0],(1.0,1.0))
        self.assertEqual(smoothed[1],(30.0,1.0))
        self.assertTrue(any(a!=tuple(b) for a,b in zip(smoothed,points)))
        self.assertTrue(all(hypot(a[0]-b[0],a[1]-b[1])<=.681
                            for a,b in zip(smoothed,points)))
        spans=spline_spans(smoothed,max_points=5)
        self.assertEqual(sum(len(segment)-1 for segment in spans),len(points))
        for index,span in enumerate(spans):
            self.assertEqual(span[-1],spans[(index+1)%len(spans)][0])

    def test_rounded_hole_and_outline_still_generate_two_contours(self):
        from freecad.RSMaker.curve_fit import spline_spans
        w=h=80
        mask=bytearray(w*h)
        rect(mask,w,6,6,74,74)
        rect(mask,w,25,25,54,54,0)
        for mode in ("balanced","high"):
            contours=st.cleaned_contours(mask,w,h,mode)
            self.assertEqual(len(contours),2)
            for path in contours:
                self.assertTrue(spline_spans(path))
                self.assertGreaterEqual(len(path),4)

    def test_quality_smoothing_preserves_hole_and_outline(self):
        w=h=70
        mask=bytearray(w*h)
        rect(mask,w,5,5,65,65)
        rect(mask,w,22,22,48,48,0)
        counts=[]
        for mode in ("fast","balanced","high"):
            loops=st.cleaned_contours(mask,w,h,mode)
            counts.append(len(loops))
            self.assertEqual(len(loops),2)
            self.assertTrue(any(st.polygon_area(p)>0 for p in loops))
            self.assertTrue(any(st.polygon_area(p)<0 for p in loops))
        self.assertEqual(counts,[2,2,2])

    def test_svg_paths_preserve_counters(self):
        w=h=50
        m=bytearray(w*h)
        rect(m,w,3,3,47,47)
        rect(m,w,14,14,35,35,0)
        rings=st.contours(m,w,h)
        self.assertEqual(len(rings),2)
        self.assertTrue(any(st.polygon_area(r)>0 for r in rings))
        self.assertTrue(any(st.polygon_area(r)<0 for r in rings))
        svg=st.to_svg(rings,w,h,2)
        self.assertIn('fill-rule="evenodd"',svg)
        self.assertIn('25mm',svg)

    def test_close_connects_nearby_artwork(self):
        w=h=60
        m=bytearray(w*h)
        rect(m,w,10,10,20,40)
        rect(m,w,23,10,35,40)
        self.assertEqual(len(st.connected_components(m,w,h)),2)
        result=st.close(m,w,h,2)
        self.assertEqual(len(st.connected_components(result,w,h)),1)


if __name__=='__main__':
    unittest.main()
