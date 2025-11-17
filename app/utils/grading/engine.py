import traceback
import re
import unicodedata
from typing import Dict, Any, List
from .logger import get_logger
from .textbook import extract_keywords
from .semantic import similarity_score
from .quality import quality_score
from .rubric import validate_rubric, apply_rubric_to_answer
from .config import Config


logger = get_logger(__name__)
cfg = Config()


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\(cid:\d+\)", "", text)
    text = re.sub(r"-\s*\n\s*", "", text)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_schema(schema_text: str, max_marks: List[int] = None):
    blocks = re.split(r"\bQ(\d+)\s*[:.)]", schema_text)
    model_answers = {}
    rubric = {"questions": []}

    for i in range(1, len(blocks), 2):
        qid = int(blocks[i])
        content = blocks[i + 1].strip()

        match = re.search(r"[Aa]nswer\s*:\s*(.*)", content, flags=re.DOTALL)
        model_answer = clean_text(match.group(1).strip()) if match else ""
        model_answers[qid] = model_answer

        if max_marks and len(max_marks) >= qid:
            mark = max_marks[qid - 1]
        else:
            mark = 5

        rubric["questions"].append({
            "question_id": qid,
            "max_marks": mark,
            "expected_keywords": [],
            "penalties": {},
            "bonus": {},
        })

    return model_answers, rubric


def parse_student_answers(student_text: str) -> Dict[int, str]:
    qa = {}
    blocks = re.split(r"\bQ(\d+)\s*[:.)]", student_text)
    for i in range(1, len(blocks), 2):
        qid = int(blocks[i])
        raw_block = blocks[i + 1].strip()
        match = re.search(r"Answer\s*:\s*(.*)", raw_block, flags=re.DOTALL | re.IGNORECASE)
        if match:
            answer = match.group(1)
        else:
            answer = raw_block
        qa[qid] = clean_text(answer)
    return qa


def evaluate_script(student_answers: Dict[int, str], model_answers: Dict[int, str], rubric: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("========== Starting Script Evaluation ==========")
    try:
        validate_rubric(rubric)
        
        results = []
        total_score = 0.0
        
        for q in rubric.get("questions", []):
            qid = q.get("question_id")
            student_answer = student_answers.get(qid, "")
            model_answer = model_answers.get(qid, "")
            
            sim = similarity_score(model_answer, student_answer)
            qual = quality_score(student_answer, max_score=1.0)
            
            question_keywords = extract_keywords(model_answer)
            q["expected_keywords"] = question_keywords
            rubric_score = apply_rubric_to_answer(student_answer, q)
            
            weights = cfg.get("weights", {"similarity": 0.6, "quality": 0.3, "rubric": 0.1})
            max_marks = float(q.get("max_marks", 0))
            
            rubric_norm = (rubric_score / max_marks) if max_marks > 0 else 0.0
            
            combined_norm = (
                weights["similarity"] * sim +
                weights["quality"] * qual +
                weights["rubric"] * rubric_norm
            )
            
            final_marks = combined_norm * max_marks
            
            feedback = []
            if sim < 0.4:
                feedback.append("Answer differs substantially from expected answer.")
            elif sim < 0.7:
                feedback.append("Answer partially matches expected answer.")
            else:
                feedback.append("Answer closely matches expected answer.")
            
            if qual < 0.5:
                feedback.append("Poor clarity/grammar detected.")
            else:
                feedback.append("Good clarity and coherence.")
            
            results.append({
                "question_id": qid,
                "student_answer": student_answer,
                "similarity_score": round(sim, 4),
                "quality_score": round(qual, 4),
                "rubric_score": round(rubric_score, 4),
                "final_marks": round(final_marks, 4),
                "max_marks": max_marks,
                "feedback": " ".join(feedback)
            })
            total_score += final_marks

        return {"questions": results, "total_score": round(total_score, 4)}

    except Exception:
        logger.exception("FATAL ERROR during evaluate_script()")
        traceback.print_exc()
        raise
