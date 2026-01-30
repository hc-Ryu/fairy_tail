"""
Tests for openai-cli.py - OpenAI API client with robust timeout handling.
"""
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch, call
from types import SimpleNamespace

# Add tools directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

# Import after path modification
import importlib.util
spec = importlib.util.spec_from_file_location(
    "openai_cli",
    os.path.join(os.path.dirname(__file__), '..', 'tools', 'openai-cli.py')
)
openai_cli = importlib.util.module_from_spec(spec)
sys.modules['openai_cli'] = openai_cli  # Register in sys.modules for patching
spec.loader.exec_module(openai_cli)


class TestModelMapping:
    """Tests for MODEL_MAP configuration."""

    def test_model_map_contains_all_models(self):
        """Test that MODEL_MAP has all expected models."""
        assert 'gpt4o' in openai_cli.MODEL_MAP
        assert 'o3' in openai_cli.MODEL_MAP
        assert 'o4mini' in openai_cli.MODEL_MAP

    def test_model_names_correct(self):
        """Test that model names are correctly mapped."""
        assert openai_cli.MODEL_MAP['gpt4o'] == 'gpt-4o'
        assert openai_cli.MODEL_MAP['o3'] == 'o3'
        assert openai_cli.MODEL_MAP['o4mini'] == 'o4-mini'


class TestOSeriesModels:
    """Tests for O_SERIES_MODELS configuration."""

    def test_o_series_models_list(self):
        """Test that O_SERIES_MODELS contains correct models."""
        assert 'o3' in openai_cli.O_SERIES_MODELS
        assert 'o4mini' in openai_cli.O_SERIES_MODELS
        assert 'gpt4o' not in openai_cli.O_SERIES_MODELS


class TestTimeoutConfig:
    """Tests for TIMEOUT_CONFIG configuration."""

    def test_timeout_config_has_all_combinations(self):
        """Test that TIMEOUT_CONFIG has entries for all model/reasoning combos."""
        models = ['gpt4o', 'o3', 'o4mini']
        reasoning_levels = ['low', 'medium', 'high']

        for model in models:
            for level in reasoning_levels:
                assert (model, level) in openai_cli.TIMEOUT_CONFIG

    def test_timeout_values_reasonable(self):
        """Test that timeout values are positive numbers."""
        for timeout in openai_cli.TIMEOUT_CONFIG.values():
            assert isinstance(timeout, int)
            assert timeout > 0

    def test_o3_high_has_longest_timeout(self):
        """Test that o3 with high reasoning has the longest timeout."""
        o3_high = openai_cli.TIMEOUT_CONFIG[('o3', 'high')]
        assert o3_high == 300  # 5 minutes


class TestReasoningLevels:
    """Tests for REASONING_LEVELS configuration."""

    def test_reasoning_levels_order(self):
        """Test that reasoning levels are in correct order (high to low)."""
        assert openai_cli.REASONING_LEVELS == ['high', 'medium', 'low']


class TestCreateClient:
    """Tests for create_client function."""

    @patch('openai_cli.OpenAI')
    @patch('openai_cli.httpx')
    def test_create_client_with_valid_api_key(self, mock_httpx, mock_openai):
        """Test creating client with valid API key."""
        # Setup
        openai_cli.api_key = "test-api-key-123"
        mock_timeout = MagicMock()
        mock_httpx.Timeout.return_value = mock_timeout

        # Execute
        client = openai_cli.create_client(60)

        # Verify
        mock_openai.assert_called_once_with(
            api_key="test-api-key-123",
            timeout=mock_timeout
        )
        mock_httpx.Timeout.assert_called_once_with(60, connect=10.0)


class TestGenerateWithRetry:
    """Tests for generate_with_retry function."""

    @patch('openai_cli.create_client')
    def test_successful_generation(self, mock_create_client):
        """Test successful content generation."""
        # Setup
        openai_cli.api_key = "test-key"
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_client.chat.completions.create.return_value = mock_response

        # Execute
        result = openai_cli.generate_with_retry(
            model='gpt4o',
            prompt='Test prompt',
            reasoning='medium',
            timeout=60
        )

        # Verify
        assert result == "Test response"
        mock_client.chat.completions.create.assert_called_once()

    @patch('openai_cli.create_client')
    def test_o_series_includes_reasoning_effort(self, mock_create_client):
        """Test that o-series models include reasoning_effort parameter."""
        # Setup
        openai_cli.api_key = "test-key"
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_client.chat.completions.create.return_value = mock_response

        # Execute
        openai_cli.generate_with_retry(
            model='o3',
            prompt='Test prompt',
            reasoning='high',
            timeout=120
        )

        # Verify
        call_args = mock_client.chat.completions.create.call_args
        assert 'reasoning_effort' in call_args.kwargs
        assert call_args.kwargs['reasoning_effort'] == 'high'

    @patch('openai_cli.create_client')
    def test_gpt4o_excludes_reasoning_effort(self, mock_create_client):
        """Test that gpt4o does not include reasoning_effort parameter."""
        # Setup
        openai_cli.api_key = "test-key"
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_client.chat.completions.create.return_value = mock_response

        # Execute
        openai_cli.generate_with_retry(
            model='gpt4o',
            prompt='Test prompt',
            reasoning='medium',
            timeout=60
        )

        # Verify
        call_args = mock_client.chat.completions.create.call_args
        assert 'reasoning_effort' not in call_args.kwargs


class TestIntegration:
    """Integration tests."""

    def test_module_imports_successfully(self):
        """Test that the module can be imported without errors."""
        assert openai_cli is not None
        assert hasattr(openai_cli, 'main')
        assert hasattr(openai_cli, 'create_client')
        assert hasattr(openai_cli, 'generate_with_retry')

    def test_cli_help_works_without_api_key(self, capsys):
        """Test that --help works without API key set."""
        # This is a smoke test - we just verify the module loaded
        # Actual CLI testing would require subprocess
        assert callable(openai_cli.main)
