from dataclasses import dataclass
from math import isfinite
from typing import Callable, Iterable


@dataclass(frozen=True)
class PointLoad:
    magnitude_kip: float
    position_ft: float


@dataclass(frozen=True)
class UniformLoad:
    magnitude_kip_ft: float
    start_ft: float
    end_ft: float


Load = PointLoad | UniformLoad


@dataclass(frozen=True)
class BeamInput:
    span_ft: float
    section_name: str
    modulus_ksi: float
    inertia_in4: float
    section_modulus_in3: float
    allowable_stress_ksi: float
    loads: tuple[Load, ...]
    support_type: str = "Simply supported"
    deflection_limit_in: float | None = None


@dataclass(frozen=True)
class BeamResult:
    span_ft: float
    section_name: str
    reaction_a_kip: float
    reaction_b_kip: float
    maximum_shear_kip: float
    maximum_moment_kip_ft: float
    maximum_deflection_in: float
    max_deflection_at_ft: float
    maximum_bending_stress_ksi: float
    allowable_stress_ksi: float
    deflection_limit_in: float
    bending_passes: bool
    deflection_passes: bool
    shear_curve: tuple[tuple[float, float], ...]
    moment_curve: tuple[tuple[float, float], ...]
    deflection_curve: tuple[tuple[float, float], ...]
    loads: tuple[Load, ...]


def positive(value: float, label: str) -> float:
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a positive number.")
    return value


