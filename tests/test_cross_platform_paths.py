import os
import tempfile
import unittest
from pathlib import Path

from peakpo.utils import (
    basename_any,
    breakdown_filename,
    change_file_path,
    dirname_any,
    make_filename,
    native_relative_path,
    resolve_stored_path,
    samefilename,
)
from peakpo.control.xrdiohelpers import parse_dioptas_map_filename


class CrossPlatformPathTests(unittest.TestCase):
    def test_windows_style_path_parts_are_understood_on_posix(self):
        path = r"C:\data\run1\sample_001.chi"

        self.assertEqual(basename_any(path), "sample_001.chi")
        self.assertEqual(dirname_any(path), r"C:\data\run1")
        self.assertEqual(
            breakdown_filename(path),
            (r"C:\data\run1", "sample_001", ".chi"),
        )

    def test_filename_helpers_use_windows_basename_when_needed(self):
        source = r"C:\data\run1\sample_001.chi"

        self.assertEqual(
            change_file_path(source, "/tmp/new"),
            os.path.join("/tmp/new", "sample_001.chi"),
        )
        self.assertEqual(
            make_filename(source, "poni"),
            os.path.join(r"C:\data\run1", "sample_001.poni"),
        )
        self.assertTrue(samefilename(source, "/Volumes/data/sample_001.tif"))

    def test_resolve_stored_path_accepts_windows_relative_separators(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "param" / "sections" / "sec_0000.csv"
            target.parent.mkdir(parents=True)
            target.write_text("x,y\n", encoding="utf-8")

            self.assertEqual(
                native_relative_path(r"param\sections\sec_0000.csv"),
                os.path.join("param", "sections", "sec_0000.csv"),
            )
            self.assertEqual(
                resolve_stored_path(
                    r"param\sections\sec_0000.csv",
                    str(root),
                ),
                str(target),
            )

    def test_resolve_stored_path_recovers_windows_absolute_by_basename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "copied" / "sample_001.chi"
            target.parent.mkdir()
            target.write_text("chi\n", encoding="utf-8")

            self.assertEqual(
                resolve_stored_path(
                    r"C:\beamtime\old\sample_001.chi",
                    str(root),
                    search_roots=(str(root),),
                ),
                str(target),
            )

    def test_dioptas_map_parser_accepts_windows_paths(self):
        parsed = parse_dioptas_map_filename(
            r"C:\beamtime\cell32_initialmap_S1_map_1_002_9999.chi")

        self.assertEqual(parsed, {"row_index": 1, "snapshot_index": 2})


if __name__ == "__main__":
    unittest.main()
