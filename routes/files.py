from re import T
import string
import uuid
from fastapi import Depends, HTTPException, APIRouter # API router allows to split the API files
from auth import get_current_user
from database import supabase, s3_client, BUCKET_NAME
from pydantic import BaseModel
router = APIRouter(
    tags = ["files"]
)

class FileUploadRequest(BaseModel):
    filename: str
    file_size: int
    file_type :str


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

# Define the presigned URL API
@router.post("/api/projects/{project_id}/files/presigned_url")
async def create_presigned_url(
    project_id: str, 
    file_request: FileUploadRequest, 
    clerk_id :str = Depends(get_current_user)):

    try:

    # Step 1: Verify the project exists and belongs to the user
     result = supabase.table("projects").select("id").eq("id", project_id).eq("clerk_id", clerk_id).execute()
     if not result.data:
        raise HTTPException(status_code=404, detail="Project not found or access denied")

    # Step 2: Generate a unique S3 key 
     file_extension = file_request.filename.split('.')[-1] if file_request.filename else ""
     unique_id = str(uuid.uuid4())
     s3_key = f"projects/{project_id}/documents/{unique_id}.{file_extension}"

    # Step 3: Generate the presigned URL(expire in 1 hour)
     presigned_url = s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": BUCKET_NAME,
            "Key": s3_key,
            "ContentType": file_request.file_type
        },
        ExpiresIn=3600 # 1 hr
     )
    # Step 4: Create a database record with status as uploading 
     document_result = supabase.table("project_documents").insert({
        "project_id": project_id,
        "s3_key": s3_key,
        "filename": file_request.filename,
        "file_size": file_request.file_size,
        "file_type": file_request.file_type,
        "processing_status": "uploading",
        "clerk_id": clerk_id
     }).execute()

     if not document_result.data:
        raise HTTPException(status_code=500, detail="Failed to create document record")

     return{
        "message": "Presigned URL generated successfully",
        "data": {
            "presigned_url": presigned_url,
            "s3_key": s3_key,
            "document": document_result.data[0] 
        }
     }
   
    except Exception as e:
        raise HTTPException(status_code=500, detail = f"Failed to generate pre-signed URLs: {str(e)}")

# Define the API url to confirm the upload 
# the supabase processing status column will be pending so we need to change it to queue
@router.put("/api/projects/{project_id}/files/uploaded_confirm")
async def uploaded_confirm(project_id:str, confirm_request:dict, clerk_id:str = Depends(get_current_user)):
    try:

        s3_key = confirm_request.get("s3_key")

        if not s3_key:
            raise HTTPException(status_code=400, detail = "s3 key is required")
        
        # Update document status
        result = supabase.table("project_documents").update({
            "processing_status": "queued" # we are yet mark status confirm as it has to go through processing pipeline
        }).eq("s3_key", s3_key).eq("project_id", project_id).eq("clerk_id", clerk_id).execute()
    
        if not result.data:
            raise HTTPException(status_code=404, detail = "Document not found or access denied")
        

        # Start background preprocessing of the current file using celery

        # Return JSON
        return {
            "message": "Upload confirmed, processing started with celery",
            "data": result.data[0]
        }     

    except Exception as e:
        raise HTTPException(status_code=500, detail = f"Failed to confirm upload: {str(e)}")

class UrlAddRequest(BaseModel):
    url: str

# define an API endpoint to post website URL
@router.post("/api/projects/{project_id}/urls")
async def add_website_url(
    project_id: str,
    url_request: UrlAddRequest,
    clerk_id:str = Depends(get_current_user)):
    
    try:
        # Basic URL validation
        url = url_request.url.strip()

        if not url.startswith(('http://', 'https://')):
            url = "https://" + url

        result = supabase.table("project_documents").insert({
         "project_id": project_id,
         "s3_key": "",
         "filename": url,
         "file_size": 0,
         "file_type": "test/html",
         "processing_status": "queued",
         "clerk_id": clerk_id,
         "source_url": url,
         "source_type": "url"
        }).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail = "Failed to create URL record")
        
        # Start background processing

        return{
            "message": "URL added successfully",
            "data": result.data[0]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail = f"Failed to add URL: {str(e)}")

# Delete document API
@router.delete("/api/projects/{project_id}/files/{document_id}")
async def delete_document(
    project_id: str,
    document_id: str,
    clerk_id:str = Depends(get_current_user)):

    try:
        # Step 1- Verify the document exists
        document_result = supabase.table("project_documents").select("*").eq("id", document_id).eq("project_id", project_id).eq("clerk_id", clerk_id).execute()
        
        if not document_result.data:
            raise HTTPException(status_code=404, detail="Document/URL not found or access denied")
        
        # Step 2- Extract the S3 key
        document_record = document_result.data[0]
        s3_key = document_record["s3_key"]

        # Step 3- Delete the document from s3 (only for files not for URLs)
        if s3_key:
            try:
                s3_client.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
                print(f"Delete from S3: {s3_key}")

            except Exception as s3_error:
                print(f"Failed to delete S3: {s3_error}")
        
        # Step 4- Delete the document record from supabase
        #delete_result = supabase.table("project_documents").delete().eq("id", document_id).execute()
        delete_result = supabase.table("project_documents").delete().match({"id": document_id}).execute()
            

        if not delete_result.data:
            raise HTTPException(status_code=500, detail = "Failed to delete the document/URL")

        return {
            "message": "Document/URL deleted successfully",
            "data": delete_result.data[0]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail = f"Failed to delete the document/URL: {str(e)}")