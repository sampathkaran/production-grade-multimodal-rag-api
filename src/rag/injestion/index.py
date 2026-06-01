from sqlalchemy.orm.base import ATTR_EMPTY
from src.services.awsS3 import BUCKET_NAME
from src.rag.injestion.utils import partition_document, analyze_elements, separate_content_types, create_ai_summary, get_page_number
from src.models.index import ProcessingStatus
from src.services.supabase import supabase
from src.services.awsS3 import s3_client
from src.services.llm import openAI
from src.services.webScrapper import scrapingbee_client
import time
from unstructured.chunking.title import chunk_by_title
import os

# Step 1: Update status to "processing"
def process_document(document_id: str):
    """
     Step 1: Update the database status to the processing
     Step 2 Download from S3 (if file) or Crawl the URL (if URL) and Extract text, table and images from the PDF (using unstructured library) from the AWS S3 document.
     Step 3: Split the extracte content into chunks.
     Step 4: Generate AI summaries for each chunk.
     Step 5: Create vector embeddings of chunk and store in PostgresQL.
     Update the project document record with the processing_status and processing_details as needed.
     - 'processing_details' : What type of elements or metadata did we retrieve from the document to show in the UI.
    """
    
    try:
        # update the initial processing status in DB
        update_status_in_database(document_id, ProcessingStatus.PROCESSING)

        doc_result = supabase.table("project_documents").select("*").eq("id", document_id ).execute()
        if not doc_result.data:
            raise Exception(f"Failed to get project document record with id: {document_id}")

        document = doc_result.data[0] 
        source_type = document.get('source_type', 'file')     
        
        # We need to update processing status in every step accordingly below

        # Step 1: Download from S3 (file) or Crawl the URL (url) and Extract content        
        update_status_in_database(document_id, status= ProcessingStatus.PARTITIONING)

        elements_summary, elements = download_and_partition(document_id, document)

        tables = sum(1 for el in elements if el.category == "Table")
        images = sum(1 for el in elements if el.category == "Image")
        text_elements = sum(1 for el in elements if el.category in ["NarrativeText", "Title", "Text"])
        print(f"Extracted: {tables} tables, {images} images, {text_elements} text_elements")
        
        update_status_in_database(
            document_id, ProcessingStatus.CHUNKING, {
                # Storing the partioning result to sowcase in UI
                # the function is "enum-aware" so it handles .value internally, but a plain dictionary is not
                ProcessingStatus.PARTITIONING.value: {
                    "elements_found": elements_summary
                }
            }
        )
        # Step 2: Chunk Elements by title
        chunks, chunking_metrics = chunk_elements(elements)
        update_status_in_database(
            document_id, ProcessingStatus.SUMMARISING, {
                # Storing chunking result to showcase in UI
                ProcessingStatus.CHUNKING.value: chunking_metrics
            }
        )

        # Step 3: Summarising Chunks
        processed_chunks = summarize_chunks(chunks, document_id, source_type)
        update_status_in_database(document_id, ProcessingStatus.VECTORIZATION)
        
        
        # Step 4: Vectorization & Storing
        vectorize_chunks_summary_and_store_in_database(processed_chunks, document_id)  
        update_status_in_database(document_id, ProcessingStatus.COMPLETED)

        return {
            "success": True,
            "document_id": document_id,
        }
    except Exception as e:
        raise Exception(f"Failed to process document {document_id}: {str(e)}")

def download_and_partition(document_id: str, document:dict):
    """
    Check if the content either a file or URL
    if: Document - Download from S3
    else: URL - Crawl the URL
    Partition into elements lke text, tables, images etc and analyze the elements summary and upload to db
    """
    
    # Get the source type
    document_source_type = document['source_type']

    if document_source_type == "url":
       # Crawl URL
       url = document['source_url']
       
       response = scrapingbee_client.get(url)

       # save to temp file
       temp_file = f"/tmp/{document_id}.html"
       with open(temp_file, 'wb') as f:
            f.write(response.content)
       elements = partition_document(temp_file, 'html', source_type="url")
       
    else:
        # Handle file processing

        s3_key = document['s3_key']
        filename = document['filename']
        file_type = filename.split(".")[-1].lower()

        # Download to a temporary location 
        temp_file = f"/tmp/{document_id}.{file_type}"
        s3_client.download_file(BUCKET_NAME, s3_key, temp_file)

        elements = partition_document(temp_file, file_type, source_type="file")

    elements_summary = analyze_elements(elements)    
    update_status_in_database(document_id, ProcessingStatus.CHUNKING,{
        "partitioning": {
            "elements_found": elements_summary
        }
    })
    os.remove(temp_file) # remove the temp file
    return elements_summary, elements


