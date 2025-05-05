import tkinter as tk
from tkinter import ttk
import matplotlib
matplotlib.use('Agg')  # Use a non-interactive backend for safety
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import time
import csv
import os

class TrendGraph(ttk.Frame):
    def __init__(self, master, set_status=None, **kwargs):
        super().__init__(master, **kwargs)
        self.set_status = set_status or (lambda msg: None)
        self.fig, self.ax = plt.subplots(figsize=(5,3), dpi=100)
        self.line_max, = self.ax.plot([], [], 'r-', label='Max')
        self.line_min, = self.ax.plot([], [], 'b-', label='Min')
        self.line_avg, = self.ax.plot([], [], 'g-', label='Avg')
        self.ax.set_ylabel('Temp (C)')
        self.ax.set_xlabel('Time (s)')
        self.ax.legend(loc='upper right')
        self.ax.grid(True)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew', padx=8, pady=8)

        # Export button
        self.export_btn = ttk.Button(self, text="Export CSV", command=self.export_csv)
        self.export_btn.grid(row=1, column=0, sticky='ew', padx=8, pady=(0,8))

        self.time_data = []
        self.max_data = []
        self.min_data = []
        self.avg_data = []
        self.start_time = time.time()
        self.time_span_seconds = 60  # 1 min window
        self.update_interval = 1000  # ms
        self.after_id = self.after(self.update_interval, self.update_graph)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def add_point(self, max_temp, min_temp, avg_temp):
        t = time.time() - self.start_time
        self.time_data.append(t)
        self.max_data.append(max_temp)
        self.min_data.append(min_temp)
        self.avg_data.append(avg_temp)

    def update_graph(self):
        t = time.time() - self.start_time
        t_min = t - self.time_span_seconds
        indices = [i for i, ti in enumerate(self.time_data) if ti >= t_min]
        plot_times = [self.time_data[i] for i in indices]
        plot_max = [self.max_data[i] for i in indices]
        plot_min = [self.min_data[i] for i in indices]
        plot_avg = [self.avg_data[i] for i in indices]
        self.line_max.set_data(plot_times, plot_max)
        self.line_min.set_data(plot_times, plot_min)
        self.line_avg.set_data(plot_times, plot_avg)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()
        self.after_id = self.after(self.update_interval, self.update_graph)

    def export_csv(self):
        if not self.time_data:
            self.set_status("No data to export.")
            return
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        filename = f"trend_{timestamp}.csv"
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Time (s)', 'Max Temp (C)', 'Min Temp (C)', 'Avg Temp (C)'])
                for t, mx, mn, av in zip(self.time_data, self.max_data, self.min_data, self.avg_data):
                    writer.writerow([t, mx, mn, av])
            self.set_status(f"Graph data exported to {filename}")
        except Exception as e:
            self.set_status(f"Export failed: {e}")

    def stop(self):
        if self.after_id:
            self.after_cancel(self.after_id) 