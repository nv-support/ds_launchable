"""Regression contracts for prompt selection, step gates, and widget locking."""

import contextlib
import importlib
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
os.environ.setdefault("OUTPUT_ROOT", tempfile.mkdtemp(prefix="brev-tests-output-"))
sys.path.insert(0, str(SCRIPTS))
lab = importlib.import_module("ds_agent_lab")


class FakeOutput:
    def __init__(self):
        self.clear_count = 0

    def clear_output(self):
        self.clear_count += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeControl:
    def __init__(self, disabled=False):
        self.disabled = disabled


@contextlib.contextmanager
def successful_status(_label):
    status = SimpleNamespace(ok=False)
    yield status
    status.ok = True


@contextlib.contextmanager
def swallowing_status(_label):
    status = SimpleNamespace(ok=False)
    try:
        yield status
        status.ok = True
    except Exception:
        pass


class RunStepStateTests(unittest.TestCase):
    def setUp(self):
        self.saved_state = dict(lab.state)

    def tearDown(self):
        lab.state.clear()
        lab.state.update(self.saved_state)

    def test_missing_prerequisite_does_not_run_work(self):
        lab.state["generated"] = False
        called = []

        result = lab.run_step(
            FakeOutput(),
            FakeControl(),
            "Run",
            lambda: called.append(True),
            requires="generated",
        )

        self.assertFalse(result)
        self.assertEqual(called, [])

    def test_related_controls_stay_locked_for_the_full_operation(self):
        button = FakeControl()
        prompt = FakeControl()
        editor = FakeControl()

        def work():
            self.assertTrue(button.disabled)
            self.assertTrue(prompt.disabled)
            self.assertTrue(editor.disabled)

        with mock.patch.object(lab, "step_status", successful_status):
            result = lab.run_step(
                FakeOutput(),
                button,
                "Generate",
                work,
                controls=(prompt, editor),
            )

        self.assertTrue(result)
        self.assertFalse(button.disabled)
        self.assertFalse(prompt.disabled)
        self.assertFalse(editor.disabled)

    def test_control_states_are_restored_after_failure(self):
        button = FakeControl(disabled=False)
        prompt = FakeControl(disabled=False)
        already_disabled = FakeControl(disabled=True)

        with mock.patch.object(lab, "step_status", swallowing_status):
            result = lab.run_step(
                FakeOutput(),
                button,
                "Run",
                lambda: (_ for _ in ()).throw(RuntimeError("boom")),
                controls=(prompt, already_disabled),
            )

        self.assertFalse(result)
        self.assertFalse(button.disabled)
        self.assertFalse(prompt.disabled)
        self.assertTrue(already_disabled.disabled)

    def test_success_flag_is_set_only_after_successful_work(self):
        lab.state["generated"] = False
        with mock.patch.object(lab, "step_status", swallowing_status):
            lab.run_step(
                FakeOutput(),
                FakeControl(),
                "Generate",
                lambda: (_ for _ in ()).throw(RuntimeError("boom")),
                success_flag="generated",
            )
        self.assertFalse(lab.state["generated"])


class PromptSelectionStateTests(unittest.TestCase):
    def setUp(self):
        self.saved_state = dict(lab.state)
        self.saved_agent = lab.AGENT
        self.saved_selected = lab.selected
        self.saved_prompt_id = lab.SELECTED_PROMPT_ID
        self.saved_sequence = lab.selected_sequence

    def tearDown(self):
        lab.state.clear()
        lab.state.update(self.saved_state)
        lab.AGENT = self.saved_agent
        lab.selected = self.saved_selected
        lab.SELECTED_PROMPT_ID = self.saved_prompt_id
        lab.selected_sequence = self.saved_sequence

    def test_selecting_prompt_invalidates_previous_generate_success(self):
        lab.state["generated"] = True

        lab.set_selection("claude", "yolov26s_detection")

        self.assertEqual(lab.SELECTED_PROMPT_ID, "yolov26s_detection")
        self.assertFalse(lab.state["generated"])

    def test_agent_only_selection_does_not_invalidate_generated_result(self):
        lab.state["generated"] = True

        lab.set_selection("claude", None)

        self.assertTrue(lab.state["generated"])


if __name__ == "__main__":
    unittest.main()
