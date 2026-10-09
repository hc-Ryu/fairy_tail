"""
Tests for synod-run.py - round runner (no API calls).
"""

import importlib.util
import json
import os

spec = importlib.util.spec_from_file_location(
    "synod_run", os.path.join(os.path.dirname(__file__), "..", "tools", "synod-run.py")
)
synod_run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(synod_run)

GEMINI_MODELS = {"flash", "flash-lite", "pro"}
OPENAI_MODELS = {"luna", "sol"}


class TestModeConfig:
    def test_modes_use_valid_models(self):
        for cfg in synod_run.MODES.values():
            assert cfg["gemini"][0] in GEMINI_MODELS
            assert cfg["openai"][0] in OPENAI_MODELS
            assert cfg["gemini"][1] in synod_run.TIMEOUTS
            assert cfg["openai"][1] in synod_run.TIMEOUTS

    def test_every_mode_has_focus(self):
        assert set(synod_run.MODES) == set(synod_run.FOCUS)


class TestPrompt:
    meta = {"mode": "review"}

    def test_solver_prompt_has_problem_and_sid(self):
        prompt = synod_run.build_prompt("solver", "gemini", self.meta, "PROBLEM_X", "")
        assert "ARCHITECT" in prompt
        assert "PROBLEM_X" in prompt
        assert "<confidence" in prompt and "<semantic_focus>" in prompt

    def test_context_included_in_later_rounds(self):
        prompt = synod_run.build_prompt("critic", "openai", self.meta, "P", "CTX_Y")
        assert "LOGIC CHECKER" in prompt
        assert "CTX_Y" in prompt


class TestStripSid:
    def test_removes_xml_blocks(self):
        text = 'Answer.\n<confidence score="90"><can_exit>true</can_exit></confidence>\n' \
               "<semantic_focus>\n1. a\n</semantic_focus>"
        assert synod_run.strip_sid(text) == "Answer."


class TestSession:
    def test_start_round_finish(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(synod_run, "SESSIONS_DIR", tmp_path / ".omc" / "synod")

        def fake_call(provider, model, level, prompt):
            return {"ok": True, "model": model, "level": level, "elapsed": 0.1, "error": None,
                    "text": f'{provider} answer\n<confidence score="95"><can_exit>true</can_exit>'
                            "</confidence>\n<semantic_focus>\n1. x\n</semantic_focus>"}

        monkeypatch.setattr(synod_run, "call_with_fallback", fake_call)
        (tmp_path / "p.md").write_text("problem", encoding="utf-8")
        (tmp_path / "c.md").write_text("claude answer", encoding="utf-8")

        args = type("A", (), {"mode": "general", "problem_file": "p.md", "claude_file": "c.md",
                              "gemini_model": None, "gemini_thinking": None, "openai_model": None,
                              "openai_reasoning": None, "max_chars": 100})
        synod_run.cmd_start(args)
        session = synod_run.resolve_session(None)
        signals = json.loads((session / "round-1-solver" / "signals.json").read_text(encoding="utf-8"))
        assert signals["gemini"]["parsed"]["confidence"]["score"] == 95

        (tmp_path / "s.md").write_text("done", encoding="utf-8")
        finish = type("F", (), {"session": None, "synthesis_file": "s.md", "confidence": 90})
        synod_run.cmd_finish(finish)
        status = json.loads((session / "status.json").read_text(encoding="utf-8"))
        assert status["status"] == "complete"
        assert status["completed_rounds"] == ["solver"]
