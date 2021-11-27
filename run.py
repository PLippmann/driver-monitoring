import cv2
from ezTrack import Tracking

track = Tracking()
video = cv2.VideoCapture(0)

while True:
    _, currFrame = video.read()
    track.refresh(currFrame)
    currFrame = track.annotated_frame()
    label = ""

    #label for gaze location prediction
    if track.mid_check() and track.mid_check_H():
        label = "Road"
    elif track.negative_x_check():
        label = "Left mirror"
    elif track.positive_x_check():
        label = "Right mirror"
    elif track.positive_y_check():
        label = "Rear view mirror"
    elif track.negative_y_check():
        label = "Center stack"
    else:
        label = "NaN"

    cv2.putText(currFrame, label, (5, 700), cv2.FONT_HERSHEY_DUPLEX, 1.6, (0, 255, 0), 2)

    label2 = ""
    if track.positive_y_check():
        label2 = "V: Rear view mirror"
    elif track.negative_y_check():
        label2 = "V: Center stack"
    elif track.mid_check():
        label2 = "V: Road"
    else:
        label2 = "V: NaN"

    label2 = "H: " + str(track.horizontal_ratio())[:4]
    cv2.putText(currFrame, label2, (5, 95), cv2.FONT_HERSHEY_DUPLEX, 1.6, (0, 255, 0), 2)

    label3 = ""
    if track.positive_x_check():
        label3 = "H: Right mirror"
    elif track.negative_x_check():
        label3 = "H: Left mirror"
    elif track.mid_check():
        label3 = "H: Road"
    else:
        label3 = "H: NaN"

    label3 = "V: " + str(track.vertical_ratio())[:4]
    cv2.putText(currFrame, label3, (5, 45), cv2.FONT_HERSHEY_DUPLEX, 1.6, (0, 255, 0), 2)

    print("Horizontal: ", track.horizontal_ratio())
    print("Vertical: ", track.vertical_ratio())
    print(label)

    #coordiantes of pupil
    left_pupil = track.eye_left_coords()
    right_pupil = track.eye_right_coords()
    cv2.putText(currFrame, "Coords E[0]: " + str(left_pupil), (900, 670), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 255, 0), 2)
    cv2.putText(currFrame, "Coords E[1]: " + str(right_pupil), (900, 700), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 255, 0), 2)

    cv2.imshow("Live Track", currFrame)

    if cv2.waitKey(1) == 27:
        print("Bye!")
        break
