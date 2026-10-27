"""Ad-hoc sensitivity probe: does each condition feature move
the predicted value in the right direction?"""

from app.services.ml_valuation import calculate_ml_valuation

BASE = {
    "smartphone_brand": "Apple",
    "model": "iPhone 15",
    "ram_gb": 8,
    "storage_gb": 128,
    "device_age_months": 24,
    "battery_health_pct": 90,
    "camera_condition_score": 85,
    "functional_test_score": 90,
    "diagnostic_score": 95,
    "diagnostics_failed_count": 0,
    "diagnostic_sensor_failed": 0,
}

CLEAN = {
    "screen_condition_score": 98,
    "body_condition_score": 95,
    "scratch_severity": 0,
    "dent_severity": 0,
    "crack_severity": 0,
    "frame_damage_severity": 0,
}


def value(overrides):
    row = dict(BASE)
    row.update(CLEAN)
    row.update(overrides)
    return calculate_ml_valuation(row, None)


print("overall condition ladder")
print("  pristine :", value({})["device_value"])
print("  scratched:", value({
    "screen_condition_score": 78,
    "body_condition_score": 72,
    "scratch_severity": 1,
    "frame_damage_severity": 1,
})["device_value"])
print("  cracked  :", value({
    "screen_condition_score": 18,
    "body_condition_score": 40,
    "scratch_severity": 2,
    "crack_severity": 3,
    "frame_damage_severity": 3,
})["device_value"])

print()
print("one flag at a time, severity 0 -> 3")
for name in (
    "scratch_severity",
    "dent_severity",
    "crack_severity",
    "frame_damage_severity",
):
    low = value({name: 0})["device_value"]
    high = value({name: 3})["device_value"]
    flag = "OK " if high < low else "!! "
    print(f"  {flag}{name:24} {low:>7} -> {high:>7}")

print()
print("other condition features, good -> bad")
for name, good, bad in (
    ("screen_condition_score", 98, 20),
    ("body_condition_score", 95, 25),
    ("camera_condition_score", 95, 25),
    ("battery_health_pct", 100, 55),
    ("device_age_months", 3, 48),
    ("functional_test_score", 100, 45),
    ("diagnostic_score", 100, 40),
    ("diagnostics_failed_count", 0, 4),
    ("ai_condition_score", 98, 30),
    ("repair_history_code", 0, 2),
    ("accessories_code", 3, 0),
    ("warranty_months_remaining", 12, 0),
):
    low = value({name: good})["device_value"]
    high = value({name: bad})["device_value"]
    flag = "OK " if high < low else "!! "
    print(
        f"  {flag}{name:26} {good:>4} -> {bad:<4}"
        f" {low:>7} -> {high:>7}"
    )
