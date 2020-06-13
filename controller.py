#! /usr/bin/env python
######################################################################
# tuner.py - a minimal command-line guitar/ukulele tuner in Python.
# Requires numpy and pyaudio.
######################################################################
# Author:  Matt Zucker
# Date:    July 2016
# License: Creative Commons Attribution-ShareAlike 3.0
#          https://creativecommons.org/licenses/by-sa/3.0/us/
######################################################################

import numpy as np
import pyaudio
import pyvjoy

######################################################################
# Feel free to play with these numbers. Might want to change NOTE_MIN
# Feel free to play with these numbers. Might want to change NOTE_MIN
# and NOTE_MAX especially for guitar/bass. Probably want to keep
# FRAME_SIZE and FRAMES_PER_FFT to be powers of two.

NOTE_MIN = 56       # Ab3
NOTE_MAX = 65       # F4
FSAMP = 44100       # Sampling frequency in Hz
FRAME_SIZE = 1024   # How many samples per frame?
FRAMES_PER_FFT = 8  # FFT takes average across how many frames?
NOISE_GATE = 1000   # Noise gate found through experimentation to prevent unwanted control inputs when not playing

# Control mappings
j = pyvjoy.VJoyDevice(1)
THROTTLE_AXIS = pyvjoy.HID_USAGE_Y
BRAKE_AXIS= pyvjoy.HID_USAGE_Z
STEER_AXIS = pyvjoy.HID_USAGE_X
UPSHIFT_BUTTON = 1
DOWNSHIFT_BUTTON = 2
LIGHTS_BUTTON = 3

######################################################################
# Derived quantities from constants above. Note that as
# SAMPLES_PER_FFT goes up, the frequency step size decreases (so
# resolution increases); however, it will incur more delay to process
# new sounds.

SAMPLES_PER_FFT = FRAME_SIZE*FRAMES_PER_FFT
FREQ_STEP = float(FSAMP)/SAMPLES_PER_FFT

######################################################################
# For printing out notes

NOTE_NAMES = 'C C# D D# E F F# G G# A A# B'.split()

######################################################################
# These three functions are based upon this very useful webpage:
# https://newt.phys.unsw.edu.au/jw/notes.html

def freq_to_number(f): return 69 + 12*np.log2(f/440.0)
def number_to_freq(n): return 440 * 2.0**((n-69)/12.0)
def note_name(n): return NOTE_NAMES[n % 12] + str(n/12 - 1)

######################################################################
# Ok, ready to go now.

# Get min/max index within FFT of notes we care about.
# See docs for numpy.rfftfreq()
def note_to_fftbin(n): return number_to_freq(n)/FREQ_STEP
imin = max(0, int(np.floor(note_to_fftbin(NOTE_MIN-1))))
imax = min(SAMPLES_PER_FFT, int(np.ceil(note_to_fftbin(NOTE_MAX+1))))

# Allocate space to run an FFT. 
buf = np.zeros(SAMPLES_PER_FFT, dtype=np.float32)
num_frames = 0

# Initialize audio
stream = pyaudio.PyAudio().open(format=pyaudio.paInt16,
                                channels=1,
                                rate=FSAMP,
                                input=True,
                                frames_per_buffer=FRAME_SIZE)

stream.start_stream()

# Create Hanning window function
window = 0.5 * (1 - np.cos(np.linspace(0, 2*np.pi, SAMPLES_PER_FFT, False)))

# Print initial text
print('sampling at {} Hz with max resolution of {} Hz'.format(FSAMP, FREQ_STEP))

speed = ''
steer_str = 'straight'
shift = ''

brake_value = 0x0
throttle_value = 0x0
steer_value = 0x8000
lights_value = 0

BRAKE_INC = 0x1800 # this should make 0 - full brake take about 0.5 second
THROTTLE_INC = 0x0800 # this should make 0 - full throttle take about 1.0 second
STEER_INC = 0x0400 # this should make 0 - full steering take about 1.5 second

BRAKE_MAX = 0xffff
THROTTLE_MAX = 0xffff
STEER_CENTER = 0x8000
STEER_MAX = 0xffff

