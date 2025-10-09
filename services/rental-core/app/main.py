from fastapi import FastAPI

app = FastAPI(title="rental-core")


@app.get("/health")
def health():
    return {"status": "ok"}
