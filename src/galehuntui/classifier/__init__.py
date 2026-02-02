"""URL classification, normalization, and deduplication.

This package provides URL processing capabilities for targeted vulnerability testing:
- URLNormalizer: Normalize URLs for consistent representation
- URLDeduper: Deduplicate URLs to eliminate redundant testing
- URLClassifier: Classify URLs by injection potential (XSS, SQLi, etc.)
- ClassificationRule: Define custom classification rules
"""

from galehuntui.classifier.normalizer import URLNormalizer
from galehuntui.classifier.deduper import URLDeduper
from galehuntui.classifier.classifier import URLClassifier, ClassificationRule

__all__ = [
    "URLNormalizer",
    "URLDeduper",
    "URLClassifier",
    "ClassificationRule",
]
