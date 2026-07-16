import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from peakpo.control.jcpdscontroller import JcpdsController


class _TableStub:
    def __init__(self):
        self.cleared = False
        self.selected_rows = []

    def clearContents(self):
        self.cleared = True

    def selectRow(self, row):
        self.selected_rows.append(row)


class JcpdsControllerReorderTests(unittest.TestCase):
    def test_move_up_rebuilds_jcpds_overlay_after_reordering(self):
        controller = object.__new__(JcpdsController)
        controller.model = SimpleNamespace(
            jcpds_lst=[
                SimpleNamespace(name="phase a"),
                SimpleNamespace(name="phase b"),
            ],
        )
        table = _TableStub()
        controller.widget = SimpleNamespace(tableWidget_JCPDS=table)
        controller.jcpdstable_ctrl = SimpleNamespace(update=Mock())
        controller._find_a_jcpds = Mock(return_value=1)
        controller._apply_changes_to_graph = Mock()

        controller.move_up_jcpds()

        self.assertEqual(
            [phase.name for phase in controller.model.jcpds_lst],
            ["phase b", "phase a"],
        )
        self.assertTrue(table.cleared)
        controller.jcpdstable_ctrl.update.assert_called_once_with()
        self.assertEqual(table.selected_rows, [0])
        controller._apply_changes_to_graph.assert_called_once_with()

    def test_move_down_rebuilds_jcpds_overlay_after_reordering(self):
        controller = object.__new__(JcpdsController)
        controller.model = SimpleNamespace(
            jcpds_lst=[
                SimpleNamespace(name="phase a"),
                SimpleNamespace(name="phase b"),
            ],
        )
        table = _TableStub()
        controller.widget = SimpleNamespace(tableWidget_JCPDS=table)
        controller.jcpdstable_ctrl = SimpleNamespace(update=Mock())
        controller._find_a_jcpds = Mock(return_value=0)
        controller._apply_changes_to_graph = Mock()

        controller.move_down_jcpds()

        self.assertEqual(
            [phase.name for phase in controller.model.jcpds_lst],
            ["phase b", "phase a"],
        )
        self.assertTrue(table.cleared)
        controller.jcpdstable_ctrl.update.assert_called_once_with()
        self.assertEqual(table.selected_rows, [1])
        controller._apply_changes_to_graph.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
