from src.services.llm import openAI
from fastapi import HTTPException
from src.services.supabase import supabase 
from src.rag.retrieval.utils import (
     get_project_settings,
     get_project_document_ids,
     build_context_from_retrieved_chunks,
     prepare_prompt_and_invoke_llm
)

from typing import List, Dict 
from src.rag.retrieval.utils import get_project_settings


def retrieve_context(project_id, user_query):
    try:
        """
        RAG Retrieval Pipeline Steps:
            Step 1: Get user's project settings from the database to know similarity threshold, number of queries, etc.
            Step 2: Retrieve the document IDs for thge current project so we can narrow down the search scope to only project
            step 3: Perform vector search using the RPC function to find the most relevant chunks 

        """

        # Step 1: Get user's project settings from the database to know similarity threshold, number of queries, etc.
        project_settings = get_project_settings(project_id)
        #print("Project settings: ", project_settings)

        # Step 2: Retrieve the document IDs for the current project.
        document_ids = get_project_document_ids(project_id)
        print("Found document IDs: ", len(document_ids)) 
        
        # Step 3: Generate query embeddings and Perform Vector Search using RPC function
        """
        search through specigic documents to get chunks that are semantically similarly to my query,
        return only hunks above a similarity threshold, sorted relevance, limited to top  N results. 
        """
        retrieved_chunks = vector_search(user_query, document_ids, project_settings)
        print(f"Retrieved {len(retrieved_chunks)} relevant chunks from vector search")

        # Step 4: Build Context from retrieved chunks
        # Format the retrieved chunks into structured context with citations
        texts, images, tables, citations = build_context_from_retrieved_chunks(retrieved_chunks)
        #validate_context(texts, images, tables, citations)

       # Step 5: Build  system prompt with injected context
       # Add the retrieved document context to the system prompts so the LLM can answer based on the documenmt
    
        return texts, images, tables, citations

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed in RAG's Retrieval: {str(e)}"
        )

def vector_search (user_query, document_ids, project_settings):

        user_query_embedding = openAI['embeddings']. embed_query(user_query)
        result = supabase.rpc('vector_search_document_chunks',{
                'query_embedding': user_query_embedding,
                'filter_document_ids': document_ids, 
                'match_threshold': project_settings['similarity_threshold'],
                'chunks_per_search': project_settings['chunks_per_search']
        }).execute()

        return result.data if result.data else []

def validate_context(texts: List[str], images: List[str], tables: List[str], citations: List[Dict]) -> None:
    """Validate and print context data in a readable format"""
    print("\n" + "="*80)
    print("📦 CONTEXT VALIDATION")
    print("="*80)
    
    # Texts - SHOW FULL TEXT
    print(f"\n📝 TEXTS: {len(texts)} chunks")
    for i, text in enumerate(texts, 1):
        print(f"\n{'='*80}")
        print(f"CHUNK [{i}] - {len(text)} characters")
        print(f"{'='*80}")
        print(text)  # ✅ Full text, no truncation
        print(f"{'='*80}\n")
    
    # Images
    print(f"\n🖼️  IMAGES: {len(images)}")
    for i, img in enumerate(images, 1):
        img_preview = str(img)[:60] + ('...' if len(str(img)) > 60 else '')
        print(f"  [{i}] {img_preview}")
    
    # Tables
    print(f"\n📊 TABLES: {len(tables)}")
    for i, table in enumerate(tables, 1):
        if isinstance(table, dict):
            rows = len(table.get('rows', []))
            cols = len(table.get('headers', []))
            print(f"  [{i}] {rows} rows × {cols} cols")
        else:
            print(f"  [{i}] Type: {type(table).__name__}")
    
    # Citations
    print(f"\n📚 CITATIONS: {len(citations)}")
    for i, cite in enumerate(citations, 1):
        chunk_id = cite['chunk_id'][:8] if cite.get('chunk_id') else 'N/A'
        print(f"  [{i}] {cite['filename']} (pg.{cite['page']}) | chunk: {chunk_id}...")
    
    # Summary
    total_chars = sum(len(text) for text in texts)
    print(f"\n{'='*80}")
    print(f"✅ Total: {len(texts)} texts ({total_chars:,} chars), {len(images)} images, {len(tables)} tables, {len(citations)} citations")
    print("="*80 + "\n")