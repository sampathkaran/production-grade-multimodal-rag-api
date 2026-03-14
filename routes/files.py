from fastapi import Depends, HTTPException, APIRouter # API router allows to split the API files
from auth import get_current_user
from database import supabase
router = APIRouter(
    tags = ["files"]
)

# Define the API to read the files
@router.get("/api/projects/{project_id}/files")
async def get_files(project_id: str, clerk_id:str = Depends(get_current_user)):
    try :
        # get all the files that belong to this project
        files_result = supabase.table("project_documents").select("*").eq("project_id", project_id).eq("clerk_id",clerk_id).order("created_at", desc=True).execute()
        
        return {
            "message" : "Files retrieved successfully",
            "data": files_result.data or []
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail = f"Failed to get files: {str(e)}")