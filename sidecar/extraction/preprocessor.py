import numpy as np
from PIL import Image, ImageFilter, ImageOps

try:
    from scipy import ndimage
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


class ImagePreprocessor:
    TARGET_DPI = 300

    def preprocess(self, image: Image.Image, source_dpi: int = 72) -> Image.Image:
        img = image

        # Upscale if below target DPI
        if source_dpi < self.TARGET_DPI:
            scale_factor = self.TARGET_DPI / source_dpi
            new_size = (
                int(img.width * scale_factor),
                int(img.height * scale_factor),
            )
            img = img.resize(new_size, Image.LANCZOS)

        # Convert to grayscale
        img = ImageOps.grayscale(img)

        # Deskew
        img = self._deskew(img)

        # Binarize via mean threshold
        arr = np.array(img)
        threshold = np.mean(arr)
        arr = ((arr > threshold) * 255).astype(np.uint8)
        img = Image.fromarray(arr)

        # Denoise
        img = img.filter(ImageFilter.MedianFilter(size=3))

        # Sharpen
        img = img.filter(ImageFilter.SHARPEN)

        return img

    def _deskew(self, img: Image.Image) -> Image.Image:
        """Deskew using projection profile analysis."""
        if not _HAS_SCIPY:
            return img
        arr = np.array(img)
        best_angle = 0
        best_score = 0
        for angle in np.arange(-5, 5.5, 0.5):
            rotated = ndimage.rotate(arr, angle, reshape=False, order=0)
            projection = np.sum(rotated, axis=1)
            score = np.sum(np.diff(projection) ** 2)
            if score > best_score:
                best_score = score
                best_angle = angle
        if abs(best_angle) > 0.5:
            img = img.rotate(best_angle, resample=Image.BICUBIC, fillcolor=255)
        return img
