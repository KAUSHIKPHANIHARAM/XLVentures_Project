"""
data/__init__.py

Public API for the data module.

Usage:
    from data import bootstrap_data_layer
    from data import DataSeeder
"""

from data.bootstrap import bootstrap_data_layer
from data.seeder import DataSeeder

__all__ = [
    "bootstrap_data_layer",
    "DataSeeder",
]
