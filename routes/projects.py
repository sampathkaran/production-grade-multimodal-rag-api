from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import supabase
from auth import get_current_user

router = APIRouter(
    tags= ["projects"]
)

class ProjectCreate(BaseModel):
    name: str
    description: str = ""

# define the get API route
@router.get("/api/projects")
async def get_projects(clerk_id: str = Depends(get_current_user)):
    """This API is to list all projects for the given user clerk id"""
    try:
        #read the projects from the supabase
        result = (
            supabase.table("projects")
            .select("*").eq('clerk_id', clerk_id) # filter for clerk id
            .execute()
        )
        
        return {
            "message": "Projects retrieved successfully",
            "data" : result.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get projects: {str(e)}")

# define the create API route for projects
@router.post("/api/projects")
# we will use a pydantic model to validate user input
async def create_projects(project: ProjectCreate, clerk_id: str = Depends(get_current_user)):
     # project is the JSON body frontend will send us
     try:

        # Insert the new project into the database
        project_result = (
            supabase.table("projects")
            .insert({
                "name": project.name, 
                "description":project.description,
                "clerk_id": clerk_id
                }).execute()
                )
        if not project_result.data:
            raise HTTPException(status_code=500, detail="Project creation failed")
        
        # Get the project id
        created_project = project_result.data[0]
        project_id = created_project["id"]

        # create default project settings 
        project_settings_result = (
            supabase.table("project_settings")
            .insert({
            "project_id": project_id,
            "embedding_model": "text-embedding-3-large",
            "rag_strategy": "basic",
            "agent_type": "agentic",
            "chunks_per_search" : 10,
            "final_context_size": 5,
            "similarity_threshold" : 0.3,
            "number_of_queries" : 5, 
            "reranking_enabled": True,
            "reranking_model": "rerank-english-v3.0",
            "vector_weight" : 0.7,  
            "keyword_weight" : 0.3  
            }).execute()
            )
        if not project_settings_result.data:
            # if the project setting creation failed we need to cleanup the project
            supabase.table("projects").delete().eq("id", project_id).execute()
            raise HTTPException(status_code=500, detail="Project settings creation failed")
        
        return {
            "message": "Project created successfully",
            "data": created_project
        }

     except Exception as e:
        raise HTTPException(status_code=500, detail= f"Failed to create project due to error: {str(e)}")

# define the delete project API route
@router.delete("/api/projects/{project_id}")
async def delete_project(project_id: str, clerk_id: str = Depends(get_current_user)):
    try:
        # Verify the project exists and belong to the user
        project_result = supabase.table("projects").select("*").eq("id", project_id).eq("clerk_id", clerk_id).execute() 
    
        if not project_result.data:
            # 404 - not found error
            raise HTTPException(status_code=404, detail="The project does not exist or access denied")
        
        # Delete project(CASCADE effect)
        deleted_project_result = supabase.table("projects").delete().eq("id", project_id).eq("clerk_id", clerk_id).execute()
        
        if not deleted_project_result.data:
            raise HTTPException(status_code=500, detail="The project deletion failed")

        return {
            "messages": "Project deleted successfully",
            "data": deleted_project_result.data[0]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get projects: {str(e)}")