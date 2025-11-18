import os, platform
from pdf2image import convert_from_path
from google.cloud import vision


if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    default_sa = os.path.join(os.path.dirname(__file__), "credentials", "gcloud-service-account.json")
    if os.path.exists(default_sa):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = default_sa


client = vision.ImageAnnotatorClient()


def extract_text_from_image(image_bytes: bytes) -> str:
    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)
    if response.error.message:
        raise Exception(f"Vision API error: {response.error.message}")
    return response.full_text_annotation.text


def process_pdf(pdf_path: str) -> str:
    if platform.system() == "Windows":
        pages = convert_from_path(
            pdf_path,
            poppler_path=r"C:\Users\aniru\Downloads\Release-25.11.0-0\poppler-25.11.0\Library\bin"
        )
    else:
        pages = convert_from_path(pdf_path)

    all_text = ""
    for i, page in enumerate(pages):
        import io
        with io.BytesIO() as buffer:
            page.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()
        text = extract_text_from_image(image_bytes)
        all_text += f"\n--- Page {i+1} ---\n{text}\n"

    return all_text
