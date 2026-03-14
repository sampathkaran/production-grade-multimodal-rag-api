from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client 
from dotenv import load_dotenv
import os 
from routes import users
from routes import projects
from routes import files
from routes import chats

load_dotenv()

# Create FASTAPI app
app = FastAPI(
    title="MultiModal RAG Application",
    description = "Backend API for Multimodal RAG application",
    version = "1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # This is where the frontend is running
    allow_credentials=True,
    allow_methods=["*"], # All methods are allowed
    allow_headers=["*"]
)

# import the routes here 
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(files.router)
app.include_router(chats.router)

# Health CheckPoints
@app.get("/")
async def root(): # async to non block i/o and free up server to accept new request
    return {"message": "MultiModal RAG Application is running"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0"
    }

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