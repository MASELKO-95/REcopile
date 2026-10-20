#!/usr/bin/env python3
import sys
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
if sys.argv[1:] == ["folder"]:
    path = filedialog.askdirectory(title="Recopile — wybierz folder")
else:
    path = filedialog.askopenfilename(title="Recopile — wybierz plik", filetypes=[("Wszystkie pliki", "*")])
root.destroy()
print(path or "")
