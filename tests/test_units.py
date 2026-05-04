from weather_truth.units import pa_to_hpa


def test_pa_to_hpa():
    assert pa_to_hpa(101500) == 1015.0
