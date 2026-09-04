import cv2
import numpy as np

from ultralytics import YOLO


# Load once when FastAPI starts.
# This prevents loading the model for every photo.
model = YOLO("yolo26n.pt")


PHONE_CLASS_NAME = "cell phone"


def detect_phone(image_bytes: bytes):
    """
    Detect a phone in an inspection image.

    Returns:
        detected:
            Whether a phone was detected.

        confidence:
            Detection confidence.

        bounding_box:
            x1, y1, x2, y2 coordinates.

        coverage_percent:
            Approximate percentage of image
            occupied by the detected phone.

        position:
            Location of phone in the frame.

        integrity_score:
            Basic capture-integrity score.
    """

    array = np.frombuffer(
        image_bytes,
        dtype=np.uint8
    )

    image = cv2.imdecode(
        array,
        cv2.IMREAD_COLOR
    )

    if image is None:
        raise ValueError(
            "Unable to decode image."
        )

    height, width = image.shape[:2]

    results = model.predict(
        source=image,
        conf=0.25,
        imgsz=640,
        verbose=False
    )

    best_detection = None

    for result in results:

        if result.boxes is None:
            continue

        for box in result.boxes:

            class_id = int(
                box.cls[0].item()
            )

            class_name = result.names[
                class_id
            ]

            if class_name != PHONE_CLASS_NAME:
                continue

            confidence = float(
                box.conf[0].item()
            )

            coordinates = (
                box.xyxy[0]
                .cpu()
                .numpy()
            )

            x1, y1, x2, y2 = map(
                int,
                coordinates
            )

            if (
                best_detection is None
                or confidence
                > best_detection["confidence"]
            ):
                best_detection = {
                    "confidence": confidence,
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                }

    if best_detection is None:

        return {
            "detected": False,
            "confidence": 0,
            "bounding_box": None,
            "coverage_percent": 0,
            "position": "not_detected",
            "integrity_score": 0,
            "message": (
                "No phone was detected. "
                "Please capture the phone clearly."
            ),
        }

    x1 = best_detection["x1"]
    y1 = best_detection["y1"]
    x2 = best_detection["x2"]
    y2 = best_detection["y2"]

    box_width = max(
        0,
        x2 - x1
    )

    box_height = max(
        0,
        y2 - y1
    )

    box_area = (
        box_width *
        box_height
    )

    image_area = (
        width *
        height
    )

    coverage_percent = (
        box_area /
        image_area *
        100
    )

    center_x = (
        x1 + x2
    ) / 2

    center_y = (
        y1 + y2
    ) / 2

    horizontal_position = (
        "left"
        if center_x < width * 0.33
        else
        "right"
        if center_x > width * 0.67
        else
        "center"
    )

    vertical_position = (
        "top"
        if center_y < height * 0.33
        else
        "bottom"
        if center_y > height * 0.67
        else
        "center"
    )

    if (
        horizontal_position == "center"
        and vertical_position == "center"
    ):
        position = "center"
    else:
        position = (
            f"{vertical_position}-"
            f"{horizontal_position}"
        )

    confidence_score = (
        best_detection["confidence"] * 100
    )

    integrity_score = confidence_score

    # Phone should occupy a reasonable part
    # of the image.
    if coverage_percent < 8:
        integrity_score -= 25
    elif coverage_percent < 15:
        integrity_score -= 10
    elif coverage_percent > 85:
        integrity_score -= 10

    # Centered captures are preferable.
    if position == "center":
        integrity_score += 10
    else:
        integrity_score -= 5

    integrity_score = max(
        0,
        min(
            100,
            round(integrity_score)
        )
    )

    if integrity_score >= 80:
        integrity_grade = "Good"
    elif integrity_score >= 60:
        integrity_grade = "Acceptable"
    elif integrity_score >= 40:
        integrity_grade = "Poor"
    else:
        integrity_grade = "Reject"

    return {
        "detected": True,
        "confidence": round(
            best_detection["confidence"],
            3
        ),
        "bounding_box": {
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
        },
        "coverage_percent": round(
            coverage_percent,
            2
        ),
        "position": position,
        "integrity_score": integrity_score,
        "integrity_grade": integrity_grade,
        "message": (
            "Phone detected successfully."
        ),
    }