import json
import logging
import pdfplumber
from typing import List
from . import engine
from .ocr import process_pdf

logger = logging.getLogger(__name__)


def extract_pdf_text(pdf_path: str) -> str:
    logger.info(f"Extracting text from {pdf_path} using pdfplumber")
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    logger.info(f"Finished extracting text from {pdf_path}")
    return text.strip()


def run_evaluation(schema_pdf: str, student_pdf: str, max_marks: List[int] = None):
    logger.info(f"Running evaluation for student: {student_pdf}, schema: {schema_pdf}")
    
    schema_text = extract_pdf_text(schema_pdf)
    student_text = process_pdf(student_pdf)
    model_answers, rubric = engine.parse_schema(schema_text, max_marks)
    student_answers = engine.parse_student_answers(student_text)
    
    result = engine.evaluate_script(student_answers, model_answers, rubric)
    
    with open("result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    logger.info("Evaluation complete. Results saved to result.json")
    return result
