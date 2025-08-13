import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from rigol_query import acquire_rigol_waveform
import numpy as np
import csv

# --- Main GUI window ---
root = tk.Tk()
root.title("Rigol Scope Control")

# --- Plot setup ---
voltage_scale_factor = 1.0  # Global variable to store user-selected scale
voltage_offset = 0  # Global variable to store offset (in bytes)

fig = Figure(figsize=(6, 4), dpi=100)
ax = fig.add_subplot(111)
ax.set_title("Waveform")
ax.set_xlabel("Time [ms]")
ax.set_ylabel("Voltage [V]")
ax.grid(True)



# Canvas
canvas = FigureCanvasTkAgg(fig, master=root)
canvas_widget = canvas.get_tk_widget()
canvas_widget.pack(padx=10, pady=(10, 0), fill="both", expand=True)

# Toolbar
toolbar_frame = tk.Frame(root)
toolbar_frame.pack(fill="x", padx=10, pady=(0, 8))

toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
toolbar.update()

# --- Control frame ---
control_frame = tk.Frame(root)
control_frame.pack(pady=5)

# Label to display selected scale factor
scale_factor_label = tk.Label(root, text="Scale factor not selected yet", fg="blue")
scale_factor_label.pack(pady=5)

# Label to display selected offset
offset_label = tk.Label(root, text="Offset not selected yet", fg="blue")
offset_label.pack(pady=5)

# Filename input
tk.Label(control_frame, text="Filename:").grid(row=0, column=0, sticky="e")
filename_entry = tk.Entry(control_frame, width=30)
filename_entry.insert(0, "test.txt")
filename_entry.grid(row=0, column=1, padx=5)

# Experimental Parameters input
tk.Label(control_frame, text="Experimental Parameters:").grid(row=1, column=0, sticky="e")
param_entry = tk.Entry(control_frame, width=30)
param_entry.grid(row=1, column=1, padx=5)

# Add Header checkbox
add_header_var = tk.BooleanVar(value=True)
tk.Checkbutton(control_frame, text="Add Header", variable=add_header_var).grid(row=2, column=1, sticky="w")

# Cached data for calibrate
cached_data = None

def update_plot(t, d, label="Waveform"):
    ax.clear()
    #voltage = (d-voltage_offset)*voltage_scale_factor
    voltage = (d.astype(np.float64) - float(voltage_offset)) * float(voltage_scale_factor)

    ax.plot(t * 1e3, voltage)
    ax.set_title(label)
    ax.set_xlabel("Time [ms]")
    ax.set_ylabel("Voltage [V]")
    ax.grid(True)
    canvas.draw()

def on_calibrate():
    global cached_data, voltage_scale_factor, voltage_offset

    try:
        t, d, byteRange, y_increment, voltscale, _ = acquire_rigol_waveform()
        option1 = 3.0 / byteRange
        option2 = voltscale / 20
        option3 = y_increment

        print("byteRange:", byteRange)
        print("calculated actual scale (V/byte):", option1)
        print("voltscale/20:", option2)
        print("y_increment:", option3)

        def select_scale(value):
            global voltage_scale_factor
            voltage_scale_factor = value
            scale_popup.destroy()
            print("Selected voltage_scale_factor =", voltage_scale_factor)
            scale_factor_label.config(text=f"Selected scale factor: {voltage_scale_factor:.6f} V/byte")
            update_plot(t, d, label="Calibration Waveform")


        # --- POPUP SELECTION WINDOW ---
        scale_popup = tk.Toplevel()
        scale_popup.title("Select Scale Factor")

        tk.Label(scale_popup, text=f"Assuming a 3V 1kHz wave, we detected scale factors:").pack(pady=(10, 2))
        tk.Label(scale_popup, text=f"Byte range = {byteRange}").pack()
        tk.Label(scale_popup, text="Please choose one:").pack(pady=(5, 10))

        tk.Button(scale_popup, text=f"Use {option1:.6f} (3.0 / byteRange)",
                  command=lambda: select_scale(option1)).pack(pady=3)
        tk.Button(scale_popup, text=f"Use {option2:.6f} (voltscale / 20)",
                  command=lambda: select_scale(option2)).pack(pady=3)
        tk.Button(scale_popup, text=f"Use {option3:.6f} (y_increment)",
                  command=lambda: select_scale(option3)).pack(pady=3)
        

        offset_option1 = min(d)
        offset_option2 = voltscale / 20
        offset_option3 = y_increment

        def select_offset(value):
            global voltage_offset
            voltage_offset = value
            offset_popup.destroy()
            print("Selected offset =", voltage_offset)
            offset_label.config(text=f"Selected offset factor: {voltage_offset:.6f} bytes")
            update_plot(t, d, label="Calibration Waveform")

        
        # --- POPUP SELECTION WINDOW ---
        offset_popup = tk.Toplevel()
        offset_popup.title("Select Offset (Byte)")

        tk.Label(offset_popup, text=f"Assuming minimum was zero volts:").pack(pady=(10, 2))
        tk.Label(offset_popup, text=f"→ Offset = {min(d)} bytes").pack()

        tk.Label(offset_popup, text="Select voltage offset:").pack(pady=(5, 10))
        minimumDetected = min(d)
        
        tk.Button(offset_popup, text=f"Use detected minimum: {int(offset_option1)}",
          command=lambda: select_offset(offset_option1)).pack(pady=3)

        
        # Cache data and update plot while waiting for user selection
        cached_data = (t, d)
        update_plot(t, d, label="Calibration Waveform")

    except Exception as e:
        messagebox.showerror("Calibration Error", str(e))


def on_collect_data():
    global voltage_scale_factor, voltage_offset
    param = param_entry.get()
    filename = filename_entry.get()
    add_hdr = add_header_var.get()

    if not filename:
        messagebox.showwarning("Filename Required", "Please enter a filename.")
        return

    try:
        #t, v = acquire_rigol_waveform()
        t, d, byteRange, y_increment, voltscale, params = acquire_rigol_waveform()
        #v = (d-voltage_offset)*voltage_scale_factor
        v = (d.astype(np.float64) - float(voltage_offset)) * float(voltage_scale_factor)

        update_plot(t, d, label="Collected Waveform")

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            if add_hdr:
                f.write(params + "\n---\n")
                writer.writerow(["Parameters:", param])
                writer.writerow([])
                writer.writerow(["Time [s]", "Voltage [V], byteval"])
            for t_val, v_val, d_val in zip(t, v, d):
                writer.writerow([t_val, v_val, d_val])

        messagebox.showinfo("Saved", f"Data saved to {filename}")
    except Exception as e:
        messagebox.showerror("Data Collection Error", str(e))

# Buttons
tk.Button(control_frame, text="Calibrate", command=on_calibrate, bg="lightblue").grid(row=0, column=2, rowspan=1, padx=10, pady=5)

tk.Button(control_frame, text="Collect Data", command=on_collect_data, bg="lightgreen").grid(row=1, column=2, rowspan=1, padx=10, pady=5)

root.mainloop()
