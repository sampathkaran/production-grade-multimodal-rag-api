import uuid
from fastapi import APIRouter, HTTPException, Depends
from src.services.supabase import supabase
from src.services.awsS3 import s3_client, BUCKET_NAME
from src.models.index import FileUploadRequest, ProcessingStatus, UrlRequest
from src.services.clerkAuth import get_current_user
from src.models.index import FileUploadRequest
from src.utils.index import validate_url
from src.config.index import app_config
from src.services.celery import perform_rag_ingestion_task

router = APIRouter(tags=["projectFilesRoutes"])

"""
`/api/projects`

- GET `/{project_id}/files` - List all project documents

"""

@router.get("/{project_id}/files")
async def get_project_files(project_id:str, current_user_clerk_id:str = Depends(get_current_user)):
    """
    Logic Flow
    1. Get current user clerk_id
    2. Select all project documents from the project doucments table for given project_id
    3. Return project documents data
    """
    try:
        project_documents_result = (
            supabase.table("project_documents")
            .select("*")
            .eq("project_id", project_id)
            .eq("clerk_id", current_user_clerk_id)
            .order("created_at", desc=True)
            .execute()
        )

        # If there are no project documents for the project, return an empty list
        # A user many or may not have any project files

        return {
            "message": "Project files retrieved successfully",
            "data": project_documents_result.data or []
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred while retrieving project {project_id} files: {str(e)}",
        )    

@router.post("/{project_id}/files/presigned_url")
async def get_upload_presigned_url(project_id:str, file_upload_request: FileUploadRequest, current_user_clerk_id:str = Depends(get_current_user)):
    """
    Logic Flow:
    1. Verify project exists and belongs to the current user
    2. Generate a S3 key
    3. Generate upload presigned URL(will expire in 1 hour)
    4. Create a project document record with pending status
    5. Return presigned URL
    """

    try:
        # Verify project exists and belong to the current user
        project_ownership_verification_result = supabase.table("projects").select("id").eq("id", project_id).eq("clerk_id", current_user_clerk_id).execute()
        
        if not project_ownership_verification_result.data:
            raise HTTPException(
                status_code=404,
                detail="Project not found or you don't have permission to upload files to this project"
            )

        # Generate unique S3 Key
        file_extension = file_upload_request.filename.split('.')[-1] if '.' in file_upload_request.filename else ''
        unique_id = str(uuid.uuid4())
        s3_key = f"projects/{project_id}/documents/{unique_id}.{file_extension}"


        # Generate presigned URL (expire in 1 hour)
        presigned_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": s3_key,
                "ContentType": file_upload_request.file_type,
            },
            ExpiresIn=3600 # 1 hour
            
        )

        if not presigned_url:
            raise HTTPException(status_code=422, detail="Failed to generate presigned URL")

        # Create database record with pending status
        document_creation_result = supabase.table("project_documents").insert({
            "project_id" :project_id,
            "filename": file_upload_request.filename,
            "s3_key": s3_key,
            "file_size" : file_upload_request.file_size,
            "file_type" : file_upload_request.file_type,
            "processing_status" : ProcessingStatus.PENDING,
            "clerk_id" : current_user_clerk_id
            }).execute()

        if not document_creation_result.data:
            raise HTTPException(status_code=422, detail="Failed to create project document - invalid data provided")

        return {
            "message": "Upload presigned URL generated successfully",
            "data" : {
                "upload_url" : presigned_url,
                "s3_key" : s3_key,
                "document": document_creation_result.data[0]
            }
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred while generating upload presigned url for {project_id}: {str(e)}",
        )

@router.post("/{project_id}/files/uploaded_confirm")
async def confirm_file_upload_to_s3(project_id:str, confirm_request: dict, current_user_clerk_id:str = Depends(get_current_user)):
    """
    Logic Flow:
    1. Verify s3 key is provided
    2. Verify the file exists ibn the DB
    3. Update the file upload status to "queued"
    4. Perform Celery - RAG Ingestion Task
    4. Update the project doucment record with the task_id
    6. Return successfully confirmed file upload data
    """

    try:
        s3_key = confirm_request.get("s3_key")
        if not s3_key:
            raise HTTPException(status_code=400, detail="s3_key is required") 

        # Verify file exists in database
        document_verification_result = (
            supabase.table("project_documents")
            .select("id")
            .eq("s3_key", s3_key)
            .eq("project_id", project_id)
            .eq("clerk_id", current_user_clerk_id)
            .execute()
        )

        if not document_verification_result.data:
            raise HTTPException(
                status_code=404,
                detail="File not found or you don't have permission to confirm upload to S3 for this file",
            )

        # Update document status to "queued"
        document_update_result = supabase.table("project_documents").update({
            "processing_status": ProcessingStatus.QUEUED
        }).eq("s3_key", s3_key).execute()
        
        if not document_verification_result.data:
            raise HTTPException(
                status_code=404,
                detail="File not found or you don't have permission to confirm upload to S3 for this file"
            )
        
        # ! Celery - Start Background Processing - RAG Injestion Task
        document_id = document_update_result.data[0]['id']
        task_result = perform_rag_ingestion_task.delay(document_id)
        task_id = task_result.id
        
        # store the task_id in the database
        document_update_result = (
            supabase.table("project_documents")
            .update({
                "task_id": task_id
            })
            .eq("id", document_id)
            .execute()
        )
        if not document_update_result.data:
            raise HTTPException(
                status_code=422,
                detail="Failed to update project document record with task_id",
            )
        return {
            "message": "File upload to s3 confirmed successfully and started background pre-processing of this file",
            "data" : document_update_result.data[0]
        }


    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred while confirming upload to S3 for {project_id}: {str(e)}",
        )

