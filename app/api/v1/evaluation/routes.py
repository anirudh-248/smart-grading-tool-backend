from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import tempfile
import shutil
from typing import Optional
import logging
from app.utils.grading.engine import cfg
from app.utils.grading.evaluation import run_evaluation


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/evaluate")
async def evaluate_answer_sheet(
    schema_pdf: UploadFile = File(...),
    answer_sheet_pdf: UploadFile = File(...),
    similarity_weight: Optional[float] = Form(0.6),
    quality_weight: Optional[float] = Form(0.3),
    rubric_weight: Optional[float] = Form(0.1),
):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as schema_temp:
            shutil.copyfileobj(schema_pdf.file, schema_temp)
            schema_path = schema_temp.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as student_temp:
            shutil.copyfileobj(answer_sheet_pdf.file, student_temp)
            student_path = student_temp.name

        cfg["weights"] = {
            "similarity": similarity_weight,
            "quality": quality_weight,
            "rubric": rubric_weight,
        }

        result = run_evaluation(schema_path, student_path)

        return {
            "status": "success",
            "weights": cfg["weights"],
            "result": result,
        }

    except Exception as e:
        logger.exception("Evaluation error")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        schema_pdf.file.close()
        answer_sheet_pdf.file.close()
