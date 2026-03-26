from PIL.ImageFont import load_default
from fastapi import APIRouter, HTTPException, Depends
from database import supabase
from auth import get_current_user
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# initialize LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)


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
        raise HTTPException(status_code=500, details= f"Failed to create chat due to error: {str(e)}")

# API to delete the chat conversation
@router.delete("/api/projects/{project_id}/chats/{chat_id}")
async def delete_chat(chat_id:str, clerk_id: str = Depends(get_current_user)):
    try:
       deleted_chat_result = supabase.table("chats").delete().eq("id",chat_id).eq("clerk_id", clerk_id ).execute()

       if not deleted_chat_result:
        raise HTTPException(status_code=404, details="Chat not found or access denied")

       
       return{
        "message": "Chat deleted successfully",
        "data": deleted_chat_result.data[0]
       } 
      
    except Exception as e:
        raise HTTPException(status_code=500, detail= f"Failed to delete chat due to error: {str(e)}")

# API to get individual chat messages
@router.get("/api/projects/{project_id}/chats/{chat_id}")
async def get_chat_Conversation(project_id:str, chat_id:str, clerk_id: str = Depends(get_current_user)):
    """Function to retrieve individual chat conversation"""

    try:

        # verify if the project exists
        result_project = supabase.table("projects").select("*").eq('id', project_id).eq('clerk_id', clerk_id).execute()
        
        if not result_project.data:
            raise HTTPException(status_code=404, detail="Project not found or access denied")
        
        # get the chat details
        result_chat = supabase.table("chats").select("*").eq('id', chat_id).eq('clerk_id', clerk_id).execute()

        if not result_chat.data:
            raise HTTPException(status_code=404, detail="Chat not found or access denied")
        
        chat = result_chat.data[0]

        # get messages for this chat id
        result_messages = supabase.table('messages').select("*").eq('chat_id', chat_id).order('created_at', desc=False).execute()

        # append this result to the above chat dictonary result
        chat['messages'] = result_messages.data or []

        return {
            "message": "Chat messages retrieved successfully",
            "data" : chat
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail= f"Failed to get chat message due to error: {str(e)}")

class SendMessageRequest(BaseModel):
    content: str

# Create a post API for chat message
@router.post("/api/projects/{project_id}/chats/{chat_id}/messages")
async def send_message(project_id:str, chat_id: str, request:SendMessageRequest, clerk_id: str = Depends(get_current_user)):
    """User message -> LLM -> AI Response"""
    try:
        # get the content value
        message = request.content
        print(f"New Message: {message[:50]}...")

        # 1. Save user message in db
        user_message_result = supabase.table("messages").insert({
            "content": message,
            "role": 'user',
            'chat_id': chat_id,
            'clerk_id': clerk_id,         
        }).execute()

        user_message = user_message_result.data[0]
        print(f"User message saved: {user_message['id']}")

        # 2. Call the LLM with system prompt and the user message
        print(f"Calling the LLM...")
        messages = [
            SystemMessage(content= "You are a helpful AI assistant. Provide clear, concise and accurate responses."),
            HumanMessage(content=message)
        ]

        response = llm.invoke(messages)
        ai_response = response.content

        print(f"LLM response received: {len(ai_response)} chars")

        # 3. Save the AI message in DB
        ai_message_result = supabase.table("messages").insert({
            "content": ai_response,
            "role": 'assistant',
            'chat_id': chat_id,
            'clerk_id': clerk_id,
            'citations': []         
        }).execute()

        ai_message = ai_message_result.data[0]
        print(f"AI message saved: {ai_message['id']}")

        # 4. Return the data
        return {
            "message": "Messages sent successfully",
            "data":{
               "userMessage": user_message,
               "aiMessage": ai_message
            }
        }
      
    except Exception as e:
        print(f"❌ Error in send_message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))  