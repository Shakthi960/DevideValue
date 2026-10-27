"""Valuation service: the DEVICE VALUE pipeline.

=================================================================
PUBLIC SURFACE
=================================================================

One prediction function:

    from app.services.valuation import (
        predict_device_value_for_device
    )

    result = predict_device_value_for_device(
        brand="samsung",
        model="galaxy s24",
        storage="8GB + 256GB",
        answers={...},
        photo_analysis={...},
        working="yes",
        diagnostics_score=94,
        diagnostics_report={...},
    )

    result["device_value"]   # -> 6842

Feature construction is available separately for callers that
need the vector without a prediction:

    condition_features_from_answers(answers)
    diagnostic_features(working, score, report)
    collect_photo_features(analysis)

There is no resale price and no exchange price. There is no
condition multiplier. The forest sees condition directly.

Compatibility names re-exported below (`normalize_text`,
`find_device`, `parse_storage`, `calculate_valuation`, ...)
exist so callers outside the valuation layer keep working after
the restructure. New code should import from the specific
modules listed above.
"""

from app.services.valuation.condition_features import (
    calculate_condition_score,
    condition_features_from_answers,
    get_condition_grade,
)
from app.services.valuation.diagnostic_features import (
    diagnostic_features,
    extract_self_report,
)
from app.services.valuation.photo_features import (
    collect_photo_features,
    severity_to_code,
)
from app.services.valuation.pipeline import (
    build_feature_row,
    calculate_device_value,
    calculate_valuation,
    predict_device_value_for_device,
)
from app.services.valuation.registry import (
    PHONE_DATA,
    PRICE_MODEL,
    build_spec_features,
    find_device,
    find_spec_row,
    normalize_brand,
    normalize_model,
    normalize_text,
    parse_ram,
    parse_storage,
    reference_price,
)