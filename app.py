from pathlib import Path
import tempfile
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pii_redactor import redact

app = FastAPI(title="PII Redaction Tool", version="1.0")

HTML = '''
<!doctype html>
<html>
<head><title>PII Redaction Tool</title></head>
<body>
<h2>PII Redaction Tool</h2>
<p>Upload a DOCX. The service returns a redacted DOCX.</p>
<form action="/redact" method="post" enctype="multipart/form-data">
  <input type="file" name="file" accept=".docx" required>
  <button type="submit">Redact</button>
</form>
</body>
</html>
'''

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/redact")
async def redact_endpoint(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".docx"):
        return {"error": "Only .docx files are supported."}
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        input_path = base / "input.docx"
        output_path = base / "redacted.docx"
        input_path.write_bytes(await file.read())
        redact(input_path, output_path)
        return FileResponse(
            output_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="redacted.docx",
        )
