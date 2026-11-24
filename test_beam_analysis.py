import unittest

from beam_analysis import BeamInput, PointLoad, UniformLoad, calculate_beam


def make_input(span_ft=20, loads=()):
    return BeamInput(
        span_ft=span_ft,
        section_name="W12x26",
        modulus_ksi=29000,
        inertia_in4=204,
        section_modulus_in3=33.4,
        allowable_stress_ksi=24,
        loads=loads,
    )


class BeamAnalysisTests(unittest.TestCase):
    def test_full_span_uniform_load(self):
        result = calculate_beam(make_input(loads=(UniformLoad(1, 0, 20),)))
        self.assertAlmostEqual(result.reaction_a_kip, 10, places=6)
        self.assertAlmostEqual(result.reaction_b_kip, 10, places=6)
        self.assertAlmostEqual(result.maximum_shear_kip, 10, places=6)
        self.assertAlmostEqual(result.maximum_moment_kip_ft, 50, places=6)
        self.assertAlmostEqual(result.maximum_deflection_in, 0.609, places=2)

    def test_center_point_load(self):
        result = calculate_beam(make_input(loads=(PointLoad(10, 10),)))
        self.assertAlmostEqual(result.reaction_a_kip, 5, places=6)
        self.assertAlmostEqual(result.reaction_b_kip, 5, places=6)
        self.assertAlmostEqual(result.maximum_shear_kip, 5, places=6)
        self.assertAlmostEqual(result.maximum_moment_kip_ft, 50, places=6)

    def test_partial_uniform_load(self):
        result = calculate_beam(make_input(loads=(UniformLoad(1, 5, 15),)))
        self.assertAlmostEqual(result.reaction_a_kip, 5, places=6)
        self.assertAlmostEqual(result.reaction_b_kip, 5, places=6)
        self.assertAlmostEqual(result.maximum_shear_kip, 5, places=6)
        self.assertAlmostEqual(result.maximum_moment_kip_ft, 37.5, places=6)

    def test_invalid_load_location(self):
        with self.assertRaisesRegex(ValueError, "inside the span"):
            calculate_beam(make_input(loads=(PointLoad(10, 20),)))

    def test_custom_deflection_limit(self):
        data = BeamInput(
            span_ft=20,
            section_name="W12x26",
            modulus_ksi=29000,
            inertia_in4=204,
            section_modulus_in3=33.4,
            allowable_stress_ksi=24,
            loads=(UniformLoad(1, 0, 20),),
            deflection_limit_in=0.5,
        )
        result = calculate_beam(data)
        self.assertEqual(result.deflection_limit_in, 0.5)
        self.assertFalse(result.deflection_passes)


if __name__ == "__main__":
    unittest.main()
