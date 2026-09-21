import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render_palette_proposals import ROLES, render_palette_proposals


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
