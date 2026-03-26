import os
from celery import Celery
from langchain_core.messages import HumanMessage
from database import BUCKET_NAME, s3_client, supabase
import time
from typing import List
from unstructured.partition.pdf import partition_pdf
from unstructured.partition.docx import partition_docx
from unstructured.partition.html import partition_html
from unstructured.partition.pptx import partition_pptx
from unstructured.partition.text import partition_text
from unstructured.partition.md import partition_md
from unstructured.chunking.title import chunk_by_title
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from dotenv import load_dotenv
from scrapingbee import ScrapingBeeClient


load_dotenv()

# initialize scraping bee client
scrapingbee_client = ScrapingBeeClient(api_key=os.getenv('SCRAPINGBEE_API_KEY'))



# initialize LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)
embedding_model = OpenAIEmbeddings(
                    model="text-embedding-3-large",
                    dimensions=1536)

#instantiate the celery
celery_app = Celery('document_processor', # name of the celery app
           broker = "redis://localhost:6379/0", # redis comes with built in db of 16, we will start with first one  
          backend = "redis://localhost:6379/0" # sepcify where the result to be stored
         )  

# define the method to update the processing statuss
def update_processing_status(document_id: str, processing_status:str, details: dict = None):
    """Update document processsing status with optional details such that we update the metadata values in each step"""
    
    # get current document
    result = supabase.table("project_documents").select("processing_details").eq("id", document_id).execute()
    
    # Start with existing details or empty dict
    current_processing_details = {}

    if result.data and result.data[0]['processing_details']:
        current_processing_details = result.data[0]['processing_details']
    
    # add new detail if provided
    if details:
        current_processing_details.update(details) # merge with the existing details


    # update processing status record in DB 
    result = supabase.table("project_documents").update({
            "processing_status" : processing_status,
            "processing_details" : current_processing_details
            }).eq("id", document_id).execute()

# use @celery to make it a celery function
@celery_app.task
def process_document(document_id: str):
    """ Document processing function """
    print("Processing the doucment")

    try:
        # Get the file/document details to download
        document_details = supabase.table("project_documents").select("*").eq("id", document_id).execute()
        document_info = document_details.data[0]
        source_type = document_info.get('source_type', 'file')
        # Step 1: Download and partition it
        
        # update the processing status
        update_processing_status(document_id, processing_status="partitioning")


        elements = download_and_partition(document_id, document_info)
          # logs
        tables = sum(1 for el in elements if el.category == "Table")
        images = sum(1 for el in elements if el.category == "Image")
        text_elements = sum(1 for el in elements if el.category in ["NarrativeText", "Title", "Text"])
        print(f"Extracted: {tables} tables, {images} images, {text_elements} text_elements")

        # Step 2: Creake chunks by Title
        chunks, chunks_metadata = create_chunks_by_title(elements)
        update_processing_status(document_id=document_id, processing_status="summarising", 
                            details = {
                              "chunking": chunks_metadata
                            })


        # Step 3: AI Summarize Hybrid Chunks 
        processed_chunks = summarise_chunks(chunks=chunks, document_id=document_id, source_type=source_type)


        # Step 4: Create Embeddings and store in the vector DB
        # We are going to vectorize the enhanced summarized AI content only not the raw data\
        # update the status first 
        update_processing_status(document_id=document_id, processing_status="vectorization")
        stored_chunk_ids = store_chunks_with_embeddings(document_id, processed_chunks)
         
        # Mark as background celery process completed
        update_processing_status(document_id=document_id, processing_status="completed")
        print(f"Background celery task completed for document: {document_id} with {len(stored_chunk_ids)} chunks")

        return {
            "message": "document upload completed successfully",
            "document_id" : document_id
        }

    except Exception as e:
        pass


