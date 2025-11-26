from .typing import *
from .externals import *


__all__ =[
    "render_pdf_to_image_bytes",
]


def render_pdf_to_image_bytes(
    pdf_path: str,
    dpi: float = 300.0,
)-> List[bytes]:
    
    pdf_document = fitz.open(pdf_path)
    images_data: List[bytes] = []
    
    PDF_default_DPI = 72.0
    zoom_factor = dpi / PDF_default_DPI
    matrix = fitz.Matrix(zoom_factor, zoom_factor)

    for page in pdf_document:
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        image_bytes = pixmap.tobytes("png")
        images_data.append(image_bytes)

    pdf_document.close()
    
    return images_data