from fastapi import HTTPException
from src.services.supabase import supabase
from langchain_core.messages import SystemMessage, HumanMessage
from src.services.llm import openAI
from typing import Dict, List

def get_project_settings(project_id):
    try:
      project_settings_result = (
        supabase.table("project_settings")
        .select("*")
        .eq('project_id', project_id)
        .execute()
      )

      if not project_settings_result.data:
        raise HTTPException(status_code=404, detail="Project settings not found") 

      project_settings = project_settings_result.data[0]
      return project_settings 

    except Exception as e:
        raise Exception(f"Failed to get project settings: {str(e)}")

def get_project_document_ids(project_id):
    try:
        document_ids_result = (
            supabase.table("project_documents")
            .select("id")
            .eq('project_id', project_id)
            .execute()
        )

        if not document_ids_result.data:
            return []

        document_ids = [document['id'] for document in document_ids_result.data]
        return document_ids

    except Exception as e:
        raise Exception(f"Failed to get document IDs: {str(e)}")


def build_context_from_retrieved_chunks(chunks: List[Dict]):
    """Returns Tuple of (texts, images, tables and citations)
    we will retrieve the original content from document chunks
    """

    if not chunks:
        return [], [], [], []
            
    texts = []
    images = []
    tables = []
    citations = []

    # Batch fetch all filenames
    """
    Structure of chunk
    {'id': '7807cf6b-623a-4bee-b814-a1fbbb18afdb', 'document_id': '6e1aeda5-01ed-4ef5-afda-e85de341cf87', 
    'content': '2 Background\n\nThe goal of reducing sequential computation also forms the foundation of the Extended Neural GPU [16], ByteNet [18] and ConvS2S [9], all of which use convolutional neural networks as basic building block, computing hidden representations in parallel for all input and output positions.
    """
    doc_ids = [chunk["document_id"] for chunk in chunks if chunk.get("document_id")]

    # Get the unique  document IDs from the doc_ids list
    unique_doc_ids = list(set(doc_ids))

    # Create a dictonary to store the filenams for the documents in the unique_doc_ids
    filename_map = {}

    # Fecth the filenames for the documents in the unique_docs_ids list
    if unique_doc_ids:
        result = (
            supabase.table("project_documents")
            .select("id", "filename")
            .in_("id", unique_doc_ids)
            .execute()
        )
        filename_map = {doc["id"]: doc["filename"] for doc in result.data}


    # Process each chunk
    for chunk in chunks:
        original_content = chunk.get('original_content', {})

        # Extract content from chunk
        chunk_text = original_content.get('text')
        chunk_images = original_content.get('images', [])
        chunk_tables = original_content.get('tables', [])

        # collect content
        if chunk_text:
            texts.append(chunk_text)

        images.extend(chunk_images)
        tables.extend(chunk_tables)


        # add citations for every chunk
        doc_id = chunk.get('document_id')
        if doc_id:
            citations.append({
                "chunk_id": chunk.get('id'),
                "document_id": doc_id,
                "filename": filename_map.get(doc_id, "Unknown Document"),
                "page": chunk.get("page_number", "Unknown"),
            })

    return texts, images, tables, citations


def prepare_prompt_and_invoke_llm(user_query: str, texts: List[str], images: List[str], tables: List[str]) -> str:
    """
    Builds system prompt with context and invoke LLM with multimodal support.
    """

    # Build system prompt parts

    prompt_parts = []

    # Main instruction
    prompt_parts.append(
        "You are a helpful AI assistant that answers questions based solely on the provided context. "
        "Your task is to provide accurate, detailed answers using ONLY the information available in the context below.\n\n"
        "IMPORTANT RULES:\n"
        "- Only answer based on the provided context (texts, tables, and images)\n"
        "- If the answer cannot be found in the context, respond with: 'I don't have enough information in the provided context to answer that question.'\n"
        "- Do not use external knowledge or make assumptions beyond what's explicitly stated\n"
        "- When referencing information, be specific and cite relevant parts of the context\n"
        "- Synthesize information from texts, tables, and images to provide comprehensive answers\n\n"
    )
    
    # Add text contexts
    if texts:
        prompt_parts.append("=" * 80)
        prompt_parts.append("CONTEXT DOCUMENTS")
        prompt_parts.append("=" * 80 + "\n")

        for i,text in enumerate(texts,1):
            prompt_parts.append(f"--- Document Chunk {i} ---")
            prompt_parts.append(text.strip())
            prompt_parts.append("") # add blank lines as a seperator
       
    # Add tables if present
    if tables:
        prompt_parts.append("\n" + "=" * 80)
        prompt_parts.append("RELATED TABLES")
        prompt_parts.append("=" * 80)
        prompt_parts.append(
            "The following tables contain structured data that may be relevant to your answer. "
            "Analyze the table contents carefully.\n"
        )
       
        
        for i, table_html in enumerate(tables, 1):
            prompt_parts.append(f"--- Table {i} ---")
            prompt_parts.append(table_html)
            prompt_parts.append("")

     # Reference iamges if present
     # images cannot be added with a string the prompt below hence handling it seperately as LLM has its API structure
    if images: 
        prompt_parts.append("\n" + "=" * 80)
        prompt_parts.append("RELATED IMAGES")
        prompt_parts.append("=" * 80)
        prompt_parts.append(
            f"{len(images)} image(s) will be provided alongside the user's question. "
            "These images may contain diagrams, charts, figures, formulas, or other visual information. "
            "Carefully analyze the visual content when formulating your response. "
            "The images are part of the retrieved context and should be used to answer the question.\n"
        )
    
    # Final Instrcution
    prompt_parts.append("=" * 80)
    prompt_parts.append(
        "Based on all the context provided above (documents, tables, and images), "
        "please answer the user's question accurately and comprehensively."
    )

    prompt_parts.append("=" * 80)

    # Why you need join — because LLM APIs don't accept a list
    system_prompt = "\n".join(prompt_parts)
     
    # The OpenAI API simply does not support images in the system message at all.

    # Build messages for LLM
    messages = [SystemMessage(content=system_prompt)]

    # Create the human message with user query and images
    if images:
        # Multi Modal message: text + images
        content_parts = [{"type": "text", "text": user_query}]

        # Add each image to the content array
        for img_base64 in images:
            # Clean base64 string if it had data URI prefix
            if img_base64.startswith("data:image"):
                img_base64 = img_base64.split(",", 1)[1] # limit to 1 split

            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64, {img_base64}"}
                }
            )

        messages.append(HumanMessage(content=content_parts))
    else:
        # Text-only message
        messages.append(HumanMessage(content=user_query))

    # Invoke LLM and return response
    print(
        f"🤖 Invoking LLM with {len(messages)} messages ({len(texts)} texts, {len(tables)} tables, {len(images)} images)..."
    )
    response = openAI["chat_llm"].invoke(messages)

    return response.content