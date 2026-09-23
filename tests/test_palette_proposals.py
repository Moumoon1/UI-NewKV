import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render_palette_proposals import ROLES, _button_text_color, render_palette_proposals


def proposal():
    return {
        'title': 'Theme proposal',
        'schemes': [{
            'id': 'D-C',
            'targetUiMode': 'dark',
            'hueStrategy': 'complementary',
            'colors': {
                'background': '#160A24',
                'card': '#241238',
                'number': '#C7B6FF',
                'icon': '#C7B6FF',
                'button': '#FFD43B',
                'tab': '#5E3B78',
            },
        }],
    }


def metallic_proposals():
    base = {
        'background': '#DAECF9',
        'card': '#F8FBFE',
        'number': '#356BB0',
        'icon': '#5B95C4',
        'tab': '#C5DCF0',
    }
    return {
        'title': 'Metallic theme proposal',
        'schemes': [
            {
                'id': 'L-M', 'targetUiMode': 'light',
                'buttonVariant': 'metallic-analogous',
                'colors': {**base, 'button': '#7FA8C5'},
            },
            {
                'id': 'L-G', 'targetUiMode': 'light',
                'buttonVariant': 'gold-bright',
                'colors': {**base, 'button': '#FFC165'},
            },
            {
                'id': 'L-D', 'targetUiMode': 'light',
                'buttonVariant': 'clean-deep',
                'colors': {**base, 'button': '#2F4864'},
            },
        ],
    }


class PaletteProposalTests(unittest.TestCase):
    def test_very_vivid_contrast_button_previews_white_text_first(self):
        candidate = proposal()
        candidate['schemes'][0]['hueStrategy'] = 'contrast'
        candidate['schemes'][0]['buttonTextPriority'] = 'vivid-contrast-white'
        candidate['schemes'][0]['colors']['button'] = '#FF00D0'
        with tempfile.TemporaryDirectory() as directory:
            manifest = render_palette_proposals(candidate, Path(directory) / 'proposal.png')
        self.assertEqual(_button_text_color(candidate['schemes'][0]), (255, 255, 255))
        self.assertEqual(manifest['buttonTextColors'], {'D-C': '#FFFFFF'})
        self.assertEqual(manifest['buttonTextPriorities'], {'D-C': 'vivid-contrast-white'})

    def test_other_button_text_depends_on_contextual_scheme(self):
        candidate = proposal()['schemes'][0]
        candidate['hueStrategy'] = 'analogous'
        candidate['buttonTextPriority'] = 'contextual'
        candidate['colors']['button'] = '#C3E7F9'
        self.assertEqual(_button_text_color(candidate), (30, 20, 34))
        candidate['colors']['button'] = '#3A1A6F'
        self.assertEqual(_button_text_color(candidate), (255, 250, 255))

    def test_vivid_white_priority_only_applies_to_contrast(self):
        candidate = proposal()
        candidate['schemes'][0]['hueStrategy'] = 'analogous'
        candidate['schemes'][0]['buttonTextPriority'] = 'vivid-contrast-white'
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'vivid contrast'):
                render_palette_proposals(candidate, Path(directory) / 'proposal.png')

    def test_explicit_button_text_requires_contextual_evidence(self):
        candidate = proposal()
        candidate['schemes'][0]['buttonTextColor'] = '#301526'
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'buttonTextEvidence'):
                render_palette_proposals(candidate, Path(directory) / 'proposal.png')
            candidate['schemes'][0]['buttonTextEvidence'] = 'Real 1:1 trial: dark text suits the actual button material and host.'
            manifest = render_palette_proposals(candidate, Path(directory) / 'proposal.png')
        self.assertEqual(manifest['buttonTextColors'], {'D-C': '#301526'})
        self.assertEqual(manifest['buttonTextPriorities'], {'D-C': 'contextual'})

    def test_gold_bright_preview_uses_brown_text_exception(self):
        scheme = metallic_proposals()['schemes'][1]
        self.assertEqual(_button_text_color(scheme), (82, 48, 27))

    def test_public_preview_has_six_anchor_roles(self):
        self.assertEqual(ROLES, ('background', 'card', 'number', 'icon', 'button', 'tab'))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proposal.png'
            manifest = render_palette_proposals(proposal(), output)
            self.assertTrue(output.exists())
            self.assertEqual(manifest['schemeIds'], ['D-C'])
            self.assertEqual(json.loads(output.with_suffix('.png.json').read_text())['pixels'],
                             manifest['pixels'])

    def test_legacy_or_split_button_roles_are_rejected(self):
        bad = proposal()
        bad['schemes'][0]['colors']['smallButton'] = '#FFD43B'
        bad['schemes'][0]['colors']['cta'] = '#FF8A1F'
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                render_palette_proposals(bad, Path(directory) / 'proposal.png')

    def test_missing_icon_anchor_is_rejected(self):
        bad = proposal()
        del bad['schemes'][0]['colors']['icon']
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                render_palette_proposals(bad, Path(directory) / 'proposal.png')

    def test_dark_number_icon_must_match_exactly(self):
        bad = proposal()
        bad['schemes'][0]['colors']['number'] = '#FF7A20'
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'number and icon anchors'):
                render_palette_proposals(bad, Path(directory) / 'proposal.png')

    def test_metallic_matrix_supports_three_button_variants(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'metallic.png'
            manifest = render_palette_proposals(metallic_proposals(), output)
            self.assertTrue(output.exists())
            self.assertEqual(manifest['schemeIds'], ['L-M', 'L-G', 'L-D'])

    def test_strategy_fields_are_mutually_exclusive(self):
        bad = metallic_proposals()
        bad['schemes'][0]['hueStrategy'] = 'analogous'
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                render_palette_proposals(bad, Path(directory) / 'proposal.png')


if __name__ == '__main__':
    unittest.main()
