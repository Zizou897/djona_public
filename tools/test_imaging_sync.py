"""Les trois copies de imaging.py (public, vendor, admin) doivent rester identiques.
Lancer : python -m unittest discover -s tools -v"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COPIES = [
    ROOT / 'public' / 'apps' / 'core' / 'imaging.py',
    ROOT / 'vendor' / 'core' / 'src' / 'app' / 'imaging.py',
    ROOT / 'admin' / 'core' / 'src' / 'app' / 'imaging.py',
]


class ImagingCopiesTest(unittest.TestCase):
    def test_copies_are_identical(self):
        contents = [p.read_bytes().replace(b'\r\n', b'\n') for p in COPIES]
        for path, content in zip(COPIES, contents):
            self.assertEqual(content, contents[0], f'{path} diffère de {COPIES[0]}')


if __name__ == '__main__':
    unittest.main()
