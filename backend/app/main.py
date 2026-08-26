from fastapi import FastAPI

app = FastAPI(
    title="ORVYN API",
    description="Backend API for ORVYN Personal Multilingual Agentic AI Assistant",
    version="0.1.0",
)


@app.get("/")
async def root():
    return {
        "message": "ORVYN API is running",
        "version": "0.1.0",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ORVYN Backend",
    }