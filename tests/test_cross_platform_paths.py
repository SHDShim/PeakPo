import os
import tempfile
import unittest
from pathlib import Path

from peakpo.utils import (
    basename_any,
    breakdown_filename,
    change_file_path,
    dirname_any,
    get_sorted_filelist,
    make_filename,
    native_relative_path,
    resolve_stored_path,
    samefilename,
)
from peakpo.control.xrdiohelpers import parse_dioptas_map_filename


class CrossPlatformPathTests(unittest.TestCase):
    def test_copied_windows_chi_folder_ignores_appledouble_and_extension_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "sample_0001.CHI"
            second = root / "sample_0002.chi"
            sidecar = root / "._sample_0001.bgsub.chi"
            for path in (first, second, sidecar):
                path.write_text("data", encoding="utf-8")
            os.utime(first, (1, 1))
            os.utime(sidecar, (2, 2))
            os.utime(second, (3, 3))

            expected = [str(first), str(second)]
            self.assertEqual(get_sorted_filelist(directory), expected)
            self.assertEqual(get_sorted_filelist(
                directory, sorted_by_name=False), expected)

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
