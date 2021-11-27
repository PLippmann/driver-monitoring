from __future__ import division
import cv2
from .iris import Iris


class Initialize(object):
    def __init__(self):
        self.left_threshold = []
        self.right_threshold = []
        self.buffer = 20

    @staticmethod
    def iris_ratio(frame):
        """Retuns ratio of pixels occupied by detected iris"""
        frame = frame[5:-5, 5:-5]
        H, W = frame.shape[:2]
        pixels = H * W
        target = pixels - cv2.countNonZero(frame)
        return target / pixels

    @staticmethod
    def threshold_optimum(eye_frame):
        """Uses average iris percentage as starting point to find optimum"""
        average_iris = 0.48
        work = {}

        for threshold in range(5, 100, 5):
            iris_frame = Iris.processing(eye_frame, threshold)
            work[threshold] = Initialize.iris_ratio(iris_frame)

        top_threshold, iris_size = min(work.items(), key=(lambda p: abs(p[1] - average_iris)))
        return top_threshold

    def check_finish(self):
        return len(self.left_threshold) >= self.buffer and len(self.right_threshold) >= self.buffer

    def threshold(self, eye):
        if eye == 0:
            return int(sum(self.left_threshold) / len(self.left_threshold))
        elif eye == 1:
            return int(sum(self.right_threshold) / len(self.right_threshold))

    def eval(self, eye_frame, eye):
        threshold = self.threshold_optimum(eye_frame)

        if eye == 0:
            self.left_threshold.append(threshold)
        elif eye == 1:
            self.right_threshold.append(threshold)
