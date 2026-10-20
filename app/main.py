from fastapi import FastAPI

app = FastAPI(title="ai-hub-demo")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
