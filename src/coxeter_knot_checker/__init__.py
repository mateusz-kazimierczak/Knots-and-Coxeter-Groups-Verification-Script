"""Simple exact checks for Coxeter-gallery knots."""

from .core import (
    AffineMap,
    GalleryCheck,
    check_gallery,
    evaluate_word,
    gallery_points,
    parse_word,
)

__all__ = [
    "AffineMap",
    "GalleryCheck",
    "check_gallery",
    "evaluate_word",
    "gallery_points",
    "parse_word",
]

__version__ = "0.1.0"
