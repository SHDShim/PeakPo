from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class DiffState:
    enabled: bool = False
    ref_chi_path: str = ""

    # 2D display
    cmap_2d: str = "RdBu_r"
    positive_side: str = "red_warm"  # red_warm | blue_cool
    auto_range_2d: bool = True
    vmin_2d: float = -1000.0
    vmax_2d: float = 1000.0

    # Loaded references
    ref_x: Optional[np.ndarray] = field(default=None, repr=False)
    ref_y: Optional[np.ndarray] = field(default=None, repr=False)
    ref_cake_int: Optional[np.ndarray] = field(default=None, repr=False)
    ref_cake_tth: Optional[np.ndarray] = field(default=None, repr=False)
    ref_cake_chi: Optional[np.ndarray] = field(default=None, repr=False)

    def clear_reference_data(self):
        self.ref_x = None
        self.ref_y = None
        self.ref_cake_int = None
        self.ref_cake_tth = None
        self.ref_cake_chi = None

    def has_ref_1d(self) -> bool:
        return (self.ref_x is not None) and (self.ref_y is not None) and (self.ref_x.size > 1)

    def has_ref_2d(self) -> bool:
        return (
            (self.ref_cake_int is not None)
            and (self.ref_cake_tth is not None)
            and (self.ref_cake_chi is not None)
            and (self.ref_cake_int.size > 0)
        )

    def to_ui_dict(self):
        return {
            "enabled": bool(self.enabled),
            "ref_chi_path": str(self.ref_chi_path or ""),
            "cmap_2d": str(self.cmap_2d),
            "positive_side": str(self.positive_side),
            "auto_range": bool(self.auto_range_2d),
            "vmin": float(self.vmin_2d),
            "vmax": float(self.vmax_2d),
        }

    def apply_ui_dict(self, data):
        data = data or {}
        self.enabled = bool(data.get("enabled", self.enabled))
        self.ref_chi_path = str(data.get("ref_chi_path", self.ref_chi_path) or "")
        self.cmap_2d = str(data.get("cmap_2d", self.cmap_2d))
        self.positive_side = str(data.get("positive_side", self.positive_side))
        self.auto_range_2d = bool(data.get("auto_range", self.auto_range_2d))
        self.vmin_2d = float(data.get("vmin", self.vmin_2d))
        self.vmax_2d = float(data.get("vmax", self.vmax_2d))
