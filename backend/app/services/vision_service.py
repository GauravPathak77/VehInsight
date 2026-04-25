import os
import re
from typing import Any

import colorname
from google.cloud import vision

from app.core.config import settings


class VisionAnalysisService:
    def __init__(self) -> None:
        if settings.google_application_credentials:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
        self.client = vision.ImageAnnotatorClient()

    @staticmethod
    def _build_image(content: bytes) -> vision.Image:
        return vision.Image(content=content)

    @staticmethod
    def _assert_no_error(response: Any) -> None:
        if response.error.message:
            raise RuntimeError(
                f"{response.error.message}\n"
                "See: https://cloud.google.com/apis/design/errors"
            )

    @staticmethod
    def _get_color_name(rgb: tuple[int, int, int]) -> str:
        try:
            return colorname.get_color_name(rgb[0], rgb[1], rgb[2])
        except ValueError:
            return f"RGB({rgb[0]}, {rgb[1]}, {rgb[2]})"

    def detect_logo(self, image_bytes: bytes) -> str:
        response = self.client.logo_detection(image=self._build_image(image_bytes))
        self._assert_no_error(response)
        if not response.logo_annotations:
            return "Not Found"
        return response.logo_annotations[0].description

    def detect_plate_number(self, image_bytes: bytes) -> str:
        response = self.client.text_detection(image=self._build_image(image_bytes))
        self._assert_no_error(response)
        if not response.text_annotations:
            return "Not Found"
        full_text = response.text_annotations[0].description
        words = re.split(r"[ \n]+", full_text.strip())
        if not words:
            return "Not Found"
        return "".join(words[:3])

    def detect_colors(self, image_bytes: bytes) -> list[dict[str, Any]]:
        response = self.client.image_properties(image=self._build_image(image_bytes))
        self._assert_no_error(response)

        dominant = response.image_properties_annotation.dominant_colors.colors
        if not dominant:
            return []

        total_fraction = sum(color.pixel_fraction for color in dominant) or 1.0
        colors: list[dict[str, Any]] = []
        for color in dominant:
            rgb = (
                int(color.color.red),
                int(color.color.green),
                int(color.color.blue),
            )
            normalized = float(color.pixel_fraction / total_fraction)
            colors.append(
                {
                    "name": self._get_color_name(rgb),
                    "rgb": rgb,
                    "confidence": round(normalized, 4),
                }
            )

        colors.sort(key=lambda item: item["confidence"], reverse=True)
        return colors[: settings.max_colors]
