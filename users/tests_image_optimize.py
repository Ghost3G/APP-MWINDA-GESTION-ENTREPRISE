from io import BytesIO

from django.test import SimpleTestCase
from PIL import Image

from users.image_optimize import optimize_image_bytes


def _png_bytes(width, height, color=(10, 20, 30), alpha=False):
    buffer = BytesIO()
    mode = 'RGBA' if alpha else 'RGB'
    fill = (*color, 180) if alpha else color
    Image.new(mode, (width, height), fill).save(buffer, format='PNG')
    return buffer.getvalue()


def _jpeg_bytes(width, height, color=(40, 50, 60)):
    buffer = BytesIO()
    Image.new('RGB', (width, height), color).save(buffer, format='JPEG', quality=95)
    return buffer.getvalue()


class ImageOptimizeTests(SimpleTestCase):
    def test_large_jpeg_is_resized_and_lighter(self):
        original = _jpeg_bytes(3200, 2400)
        optimized, name = optimize_image_bytes(original, filename='chantier.JPG', max_side=1600, quality=82)
        self.assertTrue(name.lower().endswith('.jpg'))
        self.assertLess(len(optimized), len(original))
        with Image.open(BytesIO(optimized)) as image:
            self.assertLessEqual(max(image.size), 1600)

    def test_transparent_png_becomes_webp(self):
        original = _png_bytes(800, 600, alpha=True)
        optimized, name = optimize_image_bytes(original, filename='logo.png', max_side=1600)
        self.assertTrue(name.lower().endswith('.webp'))
        self.assertGreater(len(optimized), 0)
        with Image.open(BytesIO(optimized)) as image:
            self.assertEqual(image.format, 'WEBP')

    def test_small_image_stays_reasonable(self):
        original = _jpeg_bytes(120, 80)
        optimized, _name = optimize_image_bytes(original, filename='tiny.jpg', max_side=1600)
        self.assertGreater(len(optimized), 0)
        self.assertLessEqual(len(optimized), len(original) * 2)