def apply(value, increment, max):
    value += increment
    if value > max:
        value = max
    return value

def release(value, increment):
    if value > 0:
        value -= increment
        if value < 0:
            value = 0
    return value

def center(value, increment, center):
    if value > center:
        value -= increment
        if value < center:
            value = center
    if value < center:
        value += increment
        if value > center:
            value = center
    return value

def steer(value, increment, direction, center, max):
    if (value - center) * direction < 0: # if we're the other side of center, e.g. wheel is right but we want to steer left
        direction *= 2
    value += increment * direction
    if value > max:
        value = max
    if value < 0:
        value = 0
    return value

# As long as we are getting data:
while stream.is_active():
    # Shift the buffer down and new data in
    buf[:-FRAME_SIZE] = buf[FRAME_SIZE:]
    buf[-FRAME_SIZE:] = np.fromstring(stream.read(FRAME_SIZE), np.int16)

    # Run the FFT on the windowed buffer
    fft = np.fft.rfft(buf * window)

    # Get frequency of maximum response in range
    freq = (np.abs(fft[imin:imax]).argmax() + imin) * FREQ_STEP

    # Get note number and nearest note
    n = freq_to_number(freq)
    n0 = int(round(n))

    # Console output once we have a full buffer
    num_frames += 1


    if num_frames >= FRAMES_PER_FFT:
        # use max(buf) to noise-gate input so it doesn't send random control signals when you're not playing into the microphone
        # An appropriate NOISE_GATE value must be found by experimentation.
        if max(buf) > NOISE_GATE:

            if freq < 235:
                if throttle_value > 0:
                    throttle_value = 0
                brake_value = apply(brake_value, BRAKE_INC, BRAKE_MAX)
                speed = 'brake'
            elif freq < 270:
                if brake_value > 0:
                    brake_value = 0
                throttle_value = apply(throttle_value, THROTTLE_INC, THROTTLE_MAX)
                speed = 'accel'
            else:
                speed = ''

            if freq <= 195:
                shift = 'down'
                j.set_button(DOWNSHIFT_BUTTON, 1)
                j.set_button(UPSHIFT_BUTTON, 0)
            elif freq > 320:
                shift = 'up'
                j.set_button(UPSHIFT_BUTTON, 1)
                j.set_button(DOWNSHIFT_BUTTON, 0)
            else:
                shift = ''
                j.set_button(UPSHIFT_BUTTON, 0)
                j.set_button(DOWNSHIFT_BUTTON, 0)

            if   (195 < freq and freq <= 208) or (235 < freq and freq <= 245):
                steer_value = steer(steer_value, STEER_INC, -1, STEER_CENTER, STEER_MAX)
                steer_str = 'left'
            elif (216 < freq and freq <= 232) or (259 < freq and freq <= 270):
                steer_value = steer(steer_value, STEER_INC, 1, STEER_CENTER, STEER_MAX)
                steer_str = 'right'
            else:
                steer_value = center(steer_value, STEER_INC, STEER_CENTER)
                steer_str = 'straight'

        else:
            brake_value = release(brake_value, BRAKE_INC)
            throttle_value = release(throttle_value, THROTTLE_INC)
            steer_value = center(steer_value, STEER_INC, STEER_CENTER)
            j.set_button(DOWNSHIFT_BUTTON, 0)
            j.set_button(UPSHIFT_BUTTON, 0)
            speed = ''
            steer_str = ''
            shift = ''

        # toggle light flash forever
        lights_value = 1 - lights_value
        j.set_button(LIGHTS_BUTTON, lights_value)

        j.set_axis(BRAKE_AXIS, brake_value)
        j.set_axis(THROTTLE_AXIS, throttle_value)
        j.set_axis(STEER_AXIS, steer_value)

        print('freq: {:7.2f} Hz  {:<9} {:<6} {:<5}'.format(freq, steer_str, speed, shift))

        # c# xxx-195 downshift
        # d  195-208 brake left
        # d# 208-216 brake straight
        # e  220-232 brake right
        # f  235-245 accel left
        # f# 245-259 accel straight
        # g  259-270 accel right
        # b  325-340 upshift
