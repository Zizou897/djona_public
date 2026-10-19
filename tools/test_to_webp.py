"""Tests de tools/to_webp.py — lancer : python -m unittest discover -s tools -v"""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import to_webp


def make_photo(path, size=(400, 300), mode='RGB', fmt=None):
    """Image bruitée (compressible mais pas triviale) pour obtenir un gain réaliste."""
    import random
    random.seed(1)
    image = Image.new(mode, size)
    pixels = [tuple((x * y + random.randint(0, 40)) % 256 for _ in mode)
              for y in range(size[1]) for x in range(size[0])]
    image.putdata(pixels)
    image.save(path, fmt)
    return path


class ToWebpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def run_tool(self, *args):
        return to_webp.main([str(a) for a in args])

    def test_converts_next_to_original_and_keeps_original(self):
        photo = make_photo(self.dir / 'a.png')
        self.assertEqual(self.run_tool(photo), 0)
        webp = self.dir / 'a.webp'
        self.assertTrue(webp.exists() and photo.exists())
        with Image.open(webp) as image:
            self.assertEqual(image.format, 'WEBP')
            self.assertEqual(image.size, (400, 300))

    def test_directory_recursive_output_dir_keeps_tree(self):
        (self.dir / 'src' / 'sub').mkdir(parents=True)
        make_photo(self.dir / 'src' / 'one.png')
        make_photo(self.dir / 'src' / 'sub' / 'two.png')
        out = self.dir / 'out'
        self.assertEqual(self.run_tool(self.dir / 'src', '-o', out), 0)
        self.assertTrue((out / 'one.webp').exists())
        self.assertFalse((out / 'sub' / 'two.webp').exists())  # pas récursif sans -r
        self.assertEqual(self.run_tool(self.dir / 'src', '-o', out, '-r'), 0)
        self.assertTrue((out / 'sub' / 'two.webp').exists())

    def test_existing_webp_is_not_overwritten_unless_asked(self):
        photo = make_photo(self.dir / 'a.png')
        webp = self.dir / 'a.webp'
        webp.write_bytes(b'existant')
        self.run_tool(photo)
        self.assertEqual(webp.read_bytes(), b'existant')
        self.run_tool(photo, '--overwrite')
        self.assertNotEqual(webp.read_bytes(), b'existant')

    def test_max_width_resizes_and_transparency_is_kept(self):
        logo = self.dir / 'logo.png'
        Image.new('RGBA', (800, 200), (255, 0, 0, 0)).save(logo)
        self.run_tool(logo, '--max-width', 400, '--lossless', '--keep-larger')
        with Image.open(self.dir / 'logo.webp') as image:
            self.assertEqual(image.size, (400, 100))
            self.assertIn('A', image.getbands())

    def test_dry_run_writes_nothing_and_delete_originals(self):
        photo = make_photo(self.dir / 'a.png')
        self.run_tool(photo, '--dry-run', '--delete-originals')
        self.assertTrue(photo.exists())
        self.assertFalse((self.dir / 'a.webp').exists())
        self.run_tool(photo, '--delete-originals')
        self.assertFalse(photo.exists())
        self.assertTrue((self.dir / 'a.webp').exists())

    def test_larger_webp_is_skipped_by_default(self):
        small = make_photo(self.dir / 'small.jpg', fmt='JPEG', size=(300, 300))
        Image.open(small).save(small, 'JPEG', quality=5)  # JPEG déjà très compressé
        self.run_tool(small, '-q', 100)
        self.assertFalse((self.dir / 'small.webp').exists())
        self.run_tool(small, '-q', 100, '--keep-larger')
        self.assertTrue((self.dir / 'small.webp').exists())

    def test_corrupt_file_fails_with_exit_code_1_and_bad_args(self):
        (self.dir / 'broken.jpg').write_bytes(b'pas une image')
        self.assertEqual(self.run_tool(self.dir), 1)
        self.assertEqual(self.run_tool(self.dir, '-q', 0), 2)
        self.assertEqual(self.run_tool(self.dir / 'absent'), 2)

    def test_animated_gif_is_skipped(self):
        gif = self.dir / 'anim.gif'
        frames = [Image.new('RGB', (20, 20), color).convert('P') for color in ('red', 'blue')]
        frames[0].save(gif, save_all=True, append_images=frames[1:], duration=100, loop=0)
        self.run_tool(gif)
        self.assertFalse((self.dir / 'anim.webp').exists())


if __name__ == '__main__':
    unittest.main()
