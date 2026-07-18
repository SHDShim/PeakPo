import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from peakpo.ds_cake import DiffImg
from peakpo.ds_powdiff import PatternPeakPo
from peakpo.ds_section import Section
from peakpo.model.model import PeakPoModel
from peakpo.model.param_session_io import (
    BACKUP_INDEX_FILE,
    FORMAT_FAMILY,
    FORMAT_VERSION,
    JCPDS_FILE,
    MANIFEST_FILE,
    SECTIONS_FILE,
    SESSION_FILE,
    UI_STATE_FILE,
    load_model_from_param,
    restore_to_backup_event,
    save_model_to_param,
)
from peakpo.utils import get_temp_dir, writechi


class ParamSessionPathTests(unittest.TestCase):
    def _write_chi(self, path, offset=0.0):
        x = np.asarray([1.0, 2.0, 3.0], dtype=float)
        y = np.asarray([10.0, 12.0, 14.0], dtype=float) + float(offset)
        writechi(str(path), x, y)

    def test_load_param_without_background_files_initializes_bg_arrays(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_chi = root / "base.chi"
            self._write_chi(base_chi)

            param_dir = Path(get_temp_dir(str(base_chi), branch="-param"))
            manifest = {
                "format_family": FORMAT_FAMILY,
                "format_version": FORMAT_VERSION,
                "files": {
                    "session": SESSION_FILE,
                    "sections": SECTIONS_FILE,
                    "jcpds": JCPDS_FILE,
                    "ui_state": UI_STATE_FILE,
                },
            }
            session_data = {
                "schema": 1,
                "base_pattern": {
                    "fname": base_chi.name,
                    "wavelength": 0.3344,
                    "color": "white",
                    "display": True,
                },
                "waterfall_patterns": [],
                "diff_img": {},
            }
            (param_dir / MANIFEST_FILE).write_text(
                json.dumps(manifest), encoding="utf-8")
            (param_dir / SESSION_FILE).write_text(
                json.dumps(session_data), encoding="utf-8")
            (param_dir / SECTIONS_FILE).write_text(
                json.dumps({"schema": 1, "sections": []}), encoding="utf-8")
            (param_dir / JCPDS_FILE).write_text(
                json.dumps({"schema": 1, "phases": []}), encoding="utf-8")
            (param_dir / UI_STATE_FILE).write_text(
                json.dumps({"schema": 1, "ui_state": {}}), encoding="utf-8")

            restored = PeakPoModel()
            success, meta = load_model_from_param(restored, str(base_chi))

            self.assertTrue(success, msg=str(meta))
            self.assertEqual(restored.base_ptn.params_chbg, [20, 10, 20])
            self.assertTrue(np.array_equal(restored.base_ptn.x_bg, restored.base_ptn.x_raw))
            self.assertTrue(np.array_equal(restored.base_ptn.x_bgsub, restored.base_ptn.x_raw))
            self.assertTrue(np.array_equal(restored.base_ptn.y_bg, np.zeros_like(restored.base_ptn.y_raw)))
            self.assertTrue(np.array_equal(restored.base_ptn.y_bgsub, restored.base_ptn.y_raw))

    def test_load_param_accepts_windows_section_csv_separators(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_chi = root / "base.chi"
            self._write_chi(base_chi)

            param_dir = Path(get_temp_dir(str(base_chi), branch="-param"))
            sections_dir = param_dir / "sections"
            sections_dir.mkdir(exist_ok=True)
            np.savetxt(
                sections_dir / "sec_0000.csv",
                np.asarray([
                    [1.0, 10.0, 0.0],
                    [2.0, 11.0, 0.0],
                    [3.0, 12.0, 0.0],
                ]),
                delimiter=",",
                header="x,y_bgsub,y_bg",
                comments="",
            )

            manifest = {
                "format_family": FORMAT_FAMILY,
                "format_version": FORMAT_VERSION,
                "files": {
                    "session": SESSION_FILE,
                    "sections": SECTIONS_FILE,
                    "jcpds": JCPDS_FILE,
                    "ui_state": UI_STATE_FILE,
                },
            }
            session_data = {
                "schema": 1,
                "base_pattern": {
                    "fname": base_chi.name,
                    "wavelength": 0.3344,
                    "color": "white",
                    "display": True,
                },
                "waterfall_patterns": [],
                "diff_img": {},
                "current_section_index": 0,
            }
            sections_data = {
                "schema": 1,
                "sections": [
                    {
                        "section_csv_file": "sections\\sec_0000.csv",
                        "section_csv_columns": ["x", "y_bgsub", "y_bg"],
                        "timestamp": "win-section",
                    }
                ],
            }
            (param_dir / MANIFEST_FILE).write_text(
                json.dumps(manifest), encoding="utf-8")
            (param_dir / SESSION_FILE).write_text(
                json.dumps(session_data), encoding="utf-8")
            (param_dir / SECTIONS_FILE).write_text(
                json.dumps(sections_data), encoding="utf-8")
            (param_dir / JCPDS_FILE).write_text(
                json.dumps({"schema": 1, "phases": []}), encoding="utf-8")
            (param_dir / UI_STATE_FILE).write_text(
                json.dumps({"schema": 1, "ui_state": {}}), encoding="utf-8")

            restored = PeakPoModel()
            success, meta = load_model_from_param(restored, str(base_chi))

            self.assertTrue(success, msg=str(meta))
            self.assertEqual(meta.get("missing_section_csv_files"), [])
            self.assertEqual(len(restored.section_lst), 1)
            self.assertTrue(np.array_equal(
                restored.section_lst[0].x,
                np.asarray([1.0, 2.0, 3.0]),
            ))

    def test_load_param_accepts_windows_separators_for_session_file_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_chi = root / "base.chi"
            self._write_chi(base_chi)

            calibration_dir = root / "calibration"
            image_dir = root / "images"
            calibration_dir.mkdir()
            image_dir.mkdir()
            poni_file = calibration_dir / "beam.poni"
            image_file = image_dir / "base.tif"
            poni_file.write_text("poni_version: 2\n", encoding="utf-8")
            image_file.write_bytes(b"fake image")

            param_dir = Path(get_temp_dir(str(base_chi), branch="-param"))
            manifest = {
                "format_family": FORMAT_FAMILY,
                "format_version": FORMAT_VERSION,
                "files": {
                    "session": SESSION_FILE,
                    "sections": SECTIONS_FILE,
                    "jcpds": JCPDS_FILE,
                    "ui_state": UI_STATE_FILE,
                },
            }
            session_data = {
                "schema": 1,
                "poni": "calibration\\beam.poni",
                "image_path": "images\\base.tif",
                "base_pattern": {
                    "fname": base_chi.name,
                    "wavelength": 0.3344,
                    "color": "white",
                    "display": True,
                },
                "waterfall_patterns": [],
                "diff_img": {
                    "img_filename": "images\\base.tif",
                },
            }
            (param_dir / MANIFEST_FILE).write_text(
                json.dumps(manifest), encoding="utf-8")
            (param_dir / SESSION_FILE).write_text(
                json.dumps(session_data), encoding="utf-8")
            (param_dir / SECTIONS_FILE).write_text(
                json.dumps({"schema": 1, "sections": []}), encoding="utf-8")
            (param_dir / JCPDS_FILE).write_text(
                json.dumps({"schema": 1, "phases": []}), encoding="utf-8")
            (param_dir / UI_STATE_FILE).write_text(
                json.dumps({"schema": 1, "ui_state": {}}), encoding="utf-8")

            restored = PeakPoModel()
            success, meta = load_model_from_param(restored, str(base_chi))

            self.assertTrue(success, msg=str(meta))
            self.assertEqual(restored.poni, str(poni_file))
            self.assertEqual(restored.raw_image_path, str(image_file))
            self.assertEqual(restored.diff_img.img_filename, str(image_file))

    def test_load_param_accepts_windows_separators_for_section_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_chi = root / "base.chi"
            self._write_chi(base_chi)

            param_dir = Path(get_temp_dir(str(base_chi), branch="-param"))
            sections_dir = param_dir / "sections"
            derived_dir = param_dir / "derived"
            sections_dir.mkdir(exist_ok=True)
            derived_dir.mkdir(exist_ok=True)
            derived_chi = derived_dir / "fit.chi"
            derived_poni = derived_dir / "fit.poni"
            self._write_chi(derived_chi, offset=3.0)
            derived_poni.write_text("poni_version: 2\n", encoding="utf-8")
            np.savetxt(
                sections_dir / "sec_0000.csv",
                np.asarray([
                    [1.0, 10.0, 0.0],
                    [2.0, 11.0, 0.0],
                    [3.0, 12.0, 0.0],
                ]),
                delimiter=",",
                header="x,y_bgsub,y_bg",
                comments="",
            )

            manifest = {
                "format_family": FORMAT_FAMILY,
                "format_version": FORMAT_VERSION,
                "files": {
                    "session": SESSION_FILE,
                    "sections": SECTIONS_FILE,
                    "jcpds": JCPDS_FILE,
                    "ui_state": UI_STATE_FILE,
                },
            }
            session_data = {
                "schema": 1,
                "base_pattern": {
                    "fname": base_chi.name,
                    "wavelength": 0.3344,
                    "color": "white",
                    "display": True,
                },
                "waterfall_patterns": [],
                "diff_img": {},
            }
            sections_data = {
                "schema": 1,
                "sections": [
                    {
                        "section_csv_file": "sections\\sec_0000.csv",
                        "section_csv_columns": ["x", "y_bgsub", "y_bg"],
                        "timestamp": "win-provenance",
                        "source_provenance": {
                            "source_kind": "azimuthal_integration",
                            "derived_chi": "base-param\\derived\\fit.chi",
                            "poni": "base-param\\derived\\fit.poni",
                        },
                    }
                ],
            }
            (param_dir / MANIFEST_FILE).write_text(
                json.dumps(manifest), encoding="utf-8")
            (param_dir / SESSION_FILE).write_text(
                json.dumps(session_data), encoding="utf-8")
            (param_dir / SECTIONS_FILE).write_text(
                json.dumps(sections_data), encoding="utf-8")
            (param_dir / JCPDS_FILE).write_text(
                json.dumps({"schema": 1, "phases": []}), encoding="utf-8")
            (param_dir / UI_STATE_FILE).write_text(
                json.dumps({"schema": 1, "ui_state": {}}), encoding="utf-8")

            restored = PeakPoModel()
            success, meta = load_model_from_param(restored, str(base_chi))

            self.assertTrue(success, msg=str(meta))
            provenance = restored.section_lst[0].source_provenance
            self.assertEqual(provenance["derived_chi"], str(derived_chi))
            self.assertEqual(provenance["poni"], str(derived_poni))

    def test_restore_backup_accepts_windows_snapshot_file_separators(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_chi = root / "base.chi"
            self._write_chi(base_chi)

            param_dir = Path(get_temp_dir(str(base_chi), branch="-param"))
            target_file = param_dir / "sections" / "sec_0000.csv"
            snapshot_file = param_dir / "backups" / "0" / "sections" / "sec_0000.csv"
            target_file.parent.mkdir(exist_ok=True)
            snapshot_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text("old\n", encoding="utf-8")
            snapshot_file.write_text("new\n", encoding="utf-8")
            backup_index = {
                "format_family": FORMAT_FAMILY,
                "events": [
                    {
                        "id": "0",
                        "snapshot_mode": "full",
                        "snapshot_files": ["sections\\sec_0000.csv"],
                    }
                ],
            }
            (param_dir / BACKUP_INDEX_FILE).write_text(
                json.dumps(backup_index), encoding="utf-8")

            self.assertTrue(restore_to_backup_event(str(param_dir), event_index=0))
            self.assertEqual(target_file.read_text(encoding="utf-8"), "new\n")

    def test_param_references_are_saved_relative_to_chi_root_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_chi = root / "base.chi"
            waterfall_chi = root / "waterfall.chi"
            image_file = root / "base.tif"
            poni_file = root / "beam.poni"
            jcpds_dir = root / "jcpds"
            jcpds_dir.mkdir()

            self._write_chi(base_chi)
            self._write_chi(waterfall_chi, offset=5.0)
            image_file.write_bytes(b"fake image")
            poni_file.write_text("poni_version: 2\n", encoding="utf-8")

            model = PeakPoModel()
            model.set_base_ptn(str(base_chi), 0.3344)
            model.base_ptn.color = "white"
            model.base_ptn.display = True
            model.jcpds_path = str(jcpds_dir)
            model.poni = str(poni_file)

            waterfall = PatternPeakPo()
            waterfall.read_file(str(waterfall_chi))
            waterfall.fname = str(waterfall_chi)
            waterfall.wavelength = 0.41
            waterfall.display = True
            waterfall.color = "cyan"
            model.waterfall_ptn = [waterfall]

            diff = DiffImg()
            diff.img_filename = str(image_file)
            diff.mask = np.asarray([[1, 0], [0, 1]], dtype=float)
            diff.tth_cake = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=float)
            diff.chi_cake = np.asarray([[5.0, 6.0], [7.0, 8.0]], dtype=float)
            diff.intensity_cake = np.asarray([[9.0, 10.0], [11.0, 12.0]], dtype=float)
            model.diff_img = diff

            section = Section()
            section.set(
                np.asarray([1.1, 1.2, 1.3], dtype=float),
                np.asarray([20.0, 21.0, 22.0], dtype=float),
                np.asarray([0.5, 0.5, 0.5], dtype=float),
            )
            section.timestamp = "2026-07-17T09:30:00"
            model.section_lst = [section]

            save_result = save_model_to_param(model)
            param_dir = Path(save_result.param_dir)
            param_name = param_dir.name

            derived_chi = param_dir / "derived.chi"
            derived_poni = param_dir / "derived.poni"
            self._write_chi(derived_chi, offset=2.0)
            derived_poni.write_text("poni_version: 2\n", encoding="utf-8")
            section.source_provenance = {
                "source_kind": "azimuthal_integration",
                "source_chi": str(base_chi),
                "derived_chi": str(derived_chi),
                "source_image": str(image_file),
                "poni": str(derived_poni),
            }
            model.current_section = section
            save_result = save_model_to_param(model)
            param_dir = Path(save_result.param_dir)

            with (param_dir / MANIFEST_FILE).open("r", encoding="utf-8") as stream:
                manifest = json.load(stream)
            with (param_dir / SESSION_FILE).open("r", encoding="utf-8") as stream:
                session_data = json.load(stream)
            with (param_dir / SECTIONS_FILE).open("r", encoding="utf-8") as stream:
                sections_data = json.load(stream)
            with (param_dir / BACKUP_INDEX_FILE).open("r", encoding="utf-8") as stream:
                backup_index = json.load(stream)

            def assert_portable_relative(rel_path):
                self.assertIsInstance(rel_path, str)
                self.assertFalse(os.path.isabs(rel_path))
                self.assertNotIn("\\", rel_path)

            def assert_existing_param_reference(rel_path):
                assert_portable_relative(rel_path)
                self.assertTrue(rel_path.startswith(param_name + "/"))
                self.assertTrue(
                    (root / rel_path).exists(),
                    msg=f"Missing PARAM reference target: {rel_path}",
                )

            for rel_path in manifest["files"].values():
                assert_existing_param_reference(rel_path)

            base_pattern = session_data["base_pattern"]
            assert_existing_param_reference(base_pattern["bg_file"])
            assert_existing_param_reference(base_pattern["bgsub_file"])

            waterfall_payload = session_data["waterfall_patterns"][0]
            assert_existing_param_reference(waterfall_payload["fallback_fname"])

            diff_payload = session_data["diff_img"]
            for key in ("mask_file", "cake_tth_file", "cake_azi_file", "cake_int_file"):
                assert_existing_param_reference(diff_payload[key])

            saved_section = sections_data["sections"][0]
            assert_existing_param_reference(saved_section["section_csv_file"])
            self.assertEqual(
                saved_section["source_provenance"]["derived_chi"],
                f"{param_name}/derived.chi",
            )
            self.assertEqual(
                saved_section["source_provenance"]["poni"],
                f"{param_name}/derived.poni",
            )
            assert_existing_param_reference(
                saved_section["source_provenance"]["derived_chi"])
            assert_existing_param_reference(
                saved_section["source_provenance"]["poni"])

            for event in backup_index.get("events", []):
                for key in ("changed_files", "snapshot_files"):
                    for rel_path in event.get(key, []):
                        assert_portable_relative(rel_path)

            waterfall_chi.unlink()

            restored = PeakPoModel()
            success, meta = load_model_from_param(restored, str(base_chi))
            self.assertTrue(success, msg=str(meta))
            self.assertEqual(
                restored.section_lst[0].source_provenance["derived_chi"],
                str(derived_chi),
            )
            self.assertEqual(
                restored.section_lst[0].source_provenance["poni"],
                str(derived_poni),
            )
            self.assertEqual(restored.waterfall_ptn[0]._pkpo_original_fname, str(waterfall_chi))
            self.assertTrue(restored.waterfall_ptn[0]._pkpo_fallback_in_use)
            self.assertTrue(np.array_equal(restored.diff_img.mask, diff.mask))


if __name__ == "__main__":
    unittest.main()