def download_and_partition(document_id: str, document_info: dict):
    """Download document from S3/ Crawl URL and partition into elements"""
    print(f"Download and partitioning document {document_id}")
   
    # URL/File download
    source_type = document_info.get('source_type', "file")

    # if it is url
    if source_type == "url":
        # Scrape the URL
        url = document_info['source_url']

        # Fetch content with scrapingbee
        response = scrapingbee_client.get(url=url)

        # save to temp file
        temp_file_path = f"/tmp/{document_id}.html"
        with open(temp_file_path, "wb") as f:
            f.write(response.content)
        
        elements = partition_document(temp_file_path, "html", source_type="url")

    else:
        # handle file processing
        s3_key = document_info.get("s3_key", "")
        file_name = document_info.get("filename", "")
        file_type = file_name.split(".")[-1]

        # Download to a temporary location for processing
        temp_file_path = f'/tmp/{document_id}.{file_type}'
        s3_client.download_file(BUCKET_NAME, s3_key, temp_file_path)
        
        # Partitioning
        elements = partition_document(temp_file_path, file_type, source_type="file")
    
    # call the functions to get the metadata of elements and pass it below
    elements_metadata = analyze_elements(elements)

    # calling the function above to update the processing_details record in DB
    update_processing_status(document_id, processing_status="chunking", details={
        "partitioning": {
            "elements_found": elements_metadata # UI expects this structure and key name
        }
    })
    

    # remove the temp file
    os.remove(temp_file_path)

    return elements

def partition_document(filepath: str, file_type: str, source_type:str = "file"):
    """Partition the document based on file type and source type"""
    
    if source_type == "url":
       return  partition_html(
            filename=filepath
       )

    elif file_type == "pdf":
       partition_result = partition_pdf(filename=filepath, # path to the PDF file
                            strategy="hi_res", # this strategy is slower but accurate
                            infer_table_structure=True, # convert table as HTML
                            extract_image_block_types=["Image"], # Grab the images in PDF
                            extract_image_block_to_payload=True # store images as base64
                            )
       return partition_result

    elif file_type == "docx":
       return partition_docx(filename=filepath, # path to the PDF file
                            strategy="hi_res", # this strategy is slower but accurate
                            infer_table_structure=True, # convert table as HTML
                            )

    elif file_type == "pptx":
       return partition_pptx(filename=filepath, # path to the PDF file
                            strategy="hi_res", # this strategy is slower but accurate
                            infer_table_structure=True, # convert table as HTML
                            )   
    elif file_type == "txt":
       return partition_text(filename=filepath) # path to the PDF file

    elif file_type == "md":
       return partition_md(filename=filepath) # path to the PDF file

def analyze_elements(elements):
    """Functions to analazye the type of elements extracted for updating DB and UI"""
    
    text_count = 0
    table_count = 0
    image_count = 0
    title_count = 0
    other_count = 0

    # Go trough the elements and cound what type it is
    for element in elements:
        element_name = type(element).__name__ # Get the class name like "Table" or "NarrativeText"
        
        if element_name in ["Text", "NarrativeText", "ListItem", "FigureCaption"]:
            text_count += 1
        
        elif element_name == "Table":
            table_count += 1

        elif element_name == "Image":
            image_count += 1

        elif element_name in ["Title", "Header"]:
            title_count += 1
        
        else:
            other_count += 1

    return {
        "text" : text_count,
        "images" : image_count,
        "tables" : table_count,
        "titles" : title_count,
        "others": other_count
    }

def create_chunks_by_title(elements):
    """Function to create chunks and chunks metadata"""
    print("Started to create chunks")
    chunks = chunk_by_title(
        elements = elements,
        max_characters=3000, # the hard limit size of a chunk
        new_after_n_chars=2400, # try to start a new chunk after 2400 characters(softlimit)
        combine_text_under_n_chars=500 # merge tiny chunks that are under 500 characters with neighbours
    )

    total_chunks = len(chunks)
    chunks_metadata = {
        "total_chunks" :total_chunks 
    }

    print(f" Created {total_chunks} chunks from {len(elements)} elements")
    return chunks, chunks_metadata


