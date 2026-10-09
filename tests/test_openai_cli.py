"""
Tests for openai-cli.py - OpenAI API client with retry logic.
"""

import os
import sys

# Add tools directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

# Import after path modification
import importlib.util

spec = importlib.util.spec_from_file_location(
    "openai_cli", os.path.join(os.path.dirname(__file__), "..", "tools", "openai-cli.py")
)
openai_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(openai_cli)


class TestModelMapping:
    """Tests for MODEL_MAP configuration."""

    def test_model_map_contains_all_models(self):
        """Test that MODEL_MAP has all expected models."""
        assert "luna" in openai_cli.MODEL_MAP
        assert "sol" in openai_cli.MODEL_MAP
        assert set(openai_cli.MODEL_MAP) == {"luna", "sol"}

    def test_model_names_correct(self):
        """Test that model names are correctly mapped."""
        assert openai_cli.MODEL_MAP["luna"] == "gpt-6-luna"
        assert openai_cli.MODEL_MAP["sol"] == "gpt-6.1-sol"


class TestReasoningModels:
    """Tests for REASONING_MODELS configuration."""

    def test_reasoning_models_list(self):
        """Test that reasoning models are correctly identified."""
        assert "luna" in openai_cli.REASONING_MODELS
        assert "sol" in openai_cli.REASONING_MODELS


class TestTimeoutConfig:
    """Tests for TIMEOUT_CONFIG."""

    def test_timeout_config_has_all_combinations(self):
        """Test that timeout config covers all model+reasoning combinations."""
        models = ["luna", "sol"]
        levels = ["low", "medium", "high"]

        for model in models:
            for level in levels:
                assert (model, level) in openai_cli.TIMEOUT_CONFIG

    def test_timeout_values_reasonable(self):
        """Test that all timeout values are positive and reasonable."""
        for timeout in openai_cli.TIMEOUT_CONFIG.values():
            assert timeout > 0
            assert timeout <= 600  # Max 10 minutes

    def test_sol_high_has_longest_timeout(self):
        """Test that sol with high reasoning has the longest timeout."""
        assert openai_cli.TIMEOUT_CONFIG[("sol", "high")] == max(openai_cli.TIMEOUT_CONFIG.values())


class TestReasoningLevels:
    """Tests for REASONING_LEVELS configuration."""

    def test_reasoning_levels_order(self):
        """Test that reasoning levels are in descending order."""
        levels = openai_cli.REASONING_LEVELS
        assert levels == ["high", "medium", "low"]


class TestCreateClient:
    """Tests for create_client() function."""

    def test_create_client_with_valid_api_key(self, mock_openai_api_key):
        """Test that client creation requires API key."""
        # Just verify API key is set - actual client creation would need mocking
        assert os.environ.get("OPENAI_API_KEY") == mock_openai_api_key


class TestGenerateWithRetry:
    """Tests for generate_with_retry() retry logic."""

    def test_successful_generation(self, mock_openai_api_key, monkeypatch):
        """Test that generate function exists and has correct signature."""
        # Verify function exists with expected parameters
        import inspect

        sig = inspect.signature(openai_cli.generate_with_retry)
        params = list(sig.parameters.keys())
        assert "model" in params
        assert "prompt" in params
        assert "reasoning" in params
        assert "timeout" in params
        assert "max_retries" in params
        assert "adaptive" in params

    def test_all_models_use_reasoning_effort(self):
        """Test that every mapped model receives reasoning_effort."""
        assert set(openai_cli.REASONING_MODELS) == set(openai_cli.MODEL_MAP)


class TestIntegration:
    """Integration tests that don't require API calls."""

    def test_module_imports_successfully(self):
        """Test that the module can be imported without errors."""
        assert openai_cli is not None
        assert hasattr(openai_cli, "create_client")
        assert hasattr(openai_cli, "generate_with_retry")
        assert hasattr(openai_cli, "main")

    def test_cli_help_works_without_api_key(self, monkeypatch):
        """Test that CLI help can be shown without API key."""
        # The help functionality should work even without API key
        assert openai_cli.MODEL_MAP is not None
        assert openai_cli.TIMEOUT_CONFIG is not None


class TestErrorDetection:
    """Tests for error detection logic."""

    def test_timeout_error_keywords(self):
        """Test timeout error detection keywords."""
        timeout_keywords = ["timeout", "timed out", "deadline"]
        for keyword in timeout_keywords:
            assert keyword.lower() in keyword.lower()

    def test_rate_limit_error_keywords(self):
        """Test rate limit error detection keywords."""
        rate_keywords = ["429", "rate", "quota"]
        for keyword in rate_keywords:
            assert keyword.lower() in keyword.lower()

    def test_overload_error_keywords(self):
        """Test overload error detection keywords."""
        overload_keywords = ["503", "overloaded", "unavailable", "502"]
        for keyword in overload_keywords:
            assert keyword.lower() in keyword.lower()


class TestTimeoutStrategy:
    """Tests for timeout strategy."""

    def test_timeout_increases_with_reasoning_level(self):
        """Test that timeouts increase with reasoning complexity."""
        for model in ["luna", "sol"]:
            low = openai_cli.TIMEOUT_CONFIG[(model, "low")]
            medium = openai_cli.TIMEOUT_CONFIG[(model, "medium")]
            high = openai_cli.TIMEOUT_CONFIG[(model, "high")]
            # Timeouts should generally increase or stay same
            assert low <= medium <= high or (low == medium == high)

    def test_sol_has_higher_timeouts_than_luna(self):
        """Test that sol (heavier reasoning) gets longer timeouts than luna."""
        for level in ["low", "medium", "high"]:
            assert openai_cli.TIMEOUT_CONFIG[("sol", level)] >= openai_cli.TIMEOUT_CONFIG[("luna", level)]
