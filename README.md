# python-tuner
Frequency-based keyboard/joystick input controller based on minimal command-line guitar/ukulele tuner in Python.
Writeup at <https://mzucker.github.io/2016/08/07/ukulele-tuner.html>

To run:

    python controller.py

(Possible) Future development:
- Emulate joystick input instead of keyboard
- Use a config file for mappings instead of hardcoding them
- Use a different window function for the FFT to more accurately determine the lowest harmonic pitch for lower notes