# method for AI summarization

def summarise_chunks(chunks, document_id: str, source_type: str = "file"):
    """Tranform hybrid chunks into searchable content with AI summaries"""
    print("Processing hybrid chunks with AI summarization...")

    processed_chunks=[]
    total_chunks = len(chunks)

    for i, chunk in enumerate(chunks, 1):
        current_chunk = i
        print(f"Processing chunks {current_chunk}/{total_chunks}")        
        # here we add an update step to reflect in UI for every chunk
        update_processing_status(document_id = document_id, processing_status="summarising", details = {
                                 "summarising": {
                                    "current_chunk": current_chunk,
                                    "total_chunks": total_chunks
                                 }
        })

        # Step 1 - Process the chunks to identify the type ie text, table image
        content_data = separate_chunk_content_types(chunk=chunk, source_type=source_type)
        # Debug prints
        print(f"     Types found after chunking: {content_data['types']}")
        print(f"     Tables found after chunking: {len(content_data['tables'])}, Images: {len(content_data['images'])}")

        # Step 2 - Decide if we need summarization
        if content_data['tables'] or content_data['images']:
            print(f" → Creating AI summary for mixed content...")

            enhanced_content = ai_summary_hybrid_chunk(content_data['text'],content_data['tables'], content_data['images'])
        else:
            enhanced_content = content_data['text']

        # Step 3 - Build the original content structue
        original_content = {"text": content_data['text']}
        if content_data['tables']:
            original_content['tables'] = content_data['tables']
        if content_data['images']:
            original_content['images'] = content_data['images']

        # Step 4 - create a processed chunk variable with all data
        processed_chunk = {
            "content" : enhanced_content,
            "original_content": original_content,
            "type" : content_data['types'],
            'page_number': get_page_number(chunk, i),
            "char_count" : len(enhanced_content)
        }
        
        # Step 5 - Append to this processed_chunks variables
        processed_chunks.append(processed_chunk)
    
    print(f"Processed {len(processed_chunks)} chunks")
    return processed_chunks

# get the page number function
def get_page_number(chunk, chunk_index):
    """Get pagenumber from chunk or fallback"""
    if hasattr(chunk, "metadata"):
        page_number = getattr(chunk.metadata, 'page_number', None)
        if page_number is not None:
            return page_number
    # fall back
    return chunk_index

def separate_chunk_content_types(chunk, source_type: str = "file") -> dict:
    """Analyze what type of content are there in the chunks"""
    is_source_url = source_type == "url"

    # set some placeholder to capture details
    content_data = {
        "text": chunk.text,
        "tables": [],
        "images": [],
        "types": ['text']  # to capture what type of data in chunk
    }

    # Check for images and tables in original elements
    if hasattr(chunk,'metadata') and hasattr(chunk.metadata, 'orig_elements'):
        for element in chunk.metadata.orig_elements:
            element_type = type(element).__name__

            # Handle tables
            if element_type == "Table":
                content_data['types'].append("Table")
                table_html = getattr(element.metadata, "text_as_html", element.text)
                content_data['tables'].append(table_html)
            
            # Handle images
            elif element_type == "Image" and not is_source_url:
                content_data['types'].append("Image")
                image_base64 = getattr(element.metadata, "image_base64", element.text) # if false dont error use element.text value
                content_data['images'].append(image_base64)
    # remove this
    print(f"see images and tables count after chunking: {content_data['types']}")
    # Final step cleanup the type from duplicate values            
    content_data['types'] = list(set(content_data['types']))
    
    return content_data