@router.post("/{project_id}/urls")
async def process_url(project_id: str, url_request: UrlRequest, current_user_clerk_id:str = Depends(get_current_user)):
    """
    1. Validate URL
    2. Add website URL to database
    3. Start background pre-processing of this URL
    4. Return successfully processed URL data
    """

    try:

        # Basic URL Validation
        url = url_request.url.strip()
        
        if url.startswith("http://") or url.startswith("https://"):
            url = url 
        else:
            url = f"https://{url}"

        if not validate_url(url):
            raise HTTPException(status_code=400, detail="Invalid URL")

        # Add website URL to the database
        document_creation_result =(
            supabase.table("project_documents")
            .insert(
                {
                    "project_id" : project_id,
                    "filename": url,
                    "s3_key": "",
                    "file_size": 0,
                    "file_type": "text/html",
                    "processing_status": ProcessingStatus.QUEUED,
                    "clerk_id": current_user_clerk_id,
                    "source_type": "url",
                    "source_url": url,
                }
            ).execute()
        )

        if not document_creation_result.data:
            raise HTTPException(status_code=422, detail="Failed to create project document with URL record - invalid data provided")
        
        # ! Celery - Starts Background Processsing - RAG Ingestion Task
        document_id = document_creation_result.data[0]['id']
        task_result = perform_rag_ingestion_task.delay(document_id)
        task_id = task_result.id
        
        # store the task_id in the database
        document_update_result = (
            supabase.table("project_documents")
            .update({
                "task_id": task_id
            })
            .eq("id", document_id)
            .execute()
        )
        if not document_update_result.data:
            raise HTTPException(
                status_code=422,
                detail="Failed to update project document record with task_id",
            )
        return {
            "message": "Website URL added to database successfully and started background pre-processing of this URL",
            "data": document_creation_result.data[0]
        }

   
    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred while processing urls for {project_id}: {str(e)}",
        ) 

@router.delete("/{project_id}/files/{file_id}")      
async def delete_file(project_id:str, file_id: str, current_user_clerk_id:str = Depends(get_current_user)):

    """
    Logic Flow:
    1. Verify document exists and belongs to the current user and take complete project document record
    2. Delete file from S3(only for actual files not for URLs)
    3. Delete the document from database
    4. Retrun successfully deleted document data 
    """

    try:
        # Verify document exists and belongs to the current user and take complete project document record
        document_ownership_verification_result=(
            supabase.table("project_documents")
            .select("*")
            .eq("id", file_id)
            .eq("project_id", project_id)
            .eq("clerk_id", current_user_clerk_id)
            .execute()
        )

        if not document_ownership_verification_result.data:
            raise HTTPException(status_code=404, detail = "Document not found or you don't have permission to delete this document")

        # Delete file from S3(only for actual files, not for URLs)
        s3_key = document_ownership_verification_result.data[0]['s3_key']

        if s3_key:
            s3_client.delete_object(Bucket=app_config['s3_bucket_name'], Key=s3_key)

        # Delete document from database
        document_deletion_result = (
            supabase.table("project_documents")
            .delete()
            .eq("id", file_id)
            .eq("project_id", project_id)
            .eq("clerk_id", current_user_clerk_id)
            .execute()
        )

        if not document_deletion_result.data:
            raise HTTPException(status_code=404, detail="Failed to delete document")

        
        return {
            "message": "Document deleted successfully",
            "data": document_deletion_result.data[0]
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred while deleting project document {file_id} for {project_id}: {str(e)}",
        )   

@router.get("/{project_id}/files/{file_id}/chunks")
async def get_project_document_chunks(
    project_id: str,
    file_id: str,
    current_user_clerk_id: str = Depends(get_current_user),
):
    """
    ! Logic Flow:
    * 1. Verify document exists and belongs to the current user and Take complete project document record
    * 2. Get project document chunks
    * 3. Return project document chunks data
    """
    try:
        # Verify document exists and belongs to the current user and Take complete project document record
        document_ownership_verification_result = (
            supabase.table("project_documents")
            .select("*")
            .eq("id", file_id)
            .eq("project_id", project_id)
            .eq("clerk_id", current_user_clerk_id)
            .execute()
        )

        if not document_ownership_verification_result.data:
            raise HTTPException(
                status_code=404,
                detail="Document not found or you don't have permission to delete this document",
            )

        document_chunks_result = (
            supabase.table("document_chunks")
            .select("*")
            .eq("document_id", file_id)
            .order("chunk_index")
            .execute()
        )

        return {
            "message": "Project document chunks retrieved successfully",
            "data": document_chunks_result.data or [],
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred while getting project document chunks for {file_id} for {project_id}: {str(e)}",
        )