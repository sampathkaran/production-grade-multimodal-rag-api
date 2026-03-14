import stat
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

class ProjectSettings(BaseModel):
    embedding_model: str
    rag_strategy: str
    agent_type: str
    chunks_per_search : int
    final_context_size: int
    similarity_threshold : float
    number_of_queries : int
    reranking_enabled: bool
    reranking_model: str
    vector_weight : float  
    keyword_weight : float  

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
        # # Add these debug lines
        # print("Settings data:", project_settings_result.data)
        # print("Settings count:", project_settings_result.count)
        # print("Full response:", project_settings_result)    
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

# define the API to read project page
@router.get("/api/projects/{project_id}")
async def get_project(project_id: str, clerk_id: str = Depends(get_current_user)):
    try:
        project_result = supabase.table("projects").select("*").eq("id", project_id).eq("clerk_id", clerk_id).execute()

        if not project_result.data:
            # 404 - not found error
            raise HTTPException(status_code=404, detail="Project not found")
        
        return {
            "message" : "Project retrieved successfully",
            "data": project_result.data[0]
        }
    except Exception as e:
           raise HTTPException(status_code=500,detail=f"Failed to get projects: {str(e)}")

# define a API to read the chats
@router.get("/api/projects/{project_id}/chats")
async def get_project_chats(project_id: str, clerk_id: str = Depends(get_current_user)):
    try: 
        chats_result = supabase.table("chats").select("*").eq("project_id", project_id).eq("clerk_id", clerk_id).order("created_at", desc=True).execute()

        return {
            "message": "Chats retreived successfully",
            # here we need all the chat so not using [0]
            "data": chats_result.data or []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chats: {str(e)}")

# define an API to read the project settings
@router.get("/api/projects/{project_id}/project_settings")
async def get_project_settings(project_id: str):
    try:
        settings_result = supabase.table("project_settings").select("*").eq("project_id", project_id).execute()
        
        if not settings_result.data:
            raise HTTPException(status_code=404, detail= "Project settings not found")
        return {
            "message": "Project settings retreived successfully",
            # .execute() returns a list of rows so we grab the first item in it
            "data" : settings_result.data[0]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get project settings: {str(e)}")

# define a route for update project setting API
@router.put("/api/projects/{project_id}/project_settings")
async def update_project_settings(project_id: str, settings: ProjectSettings, clerk_id: str= Depends(get_current_user)):
    try:
        # thumb rules before update is to check if the project exists or not
        precheck_result = supabase.table("projects").select("id").eq("id", project_id).eq("clerk_id", clerk_id)

        if not precheck_result:
            return HTTPException(status_code=404, detail="Project not found or access denied")
        
        #model_dump() converts a Pydantic model into a plain Python dictionary.
        update_result = supabase.table("project_settings").update(settings.model_dump()).eq("project_id", project_id).execute()
        
        if not update_result:
            return HTTPException(status_code=404, detail="Project settings not found or access denied")

        return {
            "message": "Project settings updated successfully",
            "data": update_result.data[0]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update project settings: {str(e)}")
