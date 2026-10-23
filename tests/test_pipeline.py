"""Deterministic unit tests. Mocks here are NOT model inference evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dubkit.alignment import align_phrases, normalized, source_units, timestamp, ass_subtitles
from dubkit.common import QualityError, PipelineError, save, load, digest
from dubkit.llm import endpoint, validate_translations
from dubkit.pipeline import _stage, require_sample_approval, revise_translations
from dubkit.cli import doctor, make_parser


class AlignmentTests(unittest.TestCase):
    def asr(self, words):
        return {'segments': [{'words': words}]}

    def test_exact_audio_word_boundaries_not_character_proportions(self):
        data = self.asr([{'word': '你好', 'start': 0.2, 'end': 0.7}, {'word': '世界', 'start': 1.4, 'end': 1.8}])
        cues = align_phrases([{'en': 'Hello.', 'zh': '你好。'}, {'en': 'World.', 'zh': '世界。'}], data, offset=4, wav_duration=2)
        self.assertEqual([(c['start'], c['end']) for c in cues], [(4.2, 4.7), (5.4, 5.8)])
        self.assertEqual(cues[0]['alignment_method'], 'exact_text_match_to_final_chinese_asr_word_boundaries')

    def test_content_mismatch_rejected(self):
        with self.assertRaises(QualityError):
            align_phrases([{'en': 'Hello', 'zh': '你好'}], self.asr([{'word': '你们', 'start': 0, 'end': 1}]), offset=0, wav_duration=1)

    def test_splitting_asr_word_rejected(self):
        with self.assertRaises(QualityError):
            align_phrases([{'en': 'One', 'zh': '你'}, {'en': 'Two', 'zh': '好'}], self.asr([{'word': '你好', 'start': 0, 'end': 1}]), offset=0, wav_duration=1)

    def test_normalize_only_punctuation_spacing_and_case(self):
        self.assertEqual(normalized(' GPT-5， 你好！'), 'gpt5你好')
        self.assertNotEqual(normalized('GPT-5'), normalized('GPT-4'))

    def test_semantic_sentence_not_segment_split(self):
        data = {'segments': [{'words': [{'word': 'Why', 'start': 0, 'end': 1}]},
                             {'words': [{'word': 'not?', 'start': 2, 'end': 3}]}]}
        units = source_units(data)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]['en'], 'Why not?')

    def test_nan_timestamp_rejected(self):
        with self.assertRaises(QualityError):
            source_units(self.asr([{'word': 'Hello.', 'start': float('nan'), 'end': 1}]))

    def test_ass_escapes_injected_override(self):
        output = ass_subtitles([{'start': 0, 'end': 1, 'zh': '{\\an9}你好', 'en': 'Hello'}], 1280, 720)
        self.assertNotIn('{\\an9}', output)
        self.assertIn('｛＼an9｝', output)

    def test_time_format(self):
        self.assertEqual(timestamp(62.125), '00:01:02,125')
        self.assertEqual(timestamp(62.12, True), '0:01:02.12')


class TranslationTests(unittest.TestCase):
    source = [{'id': 'u0001', 'en': 'Use GPT-5 with 32 tokens.', 'start': 0, 'end': 4}]

    def valid(self):
        return [{'id': 'u0001', 'phrases': [{'en': 'Use GPT-5 with 32 tokens.', 'zh': '使用 GPT-5，配合32个 token。'}]}]

    def test_valid(self):
        self.assertEqual(validate_translations(self.source, self.valid())[0]['id'], 'u0001')

    def test_source_omission_rejected(self):
        translated = self.valid()
        translated[0]['phrases'][0]['en'] = 'Use GPT-5.'
        with self.assertRaises(QualityError):
            validate_translations(self.source, translated)

    def test_number_omission_rejected(self):
        translated = self.valid()
        translated[0]['phrases'][0]['zh'] = '使用 GPT-5。'
        with self.assertRaises(QualityError):
            validate_translations(self.source, translated)

    def test_remote_default_blocked(self):
        with self.assertRaises(PipelineError):
            endpoint('https://example.org/v1')

    def test_url_credentials_blocked(self):
        with self.assertRaises(PipelineError):
            endpoint('https://' + 'user:password' + '@example.org/v1', True)

    def test_local_compatibility_endpoint(self):
        self.assertEqual(endpoint('http://localhost:11434/v1/'), 'http://localhost:11434/v1/chat/completions')

    def test_authorized_remote_must_use_https(self):
        with self.assertRaises(PipelineError):
            endpoint('http://example.org/v1', True)


class ResumeAndApprovalTests(unittest.TestCase):
    def test_identical_stage_reuses_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            state = {'stages': {}}
            count = []
            def execute():
                count.append(1)
                save(job / 'data.json', {'value': 1})
            self.assertTrue(_stage(job, state, 'example', {'key': 1}, ['data.json'], execute))
            self.assertFalse(_stage(job, state, 'example', {'key': 1}, ['data.json'], execute))
            self.assertEqual(len(count), 1)

    def test_changed_cached_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            state = {'stages': {}}
            _stage(job, state, 'example', {}, ['a.json'], lambda: save(job / 'a.json', {'a': 1}))
            save(job / 'a.json', {'a': 2})
            with self.assertRaises(QualityError):
                _stage(job, state, 'example', {}, ['a.json'], lambda: None)

    def test_full_run_requires_explicit_human_approved_sample(self):
        with self.assertRaises(QualityError):
            require_sample_approval(None, 'source', {})

    def test_json_round_trip_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'state.json'
            save(path, {'中文': [1, 2]})
            self.assertEqual(load(path), {'中文': [1, 2]})
            self.assertEqual(len(digest(path)), 64)

    def test_platform_scope_explicit(self):
        result = doctor()
        self.assertIn('automatic_multi_speaker_diarization', result['not_yet_supported'])

    def test_cli_requires_explicit_model_download_permission(self):
        with self.assertRaises(SystemExit):
            make_parser().parse_args(['models', 'fetch'])


if __name__ == '__main__':
    unittest.main()
