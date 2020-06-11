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
import SendKeys

######################################################################
# Feel free to play with these numbers. Might want to change NOTE_MIN
# and NOTE_MAX especially for guitar/bass. Probably want to keep
# FRAME_SIZE and FRAMES_PER_FFT to be powers of two.

NOTE_MIN = 56       # Ab3
NOTE_MAX = 65       # F4
FSAMP = 44100       # Sampling frequency in Hz
FRAME_SIZE = 1024   # How many samples per frame?
FRAMES_PER_FFT = 8  # FFT takes average across how many frames?

# Control mappings
BRAKE = 'b'
ACCEL = 'a'
LEFT = 'l'
RIGHT = 'r'
UPSHIFT = 'u'
DOWNSHIFT = 'd'

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

upshift = False
downshift = False

# As long as we are getting data:
while stream.is_active():
    command_str = ""
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

    # use max(buf) to noise-gate input so it doesn't send random control signals when you're not playing into the microphone
    if num_frames >= FRAMES_PER_FFT and max(buf) > 1000:
        print('freq: {:7.2f} Hz     note: {:>3s} {:+.2f}'.format(freq, note_name(n0), n-n0))
        if freq < 270:
            command_str += BRAKE
            if freq < 230:
                if not downshift:
                    command_str += DOWNSHIFT
                    downshift = True
            else:
                downshift = False
        else:
            command_str += ACCEL
            if freq > 310:
                if not upshift:
                    command_str += UPSHIFT
                    upshift = True
            else:
                upshift = False

        if    freq < 205 or                  (230 < freq and freq <= 242) or (270 < freq and freq <= 282) or (312 < freq and freq <= 325):
            command_str += LEFT
        elif (215 < freq and freq <= 230) or (260 < freq and freq <= 270) or (300 < freq and freq <= 312) or freq > 345:
            command_str += RIGHT
        if command_str:
            SendKeys.SendKeys(command_str + '{ENTER}', pause=0)

