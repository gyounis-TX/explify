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

        # Binarize via Otsu's method (preserves faint text better than mean)
        arr = np.array(img)
        threshold = self._otsu_threshold(arr)
        arr = ((arr > threshold) * 255).astype(np.uint8)
        img = Image.fromarray(arr)

        # Denoise
        img = img.filter(ImageFilter.MedianFilter(size=3))

        # Sharpen
        img = img.filter(ImageFilter.SHARPEN)

        return img

    @staticmethod
    def _otsu_threshold(arr: np.ndarray) -> float:
        """Compute Otsu's optimal binarization threshold.

        Finds the threshold that minimises intra-class variance between
        foreground and background pixel intensities.  Falls back to the
        image mean if the histogram is degenerate.
        """
        hist, _ = np.histogram(arr.ravel(), bins=256, range=(0, 256))
        total = arr.size
        if total == 0:
            return 128.0

        sum_total = np.dot(np.arange(256), hist)
        sum_bg = 0.0
        weight_bg = 0
        best_thresh = 0.0
        best_var = 0.0

        for t in range(256):
            weight_bg += hist[t]
            if weight_bg == 0:
                continue
            weight_fg = total - weight_bg
            if weight_fg == 0:
                break

            sum_bg += t * hist[t]
            mean_bg = sum_bg / weight_bg
            mean_fg = (sum_total - sum_bg) / weight_fg

            var_between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
            if var_between > best_var:
                best_var = var_between
                best_thresh = t

        return float(best_thresh) if best_var > 0 else float(np.mean(arr))

    def _deskew(self, img: Image.Image) -> Image.Image:
        """Deskew using projection profile analysis.

        Searches ±15° to handle severely rotated faxed documents.
        Uses a two-pass approach: coarse sweep then fine refinement.
        """
        if not _HAS_SCIPY:
            return img

        arr = np.array(img)

        # Coarse pass: ±15° in 1° steps
        best_angle = 0.0
        best_score = 0.0
        for angle in np.arange(-15, 16, 1.0):
            rotated = ndimage.rotate(arr, angle, reshape=False, order=0)
            projection = np.sum(rotated, axis=1)
            score = np.sum(np.diff(projection) ** 2)
            if score > best_score:
                best_score = score
                best_angle = angle

        # Fine pass: refine within ±1° of best at 0.25° steps
        fine_best = best_angle
        for angle in np.arange(best_angle - 1.0, best_angle + 1.25, 0.25):
            rotated = ndimage.rotate(arr, angle, reshape=False, order=0)
            projection = np.sum(rotated, axis=1)
            score = np.sum(np.diff(projection) ** 2)
            if score > best_score:
                best_score = score
                fine_best = angle

        if abs(fine_best) > 0.25:
            img = img.rotate(fine_best, resample=Image.BICUBIC, fillcolor=255)
        return img
