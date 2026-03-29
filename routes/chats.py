from fastapi import APIRouter, HTTPException, Depends
from database import supabase
from auth import get_current_user
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from dotenv import load_dotenv
from typing import Dict, List, Tuple

load_dotenv()

# initialize LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)

embedding_model = OpenAIEmbeddings(
                    model="text-embedding-3-large",
                    dimensions=1536)


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

       if not deleted_chat_result.data:
        raise HTTPException(status_code=404, detail="Chat not found or access denied")

       
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


## remove this later validation

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

####

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

        # 2. Load project settings
        # we need to load the settings selected by the user within the project like chunk_size, similarity threshold
        settings = load_project_settings(project_id)

        # 3. Get document ID for this project
        # This narrows our search scope to only documents that are part of specific projects as all documents in every project uses shared DB
        document_ids = get_document_ids(project_id)

        # Get the search strategy
        strategy = settings.get('rag_strategy', "")
       
        # 4. Generate query embeddings and perform vector search
        # convert user question into vector so we can perform similarity search
        # Perform the vector search using the RPC function
        # Search through specific documents to get the chunks that are semantically similar to the query
        #  return only chunks above a simialrity threshold, sorted by relevance, limited to the top N results
         
        # setup a control flow based on the project settings strategy

        if strategy == 'basic':
            retrieved_chunks = vector_search(user_query=message, document_ids= document_ids, project_settings=settings)
            print(f"Retrieved {len(retrieved_chunks)} chunks from vector search")

        elif strategy == 'hybrid':
            print("Executing: Hybrid Search(Vector + Keyword)")
            retrieved_chunks = hybrid_search(message, document_ids, settings)
            print(f"Retrieved {len(retrieved_chunks)} chunks from hybrid search")
        
        elif strategy == 'multi-query-vector':
            print(f"📈 Executing: Multi-Query Vector Search ({settings['number_of_queries']} queries)")
            queries = generate_query_variations(message, settings['number_of_queries'])
            print(f"🔄 Generated queries: {queries}")
            all_results = []
            for i, query in enumerate(queries,1):
                retrieved_chunk= vector_search(user_query=query, document_ids= document_ids, project_settings=settings)
                print(f"📈 Query {i} '{query}' returned: {len(retrieved_chunk)} chunks")
                all_results.append(retrieved_chunk)
            retrieved_chunks = rrf_rank_and_fuse(all_results)
            print(f"🔗 RRF fusion returned: {len(retrieved_chunks)} chunks")
        
        elif strategy == 'multi-query-hybrid':
            print(f"📈 Executing: Multi-Query Hybrid Search ({settings['number_of_queries']} queries, Vector + Keyword)")
            queries = generate_query_variations(message, settings['number_of_queries'])
            print(f"🔄 Generated queries: {queries}")

            # Stage 1: Per-query hybrid fusion
            all_hybrid_results = []
            for i, query in enumerate(queries,1):
                print(f"\n  Query {i}: '{query}'")
                # Use the existing hybrid_search function which handles weights
                retrieved_chunk = hybrid_search(query, document_ids, settings)
                print(f"Hybrid fusion returned: {len(retrieved_chunk)} chunks")
                all_hybrid_results.append(retrieved_chunk)
            # Stage 2: Cross-query fusion (equal weights across queries by default)
            print(f"\nFinal RRF fusion across {len(all_hybrid_results)} queries")
            retrieved_chunks = rrf_rank_and_fuse(all_hybrid_results)
            print(f"📊 Final result: {len(retrieved_chunks)} chunks")
        
        # Trim the chunks by the final context size in settings
        retrieved_chunks=retrieved_chunks[:settings['final_context_size']]
        print(f"Trimmed to final context size: {len(retrieved_chunks)} chunks")

        # 5. Build the context from retrieved chunks
        # Format the retrieved chunks into structured context with citations
        texts, images, tables, citations = build_context(retrieved_chunks)

        # validation
        validate_context(texts,images, tables, citations)

        # 6. Build the system prompt with injected context
        # Add retrieved document context to system prompt so the LLM can answer based on the documents
        print(f"🤖 Preparing context and calling LLM...")
        ai_response = prepare_prompt_and_invoke_llm(
            user_query = message,
            texts= texts,
            images= images,
            tables= tables
        )        

        # 8. Save AI message with citations to the database
        # Store the AI's response along with citations
        # Save the AI message in DB
        ai_message_result = supabase.table("messages").insert({
            "content": ai_response,
            "role": 'assistant',
            'chat_id': chat_id,
            'clerk_id': clerk_id,
            'citations': citations         
        }).execute()

        ai_message = ai_message_result.data[0]
        print(f"AI message saved: {ai_message['id']}")

        # Return the data
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


