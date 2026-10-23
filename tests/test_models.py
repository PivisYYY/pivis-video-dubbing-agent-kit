"""Unit tests for :mod:`dubkit.models`.

All downloads are mocked: no test touches the network or the real Hugging
Face cache. The pinned revisions are asserted literally so a typo in
models.json fails loudly. No test claims that model inference works —
weights are never downloaded or executed here.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dubkit import models  # noqa: E402


class LocalEntryNotFoundError(Exception):
    """Mimics huggingface_hub's cache-miss exception (matched by class name)."""


ASR_REPO = "mlx-community/whisper-large-v3-turbo"
ASR_REV = "a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb"
TTS_REPO = "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit"
TTS_REV = "50f45ef0047cde7e84c2ef04326acb8ada2436a7"
CUSTOM_REPO = "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit"
CUSTOM_REV = "049ef77fe8816b536193c0c25f9a214d17921282"


class FakeHub:
    """snapshot_download stand-in that records kwargs and serves fake paths."""

    def __init__(self, behavior):
        self.behavior = behavior
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.behavior(**kwargs)


def make_snapshot(tmp: Path, alias: str, files) -> Path:
    """Create a fake snapshot dir containing the given relative files."""
    snap = tmp / alias
    snap.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        target = snap / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return snap


def asr_files() -> dict:
    return {"config.json": "{}", "weights.safetensors": "fake"}


def tts_files() -> dict:
    return {
        "config.json": "{}",
        "model.safetensors": "fake",
        "model.safetensors.index.json": json.dumps(
            {"metadata": {"total_size": 4}, "weight_map": {"w": "model.safetensors"}}
        ),
        "speech_tokenizer/config.json": "{}",
        "speech_tokenizer/model.safetensors": "fake",
    }


class RegistryTests(unittest.TestCase):
    def test_load_registry_returns_inner_models_dict(self):
        registry = models.load_registry()
        self.assertEqual(set(registry), {"asr", "tts", "custom_tts"})
        for alias, entry in registry.items():
            self.assertTrue(entry["repo_id"])
            self.assertTrue(entry["revision"])

    def test_registry_pins_exact_verified_revisions(self):
        registry = models.load_registry()
        self.assertEqual(registry["asr"]["repo_id"], ASR_REPO)
        self.assertEqual(registry["asr"]["revision"], ASR_REV)
        self.assertEqual(registry["tts"]["repo_id"], TTS_REPO)
        self.assertEqual(registry["tts"]["revision"], TTS_REV)
        self.assertEqual(registry["custom_tts"]["repo_id"], CUSTOM_REPO)
        self.assertEqual(registry["custom_tts"]["revision"], CUSTOM_REV)

    def test_registry_licenses_are_recorded_honestly(self):
        registry = models.load_registry()
        self.assertEqual(registry["asr"]["license"], "unspecified")
        self.assertIn("Whisper", registry["asr"]["license_note"])
        self.assertEqual(registry["tts"]["license"], "apache-2.0")
        self.assertEqual(registry["custom_tts"]["license"], "apache-2.0")
        self.assertIn("reference audio", registry["tts"]["usage_note"])

    def test_load_registry_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.json"
            with mock.patch.object(models, "REGISTRY_PATH", missing):
                with self.assertRaises(models.RegistryError):
                    models.load_registry()

    def test_load_registry_rejects_bad_schema_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "models.json"
            bad.write_text(json.dumps({"schema_version": 2, "models": {}}), encoding="utf-8")
            with mock.patch.object(models, "REGISTRY_PATH", bad):
                with self.assertRaises(models.RegistryError):
                    models.load_registry()

    def test_load_registry_rejects_missing_models_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "models.json"
            bad.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
            with mock.patch.object(models, "REGISTRY_PATH", bad):
                with self.assertRaises(models.RegistryError):
                    models.load_registry()


