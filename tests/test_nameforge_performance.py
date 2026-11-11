"""NameForge spatial broad-phase tests; independent of FreeCAD and Qt."""
import importlib
import random
import unittest


engine = importlib.import_module("freecad.RSMaker.nameforge_engine")


class Bounds:
    def __init__(self, xmin, ymin, xmax, ymax):
        self.XMin, self.YMin = xmin, ymin
        self.XMax, self.YMax = xmax, ymax
        self.XLength, self.YLength = xmax - xmin, ymax - ymin


class Region:
    def __init__(self, x1, y1, x2, y2):
        self.BoundBox = Bounds(x1, y1, x2, y2)


class SpatialTests(unittest.TestCase):
    def test_candidates_equal_brute_force_on_random_regions(self):
        random.seed(42)
        bounds = Bounds(0, 0, 200, 200)
        index = engine.SpatialBuckets(bounds, 500)
        inserted = []
        for _ in range(500):
            x, y = random.uniform(1, 190), random.uniform(1, 190)
            rect = Region(x, y, x + random.uniform(.3, 8),
                          y + random.uniform(.3, 8))
            self.assertEqual(set(map(id, index.overlaps(rect))),
                             {id(shape) for shape in inserted if engine.overlap_xy(rect, shape)})
            index.insert(rect)
            inserted.append(rect)

    def test_sparse_shapes_avoid_quadratic_checks(self):
        rects = [Region((i % 50) * 4, (i // 50) * 4,
                        (i % 50) * 4 + 1, (i // 50) * 4 + 1) for i in range(1000)]
        index = engine.SpatialBuckets(Bounds(0, 0, 200, 100), 1000)
        for rect in rects:
            self.assertFalse(index.overlaps(rect))
            index.insert(rect)
        self.assertLess(index.candidate_checks, 10000)

    def test_large_background_is_found(self):
        index = engine.SpatialBuckets(Bounds(0, 0, 100, 100), 50)
        background = Region(0, 0, 100, 100)
        index.insert(background)
        self.assertEqual(index.overlaps(Region(20, 20, 21, 21)), [background])

    def test_cache_is_bounded(self):
        cache = engine.OrderedDict()
        for i in range(9):
            engine._remember(cache, str(i), object())
        self.assertEqual(list(cache), ["7", "8"])


if __name__ == "__main__":
    unittest.main()
