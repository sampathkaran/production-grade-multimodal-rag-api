from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client 
from dotenv import load_dotenv
import os 
from src.routes.userRoutes import router as userRoutes
from src.routes.projectRoutes import router as projectRoutes
from src.routes.projectFilesRoutes import router as projectFilesRoutes
from src.routes.chatRoutes import router as chatRoutes

from src.config.logging import configure_logging, get_logger
from src.middleware.logging_middleware import LoggingMiddleware

# configure logging before anything else
configure_logging(log_filename="application.log")
logger = get_logger(__name__)
logger.info("initializing_application", version="1.0.0")

load_dotenv()

# Create FASTAPI app
app = FastAPI(
    title="MultiModal RAG Application",
    description = "Backend API for Multimodal RAG application",
    version = "1.0.0"
)

# add the logging middleware
app.add_middleware(LoggingMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # This is where the frontend is running
    allow_credentials=True,
    allow_methods=["*"], # All methods are allowed
    allow_headers=["*"]
)

logger.info("middleware_configured")


# import the routes here 
# app.include_router(users.router)
# app.include_router(projects.router)
# app.include_router(files.router)
# app.include_router(chats.router)

app.include_router(userRoutes, prefix="/api/user")
app.include_router(projectRoutes, prefix="/api/projects")
app.include_router(projectFilesRoutes, prefix="/api/projects")
app.include_router(chatRoutes, prefix="/api/projects")

logger.info("routes_registered", routes_count=4)

# Health CheckPoints
@app.get("/")
async def root(): # async to non block i/o and free up server to accept new request
    return {"message": "MultiModal RAG Application is running"}

@app.get("/health")
async def health_check():
    """Health Check Endpoint"""
    logger.debug("health_check_called")
    return {
        "status": "healthy",
        "version": "1.0.0"
    }
logger.info("application_ready")

# # test the supabase connect by creating a post API
# @app.get("/posts")
# async def get_all_posts():
#     """Get all blogposts"""
#     try:
#         result = supabase.table("posts").select("*").order("created_at", desc=True).execute()
#         return result.data
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)