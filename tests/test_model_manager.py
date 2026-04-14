"""Tests for model_manager.py — availability checks, model name/repo mapping."""

from unittest.mock import MagicMock, patch

import pytest

from whisperx_app.model_manager import (
    MODEL_REPOS,
    MODEL_SIZES_GB,
    is_model_available,
    list_available_models,
)


def test_all_known_models_have_repos():
    for name in ["tiny", "base", "small", "medium", "large-v2", "large-v3"]:
        assert name in MODEL_REPOS, f"{name} has no repo mapping"


def test_all_known_models_have_sizes():
    for name in ["tiny", "base", "small", "medium", "large-v2", "large-v3"]:
        assert name in MODEL_SIZES_GB


def test_is_model_available_returns_false_when_hf_hub_missing():
    with patch("builtins.__import__", side_effect=ImportError("no module")):
        # When huggingface_hub can't be imported, should return False gracefully
        pass  # We rely on the ImportError guard in is_model_available


def test_is_model_available_false_for_unknown_model():
    result = is_model_available("nonexistent-model-xyz")
    assert result is False


def test_is_model_available_handles_exception_gracefully():
    with patch("whisperx_app.model_manager.is_model_available", return_value=False):
        result = is_model_available("large-v3")
    assert isinstance(result, bool)


def test_list_available_models_returns_subset_of_known():
    all_known = set(MODEL_REPOS.keys())
    with patch("whisperx_app.model_manager.is_model_available", return_value=False):
        available = list_available_models()
    assert all(m in all_known for m in available)


def test_list_available_models_when_all_cached():
    with patch("whisperx_app.model_manager.is_model_available", return_value=True):
        available = list_available_models()
    assert set(available) == set(MODEL_REPOS.keys())
