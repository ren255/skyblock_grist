from fastapi import FastAPI

app = FastAPI(title="skyblock_flip")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