class ResolveModelTests(unittest.TestCase):
    def test_unknown_alias_is_rejected_with_valid_names(self):
        with self.assertRaises(models.UnknownModelAliasError) as ctx:
            models.resolve_model("speaker_embed")
        self.assertIn("custom_tts", str(ctx.exception))

    def test_offline_hit_asr_returns_path_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            snap = make_snapshot(tmp, "asr", asr_files())
            fake = FakeHub(lambda **kw: str(snap))
            with mock.patch.object(models, "_snapshot_download", fake):
                got = models.resolve_model("asr", cache_dir=tmp / "cache")
            self.assertEqual(got, snap)
            self.assertEqual(len(fake.calls), 1)
            call = fake.calls[0]
            self.assertEqual(call["repo_id"], ASR_REPO)
            self.assertEqual(call["revision"], ASR_REV)
            self.assertTrue(call["local_files_only"])
            self.assertEqual(call["cache_dir"], str(tmp / "cache"))

    def test_offline_miss_does_not_retry_online(self):
        fake = FakeHub(lambda **kw: (_ for _ in ()).throw(LocalEntryNotFoundError("not cached")))
        with mock.patch.object(models, "_snapshot_download", fake):
            with self.assertRaises(models.ModelNotCachedError) as ctx:
                models.resolve_model("custom_tts")
        self.assertIn("--accept-download", str(ctx.exception))
        self.assertEqual(len(fake.calls), 1)  # exactly one offline attempt
        self.assertTrue(fake.calls[0]["local_files_only"])

    def test_download_failure_wraps_original_error(self):
        boom = ConnectionError("network unreachable")
        fake = FakeHub(lambda **kw: (_ for _ in ()).throw(boom))
        with mock.patch.object(models, "_snapshot_download", fake):
            with self.assertRaises(models.ModelDownloadError) as ctx:
                models.resolve_model("asr", accept_download=True)
        self.assertIn(ASR_REPO, str(ctx.exception))
        self.assertIs(ctx.exception.__cause__, boom)

    def test_accept_download_flag_is_forwarded(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = make_snapshot(Path(tmp), "asr", asr_files())
            fake = FakeHub(lambda **kw: str(snap))
            with mock.patch.object(models, "_snapshot_download", fake):
                models.resolve_model("asr", accept_download=True)
            self.assertFalse(fake.calls[0]["local_files_only"])

    def test_asr_snapshot_without_weights_fails_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = make_snapshot(Path(tmp), "asr", {"config.json": "{}"})
            fake = FakeHub(lambda **kw: str(snap))
            with mock.patch.object(models, "_snapshot_download", fake):
                with self.assertRaises(models.ModelIntegrityError) as ctx:
                    models.resolve_model("asr")
        self.assertIn("asr", str(ctx.exception))
        self.assertIn("weights", str(ctx.exception))

    def test_tts_snapshot_requires_speech_tokenizer(self):
        with tempfile.TemporaryDirectory() as tmp:
            partial = {k: v for k, v in tts_files().items() if not k.startswith("speech_tokenizer")}
            snap = make_snapshot(Path(tmp), "tts", partial)
            fake = FakeHub(lambda **kw: str(snap))
            with mock.patch.object(models, "_snapshot_download", fake):
                with self.assertRaises(models.ModelIntegrityError) as ctx:
                    models.resolve_model("tts")
        self.assertIn("speech_tokenizer", str(ctx.exception))

    def test_tts_snapshot_complete_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = make_snapshot(Path(tmp), "tts", tts_files())
            fake = FakeHub(lambda **kw: str(snap))
            with mock.patch.object(models, "_snapshot_download", fake):
                self.assertEqual(models.resolve_model("tts"), snap)

    def test_index_referencing_missing_shard_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = tts_files()
            files["model.safetensors.index.json"] = json.dumps(
                {"metadata": {}, "weight_map": {"w": "model-00002-of-00002.safetensors"}}
            )
            snap = make_snapshot(Path(tmp), "tts", files)
            fake = FakeHub(lambda **kw: str(snap))
            with mock.patch.object(models, "_snapshot_download", fake):
                with self.assertRaises(models.ModelIntegrityError) as ctx:
                    models.resolve_model("tts")
        self.assertIn("model-00002-of-00002.safetensors", str(ctx.exception))

    def test_single_weight_file_needs_no_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = {"config.json": "{}", "speech_tokenizer/config.json": "{}",
                     "speech_tokenizer/weights.npz": "fake", "model.safetensors": "fake"}
            snap = make_snapshot(Path(tmp), "tts", files)
            fake = FakeHub(lambda **kw: str(snap))
            with mock.patch.object(models, "_snapshot_download", fake):
                self.assertEqual(models.resolve_model("tts"), snap)


class ModelStatusTests(unittest.TestCase):
    def test_status_is_read_only_and_never_downloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            asr_snap = make_snapshot(tmp, "asr", asr_files())
            custom_snap = make_snapshot(tmp, "custom_tts", tts_files())

            def behavior(**kwargs):
                self.assertTrue(kwargs["local_files_only"], "status must never download")
                by_repo = {ASR_REPO: str(asr_snap), CUSTOM_REPO: str(custom_snap)}
                if kwargs["repo_id"] not in by_repo:
                    raise LocalEntryNotFoundError("not cached")
                return by_repo[kwargs["repo_id"]]

            fake = FakeHub(behavior)
            with mock.patch.object(models, "_snapshot_download", fake):
                status = models.model_status()

        self.assertEqual(set(status), {"asr", "tts", "custom_tts"})
        self.assertTrue(status["asr"]["available"])
        self.assertEqual(status["asr"]["path"], str(asr_snap))
        self.assertEqual(status["asr"]["repo_id"], ASR_REPO)
        self.assertEqual(status["asr"]["revision"], ASR_REV)
        self.assertFalse(status["tts"]["available"])
        self.assertIsNone(status["tts"]["path"])
        self.assertIn("accept-download", status["tts"]["detail"])
        self.assertTrue(status["custom_tts"]["available"])
        self.assertEqual(status["custom_tts"]["license"], "apache-2.0")
        self.assertEqual(status["custom_tts"]["revision"], CUSTOM_REV)

    def test_status_reports_integrity_failure_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = make_snapshot(Path(tmp), "asr", {"config.json": "{}"})  # no weights
            fake = FakeHub(lambda **kw: str(snap))
            with mock.patch.object(models, "_snapshot_download", fake):
                status = models.model_status()
        self.assertFalse(status["asr"]["available"])
        self.assertIn("integrity", status["asr"]["detail"])

    def test_status_survives_missing_huggingface_hub(self):
        def boom():
            raise AssertionError("should not be reached")

        fake = FakeHub(boom)

        def raise_import(**kwargs):
            raise ImportError("No module named 'huggingface_hub'")

        fake.behavior = raise_import
        with mock.patch.object(models, "_snapshot_download", fake):
            status = models.model_status()
        for alias in ("asr", "tts", "custom_tts"):
            self.assertFalse(status[alias]["available"])
            self.assertTrue(status[alias]["detail"])


if __name__ == "__main__":
    unittest.main()
