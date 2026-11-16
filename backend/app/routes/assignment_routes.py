import os
from fastapi import APIRouter, Request, UploadFile, File, Form,HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from app.database import run_query
from app.auth import get_user_from_session

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
UPLOAD_DIR = "app/uploads"

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

ALLOWED_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

@router.get("/assignments", response_class=HTMLResponse)
def assignments(request: Request):
    user = get_user_from_session(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    assignment_rows = run_query("SELECT * FROM assignments ORDER BY id", fetchall=True)
    submissions = run_query(
        "SELECT * FROM submissions WHERE user_id=%s ORDER BY submitted_at DESC",
        (user["id"],),
        fetchall=True,
    )
    return templates.TemplateResponse(
        "assignments.html",
        {"request": request, "user": user, "assignments": assignment_rows, "submissions": submissions},
    )


@router.post("/assignments/upload")
def upload_assignment(
    request: Request,
    assignment_id: int = Form(...),
    file: UploadFile = File(...),
):
    user = get_user_from_session(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

# Check extension
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOCX, and TXT files are allowed."
        )

    # Check MIME type
    if file.content_type not in ALLOWED_MIMES:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type."
        )

    # Read file
    content = file.file.read()

    # Check size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File too large."
        )


    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{user['id']}_{assignment_id}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as out:
        out.write(file.file.read())

    run_query(
        """
        INSERT INTO submissions (assignment_id, user_id, filename, file_path, notes)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (assignment_id, user["id"], file.filename, filename, "Uploaded through portal"),
        commit=True,
    )

    return RedirectResponse("/assignments", status_code=302)


@router.get("/uploads/{filename}")
def get_upload(filename: str): 

    base_dir = os.path.abspath(UPLOAD_DIR)

    path = os.path.abspath(
        os.path.join(base_dir, filename)
    )
    
    if not path.startswith(base_dir):
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )


    return FileResponse(path)
