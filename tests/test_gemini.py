"""
Tests for gemini-3.py - Gemini API client with retry logic.
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
    "gemini_cli",
    os.path.join(os.path.dirname(__file__), '..', 'tools', 'gemini-3.py')
)
gemini_cli = importlib.util.module_from_spec(spec)
sys.modules['gemini_cli'] = gemini_cli  # Register in sys.modules for patching
spec.loader.exec_module(gemini_cli)


class TestModelMapping:
    """Tests for MODEL_MAP configuration."""

    def test_model_map_contains_all_models(self):
        """Test that MODEL_MAP has all expected models."""
        assert 'flash' in gemini_cli.MODEL_MAP
        assert 'pro' in gemini_cli.MODEL_MAP
        assert '2.5-flash' in gemini_cli.MODEL_MAP
        assert '2.5-pro' in gemini_cli.MODEL_MAP

    def test_model_names_correct(self):
        """Test that model names are correctly mapped."""
        assert gemini_cli.MODEL_MAP['flash'] == 'gemini-3-flash-preview'
        assert gemini_cli.MODEL_MAP['pro'] == 'gemini-3-pro-preview'
        assert gemini_cli.MODEL_MAP['2.5-flash'] == 'gemini-2.5-flash'
        assert gemini_cli.MODEL_MAP['2.5-pro'] == 'gemini-2.5-pro'


class TestThinkingMapping:
    """Tests for THINKING_MAP configuration."""

    def test_thinking_map_contains_all_levels(self):
        """Test that THINKING_MAP has all expected levels."""
        assert 'minimal' in gemini_cli.THINKING_MAP
        assert 'low' in gemini_cli.THINKING_MAP
        assert 'medium' in gemini_cli.THINKING_MAP
        assert 'high' in gemini_cli.THINKING_MAP
        assert 'max' in gemini_cli.THINKING_MAP

    def test_thinking_budgets_increasing(self):
        """Test that thinking budgets increase appropriately."""
        assert gemini_cli.THINKING_MAP['minimal'] < gemini_cli.THINKING_MAP['low']
        assert gemini_cli.THINKING_MAP['low'] < gemini_cli.THINKING_MAP['medium']
        assert gemini_cli.THINKING_MAP['medium'] < gemini_cli.THINKING_MAP['high']
        assert gemini_cli.THINKING_MAP['high'] < gemini_cli.THINKING_MAP['max']

    def test_thinking_budget_values(self):
        """Test specific thinking budget values."""
        assert gemini_cli.THINKING_MAP['minimal'] == 50
        assert gemini_cli.THINKING_MAP['low'] == 200
        assert gemini_cli.THINKING_MAP['medium'] == 500
        assert gemini_cli.THINKING_MAP['high'] == 2000
        assert gemini_cli.THINKING_MAP['max'] == 10000


class TestCreateClient:
    """Tests for create_client() function."""

    @patch('gemini_cli.genai.Client')
    def test_create_client_with_api_key(self, mock_client_class, mock_gemini_api_key):
        """Test client creation with valid API key."""
        gemini_cli.create_client(timeout_ms=300000)
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs['api_key'] == mock_gemini_api_key

    @patch('gemini_cli.genai.Client')
    def test_create_client_with_custom_timeout(self, mock_client_class, mock_gemini_api_key):
        """Test client creation with custom timeout."""
        timeout = 600000  # 10 minutes
        gemini_cli.create_client(timeout_ms=timeout)
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs['http_options'].timeout == timeout

    @patch.dict(os.environ, {}, clear=True)
    def test_create_client_missing_api_key(self):
        """Test that missing API key causes exit."""
        with pytest.raises(SystemExit):
            gemini_cli.create_client()


class TestGenerateWithRetry:
    """Tests for generate_with_retry() function."""

    @patch('gemini_cli.genai.Client')
    def test_successful_generation_streaming(self, mock_client_class, mock_gemini_api_key):
        """Test successful generation with streaming."""
        # Mock streaming response
        mock_chunk1 = Mock()
        mock_chunk1.text = "Hello "
        mock_chunk2 = Mock()
        mock_chunk2.text = "world!"

        mock_client = Mock()
        mock_client.models.generate_content_stream.return_value = iter([mock_chunk1, mock_chunk2])
        mock_client_class.return_value = mock_client

        client = gemini_cli.create_client()
        result = gemini_cli.generate_with_retry(
            client=client,
            model='gemini-3-flash-preview',
            prompt='Test prompt',
            thinking_level='medium',
            use_streaming=True
        )

        assert result == "Hello world!"
        mock_client.models.generate_content_stream.assert_called_once()

    @patch('gemini_cli.genai.Client')
    def test_successful_generation_non_streaming(self, mock_client_class, mock_gemini_api_key):
        """Test successful generation without streaming."""
        mock_response = Mock()
        mock_response.text = "Response text"

        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = gemini_cli.create_client()
        result = gemini_cli.generate_with_retry(
            client=client,
            model='gemini-3-flash-preview',
            prompt='Test prompt',
            thinking_level='medium',
            use_streaming=False
        )

        assert result == "Response text"
        mock_client.models.generate_content.assert_called_once()

    @patch('gemini_cli.genai.Client')
    @patch('gemini_cli.time.sleep')
    def test_retry_on_timeout(self, mock_sleep, mock_client_class, mock_gemini_api_key):
        """Test retry logic on timeout error."""
        mock_response = Mock()
        mock_response.text = "Success after retry"

        mock_client = Mock()
        # First call raises timeout, second succeeds
        mock_client.models.generate_content.side_effect = [
            Exception("Request timeout"),
            mock_response
        ]
        mock_client_class.return_value = mock_client

        client = gemini_cli.create_client()
        result = gemini_cli.generate_with_retry(
            client=client,
            model='gemini-3-flash-preview',
            prompt='Test prompt',
            thinking_level='high',
            use_streaming=False,
            max_retries=3,
            adaptive=True
        )

        assert result == "Success after retry"
        assert mock_client.models.generate_content.call_count == 2
        mock_sleep.assert_called()  # Should have slept between retries

    @patch('gemini_cli.genai.Client')
    @patch('gemini_cli.time.sleep')
    def test_adaptive_downgrade_on_timeout(self, mock_sleep, mock_client_class, mock_gemini_api_key):
        """Test thinking level downgrade on timeout."""
        mock_response = Mock()
        mock_response.text = "Success with lower thinking"

        mock_client = Mock()
        # Timeout on first attempt with 'high', succeeds with 'medium'
        mock_client.models.generate_content.side_effect = [
            Exception("timeout exceeded"),
            mock_response
        ]
        mock_client_class.return_value = mock_client

        client = gemini_cli.create_client()
        result = gemini_cli.generate_with_retry(
            client=client,
            model='gemini-3-flash-preview',
            prompt='Test prompt',
            thinking_level='high',
            use_streaming=False,
            max_retries=3,
            adaptive=True
        )

        assert result == "Success with lower thinking"
        # Check that second call used lower thinking budget
        second_call_config = mock_client.models.generate_content.call_args_list[1][1]['config']
        assert second_call_config.thinking_config.thinking_budget < gemini_cli.THINKING_MAP['high']

    @patch('gemini_cli.genai.Client')
    @patch('gemini_cli.time.sleep')
    def test_rate_limit_retry(self, mock_sleep, mock_client_class, mock_gemini_api_key):
        """Test retry with longer backoff on rate limit."""
        mock_response = Mock()
        mock_response.text = "Success after rate limit"

        mock_client = Mock()
        mock_client.models.generate_content.side_effect = [
            Exception("429 rate limit exceeded"),
            mock_response
        ]
        mock_client_class.return_value = mock_client

        client = gemini_cli.create_client()
        result = gemini_cli.generate_with_retry(
            client=client,
            model='gemini-3-flash-preview',
            prompt='Test prompt',
            thinking_level='medium',
            use_streaming=False,
            max_retries=3
        )

        assert result == "Success after rate limit"
        # Should use longer backoff for rate limits
        assert mock_sleep.call_count > 0

    @patch('gemini_cli.genai.Client')
    def test_non_retryable_error(self, mock_client_class, mock_gemini_api_key):
        """Test that non-retryable errors cause immediate exit."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("Invalid API key")
        mock_client_class.return_value = mock_client

        client = gemini_cli.create_client()

        with pytest.raises(SystemExit):
            gemini_cli.generate_with_retry(
                client=client,
                model='gemini-3-flash-preview',
                prompt='Test prompt',
                thinking_level='medium',
                use_streaming=False,
                max_retries=3
            )

    @patch('gemini_cli.genai.Client')
    @patch('gemini_cli.time.sleep')
    def test_max_retries_exceeded(self, mock_sleep, mock_client_class, mock_gemini_api_key):
        """Test that max retries causes exit."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("timeout")
        mock_client_class.return_value = mock_client

        client = gemini_cli.create_client()

        with pytest.raises(SystemExit):
            gemini_cli.generate_with_retry(
                client=client,
                model='gemini-3-flash-preview',
                prompt='Test prompt',
                thinking_level='medium',
                use_streaming=False,
                max_retries=2
            )

        assert mock_client.models.generate_content.call_count == 2


class TestRetryLevels:
    """Tests for RETRY_LEVELS configuration."""

    def test_retry_levels_order(self):
        """Test that retry levels are in descending order."""
        levels = gemini_cli.RETRY_LEVELS
        assert levels == ['high', 'medium', 'low', 'minimal']

    def test_all_retry_levels_in_thinking_map(self):
        """Test that all retry levels exist in THINKING_MAP."""
        for level in gemini_cli.RETRY_LEVELS:
            assert level in gemini_cli.THINKING_MAP