def calculate_beam(data: BeamInput) -> BeamResult:
    span_ft = positive(data.span_ft, "Span")
    span_in = span_ft * 12
    modulus_ksi = positive(data.modulus_ksi, "E")
    inertia_in4 = positive(data.inertia_in4, "Ix")
    section_modulus_in3 = positive(data.section_modulus_in3, "Sx")
    allowable_stress_ksi = positive(data.allowable_stress_ksi, "Fb allowable")

    if not data.loads:
        raise ValueError("Add at least one load.")

    loads: list[tuple[str, float, float, float | None]] = []
    total_load_kip = 0.0
    moment_about_left_kip_in = 0.0

    for index, load in enumerate(data.loads, start=1):
        label = f"Load {index}"
        if isinstance(load, PointLoad):
            magnitude = positive(load.magnitude_kip, f"{label} magnitude")
            if not isfinite(load.position_ft) or load.position_ft <= 0 or load.position_ft >= span_ft:
                raise ValueError(f"{label} location must be inside the span.")
            position_in = load.position_ft * 12
            loads.append(("point", magnitude, position_in, None))
            total_load_kip += magnitude
            moment_about_left_kip_in += magnitude * position_in
        elif isinstance(load, UniformLoad):
            magnitude = positive(load.magnitude_kip_ft, f"{label} magnitude")
            if (
                not isfinite(load.start_ft)
                or not isfinite(load.end_ft)
                or load.start_ft < 0
                or load.end_ft > span_ft
                or load.start_ft >= load.end_ft
            ):
                raise ValueError(f"{label} must have 0 <= start < end <= span.")
            start_in = load.start_ft * 12
            end_in = load.end_ft * 12
            intensity_kip_in = magnitude / 12
            loads.append(("uniform", intensity_kip_in, start_in, end_in))
            resultant = intensity_kip_in * (end_in - start_in)
            total_load_kip += resultant
            moment_about_left_kip_in += resultant * (start_in + end_in) / 2
        else:
            raise ValueError(f"{label} has an unsupported load type.")

    reaction_b = moment_about_left_kip_in / span_in
    reaction_a = total_load_kip - reaction_b

    stations = {0.0, span_in}
    for _, _, start_in, end_in in loads:
        stations.add(start_in)
        if end_in is not None:
            stations.add(end_in)
    ordered_stations = sorted(stations)

    def shear_at(x: float, side: str = "right") -> float:
        shear = reaction_a
        for load_type, magnitude, start_in, end_in in loads:
            if load_type == "point":
                if start_in < x or (start_in == x and side == "right"):
                    shear -= magnitude
            else:
                assert end_in is not None
                loaded_length = max(0.0, min(x, end_in) - start_in)
                shear -= magnitude * loaded_length
        return shear

    def moment_at(x: float) -> float:
        moment = reaction_a * x
        for load_type, magnitude, start_in, end_in in loads:
            if load_type == "point":
                moment -= magnitude * max(0.0, x - start_in)
            else:
                assert end_in is not None
                from_start = max(0.0, x - start_in)
                from_end = max(0.0, x - end_in)
                moment -= magnitude * (from_start * from_start - from_end * from_end) / 2
        return moment

    def double_integrated_moment(x: float) -> float:
        value = reaction_a * x ** 3 / 6
        for load_type, magnitude, start_in, end_in in loads:
            if load_type == "point":
                value -= magnitude * max(0.0, x - start_in) ** 3 / 6
            else:
                assert end_in is not None
                from_start = max(0.0, x - start_in)
                from_end = max(0.0, x - end_in)
                value -= magnitude * (from_start ** 4 - from_end ** 4) / 24
        return value

    flexural_rigidity = modulus_ksi * inertia_in4
    end_integral = double_integrated_moment(span_in)

    def deflection_at(x: float) -> float:
        return (end_integral * x / span_in - double_integrated_moment(x)) / flexural_rigidity

    maximum_shear = max(abs(reaction_a), abs(reaction_b))
    for station in ordered_stations:
        if station > 0:
            maximum_shear = max(maximum_shear, abs(shear_at(station, "left")))
        if station < span_in:
            maximum_shear = max(maximum_shear, abs(shear_at(station, "right")))

    moment_candidates = set(ordered_stations)
    for start, end in zip(ordered_stations, ordered_stations[1:]):
        start_shear = shear_at(start, "right")
        end_shear = shear_at(end, "left")
        if start_shear * end_shear < 0:
            moment_candidates.add(start + (end - start) * start_shear / (start_shear - end_shear))

    max_moment_kip_in = 0.0
    max_moment_at_in = 0.0
    for x in moment_candidates:
        value = abs(moment_at(x))
        if value > max_moment_kip_in:
            max_moment_kip_in = value
            max_moment_at_in = x

    def maximum_absolute(fn: Callable[[float], float], end: float, samples: int = 800) -> tuple[float, float]:
        step = end / samples
        best_x = 0.0
        best_value = abs(fn(0.0))
        for index in range(samples + 1):
            x = index * step
            value = abs(fn(x))
            if value > best_value:
                best_value = value
                best_x = x
        return best_value, best_x

    maximum_deflection, max_deflection_at_in = maximum_absolute(deflection_at, span_in)
    maximum_bending_stress = max_moment_kip_in / section_modulus_in3
    deflection_limit = (
        positive(data.deflection_limit_in, "Deflection limit")
        if data.deflection_limit_in is not None
        else span_in / 360
    )

    def sample_curve(
        fn: Callable[[float], float],
        steps: int,
        include_shear_jumps: bool,
    ) -> tuple[tuple[float, float], ...]:
        xs = {span_in * index / steps for index in range(steps + 1)}
        xs.update(ordered_stations)
        points: list[tuple[float, float]] = []
        for x in sorted(xs):
            if include_shear_jumps:
                has_point = any(load_type == "point" and start == x for load_type, _, start, _ in loads)
                if has_point:
                    points.append((x / 12, fn(x, "left")))
                    points.append((x / 12, fn(x, "right")))
                else:
                    points.append((x / 12, fn(x)))
            else:
                points.append((x / 12, fn(x)))
        return tuple(points)

    shear_curve = sample_curve(shear_at, 320, True)
    moment_curve = tuple((x_ft, moment_at(x_ft * 12) / 12) for x_ft, _ in sample_curve(lambda x: moment_at(x), 320, False))
    deflection_curve = tuple((x_ft, deflection_at(x_ft * 12)) for x_ft, _ in sample_curve(lambda x: deflection_at(x), 320, False))

    return BeamResult(
        span_ft=span_ft,
        section_name=data.section_name.strip() or "Steel beam",
        reaction_a_kip=reaction_a,
        reaction_b_kip=reaction_b,
        maximum_shear_kip=maximum_shear,
        maximum_moment_kip_ft=max_moment_kip_in / 12,
        maximum_deflection_in=maximum_deflection,
        max_deflection_at_ft=max_deflection_at_in / 12,
        maximum_bending_stress_ksi=maximum_bending_stress,
        allowable_stress_ksi=allowable_stress_ksi,
        deflection_limit_in=deflection_limit,
        bending_passes=maximum_bending_stress <= allowable_stress_ksi,
        deflection_passes=maximum_deflection <= deflection_limit,
        shear_curve=shear_curve,
        moment_curve=moment_curve,
        deflection_curve=deflection_curve,
        loads=data.loads,
    )
