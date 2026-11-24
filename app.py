import csv
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from beam_analysis import BeamInput, PointLoad, UniformLoad, calculate_beam


class LoadRow(ttk.Frame):
    def __init__(self, master, on_remove, load_type="uniform", magnitude="", start="", end=""):
        super().__init__(master)
        self.on_remove = on_remove

        ttk.Label(self, text="Type").grid(row=0, column=0, sticky="w")
        self.type_var = tk.StringVar(value=load_type)
        self.type_combo = ttk.Combobox(
            self, textvariable=self.type_var, values=("Point", "Uniform"), state="readonly", width=9
        )
        self.type_combo.grid(row=1, column=0, padx=(0, 6))
        self.type_combo.bind("<<ComboboxSelected>>", lambda _event: self.update_labels())

        ttk.Label(self, text="Load").grid(row=0, column=1, sticky="w")
        self.magnitude = tk.StringVar(value=magnitude)
        ttk.Entry(self, textvariable=self.magnitude, width=12).grid(row=1, column=1, padx=(0, 6))

        self.start_label = ttk.Label(self, text="Start (ft)")
        self.start_label.grid(row=0, column=2, sticky="w")
        self.start = tk.StringVar(value=start)
        ttk.Entry(self, textvariable=self.start, width=10).grid(row=1, column=2, padx=(0, 6))

        self.end_label = ttk.Label(self, text="End (ft)")
        self.end_label.grid(row=0, column=3, sticky="w")
        self.end = tk.StringVar(value=end)
        self.end_entry = ttk.Entry(self, textvariable=self.end, width=10)
        self.end_entry.grid(row=1, column=3, padx=(0, 6))

        ttk.Button(self, text="Remove", width=8, command=self.remove).grid(row=1, column=4)
        self.update_labels()

    def update_labels(self):
        is_point = self.type_var.get().lower() == "point"
        self.start_label.configure(text="At (ft)" if is_point else "Start (ft)")
        self.end_label.configure(text="End (ft)")
        if is_point:
            self.end_entry.configure(state="disabled")
            self.end.set("")
        else:
            self.end_entry.configure(state="normal")

    def remove(self):
        self.destroy()
        self.on_remove()

    def read(self):
        load_type = self.type_var.get().lower()
        magnitude = float(self.magnitude.get())
        start = float(self.start.get())
        if load_type == "point":
            return PointLoad(magnitude, start)
        return UniformLoad(magnitude, start, float(self.end.get()))


class BeamDesignerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Beam Designer")
        self.geometry("1180x820")
        self.minsize(760, 620)
        self.configure(padx=12, pady=12)

        self.load_rows: list[LoadRow] = []
        self.project_path: str | None = None
        self.create_menu()

        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.inputs_frame = ttk.LabelFrame(self, text="Beam and material inputs", padding=12)
        self.inputs_frame.grid(row=0, column=0, sticky="nsw", padx=(0, 12))

        self.results_frame = ttk.Frame(self)
        self.results_frame.grid(row=0, column=1, sticky="nsew")
        self.results_frame.columnconfigure(0, weight=1)

        self.create_inputs()
        self.create_results()
        self.add_uniform_load("1", "0", "20")
        self.calculate()

    def create_menu(self):
        menu_bar = tk.Menu(self)
        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_project)
        file_menu.add_command(label="Open...", accelerator="Ctrl+O", command=self.open_project)
        file_menu.add_separator()
        file_menu.add_command(label="Export CSV...", command=self.export_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menu_bar.add_cascade(label="File", menu=file_menu)
        self.configure(menu=menu_bar)
        self.bind("<Control-s>", lambda _event: self.save_project())
        self.bind("<Control-o>", lambda _event: self.open_project())

    def create_inputs(self):
        fields = (
            ("span", "Span (ft)", "20"),
            ("section_name", "Section label", "W12x26"),
            ("modulus", "E (ksi)", "29000"),
            ("inertia", "Ix (in^4)", "204"),
            ("section_modulus", "Sx (in^3)", "33.4"),
            ("allowable_stress", "Fb allowable (ksi)", "24"),
            ("deflection_limit", "Deflection limit (in)", "0.667"),
        )
        self.field_vars = {}
        for index, (name, label, value) in enumerate(fields):
            row = index // 2
            column = index % 2
            ttk.Label(self.inputs_frame, text=label).grid(row=row * 2, column=column, sticky="w", padx=4, pady=(6, 1))
            var = tk.StringVar(value=value)
            self.field_vars[name] = var
            ttk.Entry(self.inputs_frame, textvariable=var, width=16).grid(
                row=row * 2 + 1, column=column, sticky="ew", padx=4
            )

        ttk.Label(self.inputs_frame, text="Support type").grid(row=8, column=0, sticky="w", padx=4, pady=(6, 1))
        self.support_var = tk.StringVar(value="Simply supported")
        ttk.Combobox(
            self.inputs_frame,
            textvariable=self.support_var,
            values=("Simply supported",),
            state="readonly",
            width=20,
        ).grid(row=9, column=0, columnspan=2, sticky="w", padx=4)

        ttk.Label(self.inputs_frame, text="Loads").grid(row=10, column=0, columnspan=2, sticky="w", pady=(12, 4))
        self.loads_container = ttk.Frame(self.inputs_frame)
        self.loads_container.grid(row=11, column=0, columnspan=2, sticky="ew")

        actions = ttk.Frame(self.inputs_frame)
        actions.grid(row=12, column=0, columnspan=2, sticky="ew", pady=(8, 4))
        ttk.Button(actions, text="Add point load", command=lambda: self.add_point_load()).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Add uniform load", command=lambda: self.add_uniform_load("1", "0", "")).pack(side="left")
        ttk.Button(self.inputs_frame, text="Export results to CSV", command=self.export_csv).grid(
            row=16, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

        ttk.Label(
            self.inputs_frame,
            text="Load magnitudes are positive downward. Locations are measured\nfrom the left support.",
            wraplength=330,
        ).grid(row=13, column=0, columnspan=2, sticky="w", pady=(6, 8))

        ttk.Button(self.inputs_frame, text="Calculate beam response", command=self.calculate).grid(
            row=14, column=0, columnspan=2, sticky="ew", pady=(4, 0)
        )
        self.error_var = tk.StringVar(value="")
        ttk.Label(self.inputs_frame, textvariable=self.error_var, foreground="#842b2b", wraplength=330).grid(
            row=15, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

    def create_results(self):
        notice = ttk.Label(
            self.results_frame,
            text="Opening example: W12x26 with illustrative properties. Verify your own section properties and allowable stress.",
            wraplength=760,
            foreground="#73531d",
            relief="solid",
            borderwidth=1,
            padding=8,
        )
        notice.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        summary = ttk.LabelFrame(self.results_frame, text="Calculated response", padding=10)
        summary.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        for column in range(3):
            summary.columnconfigure(column, weight=1)

        self.summary_vars = {}
        metrics = (
            ("reaction_a", "Left reaction"),
            ("reaction_b", "Right reaction"),
            ("maximum_shear", "Maximum |shear|"),
            ("maximum_moment", "Maximum |moment|"),
            ("maximum_deflection", "Maximum |deflection|"),
            ("maximum_stress", "Maximum bending stress"),
        )
        for index, (name, label) in enumerate(metrics):
            frame = ttk.Frame(summary, relief="solid", borderwidth=1, padding=8)
            frame.grid(row=index // 3, column=index % 3, sticky="nsew", padx=4, pady=4)
            ttk.Label(frame, text=label, foreground="#526373").pack(anchor="w")
            var = tk.StringVar(value="")
            self.summary_vars[name] = var
            ttk.Label(frame, textvariable=var).pack(anchor="w")

        self.bending_var = tk.StringVar(value="")
        self.deflection_var = tk.StringVar(value="")
        ttk.Label(summary, textvariable=self.bending_var, wraplength=360).grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=5)
        ttk.Label(summary, textvariable=self.deflection_var, wraplength=360).grid(row=2, column=2, sticky="w", padx=4, pady=5)

        self.canvases = []
        titles = (
            ("Beam and loads", "beam"),
            ("Shear diagram (kip)", "shear"),
            ("Moment diagram (kip-ft)", "moment"),
            ("Deflection diagram (in, downward positive)", "deflection"),
        )
        for row, (title, kind) in enumerate(titles, start=2):
            frame = ttk.LabelFrame(self.results_frame, text=title, padding=6)
            frame.grid(row=row, column=0, sticky="nsew", pady=(0, 6))
            frame.columnconfigure(0, weight=1)
            canvas = tk.Canvas(frame, height=150 if kind != "beam" else 130, background="white", highlightthickness=0)
            canvas.grid(row=0, column=0, sticky="nsew")
            canvas.bind("<Configure>", lambda _event, c=canvas, k=kind: self.redraw_canvas(c, k))
            self.canvases.append((kind, canvas))

        self.result = None

    def add_point_load(self):
        span = self.parse_span_or_default()
        row = LoadRow(self.loads_container, self.refresh_load_layout, "Point", "1", f"{span / 2:.2f}", "")
        row.pack(fill="x", pady=3)
        self.load_rows.append(row)

    def add_uniform_load(self, magnitude="1", start="0", end=""):
        row = LoadRow(self.loads_container, self.refresh_load_layout, "Uniform", magnitude, start, end)
        row.pack(fill="x", pady=3)
        self.load_rows.append(row)

    def refresh_load_layout(self):
        self.load_rows = [row for row in self.load_rows if row.winfo_exists()]

    def parse_span_or_default(self):
        try:
            value = float(self.field_vars["span"].get())
            return value if value > 0 else 20
        except (ValueError, KeyError):
            return 20

    def read_inputs(self):
        try:
            return BeamInput(
                span_ft=float(self.field_vars["span"].get()),
                section_name=self.field_vars["section_name"].get().strip() or "Steel beam",
                modulus_ksi=float(self.field_vars["modulus"].get()),
                inertia_in4=float(self.field_vars["inertia"].get()),
                section_modulus_in3=float(self.field_vars["section_modulus"].get()),
                allowable_stress_ksi=float(self.field_vars["allowable_stress"].get()),
                loads=tuple(row.read() for row in self.load_rows),
                support_type=self.support_var.get(),
                deflection_limit_in=float(self.field_vars["deflection_limit"].get()),
            )
        except ValueError as exc:
            raise ValueError("Enter valid numeric values for all fields.") from exc

    def save_project(self):
        if self.project_path:
            path = self.project_path
        else:
            path = filedialog.asksaveasfilename(
                defaultextension=".beam.json",
                filetypes=(("Beam Designer project", "*.beam.json"), ("JSON files", "*.json"), ("All files", "*.*")),
                title="Save Beam",
            )
        if not path:
            return
        try:
            data = self.read_inputs()
            project = {
                "version": 1,
                "support_type": data.support_type,
                "span_ft": data.span_ft,
                "section_name": data.section_name,
                "modulus_ksi": data.modulus_ksi,
                "inertia_in4": data.inertia_in4,
                "section_modulus_in3": data.section_modulus_in3,
                "allowable_stress_ksi": data.allowable_stress_ksi,
                "deflection_limit_in": data.deflection_limit_in,
                "loads": [],
            }
            for load in data.loads:
                if isinstance(load, PointLoad):
                    project["loads"].append({
                        "type": "point",
                        "magnitude": load.magnitude_kip,
                        "start": load.position_ft,
                    })
                else:
                    project["loads"].append({
                        "type": "uniform",
                        "magnitude": load.magnitude_kip_ft,
                        "start": load.start_ft,
                        "end": load.end_ft,
                    })
            Path(path).write_text(json.dumps(project, indent=2), encoding="utf-8")
            self.project_path = path
            self.title(f"Beam Designer - {Path(path).name}")
        except (ValueError, OSError) as exc:
            messagebox.showerror("Save Beam", f"Could not save the beam:\n{exc}")

    def open_project(self):
        path = filedialog.askopenfilename(
            filetypes=(("Beam Designer project", "*.beam.json"), ("JSON files", "*.json"), ("All files", "*.*")),
            title="Open Beam",
        )
        if not path:
            return
        try:
            project = json.loads(Path(path).read_text(encoding="utf-8"))
            values = (
                ("span", "span_ft"),
                ("section_name", "section_name"),
                ("modulus", "modulus_ksi"),
                ("inertia", "inertia_in4"),
                ("section_modulus", "section_modulus_in3"),
                ("allowable_stress", "allowable_stress_ksi"),
                ("deflection_limit", "deflection_limit_in"),
            )
            for field_name, key in values:
                value = project.get(key)
                if value is not None:
                    self.field_vars[field_name].set(str(value))
            support_type = project.get("support_type", "Simply supported")
            if support_type not in ("Simply supported",):
                raise ValueError("The saved beam uses an unsupported support type.")
            self.support_var.set(support_type)

            for row in list(self.load_rows):
                row.destroy()
            self.load_rows = []
            for load in project.get("loads", []):
                if load.get("type") == "point":
                    self.add_point_load_from_values(load["magnitude"], load["start"])
                elif load.get("type") == "uniform":
                    self.add_uniform_load(
                        str(load["magnitude"]),
                        str(load["start"]),
                        str(load["end"]),
                    )
                else:
                    raise ValueError("The project contains an unsupported load type.")
            if not self.load_rows:
                raise ValueError("The project contains no loads.")

            self.project_path = path
            self.title(f"Beam Designer - {Path(path).name}")
            self.calculate()
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError) as exc:
            messagebox.showerror("Open Beam", f"Could not open the beam:\n{exc}")

    def add_point_load_from_values(self, magnitude, start):
        row = LoadRow(
            self.loads_container,
            self.refresh_load_layout,
            "Point",
            str(magnitude),
            str(start),
            "",
        )
        row.pack(fill="x", pady=3)
        self.load_rows.append(row)

    def calculate(self):
        self.error_var.set("")
        try:
            data = self.read_inputs()
            self.result = calculate_beam(data)
        except ValueError as exc:
            self.error_var.set(str(exc))
            return

        result = self.result
        self.summary_vars["reaction_a"].set(f"{result.reaction_a_kip:.2f} kip")
        self.summary_vars["reaction_b"].set(f"{result.reaction_b_kip:.2f} kip")
        self.summary_vars["maximum_shear"].set(f"{result.maximum_shear_kip:.2f} kip")
        self.summary_vars["maximum_moment"].set(f"{result.maximum_moment_kip_ft:.2f} kip-ft")
        self.summary_vars["maximum_deflection"].set(
            f"{result.maximum_deflection_in:.3f} in at {result.max_deflection_at_ft:.2f} ft"
        )
        self.summary_vars["maximum_stress"].set(f"{result.maximum_bending_stress_ksi:.2f} ksi")
        bending_status = "PASS" if result.bending_passes else "FAIL"
        deflection_status = "PASS" if result.deflection_passes else "FAIL"
        self.bending_var.set(
            f"Bending: {bending_status}\n{result.maximum_bending_stress_ksi:.2f} ksi / "
            f"{result.allowable_stress_ksi:.2f} ksi allowable"
        )
        self.deflection_var.set(
            f"Deflection: {deflection_status}\n{result.maximum_deflection_in:.3f} in / "
            f"{result.deflection_limit_in:.3f} in limit (L/360)"
        )
        for kind, canvas in self.canvases:
            self.redraw_canvas(canvas, kind)

    def export_csv(self):
        if not self.result:
            messagebox.showwarning("Export CSV", "Calculate a beam response before exporting.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=(("CSV file", "*.csv"), ("All files", "*.*")),
            title="Export Beam Results",
        )
        if not path:
            return

        def interpolate(points, x_ft):
            if x_ft <= points[0][0]:
                return points[0][1]
            if x_ft >= points[-1][0]:
                return points[-1][1]
            for (x1, y1), (x2, y2) in zip(points, points[1:]):
                if x1 <= x_ft <= x2:
                    fraction = (x_ft - x1) / (x2 - x1) if x2 != x1 else 0
                    return y1 + fraction * (y2 - y1)
            return 0.0

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(["x_ft", "V_kip", "M_kip_ft", "deflection_in"])
                steps = 320
                for index in range(steps + 1):
                    x_ft = self.result.span_ft * index / steps
                    writer.writerow([
                        f"{x_ft:.6f}",
                        f"{interpolate(self.result.shear_curve, x_ft):.6f}",
                        f"{interpolate(self.result.moment_curve, x_ft):.6f}",
                        f"{interpolate(self.result.deflection_curve, x_ft):.9f}",
                    ])
        except OSError as exc:
            messagebox.showerror("Export CSV", f"Could not export the CSV:\n{exc}")

    def redraw_canvas(self, canvas, kind):
        if not self.result:
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 300)
        height = canvas.winfo_height()
        if kind == "beam":
            self.draw_beam(canvas, width, height)
        elif kind == "shear":
            self.draw_curve(canvas, width, height, self.result.shear_curve, "kip")
        elif kind == "moment":
            self.draw_curve(canvas, width, height, self.result.moment_curve, "kip-ft")
        else:
            self.draw_curve(canvas, width, height, self.result.deflection_curve, "in")

    def draw_beam(self, canvas, width, height):
        left, right = 55, width - 55
        beam_y = 75
        result = self.result
        canvas.create_line(left, beam_y, right, beam_y, fill="#173d5c", width=8)

        for load in result.loads:
            if isinstance(load, PointLoad):
                x = left + load.position_ft / result.span_ft * (right - left)
                canvas.create_line(x, 25, x, beam_y - 5, fill="#a34832", width=2, arrow=tk.LAST)
                canvas.create_text(x, 14, text=f"{load.magnitude_kip:.2f} kip", fill="#793723", font=("Segoe UI", 9))
            else:
                x1 = left + load.start_ft / result.span_ft * (right - left)
                x2 = left + load.end_ft / result.span_ft * (right - left)
                canvas.create_line(x1, 34, x2, 34, fill="#a34832", width=2)
                canvas.create_text((x1 + x2) / 2, 20, text=f"{load.magnitude_kip_ft:.2f} kip/ft", fill="#793723", font=("Segoe UI", 9))
                count = max(3, min(12, round((load.end_ft - load.start_ft) / result.span_ft * 16)))
                for index in range(count + 1):
                    x = x1 + (x2 - x1) * index / count
                    canvas.create_line(x, 36, x, beam_y - 5, fill="#a34832", width=1, arrow=tk.LAST)

        for x, label in ((left, "A"), (right, "B")):
            canvas.create_polygon(x - 12, 100, x, 82, x + 12, 100, fill="#dbe7ee", outline="#536575")
            canvas.create_line(x - 18, 101, x + 18, 101, fill="#536575")
            canvas.create_text(x, 116, text=label, fill="#536575")
        canvas.create_text(width / 2, 116, text=f"L = {result.span_ft:.2f} ft  ·  {result.section_name}", fill="#536575")

    def draw_curve(self, canvas, width, height, points, unit):
        if len(points) < 2:
            return
        left, right = 58, width - 18
        top, bottom = 18, height - 35
        values = [value for _, value in points]
        raw_min = min(0.0, *values)
        raw_max = max(0.0, *values)
        value_range = raw_max - raw_min or 1.0
        min_value = raw_min - value_range * 0.1
        max_value = raw_max + value_range * 0.1
        x_max = points[-1][0] or 1

        def x_at(value):
            return left + value / x_max * (right - left)

        def y_at(value):
            return bottom - (value - min_value) / (max_value - min_value) * (bottom - top)

        zero_y = y_at(0)
        canvas.create_line(left, zero_y, right, zero_y, fill="#8c9aa6", width=1)
        canvas.create_line(left, top, left, bottom, fill="#c4cdd5", width=1)

        pixel_points = [(x_at(x), y_at(value)) for x, value in points]
        for start, end in zip(pixel_points, pixel_points[1:]):
            canvas.create_line(*start, *end, fill="#176c9c", width=2)

        canvas.create_text(4, top + 4, text=f"{raw_max:.2f} {unit}", anchor="nw", fill="#536575", font=("Segoe UI", 9))
        canvas.create_text(4, bottom, text=f"{raw_min:.2f} {unit}", anchor="sw", fill="#536575", font=("Segoe UI", 9))
        canvas.create_text(left, height - 12, text="0 ft", anchor="w", fill="#536575", font=("Segoe UI", 9))
        canvas.create_text(right, height - 12, text=f"{x_max:.2f} ft", anchor="e", fill="#536575", font=("Segoe UI", 9))


def main():
    app = BeamDesignerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
