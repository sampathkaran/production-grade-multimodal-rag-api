from src.services.llm import openAI
from fastapi import HTTPException
from src.services.supabase import supabase 
from src.rag.retrieval.utils import (
     get_project_settings,
     get_project_document_ids,
     build_context_from_retrieved_chunks,
     prepare_prompt_and_invoke_llm,
     rrf,
     generate_query_variations
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

        # Step 3: Get the strategy
        strategy = project_settings['rag_strategy']
        print(f"\n RAG STRATEGY: {strategy.upper()}")
        
        # Step 3: Generate query embeddings and Perform Vector Search using RPC function
        """
        search through specigic documents to get chunks that are semantically similarly to my query,
        return only hunks above a similarity threshold, sorted relevance, limited to top  N results. 
        """

        if strategy == 'basic': # perform only vector search
            print("Executing: Vector Search")
            retrieved_chunks = vector_search(user_query, document_ids, project_settings)
            print(f"Retrieved {len(retrieved_chunks)} relevant chunks from vector search")
        
        # Step 4: Perform hybrid search
        elif strategy == 'hybrid': # perform both vector and keyword search
            print("Executing: Hybrid Search (Vector + Keyword)")
            retrieved_chunks = hybrid_search(user_query, document_ids, project_settings)
            print(f"📈 Hybrid search returned: {len(retrieved_chunks)} chunks")

        # Step 5: Multi-query vector search
        elif strategy == 'multi-query-vector': # this is reference to knowlegebase component
            print(f"Executing: Multi Query vector Search ({project_settings['number_of_queries']} queries)")
            retrieved_chunks = multi_query_vector_search(user_query, document_ids, project_settings)

        # Step 6: Multi-query hybrid search
        elif strategy == "multi-query-hybrid":
            retrieved_chunks = multi_query_hybrid_search(
                user_query, document_ids, project_settings
            )
            print(f"Multi-query hybrid search resulted in: {len(retrieved_chunks)} chunks")
        
        # Step 7: Selecting top k chunks
        retrieved_chunks = retrieved_chunks[: project_settings["final_context_size"]]


        # Step 8: Build Context from retrieved chunks
        # Format the retrieved chunks into structured context with citations
        texts, images, tables, citations = build_context_from_retrieved_chunks(retrieved_chunks)
        #validate_context(texts, images, tables, citations)

       # Step 9: Build  system prompt with injected context
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

def keyword_search(user_query, document_ids, project_settings):
    """Execute keyword search"""
    keyword_search_result_chunks = supabase.rpc('keyword_search_document_chunks', {
        'query_text' : user_query,
        'filter_document_ids': document_ids,
        'chunks_per_search': project_settings['chunks_per_search']
    }).execute()
    
    return (
        keyword_search_result_chunks.data if keyword_search_result_chunks.data else []
    )

def hybrid_search(user_query:str, document_ids: List[str], project_settings: dict) -> List[Dict]:
    """Execute hybrid search by combining vector and keyword results"""

    # Get results from both search methods
    vector_results = vector_search(user_query, document_ids, project_settings)
    keyword_results = keyword_search(user_query, document_ids, project_settings)\

    print(f"📈 Vector search returned: {len(vector_results)} chunks")
    print(f"📈 Keyword search returned: {len(keyword_results)} chunks")

    
    # Combine using RRF with configured weights
    return rrf(
        [vector_results, keyword_results], [project_settings['vector_weight'], project_settings['keyword_weight']]
    )
  
def multi_query_vector_search(user_query, document_ids, project_settings):
    """Execute multi-query vector search using query variations"""
    queries = generate_query_variations(
        user_query, project_settings["number_of_queries"]
    )

    print(f"Generated chunks for {len(queries)} query variations")

    all_chunks = []
    for i, query in enumerate(queries,1):
        chunks = vector_search(query, document_ids, project_settings)
        all_chunks.append(chunks)
        print(
            f"Vector search for query {i}/{len(queries)}: {query} resulted in: {len(chunks)} chunks"
        )

    final_chunks = rrf(all_chunks)
    print(f"RRF Fusion returned {len(final_chunks)} chunks")
    return final_chunks

def multi_query_hybrid_search(user_query, document_ids, project_settings):
    """Execute multi-query hybrid search using query variations"""
    queries = generate_query_variations(
        user_query, project_settings["number_of_queries"]
    )
    print(f"Generated {len(queries)} query variations for hybrid search")

    all_chunks = []
    for index, query in enumerate(queries):
        chunks = hybrid_search(query, document_ids, project_settings)
        all_chunks.append(chunks)
        print(
            f"Hybrid search for query {index+1}/{len(queries)}: {query} resulted in: {len(chunks)} chunks"
        )

    final_chunks = rrf(all_chunks)
    print(f"RRF Fusion returned {len(final_chunks)} chunks")
    return final_chunks
  
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