def ai_summary_hybrid_chunk(text: str, tables_html: List[str], images_base64: List[str]):
    """Function to summarize hybrid chunk"""

    try:
        # Build the text prompt with more efficient instructions
        # pass the instruction make LLM as a smart indexer
        prompt_text = f"""Create a searchable index for this document content.
CONTENT:
{text}        
"""
        # Add tables if present
        if tables_html:
            prompt_text += "TABLES:\n"
            for i, table in enumerate(tables_html, 1):
                prompt_text += f"Table {i}:\n{table}\n\n"
       # ---Build message_content ---
        # Initialize FIRST, then append in correct order
        message_content = [{"type": "text", "text": prompt_text}]       
                # Add images if present
        if images_base64:
            for i, image in enumerate(images_base64, 1):
                message_content.append({
                    "type" : "image_url",
                    "image_url" : {"url": f"data:image/jpeg;base64,{image}"}
                })

                print(f"Image {i} included in summary request")
        
               # More concise but effective prompt
               # It tells the LLM to act as a search index generator — turning raw document content into structured, searchable metadata.
        instruction = ""
        instruction += """
Generate a structured search index (aim for 250-400 words):

QUESTIONS: List 5-7 key questions this content answers (use what/how/why/when/who variations)

KEYWORDS: Include:
- Specific data (numbers, dates, percentages, amounts)
- Core concepts and themes
- Technical terms and casual alternatives
- Industry terminology
"""
        if images_base64:
           instruction += """ 
VISUALS (if images present):
- Chart/graph types and what they show
- Trends and patterns visible
- Key insights from visualizations"""
        if tables_html:
            instruction += """ 
DATA RELATIONSHIPS (if tables present):
- Column headers and their meaning
- Key metrics and relationships
- Notable values or patterns"""
        instruction += """
Focus on terms users would actually search for. Be specific and comprehensive.

SEARCH INDEX:"""

        # Build the message content with the text prompt
        message_content.append({"type": "text", "text": instruction}) # we write this way to support text + image format              
        
        message = HumanMessage(content=message_content)

        response = llm.invoke([message])

        return response.content
    
    except Exception as e:
        print(f" AI summary failed: {e}")


def store_chunks_with_embeddings(document_id:str, processed_chunks: list):
    """Generate embeddings and store chunks in one efficient operation"""

    if not processed_chunks:
        print("No chunks to process")
        return []
    
    # Step 1 - Generate embeddings for all chunks
    print(f"Generating embeddings for {len(processed_chunks)} chunks...")

    # Extract the content part from the chunks
    contents = [chunk_data['content'] for chunk_data in processed_chunks]

    # Generate the embeddings in batches to avoid API limits
    batch_size = 10
    all_embeddings = []
    print(f"Number of chunks to embed: {len(contents)}")
    for i in range(0, len(contents), batch_size):
        batch_contents = contents[i : i + batch_size] # this is where the batch happens
        batch_embeddings = embedding_model.embed_documents(batch_contents)
        print(f"Batch returned {len(batch_embeddings)} embeddings")
        all_embeddings.extend(batch_embeddings)
        # applying ceiling division formual for total size of batch x = (a+b-1)//b
        print(f"Generated embeddings for batch {i//batch_size + 1}/{(len(contents) + batch_size -1)//batch_size}")   

    # Step 2: Store chunks with embeddings in database under documents_chunk column
    print("Storing chunks with embeddings in database")
    stored_chunk_ids=[]


    for i, (chunk, embedding) in enumerate(zip(processed_chunks, all_embeddings)):
        # Append document id, chunk_index and embeddings
        chunk_with_embedding = {
            **chunk, # unpack the dictonary
            'document_id': document_id,
            'chunk_index': i,
            'embedding': embedding #
        }
     
        # store the above data in DB, here FTS columns is auto generated see in sql commands
        # supabase looks into keys and add the values to columns if it is unorder
        result = supabase.table('document_chunks').insert(chunk_with_embedding).execute()
        stored_chunk_ids.append(result.data[0]['id'])

    print(f"Successfully stored {len(processed_chunks)} chunks with embeddings")
    return stored_chunk_ids