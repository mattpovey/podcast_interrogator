from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import logging
from elasticsearch import Elasticsearch
import chromadb
import os
from datetime import datetime
import openai
import json
import random
from dotenv import load_dotenv
from config.search_examples import FULLTEXT_EXAMPLES, SEMANTIC_EXAMPLES, RAG_EXAMPLES
from config.app_settings import (
    SHOW_PROGRESS, POD_PREFIX, ELASTICSEARCH_INDEX, SEMANTIC_COLLECTION,
    LLM_PROVIDER, LLM_API_BASE, LLM_MODEL, LLM_TEMPERATURE, LLM_TOP_P
)
from config.config_validator import validate_config
import logging.handlers

# Load environment variables from .env file
load_dotenv('./.env')

# Validate configuration
if not validate_config():
    raise ValueError("Invalid configuration. Please check the error messages above.")

# Initialize Flask app with explicit template and static folders
app = Flask(__name__,
           template_folder='templates',
           static_folder='static')

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging with a RotatingFileHandler
log_handler = logging.handlers.RotatingFileHandler(
    'logs/search_queries.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    delay=True
)
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
log_handler.setLevel(logging.INFO)

# Configure the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(log_handler)

# Initialize Elasticsearch client with environment variables
es_config = {
    'hosts': [os.getenv('ELASTICSEARCH_URL')]
}

# Only add basic auth if credentials are provided
es_user = os.getenv('ELASTICSEARCH_USER')
es_pass = os.getenv('ELASTICSEARCH_PASSWORD')
if es_user and es_pass:
    es_config['basic_auth'] = (es_user, es_pass)

es = Elasticsearch(**es_config)

# Initialize ChromaDB client with environment variables
try:
    chroma_client = chromadb.HttpClient(
        host=os.getenv('CHROMADB_HOST'),
        port=int(os.getenv('CHROMADB_PORT')),
        ssl=False
    )
except Exception as e:
    logging.warning(f"Failed to initialize ChromaDB client: {str(e)}")
    chroma_client = None

# Initialize LLM client
def create_llm_client():
    """Create OpenAI-compatible client for the configured LLM provider."""
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise ValueError("LLM_API_KEY environment variable not set")
    
    return openai.OpenAI(
        api_key=api_key,
        base_url=os.getenv('LLM_API_BASE', LLM_API_BASE),
    )

def format_date(date_str):
    """Format date string for display."""
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return date.strftime("%B %d, %Y")
    except:
        return date_str

def get_search_queries(query, llm_client):
    """Use LLM to generate semantic search queries based on the user's question."""
    search_prompt = f"""Given a user's history question, create THREE different semantic search queries that will help find relevant information in a podcast transcript database.
The queries should:
1. Look for different aspects of the topic
2. Use natural language
3. Be specific enough to find relevant content
4. Cover complementary aspects of the question
5. Focuses on the core concepts of the question
6. Focus on concepts rather than asking questions

For example, if the user asks "What was the significance of the Battle of Waterloo?", the queries could be:
1. "Battle of Waterloo"
2. "Napoleon"
3. "Wellington"

if the user asks, "Which of Tom or Dom is more sacral?", the queries could be:
1. "Sacral"
2. "Religious importance"
3. "Sacred"

User's question: {query}

You must respond with valid JSON in exactly this format:
{{
    "query1": "first semantic search query",
    "explanation1": "why this query will help",
    "query2": "second semantic search query",
    "explanation2": "why this query will help",
    "query3": "third semantic search query",
    "explanation3": "why this query will help"
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
        result = json.loads(response_text)
        
        return result
        
    except Exception as e:
        # Extract the key topic from the query by removing common question words and phrases
        topic = query.lower()
        topic = topic.replace("what does", "").replace("what did", "")
        topic = topic.replace("how does", "").replace("how did", "")
        topic = topic.replace("who was", "").replace("who is", "")
        topic = topic.replace("when was", "").replace("when did", "")
        topic = topic.replace("where was", "").replace("where did", "")
        topic = topic.replace("why did", "").replace("why was", "")
        topic = topic.replace("the podcast", "").replace("think of", "").replace("talk about", "")
        topic = topic.strip()

        return {
            "query1": topic,
            "explanation1": "Direct search for the main topic",
            "query2": f"historical background {topic}",
            "explanation2": "Looking for historical context",
            "query3": f"significance impact {topic}",
            "explanation3": "Looking for significance and impact"
        }

def create_prompt(original_query, context1, context2, context3):
    """Create a prompt for the LLM using the retrieved contexts."""
    return f"""You are an expert historian tasked with answering questions about history based on content from "The Rest Is History" podcast. 
