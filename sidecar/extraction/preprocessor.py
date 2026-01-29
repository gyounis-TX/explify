import numpy as np
from PIL import Image, ImageFilter, ImageOps


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
