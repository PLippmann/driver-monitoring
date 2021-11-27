import cv2
from .iris import Iris
from math import hypot
import numpy as np


class PointCloud(object):
    def __init__(self, frame, landmarks, eye, initialize):
        self.frame = None
        self.origin = None
        self.center = None
        self.pupil = None

        self._analyze(frame, landmarks, eye, initialize)

    def _reduce_frame(self, frame, landmarks, points):
        """Reduce frame to purely the eye and margin for error via pointcloud"""
        region = np.array([(landmarks.part(point).x, landmarks.part(point).y) for point in points])
        region = region.astype(np.int32)

        H, W = frame.shape[:2]
        black_frame = np.zeros((H, W), np.uint8)
        mask = np.full((H, W), 255, np.uint8)
        cv2.fillPoly(mask, [region], (0, 0, 0))
        eye = cv2.bitwise_not(black_frame, frame.copy(), mask=mask)
        min_x = np.min(region[:, 0]) - 5
        min_y = np.min(region[:, 1]) - 5
        max_x = np.max(region[:, 0]) + 5
        max_y = np.max(region[:, 1]) + 5

        self.frame = eye[min_y:max_y, min_x:max_x]
        self.origin = (min_x, min_y)

        H, W = self.frame.shape[:2]
        self.center = (W / 2, H / 2)

    def _analyze(self, original_frame, landmarks, eye, initialize):
        """Gives exact points for eye relevant coordiantes from dlib point cloud"""
        if eye == 0:
            points = [36, 37, 38, 39, 40, 41] #dlib points for left eye
        elif eye == 1:
            points = [42, 43, 44, 45, 46, 47] #dlib points for right eye
        else:
            return

        self.blinking = self._is_closed(landmarks, points)
        self._reduce_frame(original_frame, landmarks, points)

        if not initialize.check_finish():
            initialize.eval(self.frame, eye)

        threshold = initialize.threshold(eye)
        self.pupil = Iris(self.frame, threshold)

    def _is_closed(self, landmarks, points):
        """Determines whether the iris is visible or not by how much of the eye can be seen"""
        left = (landmarks.part(points[0]).x, landmarks.part(points[0]).y)
        right = (landmarks.part(points[3]).x, landmarks.part(points[3]).y)
        top = self._find_mid_helper(landmarks.part(points[1]), landmarks.part(points[2]))
        bottom = self._find_mid_helper(landmarks.part(points[5]), landmarks.part(points[4]))
        eye_W = hypot((left[0] - right[0]), (left[1] - right[1]))
        eye_H = hypot((top[0] - bottom[0]), (top[1] - bottom[1]))

        try:
            ratio = eye_W / eye_H
        except ZeroDivisionError:
            ratio = None

        return ratio

    @staticmethod
    def _find_mid_helper(p1, p2):
        x_plane = int((p1.x + p2.x) / 2)
        y_plane = int((p1.y + p2.y) / 2)
        return (x_plane, y_plane)