The podcast is hosted by Tom Holland and Dominic Sandbrook, usually known as Tom and Dom. There are frequenly guests on the podcast. 
Tom and Dom are both historians who have published many books as well as presenting hundreds of episodes of the podcast.
Use the information provided in the FULL context below to answer the question comprehensively. If the contexts don't contain enough information to fully answer the question, say so.

For significant facts or claims in your answer, you should include a citation to the source episode. Citations should be numbered in the format [n](episode_url) and should be placed immediately after the fact they support.

Here are two examples of how to format your answer:

Example 1:
Question: What was the significance of the Battle of Waterloo?
Answer: The Battle of Waterloo marked the final defeat of Napoleon Bonaparte. [n](http://example.com/123) The battle resulted in massive casualties, with over 40,000 dead and wounded. [n](http://example.com/124) The victory by Wellington's forces reshaped the balance of power in Europe. [n](http://example.com/123)

Example 2: 
Question: How did the Roman Empire fall?
Answer: The fall of the Roman Empire was not a single event but a gradual process spanning centuries. [n](http://example.com/45) Economic instability played a major role, with the empire facing severe inflation and trade disruption. [n](http://example.com/46) The increasing reliance on foreign mercenaries also weakened the empire's military foundation. [n](http://example.com/47)

Remember:
1. Provide a comprehensive answer
2. Use quotes from the podcast where possible
3. Consider the full context that is provided to you
4. If the contexts don't contain enough information to answer fully, say so
5. Significant facts should have a citation but your discussion of the subject does not need citations
6. Use this exact format for citations [n](episode_url)
7. Place citations immediately after the fact they support
8. Include a list of the sources used at the end of your answer in the format [Source: Episode Title](episode_url)
9. Take care to use correct markdown formatting
10. If an episode title contains square brackets or parentheses, they must be escaped with backslashes:
    - Replace [ with \\[
    - Replace ] with \\]
    - Replace ( with \\(
    - Replace ) with \\)
    For example: "The Battle \\[Part 1\\] \\(1815\\)" becomes [Source: The Battle \[Part 1\] \(1815\)](url)

Context 1:
{context1}

Context 2:
{context2}

Context 3:
{context3}

Question: {original_query}

Answer: """

def perform_search(collection, query, n_results=15):
    """Perform a single semantic search and return results."""
    return collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )

def log_search(search_type, query):
    """Log search queries with timestamp"""
    logging.info(f"Search Type: {search_type}, Query: {query}")

# Add function to check collection existence
def get_or_verify_collection(name):
    """Get a collection and verify it exists."""
    try:
        # In ChromaDB v0.6.0, list_collections returns just the names
        collections = chroma_client.list_collections()
        logging.info(f"Available collections: {collections}")
        
        if name not in collections:
            raise ValueError(f"Collection {name} not found. Available collections: {collections}")
            
        collection = chroma_client.get_collection(name=name)
        return collection
    except Exception as e:
        logging.error(f"Error accessing collection {name}: {str(e)}")
        raise

def get_random_examples(examples_list, num_examples=3):
    """Get a random selection of example queries."""
    return random.sample(examples_list, min(num_examples, len(examples_list)))

def send_progress_event(event_type, data):
    """Helper function to format SSE messages."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

@app.route('/')
def home():
    provider_name = os.getenv('LLM_PROVIDER', LLM_PROVIDER)
    provider_url = os.getenv('LLM_API_BASE', LLM_API_BASE)
    return render_template('index.html', provider_name=provider_name, provider_url=provider_url)

@app.route('/about')
def about():
    provider_name = os.getenv('LLM_PROVIDER', LLM_PROVIDER)
    provider_url = os.getenv('LLM_API_BASE', LLM_API_BASE)
    return render_template('about.html', provider_name=provider_name, provider_url=provider_url)

@app.route('/search/fulltext')
def fulltext_search_page():
    examples = get_random_examples(FULLTEXT_EXAMPLES)
    return render_template('fulltext_search.html', examples=examples)

@app.route('/search/semantic')
def semantic_search_page():
    examples = get_random_examples(SEMANTIC_EXAMPLES)
    return render_template('semantic_search.html', examples=examples)

@app.route('/search/rag')
def rag_search_page():
    examples = get_random_examples(RAG_EXAMPLES)
    return render_template('rag_search.html', examples=examples)

# API endpoints
@app.route('/api/search/elastic', methods=['POST'])
def elastic_search():
    query = request.form.get('query')
    field = request.form.get('field', 'text')
    page = int(request.form.get('page', 1))
    page_size = 20  # Number of results per page
    
    if not query:
        return jsonify({'error': 'Query cannot be empty'}), 400

    log_search('elastic', query)
    
    try:
        # Check if index exists
        if not es.indices.exists(index=ELASTICSEARCH_INDEX):
            return jsonify({"error": "Elasticsearch index not found"}), 404

        # Get index mapping to check available fields
        mapping = es.indices.get_mapping(index=ELASTICSEARCH_INDEX)
        properties = mapping[ELASTICSEARCH_INDEX]['mappings'].get('properties', {})
        
        # Log available fields
        logging.info(f"Available fields in index: {list(properties.keys())}")
        
        # Map frontend field names to actual index field names
        field_mapping = {
            'text': 'text',
            'title': 'title',
            'description': 'description'
        }
        
        # Get the correct field name or default to 'text'
        es_field = field_mapping.get(field, 'text')
        
        # First, get total count of matches
        count_query = {
            "query": {
                "match": {
                    es_field: {
                        "query": query,
                        "operator": "and"
                    }
                }
            }
        }
        
        count_result = es.count(index=ELASTICSEARCH_INDEX, body=count_query)
        total_hits = count_result['count']
        
        # Calculate pagination values
        from_ = (page - 1) * page_size
        total_pages = (total_hits + page_size - 1) // page_size
        
        # Build the search query with pagination
        es_query = {
            "query": {
                "match": {
                    es_field: {
                        "query": query,
                        "operator": "and"
                    }
                }
            },
            "highlight": {
                "fields": {
                    es_field: {
                        "fragment_size": 1000,
                        "number_of_fragments": 1,
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"],
                        "type": "unified",
                        "no_match_size": 1000
                    }
                },
                "boundary_scanner": "sentence",
                "boundary_scanner_locale": "en-US",
                "fragment_size": 1000,
                "number_of_fragments": 1,
                "no_match_size": 1000
            },
            "_source": ["title", "date", "timecode", "text", "url", "line_index"],
            "sort": [
                {"_score": "desc"},
                {"line_index": "asc"}
            ],
            "size": page_size,
            "from": from_
        }

        # Execute search
        results = es.search(index=ELASTICSEARCH_INDEX, body=es_query)
        logging.info(f"Search query executed successfully. Showing results {from_ + 1}-{min(from_ + page_size, total_hits)} out of {total_hits} total matches")
        
        # Add pagination info to response
        response = {
            'hits': results['hits'],
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'total_hits': total_hits,
                'page_size': page_size,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        logging.error(f"Elasticsearch error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search/semantic', methods=['POST'])
def semantic_search():
    query = request.form.get('query')
    n_results = min(int(request.form.get('n_results', 15)), 50)  # Cap at 50 results
    
    if not query:
        return jsonify({'error': 'Query cannot be empty'}), 400

    log_search('semantic', query)
    
    try:
        if chroma_client is None:
            return jsonify({'error': 'Semantic search is currently unavailable'}), 503
            
        # Get the collection
        try:
            collection = get_or_verify_collection(SEMANTIC_COLLECTION)
            logging.info(f"Successfully connected to ChromaDB collection")
        except Exception as e:
            logging.error(f"Error connecting to ChromaDB collection: {str(e)}")
            return jsonify({'error': f'Database connection error: {str(e)}'}), 503
        
        # Perform semantic search
        try:
            results = perform_search(collection, query, n_results)
            logging.info(f"Semantic search returned {len(results['documents'][0])} results")
            
            if not results['documents'][0]:
                logging.warning(f"No results found for semantic search query")
                return jsonify({'error': 'No relevant information found in the podcast transcripts'}), 404
            
            return jsonify(results)
            
        except Exception as e:
            logging.error(f"Error performing semantic search: {str(e)}")
            return jsonify({'error': f'Search error: {str(e)}'}), 500
        
    except Exception as e:
        logging.error(f"Unexpected error in semantic_search: {str(e)}")
        return jsonify({'error': str(e)}), 500

def format_context(documents, metadatas, collection):
    """Format search results with context."""
    formatted = []
    # Only process the first 3 results for context
    for doc, meta in list(zip(documents[0], metadatas[0]))[:3]:
        # Escape both square brackets and parentheses in title
        title = meta.get('title', 'Unknown Episode')
        title = title.replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)')
        url = meta.get('url', '')
        line_index = meta.get('line_index', 0)
        
        # Get surrounding context (previous and next snippets)
        try:
            # Query for previous line
            prev_results = None
            if line_index > 0:
                try:
                    prev_results = collection.query(
                        query_texts=[""],  # Empty query to match based on metadata
                        where={
                            "$and": [
                                {"title": meta.get('title')},
                                {"line_index": line_index - 1}
                            ]
                        },
                        n_results=1
                    )
                except Exception as e:
                    logging.debug(f"No previous context found: {str(e)}")

            # Query for next line
            next_results = None
            try:
                next_results = collection.query(
                    query_texts=[""],  # Empty query to match based on metadata
                    where={
                        "$and": [
                            {"title": meta.get('title')},
                            {"line_index": line_index + 1}
                        ]
                    },
                    n_results=1
                )
            except Exception as e:
                logging.debug(f"No next context found: {str(e)}")
            
            # Build the complete context
            context_parts = []
            
            # Add previous context if available
            if prev_results and prev_results.get('documents') and prev_results['documents'][0]:
                context_parts.append(f"[Previous] {prev_results['documents'][0][0]}")
            
            # Add the main snippet
            context_parts.append(doc)
            
            # Add next context if available
            if next_results and next_results.get('documents') and next_results['documents'][0]:
                context_parts.append(f"[Next] {next_results['documents'][0][0]}")
            
            # Add timestamp to URL if available
            if meta.get('start_timecode'):
                try:
                    time_parts = meta['start_timecode'].split(',')[0].split(':')
                    hours, minutes, seconds = map(int, time_parts)
                    total_seconds = hours * 3600 + minutes * 60 + seconds
                    url = f"{url}#t={total_seconds}.0" if url else ''
                except (ValueError, IndexError):
                    pass
            
            # Join context parts and create the formatted string separately to avoid f-string backslash issues
            context_text = '\n'.join(context_parts)
            source_text = f"[Source: {title}]({url})"
            formatted.append(f"{context_text}\n{source_text}")
            
        except Exception as e:
            # If fetching context fails, just use the original snippet
            logging.error(f"Error fetching context: {str(e)}")
            source_text = f"[Source: {title}]({url})"
            formatted.append(f"{doc}\n{source_text}")
    
    # Add remaining results without context
    for doc, meta in list(zip(documents[0], metadatas[0]))[3:]:
        title = meta.get('title', 'Unknown Episode')
        title = title.replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)')
        url = meta.get('url', '')
        
        # Add timestamp to URL if available
        if meta.get('start_timecode'):
            try:
                time_parts = meta['start_timecode'].split(',')[0].split(':')
                hours, minutes, seconds = map(int, time_parts)
                total_seconds = hours * 3600 + minutes * 60 + seconds
                url = f"{url}#t={total_seconds}.0" if url else ''
            except (ValueError, IndexError):
                pass
        
        source_text = f"[Source: {title}]({url})"
        formatted.append(f"{doc}\n{source_text}")
    
    return "\n\n".join(formatted)

@app.route('/api/search/rag', methods=['POST'])
def rag_search():
    query = request.form.get('query')
    n_results = min(int(request.form.get('n_results', 15)), 50)  # Cap at 50 results
    
    if not query:
        return jsonify({'error': 'Query cannot be empty'}), 400

    log_search('rag', query)

    def generate():
        # Initialize timing tracking
        timings = {
            'start': datetime.now(),
            'phases': {},
            'last_phase_start': datetime.now()
        }

        try:
            if chroma_client is None:
                yield send_progress_event('error', {'message': 'RAG search is currently unavailable'})
                return
                
            # Get the collection
            try:
                yield send_progress_event('progress', {
                    'phase': 'init', 
                    'message': 'Initializing search...'
                })
                collection = get_or_verify_collection(SEMANTIC_COLLECTION)
                logging.info(f"Successfully connected to ChromaDB collection")
            except Exception as e:
                logging.error(f"Error connecting to ChromaDB collection: {str(e)}")
                yield send_progress_event('error', {'message': f'Database connection error: {str(e)}'})
                return
            
            # Create LLM client
            try:
                # Record timing for previous phase
                phase_duration = (datetime.now() - timings['last_phase_start']).total_seconds() * 1000
                timings['phases']['init'] = phase_duration
                timings['last_phase_start'] = datetime.now()
                logging.info(f"Phase timing - init: {phase_duration:.2f}ms")

                yield send_progress_event('progress', {
                    'phase': 'llm_init', 
                    'message': 'Initializing AI model...'
                })
                llm_client = create_llm_client()
                logging.info("Successfully created LLM client")
            except Exception as e:
                logging.error(f"Error creating LLM client: {str(e)}")
                yield send_progress_event('error', {'message': f'LLM client error: {str(e)}'})
                return
            
            # Generate search queries
            try:
                # Record timing for previous phase
                phase_duration = (datetime.now() - timings['last_phase_start']).total_seconds() * 1000
                timings['phases']['llm_init'] = phase_duration
                timings['last_phase_start'] = datetime.now()
                logging.info(f"Phase timing - llm_init: {phase_duration:.2f}ms")

                yield send_progress_event('progress', {
                    'phase': 'query_gen', 
                    'message': 'Generating search queries...'
                })
                search_queries = get_search_queries(query, llm_client)
                yield send_progress_event('progress', {
                    'phase': 'query_gen_complete',
                    'message': 'Generated search queries:',
                    'queries': search_queries
                })
                logging.info("Successfully generated search queries")
            except Exception as e:
                logging.error(f"Error generating search queries: {str(e)}")
                yield send_progress_event('error', {'message': f'Error generating search queries: {str(e)}'})
                return
            
            # Perform semantic searches
            try:
                # Record timing for previous phase
                phase_duration = (datetime.now() - timings['last_phase_start']).total_seconds() * 1000
                timings['phases']['query_gen'] = phase_duration
                timings['last_phase_start'] = datetime.now()
                logging.info(f"Phase timing - query_gen: {phase_duration:.2f}ms")

                yield send_progress_event('progress', {
                    'phase': 'search', 
                    'message': 'Searching podcast transcripts...'
                })
                results1 = perform_search(collection, search_queries['query1'], n_results)
                results2 = perform_search(collection, search_queries['query2'], n_results)
                results3 = perform_search(collection, search_queries['query3'], n_results)
                yield send_progress_event('progress', {
                    'phase': 'search_complete', 
                    'message': 'Found relevant podcast segments'
                })
                logging.info(f"Successfully performed semantic searches")
            except Exception as e:
                logging.error(f"Error performing semantic searches: {str(e)}")
                yield send_progress_event('error', {'message': f'Search error: {str(e)}'})
                return
            
            # Create context from search results
            try:
                # Record timing for previous phase
                phase_duration = (datetime.now() - timings['last_phase_start']).total_seconds() * 1000
                timings['phases']['search'] = phase_duration
                timings['last_phase_start'] = datetime.now()
                logging.info(f"Phase timing - search: {phase_duration:.2f}ms")

                yield send_progress_event('progress', {
                    'phase': 'context', 
                    'message': 'Processing search results...'
                })
                context1 = format_context(results1['documents'], results1['metadatas'], collection)
                context2 = format_context(results2['documents'], results2['metadatas'], collection)
                context3 = format_context(results3['documents'], results3['metadatas'], collection)
                yield send_progress_event('progress', {
                    'phase': 'context_complete', 
                    'message': 'Processed search results'
                })
                logging.info("Successfully created context from search results")
            except Exception as e:
                logging.error(f"Error creating context: {str(e)}")
                yield send_progress_event('error', {'message': f'Error processing search results: {str(e)}'})
                return
            
            # Generate LLM response
            try:
                # Record timing for previous phase
                phase_duration = (datetime.now() - timings['last_phase_start']).total_seconds() * 1000
                timings['phases']['context'] = phase_duration
                timings['last_phase_start'] = datetime.now()
                logging.info(f"Phase timing - context: {phase_duration:.2f}ms")

                yield send_progress_event('progress', {
                    'phase': 'answer', 
                    'message': 'Generating answer...'
                })
                prompt = create_prompt(query, context1, context2, context3)
                model_name = os.getenv('LLM_MODEL', LLM_MODEL)
                provider_name = os.getenv('LLM_PROVIDER', LLM_PROVIDER)
                provider_url = os.getenv('LLM_API_BASE', LLM_API_BASE)
                
                if not model_name:
                    raise ValueError("LLM_MODEL environment variable is not set")
                    
                response = llm_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a knowledgeable historian and fan of the podcast, The Rest is History,who provides accurate, well-reasoned answers based on podcast content."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=LLM_TEMPERATURE,
                    top_p=LLM_TOP_P
                )
                logging.info("Successfully generated LLM response")
            except Exception as e:
                logging.error(f"Error generating LLM response: {str(e)}")
                yield send_progress_event('error', {'message': f'Error generating answer: {str(e)}'})
                return
            
            # Record timing for final phase and total time
            phase_duration = (datetime.now() - timings['last_phase_start']).total_seconds() * 1000
            timings['phases']['answer'] = phase_duration
            total_duration = (datetime.now() - timings['start']).total_seconds() * 1000
            logging.info(f"Phase timing - answer: {phase_duration:.2f}ms")
            logging.info(f"Total execution time: {total_duration:.2f}ms")
            
            # Combine all results
            processed_results = {
                'llm_response': response.choices[0].message.content,
                'model_info': {
                    'provider': provider_name,
                    'provider_url': provider_url,
                    'model': model_name
                },
                'search_queries': search_queries,
                'results1': {
                    'documents': results1['documents'],
                    'metadatas': results1['metadatas'],
                    'distances': results1['distances']
                },
                'results2': {
                    'documents': results2['documents'],
                    'metadatas': results2['metadatas'],
                    'distances': results2['distances']
                },
                'results3': {
                    'documents': results3['documents'],
                    'metadatas': results3['metadatas'],
                    'distances': results3['distances']
                },
                'show_progress': SHOW_PROGRESS,
                'timings': timings if SHOW_PROGRESS else None
            }
            
            yield send_progress_event('complete', processed_results)
            logging.info("Successfully completed RAG search")
            
        except Exception as e:
            logging.error(f"Unexpected error in rag_search: {str(e)}")
            yield send_progress_event('error', {'message': str(e)})
            return

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/recommendations', methods=['GET'])
def recommendations_page():
    return render_template('recommend.html')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000) 