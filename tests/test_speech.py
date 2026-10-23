"""Speech wrapper unit tests; mocked outputs are not inference evidence."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
import numpy as np
import soundfile as sf
from dubkit import speech
from dubkit.common import PipelineError, QualityError


class SpeechWrapperTests(unittest.TestCase):
    def setUp(self):
        speech._LOADED_TTS_MODELS.clear()

    def test_empty_text_rejected(self):
        with self.assertRaises(PipelineError):
            speech.synthesize('', 'unused.wav', 'model')

    def test_base_requires_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PipelineError):
                speech.synthesize('你好', Path(tmp) / 'out.wav', 'model', mode='clone')

    def test_reference_text_path_not_content_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / 'ref.wav'
            sf.write(ref, np.zeros(160), 16000)
            text = Path(tmp) / 'ref.txt'
            text.write_text('你好')
            with self.assertRaises(PipelineError):
                speech.synthesize('你好', Path(tmp) / 'out.wav', 'model', mode='clone', ref_audio=ref, ref_text=str(text))

    def test_custom_rejects_private_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PipelineError):
                speech.synthesize('你好', Path(tmp) / 'out.wav', 'model', ref_audio='ref.wav', ref_text='你好')

    def test_asr_never_receives_expected_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            sf.write(path, np.zeros(160), 16000)
            response = {'text': '你好', 'segments': [{'words': [{'word': '你好', 'start': np.float32(0.1), 'end': np.float32(0.5)}]}]}
            with patch.object(speech.mlx_whisper, 'transcribe', return_value=response) as call:
                result = speech.transcribe(path, 'model', language='zh')
            kwargs = call.call_args.kwargs
            self.assertNotIn('initial_prompt', kwargs)
            self.assertNotIn('prompt', kwargs)
            self.assertFalse(kwargs['condition_on_previous_text'])
            self.assertEqual(json.loads(json.dumps(result))['text'], '你好')

    def test_no_words_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            path.write_bytes(b'unit test placeholder')
            with patch.object(speech.mlx_whisper, 'transcribe', return_value={'segments': []}):
                with self.assertRaises(QualityError):
                    speech.transcribe(path, 'model')

    def test_custom_passes_real_voice_argument_and_converts_pcm(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'out.wav'
            captured = {}
            def generate(**kwargs):
                captured.update(kwargs)
                sf.write(Path(kwargs['output_path']) / 'audio_000.wav', np.ones(2400, dtype=np.float32) * 0.1, 24000, subtype='FLOAT')
            with patch.object(speech, 'load_model', return_value=object()), patch.object(speech, 'generate_audio', side_effect=generate):
                result = speech.synthesize('你好', output, 'model', speaker='Ryan')
            self.assertEqual(captured['voice'], 'Ryan')
            self.assertIsNone(captured['stt_model'])
            self.assertIsNone(captured['ref_audio'])
            self.assertAlmostEqual(result['duration_s'], 0.1)
            self.assertEqual(result['sample_rate_hz'], 24000)
            self.assertEqual(sf.info(output).subtype, 'PCM_16')

    def test_zero_or_multiple_outputs_rejected(self):
        for count in (0, 2):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as tmp:
                def generate(**kwargs):
                    for index in range(count):
                        sf.write(Path(kwargs['output_path']) / f'audio_{index}.wav', np.zeros(240), 24000)
                with patch.object(speech, 'load_model', return_value=object()), patch.object(speech, 'generate_audio', side_effect=generate):
                    with self.assertRaises(PipelineError):
                        speech.synthesize('你好', Path(tmp) / 'out.wav', 'model')


if __name__ == '__main__':
    unittest.main()