def update_status_in_database(document_id: str, status: ProcessingStatus, details:dict=None):
  
    """
    Update the project document record with the new status and details.
    """
    try: 
        # Get current document
        document_result = (
        supabase.table("project_documents")
        .select("processing_details")
        .eq("id", document_id)
        .execute()
        )
        if not document_result.data:
            raise Exception(
                f"Failed to get project document record with id: {document_id}"
            )

        # Start with exisiting processing details or empty dict
        current_details = {}
        if document_result.data[0]["processing_details"]:
            current_details = document_result.data[0]["processing_details"]

        # Add new details if provided
        if details:
            current_details.update(details) # Note : update() - built-in dict method that merges another dictionary into the current one.

        # Update the project document record with the new details
        document_update_result = (
            supabase.table("project_documents")
            .update(
                {
                    "processing_status": status.value,
                    "processing_details": current_details,
                }
            )
            .eq("id", document_id)
            .execute()
        )

        if not document_update_result.data:
            raise Exception(
                f"Failed to update project document record with id: {document_id}"
            )

    except Exception as e:
        raise Exception(f"Failed to update status in database: {str(e)}")


def chunk_elements(elements):
    """Chunk elements by title and collect metrics"""
    try:
        chunks = chunk_by_title(
            elements, # The parsed PDF elements from previou step
            max_characters = 3000, # Hard limit - never exceed 3000 characters per chunk
            new_after_n_chars=2400, # Try to start a new chunk after 2400 characters
            combine_text_under_n_chars=500 # Merge tinychunks under 500 chars with neighbours
        )

        # collect chunking metrics
        total_chunks = len(chunks)

        # to display the total number of chunks in the UI
        chunking_metrics = {
            "total_chunks": total_chunks
        }
        
        print(f"✅ Created {total_chunks} chunks from {len(elements)} elements")
        return chunks, chunking_metrics
    
    except Exception as e:
        raise Exception(f"Failed to chunk elements by title: {str(e)}")

def summarize_chunks(chunks, document_id, source_type="file"):
    """
    Create user-friendly, searchable chunks
    We will summarize only hydribd chunks ie text and image or text and table or table and image 
    """

    try:
        processed_chunks = [] # Initialize an empty list
        total_chunks = len(chunks)
        
        for i, chunk in enumerate(chunks, 1):
            current_chunk = i
            
            # Update progress directly
            update_status_in_database(document_id, ProcessingStatus.SUMMARISING, {
                ProcessingStatus.SUMMARISING.value: {
                    "current_chunk": current_chunk,
                    "total_chunks": total_chunks
                }
            })

            # step a - extract the content from the chunk

            # Normalize the raw chunk into typed content buckets (text/tables/images, etc.).
            # content_data = {
            #     "text": "This is the main text content of the chunk...",
            #     "tables": ["<table><tr><th>Header</th></tr><tr><td>Data</td></tr></table>"],
            #     "images": ["iVBORw0KGgoAAAANSUhEUgAA..."],  # base64 encoded image strings
            #     "types": ["text", "table", "image"]  # or ["text"], ["text", "table"], etc.
            # }            
            content_data = separate_content_types(chunk, source_type)

            # Debug prints
            print(f"Chunk Types found: {content_data['types']}")
            print(f"Chunk Tables found: {len(content_data['tables'])}, Chunk Images found: {len(content_data['images'])}")

            # step b - use AI summarizaton only when the cuhnk contains atleast one table or image
            if content_data['tables'] or content_data['images']:
                enhanced_content = create_ai_summary(content_data["text"], content_data["tables"], content_data["images"])
            
            else:
                enhanced_content= content_data['text']

            # Preserve the original content structure for tracebility in the UI
            # Also we don't use langchain document instead manually create the structure
            original_content = {"text": content_data['text']}
            if content_data['tables']:
                original_content['tables'] = content_data['tables']
            if content_data['images']:
                original_content['images'] = content_data['images']

            # Create a processed chunk with all data
            processed_chunk = {
                'content': enhanced_content,
                'original_content': original_content,
                'type': content_data['types'],
                'page_number': get_page_number(chunk, i),
                'char_count': len(enhanced_content)
            }

            processed_chunks.append(processed_chunk)

            # Rough example for processed_chunk:
            # {
            #     "content": "AI-enhanced summary of the chunk... Image looks like this: <image_base64> ... Table looks like this: <table_html> ...",
            #     "original_content": {
            #         "text": "Full paragraph of the chunk...",
            #         "tables": ["<table><tr><th>Region</th><th>Revenue</th></tr><tr><td>APAC</td><td>$1.2M</td></tr></table>"],
            #         "images": ["iVBORw0KGgoAAA...base64..."]
            #     },
            #     "type": ["text", "table", "image"],
            #     "page_number": 3,
            #     "char_count": 142
            # }

        return processed_chunks
    except Exception as e:
        raise Exception(f"Failed to summarise chunks: {str(e)}")

