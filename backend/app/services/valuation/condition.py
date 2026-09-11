from app.services.valuation.registry import normalize_text


# ============================================================
# CONDITION GRADE
# ============================================================

EXCHANGE_RATE = 0.88

GRADE_MULTIPLIERS = {
    "A+": 1.00,
    "A": 0.94,
    "B": 0.86,
    "C": 0.75,
    "D": 0.60,
}

def get_condition_grade(
    score
):

    if score >= 90:
        return "A+"

    if score >= 80:
        return "A"

    if score >= 70:
        return "B"

    if score >= 60:
        return "C"

    return "D"


def photo_condition_metrics(
    condition_score
):
    """Condition multiplier + grade used by the AI photo flows.

    multiplier: 100 -> 1.00, 0 -> 0.60
    """

    condition_multiplier = 0.60 + (
        max(
            0.0,
            min(100.0, condition_score)
        )
        / 100.0
    ) * 0.40

    condition_grade = get_condition_grade(
        condition_score
    )

    return condition_multiplier, condition_grade


# ============================================================
# CONDITION SCORE
# ============================================================

def calculate_condition_score(
    answers
):

    score = 100

    # ========================================================
    # AGE
    # ========================================================

    age = normalize_text(
        answers.get("age")
        or answers.get("device_age")
        or answers.get("purchase_age")
    )

    age_deductions = {

        "less than 6 months": 0,
        "0-6 months": 0,

        "6 to 12 months": 5,
        "6-12 months": 5,

        "1 year": 8,

        "1 to 2 years": 12,
        "1-2 years": 12,

        "2 years": 18,

        "2 to 3 years": 25,
        "2-3 years": 25,

        "3+ years": 32,
        "more than 3 years": 32,
    }

    score -= age_deductions.get(
        age,
        0
    )

    # ========================================================
    # SCREEN
    # ========================================================

    screen = normalize_text(
        answers.get("screen")
        or answers.get("screen_condition")
    )

    screen_deductions = {

        "excellent": 0,
        "like new": 0,

        "good": 5,

        "minor scratches": 8,

        "scratched": 12,

        "cracked": 30,

        "broken": 40,

        "display problem": 40,
    }

    score -= screen_deductions.get(
        screen,
        0
    )

    # ========================================================
    # BODY
    # ========================================================

    body = normalize_text(
        answers.get("body")
        or answers.get("body_condition")
    )

    body_deductions = {

        "excellent": 0,
        "like new": 0,

        "good": 5,

        "minor scratches": 8,

        "scratches": 10,
        "multiple scratches": 10,

        "dents": 18,
        "minor dents": 18,

        "heavy damage": 30,
        "major damage": 30,

        "broken": 40,
    }

    score -= body_deductions.get(
        body,
        0
    )

    # ========================================================
    # BATTERY
    # ========================================================

    battery = normalize_text(
        answers.get("battery")
        or answers.get("battery_health")
        or answers.get("battery_condition")
    )

    battery_deductions = {

        "excellent": 0,

        "good": 3,

        "80-100%": 3,

        "70-80%": 8,
        "below 80": 8,

        "below 70%": 15,
        "poor": 15,

        "replaced": 5,
    }

    score -= battery_deductions.get(
        battery,
        0
    )

    # ========================================================
    # FUNCTIONALITY
    # ========================================================

    functionality = normalize_text(
        answers.get("functionality")
        or answers.get("working_condition")
    )

    functionality_deductions = {

        "fully working": 0,
        "everything works": 0,
        "good": 0,
        "yes": 0,

        "minor issues": 10,
        "not sure": 5,

        "some issues": 15,
        "no": 15,

        "major issues": 30,

        "not working": 50,
    }

    score -= functionality_deductions.get(
        functionality,
        0
    )

    # ========================================================
    # ACCESSORIES
    # ========================================================

    charger = normalize_text(
        answers.get("original_charger")
        or answers.get("accessories")
        or answers.get("charger_box")
        or answers.get("charger")
    )

    box = normalize_text(
        answers.get("original_box")
    )

    if box == "yes" and charger == "yes":

        score += 2

    elif charger == "yes":

        score += 0

    elif box == "yes":

        score += 0

    else:

        score -= 3

    # ========================================================
    # REPAIR HISTORY
    # ========================================================

    repair = normalize_text(
        answers.get("repair_history")
        or answers.get("repair")
        or answers.get("repair_status")
    )

    if repair in [
        "no",
        "no repairs",
        "none",
    ]:

        score += 0

    elif repair in [
        "authorized",
        "authorized service",
        "yes authorized service",
    ]:

        score -= 5

    elif repair in [
        "third party",
        "third-party service",
        "yes third party service",
    ]:

        score -= 12

    elif repair in [
        "unknown",
        "i don't know",
    ]:

        score -= 3

    # ========================================================
    # FINAL RANGE
    # ========================================================

    return max(
        0,
        min(
            100,
            score
        )
    )
