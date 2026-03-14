from fastapi import APIRouter, HTTPException, Depends
from database import supabase
from auth import get_current_user
from pydantic import BaseModel

router = APIRouter(
    tags = ["chats"]
)

class ChatCreate(BaseModel):
    title: str

# API to create the chat conversation
@router.post("/api/projects/{project_id}/chats")
async def create_chat(project_id: str, chat: ChatCreate, clerk_id: str = Depends(get_current_user)):
    try:
     chat_result = supabase.table("chats").insert({
        "title": chat.title,
        "project_id": project_id,
        "clerk_id": clerk_id
        }).execute()

     return{
        "message": "Chat created successfully",
        "data": chat_result.data[0]
     }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail= f"Failed to create chat due to error: {str(e)}")

# API to delete the chat conversation
@router.delete("/api/projects/{project_id}/chats/{chat_id}")
async def delete_chat(chat_id:str, clerk_id: str = Depends(get_current_user)):
    try:
       deleted_chat_result = supabase.table("chats").delete().eq("id",chat_id).eq("clerk_id", clerk_id ).execute()

       if not deleted_chat_result:
        raise HTTPException(status_code=404, detail="Chat not found or access denied")

       
       return{
        "message": "Chat deleted successfully",
        "data": deleted_chat_result.data[0]
       } 
      
    except Exception as e:
        raise HTTPException(status_code=500, detail= f"Failed to delete chat due to error: {str(e)}")