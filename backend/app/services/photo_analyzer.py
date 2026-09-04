import cv2
import numpy as np
from app.services.phone_detector import (
    detect_phone
)


def analyze_image(image_bytes: bytes):
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Unable to read image")

    height, width = image.shape[:2]

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    brightness = float(np.mean(gray))

    blur_score = float(
        cv2.Laplacian(gray, cv2.CV_64F).var()
    )

    resolution_score = min(
        100,
        (width * height) / (1920 * 1080) * 100
    )

    quality_score = 100

    if brightness < 45:
        quality_score -= 25
    elif brightness < 70:
        quality_score -= 10

    if brightness > 225:
        quality_score -= 15

    if blur_score < 80:
        quality_score -= 30
    elif blur_score < 180:
        quality_score -= 15

    if resolution_score < 50:
        quality_score -= 20

    quality_score = max(
        0,
        min(100, round(quality_score))
    )

    if quality_score >= 80:
        quality_grade = "Excellent"
    elif quality_score >= 60:
        quality_grade = "Good"
    elif quality_score >= 40:
        quality_grade = "Fair"
    else:
        quality_grade = "Poor"

    phone_detection = detect_phone(
    image_bytes
)

    return {
        "width": width,
        "height": height,
        "brightness": round(
            brightness,
            2
        ),
        "blur_score": round(
            blur_score,
            2
        ),
        "resolution_score": round(
            resolution_score,
            2
        ),
        "quality_score": quality_score,
        "quality_grade": quality_grade,

        "phone_detection": phone_detection,
    }