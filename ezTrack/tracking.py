from __future__ import division
import cv2
from .pointCloud import PointCloud
from .initialize import Initialize
import dlib
import os


class Tracking(object):
    def __init__(self):
        self.frame = None
        self.eye_left = None
        self.eye_right = None
        self.initialize = Initialize()

        self._face_detector = dlib.get_frontal_face_detector()
        current_directory = os.path.abspath(os.path.dirname(__file__))
        path = os.path.abspath(os.path.join(current_directory, "dlib_cloud/cloud_68_face_landmarks.dat"))
        self._predictor = dlib.shape_predictor(path)

    @property
    def check_pupils(self):
        """Returns false if pupils not found"""
        try:
            int(self.eye_left.pupil.x)
            int(self.eye_left.pupil.y)
            int(self.eye_right.pupil.x)
            int(self.eye_right.pupil.y)
            return True
        except Exception:
            return False

    def _analyze(self):
        """Find face from frame and label eyes via pointcloud"""
        frame = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
        faces = self._face_detector(frame)

        try:
            landmarks = self._predictor(frame, faces[0])
            self.eye_left = PointCloud(frame, landmarks, 0, self.initialize)
            self.eye_right = PointCloud(frame, landmarks, 1, self.initialize)

        except IndexError:
            self.eye_left = None
            self.eye_right = None

    def eye_left_coords(self):
        if self.check_pupils:
            x = self.eye_left.origin[0] + self.eye_left.pupil.x
            y = self.eye_left.origin[1] + self.eye_left.pupil.y
            return (x, y)

    def eye_right_coords(self):
        if self.check_pupils:
            x = self.eye_right.origin[0] + self.eye_right.pupil.x
            y = self.eye_right.origin[1] + self.eye_right.pupil.y
            return (x, y)

    def horizontal_ratio(self):
        """Gives horizontal angel of gaze"""
        if self.check_pupils:
            pupil_left = self.eye_left.pupil.x / (self.eye_left.center[0] * 2 - 10)
            pupil_right = self.eye_right.pupil.x / (self.eye_right.center[0] * 2 - 10)
            return (pupil_left + pupil_right) / 2

    def vertical_ratio(self):
        """Gives vertical angel of gaze"""
        if self.check_pupils:
            pupil_left = self.eye_left.pupil.y / (self.eye_left.center[1] * 2 - 10)
            pupil_right = self.eye_right.pupil.y / (self.eye_right.center[1] * 2 - 10)
            return (pupil_left + pupil_right) / 2

    def negative_y_check(self):
        if self.check_pupils:
            return self.vertical_ratio() >= 0.75

    def positive_y_check(self):
        if self.check_pupils:
            return self.vertical_ratio() <= 0.60

    def positive_x_check(self):
        if self.check_pupils:
            return self.horizontal_ratio() <= 0.4

    def negative_x_check(self):
        if self.check_pupils:
            return self.horizontal_ratio() >= 0.72

    def mid_check(self):
        if self.check_pupils:
            return self.positive_x_check() is not True and self.negative_x_check() is not True

    def mid_check_H(self):
        if self.check_pupils:
            return self.positive_y_check() is not True and self.negative_y_check() is not True

    def refresh(self, frame):
        self.frame = frame
        self._analyze()

    def annotated_frame(self):
        frame = self.frame.copy()
        if self.check_pupils:
            color = (255, 0, 255)
            x_left, y_left = self.eye_left_coords()
            x_right, y_right = self.eye_right_coords()
            cv2.circle(frame, (x_left, y_left), 2, color)
            cv2.circle(frame, (x_right, y_right), 2, color)

        return frame
