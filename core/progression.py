from config import INTENSITY, DELOAD_WEIGHT_FACTOR, CONSECUTIVE_FAIL_THRESHOLD
from core.templates import is_lower_body


def compute_progression(sets_logged: list[dict], intensity: str, slot: str,
                         current_weight: float, consecutive_failures: int) -> dict:
    """
    Given logged sets, decide: increase / maintain / decrease.
    Returns dict with decision, next_weight, new_consecutive_failures.
    """
    cfg = INTENSITY[intensity]
    rep_min, rep_max = cfg["reps"]

    if not sets_logged:
        return {
            "decision": "no_data",
            "next_weight_kg": current_weight,
            "consecutive_failures": consecutive_failures,
            "avg_reps": 0,
        }

    reps_list = [s["reps"] for s in sets_logged if s["reps"] > 0]
    failed    = [s for s in sets_logged if s["reps"] == 0]

    if not reps_list:
        # All sets failed
        new_failures = consecutive_failures + 1
        lower = is_lower_body(slot)
        dec   = cfg["decrement_lower"] if lower else cfg["decrement_standard"]
        return {
            "decision": "decrease",
            "next_weight_kg": max(0.0, current_weight - dec),
            "consecutive_failures": new_failures,
            "avg_reps": 0,
        }

    avg = sum(reps_list) / len(reps_list)
    lower = is_lower_body(slot)

    # Check for individual-exercise deload trigger
    if consecutive_failures >= CONSECUTIVE_FAIL_THRESHOLD:
        dec = cfg["decrement_lower"] if lower else cfg["decrement_standard"]
        return {
            "decision": "single_deload",
            "next_weight_kg": round(current_weight * 0.9, 1),  # -10%
            "consecutive_failures": 0,
            "avg_reps": round(avg, 1),
        }

    if avg >= rep_max:
        inc = cfg["increment_lower"] if lower else cfg["increment_standard"]
        return {
            "decision": "increase",
            "next_weight_kg": current_weight + inc,
            "consecutive_failures": 0,
            "avg_reps": round(avg, 1),
        }
    elif avg >= rep_min:
        return {
            "decision": "maintain",
            "next_weight_kg": current_weight,
            "consecutive_failures": 0,
            "avg_reps": round(avg, 1),
        }
    else:
        new_failures = consecutive_failures + (1 if failed else 0)
        dec = cfg["decrement_lower"] if lower else cfg["decrement_standard"]
        return {
            "decision": "decrease",
            "next_weight_kg": max(0.0, current_weight - dec),
            "consecutive_failures": new_failures,
            "avg_reps": round(avg, 1),
        }


def apply_deload(weight_kg: float, intensity_cfg: dict) -> tuple[float, int, tuple]:
    """Return (deload_weight, deload_sets, deload_reps)."""
    deload_weight = round(weight_kg * DELOAD_WEIGHT_FACTOR, 1)
    deload_sets   = max(1, intensity_cfg["sets"][0] - 1)
    deload_reps   = INTENSITY["easy"]["reps"]
    return deload_weight, deload_sets, deload_reps


def advance_week(user: dict, split: str) -> dict:
    """
    Call after the last day of a split cycle is completed.
    Returns updated week fields.
    """
    from config import DELOAD_WEEK
    week = user["week_number"] + 1
    is_deload = False

    if week > DELOAD_WEEK:
        week = 1
        is_deload = True  # next block is deload week

    return {"week_number": week, "is_deload": int(is_deload)}
