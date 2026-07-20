import tkinter as tk
from tkinter import filedialog
from friday import execute  # 🔥 IMPORT YOUR FUNCTION

def send_command():
    cmd = entry.get()
    if cmd:
        output.insert(tk.END, f"You: {cmd}\n")
        execute(cmd)
        entry.delete(0, tk.END)

def upload_file():
    file_path = filedialog.askopenfilename()
    if file_path:
        output.insert(tk.END, f"File: {file_path}\n")
        execute(f"summarize pdf {file_path}")

# UI WINDOW
root = tk.Tk()
root.title("FRIDAY AI")

# OUTPUT BOX
output = tk.Text(root, height=20, width=60)
output.pack()

# INPUT BOX
entry = tk.Entry(root, width=50)
entry.pack()

# BUTTONS
send_btn = tk.Button(root, text="Send", command=send_command)
send_btn.pack()

upload_btn = tk.Button(root, text="Upload File", command=upload_file)
upload_btn.pack()

root.mainloop()