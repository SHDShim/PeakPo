from dataclasses import dataclass, field
from typing import Optional
import numpy as np

_SCALE_MODE_LABEL_TO_ID = {
    "Symmetric (0 centered)": "asymmetric_centered",
    "Asymmetric (0 centered)": "asymmetric_centered",
    "0 centered": "asymmetric_centered",
    "0 Centered": "asymmetric_centered",
    "Positive only (0 as min)": "free_range",
    "Negative only (0 as max)": "free_range",
    "Cake-like free range": "free_range",
    "Free range": "free_range",
}


@dataclass
class DiffState:
    enabled: bool = False
    ref_chi_path: str = ""

    # 2D display
    cmap_2d: str = "coolwarm"
    positive_side: str = "red_warm"  # red_warm | blue_cool
    scale_mode_2d: str = "asymmetric_centered"
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
            "ref_chi_path": str(self.ref_chi_path or ""),
            "cmap_2d": str(self.cmap_2d),
            "positive_side": str(self.positive_side),
            "scale_mode": str(self.scale_mode_2d),
            "vmin": float(self.vmin_2d),
            "vmax": float(self.vmax_2d),
        }

    def apply_ui_dict(self, data):
        data = data or {}
        # Diff toggle is runtime-only and intentionally not loaded from JSON.
        self.enabled = False
        self.ref_chi_path = str(data.get("ref_chi_path", self.ref_chi_path) or "")
        self.cmap_2d = str(data.get("cmap_2d", self.cmap_2d))
        self.positive_side = str(data.get("positive_side", self.positive_side))
        raw_mode = str(data.get("scale_mode", self.scale_mode_2d))
        self.scale_mode_2d = _SCALE_MODE_LABEL_TO_ID.get(raw_mode, raw_mode)
        self.vmin_2d = float(data.get("vmin", self.vmin_2d))
        self.vmax_2d = float(data.get("vmax", self.vmax_2d))
        # Backward compatibility: old JSON had auto_range flag.
        if "auto_range" in data and "scale_mode" not in data:
            if bool(data.get("auto_range")):
                self.scale_mode_2d = "free_range"
