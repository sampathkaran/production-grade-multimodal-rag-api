from fastapi import APIRouter, HTTPException, Depends
from src.services.supabase import supabase
from src.services.clerkAuth import get_current_user
from src.models.index import ChatCreate
from src.config.logging import get_logger, set_project_id, set_user_id

logger = get_logger(__name__)

router = APIRouter(tags=["chatRoutes"])

"""
`/api/projects/{project_id}/chats`
  - POST `/` - Create a new chat
  - DELETE `/{chat_id}` - Delete a specific chat
"""

@router.post("/{project_id}/chats")
async def create_chat(project_id:str,chat:ChatCreate, current_user_clerk_id:str = Depends(get_current_user)):
    """
    Logic flow
    1. Get current user clerk_id
    2. Insert new chat into datavase
    3. Check if hcat creation failed, then return error
    4. Return successfully created chat data    
    """
    set_project_id(project_id)
    set_user_id(current_user_clerk_id)
    logger.info("creating_chat", title=chat.title)

    try:
        chat_insert_data = {
            "title": chat.title,
            "project_id": project_id,
            "clerk_id": current_user_clerk_id,
        }
        chat_creation_result = (
            supabase.table("chats").insert(chat_insert_data).execute()
        )

        if not chat_creation_result.data:
            logger.warning("chat_creation_failed", reason="invalid_data")
            raise HTTPException(
                status_code=422, detail="Failed to create chat - invalid data provided"
            )
        chat_id = chat_creation_result.data[0].get("id")
        logger.info("chat_created_successfully", chat_id=chat_id)

        return {
            "message": "Chat created successfully",
            "data": chat_creation_result.data[0],
        }
    except HTTPException as e:
        raise e

    except Exception as e:
        logger.error("chat_creation_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred while creating chat: {str(e)}",
        )

@router.delete("/{project_id}/chats/{chat_id}")
async def delete_chat(
    project_id:str, chat_id: str, current_user_clerk_id: str = Depends(get_current_user)
):
    """
    ! Logic Flow
    * 1. Get current user clerk_id
    * 2. Verify if the chat exists and belongs to the current user
    * 3. Delete chat
    * 4. Return successfully deleted chat data
    """
    
    set_user_id(current_user_clerk_id)
    logger.info("deleting_chat", chat_id=chat_id)

    try:
        chat_deletion_result = (
            supabase.table("chats")
            .delete()
            .eq("id", chat_id)
            .eq("clerk_id", current_user_clerk_id)
            .execute()
        )
        if chat_deletion_result.data:
            set_project_id(chat_deletion_result.data[0].get("project_id"))

        if not chat_deletion_result.data:
            logger.warning("chat_deletion_failed", chat_id=chat_id, reason="not_found_or_unauthorized")
            raise HTTPException(
                status_code=404,
                detail="Chat not found or you don't have permission to delete it",
            )
        logger.info("chat_deleted_successfully", chat_id=chat_id)
        return {
            "message": "Chat deleted successfully",
            "data": chat_deletion_result.data[0],
        }
    except HTTPException as e:
        raise e

    except Exception as e:
        logger.error("chat_deletion_error", chat_id=chat_id, error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred while deleting chat {chat_id}: {str(e)}",
        )


@router.get("/{project_id}/chats/{chat_id}")
async def get_chat(chat_id: str, current_user_clerk_id: str = Depends(get_current_user)):
    """
    ! Logic Flow:
    1. Get current user clerk_id
    2. Veriify if the chat exists and belongs to the current user
    3. Get chat messages
    4. Return chat data
    """
    set_user_id(current_user_clerk_id)
    try:
        # Verify if the chat exists and belongs to the current user
        chat_ownership_verification_result = (
            supabase.table("chats")
            .select("*")
            .eq("id", chat_id)
            .eq("clerk_id", current_user_clerk_id)
            .execute()
        )

        chat_result = chat_ownership_verification_result.data[0]
        set_project_id(chat_result.get("project_id"))

        if not chat_ownership_verification_result.data:
            logger.warning("chat_not_found_error", chat_id=chat_id)
            raise HTTPException(
                status_code=404,
                detail="Chat not found or you don't have permission to access it"
            )
       
        # Get messages for this chat
        message_result = (
            supabase.table("messages")
            .select("*")
            .eq("chat_id", chat_id)
            .order("created_at", desc=False)
            .execute()
        )

        chat_result["messages"] = message_result.data or []

        return {
            "message": "Chat retrieved successfully",
            "data": chat_result,
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        logger.error("chat_data_not_found", chat_id=chat_id, error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred while getting chat {chat_id}: {str(e)}",
        )        