"""Diagnostics -> numeric model features.

=================================================================
DIAGNOSTICS ARE MODEL INPUTS, NOT DISPLAY TEXT
=================================================================

The full-inspection flow runs hardware sensor tests in the
browser (camera, microphone, motion, location, touchscreen),
collects a self-report, and stores the outcome on the
inspection record as:

    working            "yes" | "no"
    diagnostics_score  0..100
    diagnostics_report {
        "sensorResults": {test_id: "passed"|"failed"|...},
        "selfReport":    {question_key: answer},
        "finalScore":    0..100
    }

This module converts that into the features the valuation model
consumes:

    diagnostic_score                  = passed / total * 100
    diagnostics_failed_count          = number of failures
    diagnostic_camera_failed          1/0
    diagnostic_microphone_failed      1/0
    diagnostic_touch_failed           1/0
    diagnostic_sensor_failed          1/0  (motion / location)
    diagnostic_connectivity_failed    1/0

The individual failure flags matter. A phone whose camera is
dead is not worth the same as one whose GPS chip is dead, and a
single average score cannot express that difference. Splitting
them into separate columns lets the forest learn separate
penalties.

`unsupported` is treated as neither pass nor failure: a browser
that cannot test GPS should not be scored as a GPS failure.
"""

import json

from app.core.logger import get_logger
from ml.feature_schema import (
    DEFAULT_CONDITION_FEATURES,
    SENSOR_FAILURE_FEATURES,
    SENSOR_TEST_KEYS,
    SENSOR_CONNECTIVITY_KEYS,
)


logger = get_logger(__name__)


# Feature column -> sensor test id. Several sensors share the
# combined `diagnostic_sensor_failed` column.
_SENSOR_TO_FEATURE = {
    key: feature
    for key, feature in (
        SENSOR_FAILURE_FEATURES.items()
    )
}

# Connectivity failures reported in the self-report rather than
# as a sensor test.
_CONNECTIVITY_ANSWERS = {
    "wifi_only",
    "nothing",
    "no",
    "frequent",
}


def parse_diagnostics_report(raw):
    """Return the report as a dict, or None.

    Accepts the JSON string stored on the model or an already
    decoded dict.
    """

    if not raw:
        return None

    if isinstance(raw, dict):
        return raw

    try:
        decoded = json.loads(raw)

    except (TypeError, ValueError) as exc:

        logger.warning(
            "Could not parse diagnostics report: %s",
            exc,
        )
        return None

    return decoded if isinstance(decoded, dict) else None


def _sensor_results(report):
    if not report:
        return {}

    results = report.get("sensorResults")

    if not isinstance(results, dict):
        return {}

    return {
        str(key).lower(): str(value).lower()
        for key, value in results.items()
    }


def _self_report(report):
    if not report:
        return {}

    self_report = report.get("selfReport")

    if not isinstance(self_report, dict):
        return {}

    return {
        str(key).lower(): str(value).lower()
        for key, value in self_report.items()
    }


def compute_diagnostic_score(
    sensor_results,
    reported_score=None
) -> float:
    """passed / total * 100.

    Falls back to the client-reported score when no sensor
    results were recorded, so a flow that only submits a
    self-report still contributes a real diagnostic signal.
    """

    scored = {
        key: value
        for key, value in sensor_results.items()
        if value in ("passed", "failed")
    }

    if scored:

        passed = sum(
            1
            for value in scored.values()
            if value == "passed"
        )

        return round(
            (passed / len(scored)) * 100.0,
            2,
        )

    if reported_score is not None:

        try:
            return max(
                0.0,
                min(100.0, float(reported_score)),
            )

        except (TypeError, ValueError):
            return DEFAULT_CONDITION_FEATURES[
                "diagnostic_score"
            ]

    return DEFAULT_CONDITION_FEATURES[
        "diagnostic_score"
    ]


def diagnostic_features(
    working=None,
    diagnostics_score=None,
    diagnostics_report=None,
    sensor_results=None,
    self_report=None
) -> dict:
    """Build the diagnostic condition features.

    working:
        "no" short-circuits to a zeroed diagnostic signal: a
        phone the owner has declared non-functional cannot pass
        tests.
    """

    report = parse_diagnostics_report(diagnostics_report)

    if sensor_results is None:
        sensor_results = _sensor_results(report)

    else:
        sensor_results = {
            str(key).lower(): str(value).lower()
            for key, value in sensor_results.items()
        }

    if self_report is None:
        self_report = _self_report(report)

    defaults = DEFAULT_CONDITION_FEATURES

    if working is not None and str(
        working
    ).strip().lower() in ("no", "false"):

        logger.info(
            "Device declared not working; "
            "zeroing diagnostic features."
        )

        return {
            "diagnostic_score": 0.0,
            "diagnostics_failed_count": float(
                len(SENSOR_TEST_KEYS)
            ),
            "diagnostic_camera_failed": 1.0,
            "diagnostic_microphone_failed": 1.0,
            "diagnostic_touch_failed": 1.0,
            "diagnostic_sensor_failed": 1.0,
            "diagnostic_connectivity_failed": 1.0,
        }

    score = compute_diagnostic_score(
        sensor_results,
        reported_score=diagnostics_score,
    )

    failures = {
        key
        for key, value in sensor_results.items()
        if value == "failed"
    }

    failed_count = float(len(failures))

    features = {
        "diagnostic_score": score,
        "diagnostics_failed_count": failed_count,
    }

    # Individual sensor failure flags.

    for test_key, feature in _SENSOR_TO_FEATURE.items():

        current = features.get(
            feature,
            defaults[feature],
        )

        if test_key in failures:
            features[feature] = 1.0

        else:
            features.setdefault(
                feature,
                float(current),
            )

    for feature in (
        "diagnostic_camera_failed",
        "diagnostic_microphone_failed",
        "diagnostic_touch_failed",
        "diagnostic_sensor_failed",
    ):
        features.setdefault(
            feature,
            defaults[feature],
        )

    # Connectivity, from the self-report.

    connectivity_failed = defaults[
        "diagnostic_connectivity_failed"
    ]

    for key in SENSOR_CONNECTIVITY_KEYS:

        value = self_report.get(key)

        if value and value in _CONNECTIVITY_ANSWERS:
            connectivity_failed = 1.0
            break

    # An explicit connectivity failure is also a functional
    # failure, so fold it into the count.
    if connectivity_failed:
        features["diagnostics_failed_count"] = max(
            failed_count,
            1.0,
        )

    features[
        "diagnostic_connectivity_failed"
    ] = connectivity_failed

    return features


def extract_self_report(diagnostics_report):
    """Pull the self-report dict out of a stored report."""

    return _self_report(
        parse_diagnostics_report(diagnostics_report)
    )