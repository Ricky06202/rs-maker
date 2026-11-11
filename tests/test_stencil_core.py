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
