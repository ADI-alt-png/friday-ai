import tkinter as tk
import queue

status_label = None
status_queue = queue.Queue()

def process_status_queue():
    if status_label:
        try:
            while True:
                status_label.config(text=status_queue.get_nowait())
        except queue.Empty:
            pass
        status_label.after(100, process_status_queue)

def create_status_overlay():
    global status_label

    root = tk.Toplevel()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", "black")

    root.geometry("250x80+20+20")

    status_label = tk.Label(
        root,
        text="Status: OFF",
        fg="white",
        bg="black",
        font=("Segoe UI", 12, "bold")
    )
    status_label.pack(fill="both", expand=True)
    process_status_queue()


def update_status(text):
    status_queue.put(text)