def vectorize_chunks_summary_and_store_in_database(processed_chunks, document_id):
    """Generate vector embeddings of the ai-summary of the chunks and store in the database."""
    try:
       # processed_chunks example (list of dicts):
       
        # processed chunks = [{
        #     "content": "Ai-enhanced summary of the chunk...", <----- **This is the content that will be vectorized.**
        #     "original_content": {"text": "...", "tables": ["<table...>"], "images": ["<base64>"]},
        #     "type": ["text", "table", "image"],
        #     "page_number": 3,
        #     "char_count": 142
        # }, {....}]

        # Step 1: Vectorizing Chunks

        # create a list of summarized content
        ai_summary_list = [chunk_data['content'] for chunk_data in processed_chunks]
        # ai_summary_list = ["Ai-enhanced summary of the chunk...", "Ai-enhanced summary of the chunk...", ...]

        # Edge case: More chunks processing exceeds API limit. We will generate in batches

        batch_size=10
        all_vectorized_embeddings = []

        for i in range(0, len(ai_summary_list), batch_size):
            batch_texts = ai_summary_list[i: i + batch_size]

            # Simple retry mechanism
            attempt = 0

            while True:
                try: 
                    batch_embeddings = openAI['embeddings'].embed_documents(batch_texts)
                    all_vectorized_embeddings.extend(batch_embeddings)
                    print(f" ✅ Generated embeddings for batch {i//batch_size + 1}/{(len(ai_summary_list) + batch_size - 1)//batch_size}")
                    break
                except Exception as e:
                    attempt +=1
                    if attempt >= 3:
                        raise e
                    wait = 2 ** attempt 
                    time.sleep(wait)
        
        # Step 2: Store Chunks with embeddings
        # chunk_embedding_pairs: list of tuples (processed_chunk, embedding_vector)
                # Example:
        # [
        #     ({"content": "...", "page_number": 1, "type": ["text"]}, [0.123, -0.456, 0.789, ...]),
        #     ({"content": "...", "page_number": 2, "type": ["text", "table"]}, [0.234, -0.567, 0.890, ...]),
        #     ...
        # ] 

        chunk_embedding_pairs = list(zip(processed_chunks, all_vectorized_embeddings))
        stored_chunk_ids = []

        for i, (processed_chunk, embedding_vector) in enumerate(chunk_embedding_pairs):
            # Add document_id, chunk_index, and embedding to each processed_chunk
            # chunk_data_with_embedding example:
            # {
            #     * Same as above but added document_id, chunk_index, and embedding.
            #     "content": "AI-enhanced summary of the chunk...","original_content": {"text": "...", "tables": ["<table>...</table>"], "images": ["<base64>"]},"type": ["text", "table", "image"],"page_number": 3,"char_count": 142,
            #     "document_id": "doc_123",
            #     "chunk_index": 0,
            #     "embedding": [0.123, -0.456, 0.789, 0.234, ...]  # 1536 dimensions
            # }
            chunk_data_with_embedding = {
                **processed_chunk, # ** unpacks the dict 
                "document_id": document_id,
                "chunk_index": i,
                "embedding": embedding_vector,
            }
            result = (
                supabase.table("document_chunks")
                .insert(chunk_data_with_embedding)
                .execute()
            )
            stored_chunk_ids.append(result.data[0]["id"])

        # print(f"Successfully stored {len(processed_chunks)} chunks with embeddings")
        return stored_chunk_ids

    except Exception as e:
        raise Exception(f"Failed to vectorize chunks and store in database: {str(e)}")