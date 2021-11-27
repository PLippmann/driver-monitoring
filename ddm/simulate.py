import matplotlib.pyplot as plt
from matplotlib import cm
import numpy as np
import pandas as pd
from sys import argv
import random
import csv
from itertools import repeat


'''
file = "final.txt"
x,y,z = np.loadtxt(file, unpack=True)
df = pd.DataFrame({'x': x, 'y': y, 'z': z})
'''

TIME = 30.0 #time in seconds + 1
STEP = 0.1  #timestep size in seconds
DIST = 250.0 #distance of merging lane in meters
LABEL_LIST = ['R','L','N'] #for now: True == useful, False == not useful

NSTEPS = int(TIME // STEP)


def simulator(x, t, alpha, G_l, G_f, gamma, tau_v, tau_end, beta_v, beta_end, d_v, d_end, theta_v, theta_end, dt, dW):
    for i in range(1, NSTEPS):
        dx = alpha * (G_l[i] * ((tau_v[i] + beta_v*d_v[i]) - theta_v[i]) - gamma * G_f[i] * ((tau_end[i] + beta_end*d_end[i]) - theta_end[i])) * dt + dW[i]
        x[i] = dx + x[i-1]
        if x[i] > 10.0 or x[i] < -10.0:
            return x[:i+1],t[:i+1]

    return x,t


def plotter(x,t,labels):
    temp_label = list()
    for label in labels:
        if len(temp_label) != len(t):
            if label == 'L':
                temp_label.append(1)
                #temp_label.extend(repeat(1,5))
            elif label == 'R':
                temp_label.append(0)
                #temp_label.extend(repeat(0,5))
            else:
                temp_label.append(-1)
                #temp_label.extend(repeat(-1,5))
        else:
            break

    fig, axs = plt.subplots(2, 1, gridspec_kw={'height_ratios': [3,1]})

    axs[0].plot(t, x)
    axs[0].set(xlabel='time (s)', ylabel='Decision Drift', title='DDM Simulated Over Time')
    axs[0].set(ylim=(-10.1, 10.1))
    axs[0].grid()

    axs[1].set(xlabel='time (s)', ylabel='Gaze Labels')
    axs[1].scatter(t,temp_label)

    fig.tight_layout()
    fig.savefig("ddm.png")
    plt.show()


def file_writer(x, t, alpha, G_l, G_f, gamma, tau_v, tau_end, beta_v, beta_end, d_v, d_end, theta_v, theta_end, dt, dW):
    #data = [x, t, alpha, G_l, G_f, gamma, tau_v, tau_end, beta_v, beta_end, d_v, d_end, theta_v, theta_end, dt, dW]
    #df = pd.DataFrame(data={'Drift': x, 't': t, 'alpha': alpha, 'G_l': G_l, 'G_f': G_f, 'gamma': gamma, 'tau_v': tau_v, 'tau_end': tau_end, 'beta_v': beta_v, 'beta_end': beta_end, 'd_v': d_v, 'd_end': d_end, 'theta_v': theta_v, 'theta_end': theta_end, 'dt': dt, 'dW': dW})
    df = pd.DataFrame(data={'Drift': x, 't': t})
    df.to_csv("./sim_data.csv", sep=',',index=False)


def generator():
    print("Time of simulation [s]: ", TIME)
    print("Distance of merge lane [m]: ", DIST)
    print("Number of time steps: ", NSTEPS + 1, "\n")

    time = [0.0 for x in range(NSTEPS)]
    for i in range(1, NSTEPS):
        time[i] = time[i-1] + STEP

    labels = [np.random.choice(LABEL_LIST, p = [0.7,0.1,0.2]) for x in range(NSTEPS)]
    print("Gaze labels: ", labels, "\n")

    '''
    vel = [0.0 for x in range(NSTEPS)]
    start_vel = 0.0
    max_speed = 100.0
    acc = 10 #toyota prius 0-100 10.6s, super simplification

    for i in range(1, NSTEPS):
        if vel[i-1] < max_speed:
            vel[i] = vel[i-1] + acc
        else:
            vel[i] = max_speed
    '''
#---------------------------------------------
    d_end = np.array([DIST for x in range(NSTEPS)])

    for i in range(1, NSTEPS):
        if d_end[i-1] >= 0:
            d_end[i] = d_end[i-1] - DIST/NSTEPS
        else:
            print("CRASH")

    d_v = np.array([DIST for x in range(NSTEPS)])

    for i in range(1, NSTEPS):
        if d_v[i-1] >= 0:
            d_v[i] = d_v[i-1] - DIST/NSTEPS
        else:
            print("CRASH")

    tau_v = np.array([TIME for x in range(NSTEPS)])

    for i in range(1, NSTEPS):
        if tau_v[i-1] >= 0:
            tau_v[i] = tau_v[i-1] - TIME/NSTEPS

    tau_end = np.array([TIME for x in range(NSTEPS)])

    for i in range(1, NSTEPS):
        if tau_end[i-1] >= 0:
            tau_end[i] = tau_end[i-1] - TIME/NSTEPS
#---------------------------------------------
    G_l = list()  #looks left mirror
    G_f = list()  #looks forward road

    for label in labels:
        if label == 'R':
            G_l.append(0.0)
            G_f.append(1.0)
            #G_l.extend(repeat(0.0,5))
            #G_f.extend(repeat(1.0,5))
        elif label == 'L':
            G_l.append(1.0)
            G_f.append(0.0)
            #G_l.extend(repeat(1.0,5))
            #G_f.extend(repeat(0.0,5))
        else:
            G_l.append(0.0)
            G_f.append(0.0)
            #G_l.extend(repeat(0.0,5))
            #G_f.extend(repeat(0.0,5))

    #inputs
    alpha = 0.01  #baseline drift rate
    gamma = 0.001  #weight for front gaze
    beta_v  = 0.01  #weight of distance to vehile information
    beta_end = 0.001  #weight of distance to end of merge information
    theta_v = np.array([1 for x in range(NSTEPS)])  #critical value
    theta_end = np.array([100 for x in range(NSTEPS)])  #critical value
    dt = STEP  #timestep size
    dW = 0 + 1 * np.random.standard_normal(NSTEPS)
    print("Noise: ", dW)

    #outputs
    x = np.array([0.0 for x in range(NSTEPS)])  #position of decision between 1 and -1
    t = time

    return x, t, alpha, G_l, G_f, gamma, tau_v, tau_end, beta_v, beta_end, d_v, d_end, theta_v, theta_end, dt, dW, labels


if __name__ == "__main__":
    x, t, alpha, G_l, G_f, gamma, tau_v, tau_end, beta_v, beta_end, d_v, d_end, theta_v, theta_end, dt, dW, labels = generator()
    x, t = simulator(x, t, alpha, G_l, G_f, gamma, tau_v, tau_end, beta_v, beta_end, d_v, d_end, theta_v, theta_end, dt, dW)
    file_writer(x, t, alpha, G_l, G_f, gamma, tau_v, tau_end, beta_v, beta_end, d_v, d_end, theta_v, theta_end, dt, dW)
    plotter(x,t,labels)
