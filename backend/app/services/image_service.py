import base64
from typing import Any

import cv2
import numpy as np


def annotate_image(
    image_bytes: bytes, logo_name: str, plate_number: str, colors: list[dict[str, Any]]
) -> str:
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Invalid image input.")

    img_height, img_width, _ = image.shape
    overlay_height = min(140, max(100, img_height // 5))
    cv2.rectangle(image, (10, 0), (img_width - 10, overlay_height), (255, 255, 255), cv2.FILLED)

    cv2.putText(
        image,
        f"Model: {logo_name}",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        image,
        f"Plate: {plate_number}",
        (20, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )

    if colors:
        band_y = 90
        band_height = 35
        band_width = (img_width - 20) // len(colors)
        for index, color in enumerate(colors):
            rgb = color["rgb"]
            start_x = 10 + index * band_width
            end_x = start_x + band_width
            cv2.rectangle(image, (start_x, band_y), (end_x, band_y + band_height), rgb[::-1], -1)

    success, encoded = cv2.imencode(".png", image)
    if not success:
        raise RuntimeError("Failed to encode processed image.")

    return base64.b64encode(encoded.tobytes()).decode("utf-8")
