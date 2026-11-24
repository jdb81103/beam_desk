# Beam Designer

Beam Designer is a Python Tkinter desktop app for performing preliminary
analysis of a simply supported beam. It accepts span, section properties,
allowable stress, and point or uniform loads, then displays reactions,
shear, moment, deflection, and pass/fail checks. Projects can be saved and
opened, and results can be exported to CSV or PDF.

## Install

Python 3.10 or newer is required. Tkinter is included with most Python
installations. Install the Matplotlib package used for PDF export:

```powershell
python -m pip install matplotlib
```

## Start

From the project directory, run:

```powershell
python app.py
```
