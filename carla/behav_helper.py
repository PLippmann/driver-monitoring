import random
import time

#TODO
#Have gaze tracking output a flag in relation to useful frames

def gen():
    return random.choice([True, False])


def helperViz(future, timer1sec):
    if time.time() > future:
        if time.time() - timer1sec >= 0.3:
            return True


def behav_proc(future, timer1sec, merge, d_remain, m_frames = 0):  
    #m_frames sampled frames mirror, d_remain possible distance left in merging lane; pass these from main loop
    key = "NOSIGNAL"
    if not merge:
        if m_frames < 1.5*30 and d_remain < 115.0:
            key = "AUDIO"

            if helperViz(future, timer1sec):
                key = "VISUAL"

    return key  #if key == audio then emit audio signal, if key == visual emit both


'''
m_Frames:
make list with final label if final label == left mirror
check len(list)
should be one entry one frame
then check condition above
'''