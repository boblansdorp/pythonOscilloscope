# rigol_query.py

import numpy as np
import matplotlib.pyplot as plt
import pyvisa
import time
import sys

def acquire_rigol_waveform():
    channel='CHAN1'
    stop_point=1000000
    rm = pyvisa.ResourceManager()
    instruments = rm.list_resources()
    print("Instrument list:", instruments)

    NAME = next((x for x in instruments if 'USB' in x), None)
    if NAME is None:
        raise RuntimeError("No USB scope found.")

    scope = rm.open_resource(NAME, timeout=20000, chunk_size=1024000)
    scope.write_termination = '\n'
    scope.read_termination = '\n'
    scope.timeout = 5000

    scope.write(":WAV:MODE RAW")
    scope.write(":WAV:FORM BYTE")
    scope.write(f":WAV:SOUR {channel}")
    memory_depth = scope.query(":ACQ:MDEP?").strip()
    print("Memory depth (points):", memory_depth)

    scope.write(":SING")
    print("Waiting for trigger...", end='', flush=True)
    start_time = time.time()

    while True:
        status = scope.query(":TRIG:STAT?").strip()
        if status in ["STOP", "TD"]:
            print(f"\nTriggered. Status: {status}")
            break
        if time.time() - start_time > 10:
            raise TimeoutError("Trigger timeout.")
        time.sleep(0.1)

    sample_rate = float(scope.query(":ACQuire:SRATe?").strip())
    dt = 1 / sample_rate

    voltscale = float(scope.query(f":{channel}:SCAL?").strip())
    voltoffset = float(scope.query(f":{channel}:OFFS?").strip())

    scope.write(":WAV:STAR 1")
    scope.write(f":WAV:STOP {stop_point}")
    preamble = scope.query(":WAV:PRE?").strip().split(',')
    y_increment = float(preamble[7])
    y_origin = float(preamble[8])
    y_reference = float(preamble[9])

    scope.write(":WAV:DATA?")
    raw = scope.read_raw()
    if raw[0] != 35:  # ASCII '#'
        raise Exception("Invalid block header")
    num_digits = int(chr(raw[1]))
    num_bytes = int(raw[2:2 + num_digits].decode())
    data_bytes = raw[2 + num_digits:2 + num_digits + num_bytes]

    data = np.frombuffer(data_bytes, dtype=np.uint8)
    #voltages = (data - y_reference) * y_increment - voltoffset
    t_pts = np.arange(len(data)) * dt
    byteRange = max(data)- min(data)
    return t_pts, data, byteRange, y_increment, voltscale
