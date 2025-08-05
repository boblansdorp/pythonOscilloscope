import numpy as np
import matplotlib.pyplot as plt
import pyvisa
import time

# --- VISA Setup ---
rm = pyvisa.ResourceManager()
instruments = rm.list_resources()
devs = list(filter(lambda x: 'USB' in x, instruments))
print("Instrument list:", instruments)

# Your instrument resource name (update if different)
NAME = 'USB0::0x1AB1::0x04CE::DS1ZA180602497::INSTR'

# Open connection
scope = rm.open_resource(NAME, timeout=20000, chunk_size=1024000)
scope.write_termination = '\n'
scope.read_termination = '\n'
scope.timeout = 5000
scope.write(":WAV:MODE RAW")
print("Sent: :WAV:MODE RAW")

# 1. Send :WAV:FORM BYTE
scope.write(":WAV:FORM BYTE")
print("Sent: :WAV:FORM BYTE")

# 2. Send and read :ACQ:MDEP?
memory_depth = scope.query(":ACQ:MDEP?")
print("Memory depth (points):", memory_depth.strip())

# 3. Send :SING to take a single acquisition
scope.write(":SING")
print("Sent: :SING (single trigger)")


# Poll trigger status every 100ms, max 10s
start_time = time.time()
print("Waiting for trigger...", end='', flush=True)

while True:
    status = scope.query(":TRIG:STAT?").strip()
    print(".", end='', flush=True)

    if status in ["STOP", "TD"]:
        print(f"\nTriggered. Status: {status}")
        break
    else:
        print("waiting to complete trigger acquisition...")
        

    if time.time() - start_time > 10:
        print("\nERROR: Trigger timeout after 10 seconds.")
        sys.exit("Aborting program due to trigger timeout.")

    time.sleep(0.1)  # 100 ms delay



# --- Get scaling info ---
#timescale = float(scope.query(":TIM:SCAL?").strip())
#timeoffset = float(scope.query(":TIM:OFFS?").strip())
sampleRate = float(scope.query(":ACQuire:SRATe?").strip())
print("Samplerate: ", sampleRate)
timescale = 1/sampleRate
dt = 1 / sampleRate

timeoffset = 0
voltscale = float(scope.query(':CHAN1:SCAL?').strip())
voltoffset = float(scope.query(":CHAN1:OFFS?").strip())

print(f"timescale: {timescale} [s]")
print(f"time offset: {timeoffset} [s]")
print(f"volt scale: {voltscale} [V]")
print(f"volt offset: {voltoffset} [V]")

# --- Prepare plot ---
colors = ['yellow', 'cyan', 'magenta', 'blue']
# channels = ['CHAN1', 'CHAN2', 'CHAN3', 'CHAN4']
channels = ['CHAN1']
scope.write(":WAV:STAR 1")
print("Sent: :WAV:STAR 1")
scope.write(":WAV:STOP 1000000")
print("Sent: :WAV:STOP 1000000")

preamble = scope.query(":WAV:PRE?").strip().split(',')
print("preamble: ", preamble)
y_increment = float(preamble[7])
y_origin    = float(preamble[8])
y_reference = float(preamble[9])
print("y_increment: ", y_increment)
print("y_origin: ", y_origin)
print("y_reference: ", y_reference)




fig = plt.figure()
ax = fig.add_subplot(111)
plt.ion()
fig.show()
fig.canvas.draw()

# --- Main Loop ---
for i in range(1):
    time.sleep(0.05)  # adjust for update speed
    data_matrix = []

    for ch in channels:
        try:
            scope.write(":WAV:DATA?")
            raw = scope.read_raw()

            # Parse binary block header
            if raw[0] != 35:  # ASCII '#'
                raise Exception("Invalid block header")

            num_digits = int(chr(raw[1]))  # e.g. '8' if header is "#800012000"
            print('num digits in header: ', num_digits)
            num_bytes = int(raw[2:2 + num_digits].decode())
            data_start = 2 + num_digits
            data_end = data_start + num_bytes

            # Extract only the actual waveform data
            data_bytes = raw[data_start:data_end]


            data = np.frombuffer(data_bytes, dtype=np.uint8)
            #voltages = ((240 - data) * (voltscale / 25.0)) - (voltoffset + voltscale * 4.6)
            #voltages = (data - 130.0) * voltscale / 25.0  - voltoffset 
            voltages = (data - y_reference - y_origin) * voltscale / 25.0 # - y_increment 
            data_matrix.append(voltages)

        except Exception as e:
            print(f"Channel {ch} error: {e}")
            voltages = np.zeros(1200)
            data_matrix.append(voltages)


    data_matrix = np.array(data_matrix)

    # Compute time vector based on data length
    num_points = data_matrix.shape[1]
    t_pts = np.arange(num_points) * dt  # time from 0 to (N-1)*dt

    # Adjust time unit for nicer axes
    t_end = t_pts[-1]
    if t_end < 1e-3:
        print("using μs time scale")
        t_scl = 1e6
        t_unit = "μs"
    elif t_end < 1:
        print("using ms time scale")
        t_scl = 1e3
        t_unit = "ms"
    else:
        t_scl = 1
        t_unit = "s"

    t_pts *= t_scl

    # --- Update Plot ---
    ax.clear()
    for data, color, chan in zip(data_matrix, colors, channels):
        ax.plot(t_pts, data, c=color, label=chan)
    ax.set_xlabel(f"Time [{t_unit}]")
    ax.set_ylabel("Voltage [V]")
    ax.legend()
    ax.grid(True)
    fig.canvas.draw()

plt.ioff()      # turn off interactive mode
plt.show()      # blocks until you close the plot window

#plt.close()