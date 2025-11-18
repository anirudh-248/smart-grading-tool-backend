import os
from pdf2image import convert_from_path
from google.cloud import vision


if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    default_sa = os.path.join(os.path.dirname(__file__), "credentials", "gcloud-service-account.json")
    if os.path.exists(default_sa):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = default_sa

try:
    client = vision.ImageAnnotatorClient()
except Exception as e:
    raise RuntimeError(
        "Failed to create Google Vision client. Set `GOOGLE_APPLICATION_CREDENTIALS` "
        "to a valid service account JSON."
    ) from e


def extract_text_from_image(image_path: str) -> str:
    """Extract text from an image using Google Vision API."""
    with open(image_path, "rb") as image_file:
        content = image_file.read()

    image = vision.Image(content=content)
    response = client.document_text_detection(image=image)

    if response.error.message:
        raise Exception(f"Vision API error: {response.error.message}")

    return response.full_text_annotation.text


def process_pdf(pdf_path: str) -> str:
    """Convert a PDF into images and extract text from each page."""
    pages = convert_from_path(
        pdf_path,
        poppler_path=r"C:\Users\aniru\Downloads\Release-25.11.0-0\poppler-25.11.0\Library\bin"
    )

    all_text = ""
    for i, page in enumerate(pages):
        image_path = f"temp_page_{i}.png"
        page.save(image_path, "PNG")

        text = extract_text_from_image(image_path)
        all_text += f"\n--- Page {i+1} ---\n{text}\n"

        os.remove(image_path)

    return all_text
