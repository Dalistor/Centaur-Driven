import unittest

from intervals import merge, total_length


class IntervalTests(unittest.TestCase):
    def test_touching_intervals_are_joined(self):
        self.assertEqual(merge([[1, 3], [3, 5]]), [[1, 5]])

    def test_contained_interval_does_not_shrink_the_outer_one(self):
        self.assertEqual(merge([[1, 10], [2, 3]]), [[1, 10]])
        self.assertEqual(total_length([[1, 10], [2, 3], [20, 21]]), 10)

    def test_disjoint_intervals_stay_apart(self):
        self.assertEqual(merge([[5, 6], [1, 2]]), [[1, 2], [5, 6]])


if __name__ == '__main__':
    unittest.main()
