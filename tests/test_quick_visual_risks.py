import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from quick_visual_risks import button, icon, seam, inspect_review


class QuickVisualRiskTests(unittest.TestCase):
    def test_hard_cut_fails_and_gradual_seam_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'preview.png'
            im = Image.new('RGB', (6, 20), (240, 210, 255))
            for y in range(10, 20):
                for x in range(6):
                    im.putpixel((x, y), (210, 165, 235))
            im.save(path)
            self.assertEqual(seam(path, 10, [0, 3, 5])['status'], 'fail')
            for y in range(4, 20):
                t = min(1, (y - 4) / 12)
                color = tuple(round(a * (1 - t) + b * t)
                              for a, b in zip((240, 210, 255), (210, 165, 235)))
                for x in range(6):
                    im.putpixel((x, y), color)
            im.save(path)
            self.assertEqual(seam(path, 10, [0, 3, 5])['status'], 'pass')

    def test_white_is_recorded_even_when_it_loses(self):
        report = button('#A8EB35', {'white': '#FFFFFF',
                                    'tinted-white': '#F7FFE8',
                                    'same-family-dark': '#18391C'})
        ratios = {row['name']: row['contrast'] for row in report['candidates']}
        self.assertEqual(report['status'], 'pass')
        self.assertLess(ratios['white'], 1.5)
        self.assertGreater(ratios['same-family-dark'], 8)
        wrong_family = button('#A8EB35', {'white': '#FFFFFF',
                                           'tinted-white': '#F7FFE8',
                                           'same-family-dark': '#050015'})
        self.assertEqual(wrong_family['status'], 'fail')

    def test_top_opaque_gradient_dark_end_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'snapshot.json'
            paint = {'type': 'GRADIENT_LINEAR', 'visible': True,
                     'opacity': 1, 'blendMode': 'NORMAL',
                     'gradientStops': [
                         {'color': {'r': .68, 'g': .26, 'b': 1, 'a': 1}},
                         {'color': {'r': .45, 'g': .19, 'b': .70, 'a': 1}}]}
            path.write_text(json.dumps({'nodes': [
                {'id': '1:2', 'props': {'fills': [paint]}}]}))
            report = icon(path, '1:2', 0, .85)
            self.assertEqual(report['status'], 'fail')
            self.assertEqual(report['dimStopIndices'], [1])

    def test_icon_mode_brightness_gate_cannot_be_lowered(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'snapshot.json'

            def write_blue(value):
                path.write_text(json.dumps({'nodes': [{'id': '1:2', 'props': {
                    'fills': [{'type': 'SOLID', 'visible': True, 'opacity': 1,
                               'blendMode': 'NORMAL',
                               'color': {'r': .3, 'g': .4, 'b': value, 'a': 1}}]}}]}))

            write_blue(.8)
            self.assertEqual(icon(path, '1:2', 0, .4, 'dark')['status'], 'fail')
            write_blue(.81)
            self.assertEqual(icon(path, '1:2', 0, .4, 'dark')['status'], 'pass')
            self.assertEqual(icon(path, '1:2', 0, .4, 'light')['status'], 'fail')
            write_blue(1)
            self.assertEqual(icon(path, '1:2', 0, .4, 'light')['status'], 'pass')

    def test_bound_review_rejects_stale_screenshot_and_accepts_actual_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / 'preview.png'
            Image.new('RGB', (6, 20), (210, 165, 235)).save(screenshot)
            icon_doc = root / 'icon.json'
            icon_doc.write_text(json.dumps({'nodes': [{'id': '1:2', 'props': {
                'fills': [{'type': 'SOLID', 'visible': True, 'opacity': 1,
                           'blendMode': 'NORMAL', 'color': {'r': .7, 'g': .3, 'b': 1}}]}}]}))
            review = {'schemaVersion': 1, 'sourceHash': 'S', 'projectedHash': 'P',
                      'targetUiMode': 'dark',
                      'screenshot': str(screenshot),
                      'screenshotSha256': hashlib.sha256(screenshot.read_bytes()).hexdigest(),
                      'seam': {'seamY': 10, 'columns': [0, 5], 'transitionStartY': 4},
                      'buttons': [{'id': 'primary', 'buttonColor': '#A8EB35',
                                   'candidates': {'white': '#FFFFFF',
                                                  'tinted-white': '#F7FFE8',
                                                  'same-family-dark': '#18391C'},
                                   'chosen': 'same-family-dark',
                                   'visualStatus': 'pass', 'previewImage': str(screenshot)}],
                      'icons': [{'id': 'task', 'snapshot': str(icon_doc),
                                 'nodeId': '1:2', 'topIndex': 0,
                                 'minimumBrightness': .85,
                                 'visualStatus': 'pass', 'previewImage': str(screenshot)}],
                      'overallVisualStatus': 'pass'}
            self.assertEqual(inspect_review(review, 'S', 'P')['status'], 'pass')
            review['screenshotSha256'] = 'stale'
            self.assertEqual(inspect_review(review, 'S', 'P')['status'], 'fail')
            review['screenshotSha256'] = hashlib.sha256(screenshot.read_bytes()).hexdigest()
            del review['targetUiMode']
            self.assertEqual(inspect_review(review, 'S', 'P')['status'], 'fail')


if __name__ == '__main__':
    unittest.main()
