# app/common/enums.py

from enum import Enum


class FoodType(str, Enum):
    veg = "veg"
    non_veg = "non_veg"


class ItemSort(str, Enum):
    high_to_low = "high_to_low"
    low_to_high = "low_to_high"