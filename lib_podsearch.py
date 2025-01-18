import openai
import chromadb
from datetime import datetime
import textwrap
import json
from config import max_tokens
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

def create_chroma_client():
    """Create a ChromaDB client connected to the server."""
    return chromadb.HttpClient(
        host=os.getenv('CHROMADB_HOST', '127.0.0.1'),
        port=os.getenv('CHROMADB_PORT', '8000'),
        ssl=False
    )

def create_llm_client():
    """Create OpenAI-compatible client for SambaNova."""
    api_key = os.getenv("SAMBANOVA_API_KEY")
    if not api_key:
        raise ValueError("SAMBANOVA_API_KEY environment variable not set")
    
    return openai.OpenAI(
        api_key=api_key,
        base_url="https://api.sambanova.ai/v1",
    )

def format_date(date_str):
    """Format date string for display."""
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return date.strftime("%B %d, %Y")
    except:
        return date_str

def format_sources(results):
    """Format the source information from ChromaDB results."""
    sources = []
    for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
        source = (
            f"From episode: {metadata['title']}\n"
            f"Date: {format_date(metadata['date'])}\n"
            f"Timecode: {metadata['start_timecode']} --> {metadata['end_timecode']}\n"
            f"URL: {metadata['url']}#t={int(float(metadata['start_timecode'].split(':')[0])*3600 + float(metadata['start_timecode'].split(':')[1])*60 + float(metadata['start_timecode'].split(':')[2].split(',')[0]))}\n"
            f"Passage: {doc}\n"
        )
        sources.append(source)
    return "\n---\n".join(sources)

def get_search_queries(query, llm_client):
    """Use LLM to generate semantic search queries based on the user's question."""
    search_prompt = f"""Given a user's history question, create TWO different semantic search queries that will help find relevant information in a podcast transcript database.
The queries should:
1. Look for different aspects of the topic
2. Use natural language
3. Be specific enough to find relevant content
4. Cover complementary aspects of the question
5. Focuses on the core concepts of the question

User's question: {query}

You must respond with valid JSON in exactly this format:
{{
    "query1": "first semantic search query",
    "explanation1": "why this query will help",
    "query2": "second semantic search query",
    "explanation2": "why this query will help"
}}

Do not include any other text before or after the JSON."""

    try:
        response = llm_client.chat.completions.create(
            model=os.getenv('SEMANTIC_SEARCH_MODEL'),
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates effective semantic search queries. Always respond with valid JSON."},
                {"role": "user", "content": search_prompt}
            ],
            temperature=0.1,
            top_p=0.1
        )
        
        response_text = response.choices[0].message.content.strip()
        
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    raise Exception("Could not parse JSON from response")
            else:
                raise Exception("No JSON found in response")
        
        required_fields = ['query1', 'explanation1', 'query2', 'explanation2']
        if not all(field in result for field in required_fields):
            raise Exception("Response missing required fields")
        
        print("\nGenerated search queries:")
        print(f"1. {result['query1']}")
        print(f"   Reason: {result['explanation1']}")
        print(f"2. {result['query2']}")
        print(f"   Reason: {result['explanation2']}\n")
        return result
        
    except Exception as e:
        print(f"Error generating search queries: {e}")
        print("Falling back to default queries...")
        return {
            "query1": f"key events and facts about {query}",
            "explanation1": "Looking for main historical facts",
            "query2": f"analysis and significance of {query}",
            "explanation2": "Looking for historical analysis and importance"
        }

def create_prompt(original_query, context1, context2):
    """Create a prompt for the LLM using the retrieved contexts."""
    return f"""You are an expert historian tasked with answering questions about history based on content from "The Rest Is History" podcast. 
Use the information provided in BOTH contexts below to answer the question comprehensively. If the contexts don't contain enough information to fully answer the question, say so.
Be specific and cite episodes when possible. Synthesize information from both contexts when relevant.

Context 1:
{context1}

Context 2:
{context2}

Question: {original_query}

Answer: """

def perform_search(collection, query, n_results=3):
    """Perform a single semantic search and return formatted results."""
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    
    if not results['documents']:
        return "No relevant passages found."
    
    return format_sources(results)

def rag_search(query, n_results=3, collection_name="rihpodcast_semantic"):
    """Perform RAG search using ChromaDB and LLM with multiple search queries."""
    chroma_client = create_chroma_client()
    llm_client = create_llm_client()
    
    try:
        collection = chroma_client.get_collection(name=collection_name)
    except Exception as e:
        print(f"Error: Collection '{collection_name}' not found.")
        return
    
    search_queries = get_search_queries(query, llm_client)
    
    context1 = perform_search(collection, search_queries['query1'], n_results)
    context2 = perform_search(collection, search_queries['query2'], n_results)
    
    if context1 == "No relevant passages found." and context2 == "No relevant passages found.":
        print("No relevant passages found for either search query.")
        return
    
    prompt = create_prompt(query, context1, context2)
    
    try:
        response = llm_client.chat.completions.create(
            model='Meta-Llama-3.1-8B-Instruct',
            messages=[
                {"role": "system", "content": "You are a knowledgeable historian who provides accurate, well-reasoned answers based on podcast content."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            top_p=0.1
        )
        
        print("\nAnswer from podcast content:")
        print("=" * 80)
        print(response.choices[0].message.content)
        print("=" * 80)
        
        print("\nSources from first search query:")
        print("=" * 80)
        print(context1)
        
        print("\nSources from second search query:")
        print("=" * 80)
        print(context2)
        
    except Exception as e:
        print(f"Error getting LLM response: {e}") 