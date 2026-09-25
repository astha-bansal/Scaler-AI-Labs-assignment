from pathlib import Path
import tempfile
import shutil

from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse

from pii_redactor import redact


app = FastAPI(title="PII Redaction Tool", version="1.0")


HTML = """
<!doctype html>
<html>
<head>
    <title>PII Redaction Tool</title>
</head>
<body>
    <h2>PII Redaction Tool</h2>
    <p>Upload a DOCX. The service returns a redacted DOCX.</p>

    <form action="/redact" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".docx" required>
        <button type="submit">Redact</button>
    </form>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return HTML


@app.get("/health")
def health():
    return {"status": "ok"}


def cleanup_directory(directory: Path):
    """Delete temporary files after the response has been sent."""
    shutil.rmtree(directory, ignore_errors=True)


@app.post("/redact")
async def redact_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    if not file.filename or not file.filename.lower().endswith(".docx"):
        return {"error": "Only .docx files are supported."}

    temp_dir = Path(tempfile.mkdtemp())

    input_path = temp_dir / "input.docx"
    output_path = temp_dir / "redacted.docx"

    try:
        input_path.write_bytes(await file.read())
        
        inventory_path = Path(__file__).with_name("entity_inventory.json")
        redact(input_path, output_path, inventory_path)
        
        if not output_path.exists():
            raise RuntimeError("Redaction completed but output file was not created.")

        # Delete temporary files only after FileResponse finishes.
        background_tasks.add_task(cleanup_directory, temp_dir)

        return FileResponse(
            path=str(output_path),
            media_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            filename="redacted.docx",
        )

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