def load_project_settings(project_id:str)->Dict:
    """Function to load user applied project settings"""
    print("Fetching project settings...")
    result = supabase.table('project_settings').select('*').eq('project_id', project_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Project settings not found")

    settings = result.data[0]
    print("Settings retrieved")
    return settings

def get_document_ids(project_id:str)->List[str]:
    """Get all the document ids belonging to the project"""
    print("Fetching project document ids ...")
    document_result = supabase.table('project_documents').select("id").eq('project_id', project_id).execute()

    document_ids = [doc['id'] for doc in document_result.data]
    print(f"Found {len(document_ids)} documents ")
    return document_ids


def vector_search(user_query:str, document_ids: List[str], project_settings: dict) -> List[Dict]:
    """Execute the vector search"""
    query_embedding = embedding_model.embed_query(user_query)

    result = supabase.rpc('vector_search_document_chunks', 
    {
    'query_embedding' : query_embedding, 
    'filter_document_ids': document_ids, 
    'match_threshold' : project_settings['similarity_threshold'], 
    'chunks_per_search' : project_settings['chunks_per_search']
    }).execute()

    return result.data if result.data else []

# keyword search function
def keyword_search(user_query:str, document_ids: List[str], project_settings: dict) -> List[Dict]:
    """Execute keyword search"""
    result = supabase.rpc('keyword_search_document_chunks', {
       "query_text" : user_query, 
       "filter_document_ids" : document_ids, 
       "chunks_per_search" : project_settings['chunks_per_search']
    }).execute()

    return result.data if result.data else []

# Hybrid search function
def hybrid_search(message:str, document_ids: List[str], settings: dict) -> List[Dict]:
    """Execute hybrid search by combining vector and keyword search"""
    # Get results from both search methods
    keyword_results = keyword_search(user_query=message, document_ids= document_ids, project_settings=settings)
    vector_results = vector_search(user_query=message, document_ids= document_ids, project_settings=settings)

    print(f"📈 Vector search returned: {len(vector_results)} chunks")
    print(f"📈 Keyword search returned: {len(keyword_results)} chunks")
    
    # Combine using RRF with configured weights
    return rrf_rank_and_fuse(
        [vector_results, keyword_results],
        [settings['vector_weight'], settings['keyword_weight']]
    )



def build_context(chunks: List[Dict]) -> Tuple[List[str], List[str], List[str], List[Dict]]:
    """
    This get all the necessary information from the chunks, structure it and send it for LLM

    Returns:
      Tuple of (text, images, tables, citations)
    """
    if not chunks:
        return [], [], [], []
    
    texts = []
    images = []
    tables = []
    citations = []

    # Batch fetch all filenames in ONE query
    # as the document chunk does not have file name so using document_id we search the filename in project documents
    doc_ids = [chunk['document_id'] for chunk in chunks if chunk.get('document_id')]
    unique_doc_ids: List[str] = list(set(doc_ids))

    filename_map = {}

    if unique_doc_ids:
        result = supabase.table('project_documents')\
                 .select('id, filename')\
                 .in_('id', unique_doc_ids).execute()
        
        filename_map = {doc['id'] : doc['filename'] for doc in result.data} 
        # result {'10474554-d0ae-4ff1-8c2e-fb15bdb6906f': 'attention-is-all-you-need.pdf'}


    # Process each chunk
    for chunk in chunks:
        original_content = chunk['original_content']

        # Extract content from chunks
        chunk_text = original_content.get('text', "")
        chunk_images = original_content.get('images', [])
        chunk_tables = original_content.get('tables', [])

        # collect the content
        # Note in original content column the text datatype is str whereas images and tables are list
        if chunk_text:
            texts.append(chunk_text)
        images.extend(chunk_images)
        tables.extend(chunk_tables)

        # Add citations for every chunk
        doc_id = chunk.get('document_id')
        if doc_id:
            citations.append({
                "chunk_id": chunk.get('id', ""),
                "document_id": doc_id,
                "filename": filename_map.get(doc_id, "Unknown Document"),
                #filename_map.get("10474554-d0ae-4ff1-8c2e-fb15bdb6906f")
                "page": chunk.get('page_number', 'unknown')
            })  

    return texts, images, tables, citations # python automatically return value seperated as commas a tuple

def prepare_prompt_and_invoke_llm(
    user_query: str,
    texts: List[str],
    images: List[str],
    tables: List[str]) -> str:

    """
    Build system prompt with context and invokes LLM with multimodal support

    Args:
     user_query: The user's question
     texts: List of text chunks from retrieval
     images: List of base64 encoded images
     tables: List of HTML table strings

    Returns:
      AI Response string 
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

        for i, text in enumerate(texts):
            prompt_parts.append(f"--- Document Chunk {i} ---")
            prompt_parts.append(text.strip())
            prompt_parts.append("")
        
    # Add Tables if present
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
    
    # Reference Images if present
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
    
    # Final Instruction
    prompt_parts.append("=" * 80)
    prompt_parts.append(
        "Based on all the context provided above (documents, tables, and images), "
        "please answer the user's question accurately and comprehensively."
    )
    prompt_parts.append("=" * 80)

    system_prompt = "\n".join(prompt_parts) # takes all the string in the list and combine as 1 string

    # Build messages for LLM
    messages = [SystemMessage(content=system_prompt)]

    # Create human message with use query and images base64
    if images:
        # Multimodal message query + image
        content_parts = [{"type": "text", "text": user_query}]

        # Add each image to the content array
        for img_base64 in images:
            # Clean base64 string if it has data URI prefix
            if img_base64.startswith('data:image'):
                img_base64 = img_base64.split(',', 1)[1]
            
            content_parts.append(
                {"type": "image_url",
                  "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}
                })
        
        messages.append(HumanMessage(content=content_parts))

    else:
        # Text-only message
        messages.append(HumanMessage(content=user_query))
    
    # Invoke LLM and return response
    print(f"🤖 Invoking LLM with {len(messages)} messages ({len(texts)} texts, {len(tables)} tables, {len(images)} images)...")

    response = llm.invoke(messages)

    return response.content

# RRF function
def rrf_rank_and_fuse(search_results_list: List[List[Dict]], weights: List[float]=None, k: int=60) -> List[Dict]:
    if not search_results_list or not any(search_results_list):
        return []
    if weights is None:
        # calculate equal share
        """
        [1/2] * 2 
        [0.5] * 2
        [0.5, 0.5]
        """
        weights  = [1.0/len(search_results_list)] * len(search_results_list)

    chunk_scores = {} # calculate the RRF score per chunk
    all_chunks = {} # stores the actual chunk data

    for search_idx, results in enumerate(search_results_list):
        weight = weights[search_idx] # to extract weight
        
        for position, chunk in enumerate(results):
            chunk_id = chunk.get('id')
            if not chunk_id:
                continue

            rrf_score = weight * (1.0/ (k + position + 1))
           
            # if it a duplicate chunk we need to add its RRF score
            if chunk_id in chunk_scores:
                chunk_scores[chunk_id] = chunk_scores[chunk_id]  + rrf_score

            else:
                chunk_scores[chunk_id] = rrf_score
                all_chunks[chunk_id] = chunk
    #sorted(iterable, key=function, reverse=bool)
    """
    chunk_scores.keys()
    ["chunk-A", "chunk-B", "chunk-C", "chunk-D"]
    
    lambda cid: chunk_scores[cid] as we want to sort by RRF score not by the ids
    for each key lookup in score 
    "chunk-A" → chunk_scores["chunk-A"] → 0.01626
    "chunk-B" → chunk_scores["chunk-B"] → 0.01626
    "chunk-C" → chunk_scores["chunk-C"] → 0.00794
    "chunk-D" → chunk_scores["chunk-D"] → 0.00476
   
    reverse=True
    high first

    """

    sorted_chunk_ids = sorted(    # sort the RRF scores
              chunk_scores.keys(), key= lambda x : chunk_scores[x], reverse=True
        ) 

    return [all_chunks[chunk_id] for chunk_id in sorted_chunk_ids]

class QueryVariations(BaseModel):
    queries: List[str]
def generate_query_variations(original_query: str, num_queries: int =3) -> List[str]:
    """Generate query variations using LLM"""
    system_prompt= f"""Generate {num_queries-1} alternative ways to phrase this question for document search. Use different keywords and synonyms while maintaining the same intent. Return exactly {num_queries-1} variations."""
    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Original query: {original_query}")
        ] 

        structured_llm = llm.with_structured_output(QueryVariations)
        result = structured_llm.invoke(messages)

        return [original_query] + result.queries[:num_queries-1]
    
    except Exception:
        return [original_query]