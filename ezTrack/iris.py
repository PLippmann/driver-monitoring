import cv2
import numpy as np


class Iris(object):
    def __init__(self, eye_frame, threshold):
        self.curr_frame = None
        self.threshold = threshold
        self.x = None
        self.y = None

        self.iris_center(eye_frame)

    @staticmethod
    def processing(eye_frame, threshold):
        """Process frame to isolate iris from other parts of the image"""
        kernel = np.ones((3, 3), np.uint8)
        processed_frame = cv2.bilateralFilter(eye_frame, 10, 15, 15)
        processed_frame = cv2.erode(processed_frame, kernel, iterations=3)
        processed_frame = cv2.threshold(processed_frame, threshold, 255, cv2.THRESH_BINARY)[1]

        return processed_frame

    def iris_center(self, eye_frame):
        """Detect iris and finds its center"""
        self.curr_frame = self.processing(eye_frame, self.threshold)

        contours, _ = cv2.findContours(self.curr_frame, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)[-2:]
        contours = sorted(contours, key=cv2.contourArea)

        try:
            moments = cv2.moments(contours[-2])
            self.x = int(moments['m10'] / moments['m00'])
            self.y = int(moments['m01'] / moments['m00'])
        except (IndexError, ZeroDivisionError):
            pass
