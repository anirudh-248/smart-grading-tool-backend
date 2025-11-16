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
    max_marks: Optional[str] = Form(None)
):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as schema_temp:
            shutil.copyfileobj(schema_pdf.file, schema_temp)
            schema_path = schema_temp.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as student_temp:
            shutil.copyfileobj(answer_sheet_pdf.file, student_temp)
            student_path = student_temp.name

        if max_marks:
            try:
                max_marks_list = [int(x.strip()) for x in max_marks.split(",")]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="max_marks must be comma-separated integers like: 5,10,8"
                )
        else:
            max_marks_list = None

        cfg["weights"] = {
            "similarity": similarity_weight,
            "quality": quality_weight,
            "rubric": rubric_weight,
        }

        result = run_evaluation(schema_path, student_path, max_marks_list)

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
