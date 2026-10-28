"""Bundle the pinned, local compression-only dependency for Figma's JS runtime."""
from pathlib import Path


def zlib_helper():
    source = (Path(__file__).parent / 'vendor/pako/pako_deflate-1.0.11.min.js').read_text()
    return ('// Pako 1.0.11, MIT AND Zlib; see scripts/vendor/pako/LICENSE.\n'
            'const themeZlib = (() => { const module = {exports:{}}; '
            'const exports = module.exports;\n' + source + '\nreturn module.exports; })();\n')
