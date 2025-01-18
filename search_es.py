# Search functionality for podcast transcripts using Elasticsearch
# Note: This file doesn't need PostgreSQL modifications as it gets all its data
# from the Elasticsearch index, which is populated by index_es.py
# Updated to use title as primary identifier instead of episode number

from elasticsearch import Elasticsearch
import re
import sys
import os
from dotenv import load_dotenv
from frontend.app.config.app_settings import ELASTICSEARCH_INDEX

# Load environment variables
load_dotenv('.env')

# Initialize Elasticsearch client
es = Elasticsearch(
    hosts=[os.getenv('ELASTICSEARCH_URL', 'http://127.0.0.1:9200')],
    basic_auth=(
        os.getenv('ELASTICSEARCH_USER'),
        os.getenv('ELASTICSEARCH_PASSWORD')
    )
)

def validate_query(query):
    # Simplified validation since Elasticsearch handles more complex queries
    if not query or len(query.strip()) == 0:
        return False, "Query cannot be empty"
    return True, ""

def search(query, field="text", index_name=ELASTICSEARCH_INDEX):
    """
    Enhanced search function using Elasticsearch's query DSL
    
    Parameters:
    - query: search query string
    - field: specific field to search in, or "all" for multi-field search
    - index_name: name of the Elasticsearch index
    """
    print(f"Searching in field(s): {field}")
    print(f"Query: {query}\n")

    # Define the query based on the specified field
    if field == "title":
        es_query = {
            "query": {
                "match": {
                    "title": {
                        "query": query,
                        "operator": "and"
                    }
                }
            }
        }
    elif field == "description":
        es_query = {
            "query": {
                "match": {
                    "description": {
                        "query": query,
                        "operator": "and"
                    }
                }
            }
        }
    elif field == "text":
        es_query = {
            "query": {
                "match": {
                    "text": {
                        "query": query,
                        "operator": "and"
                    }
                }
            }
        }
    elif field == "all":
        # Multi-field search with boosts
        es_query = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "description^2", "text"],
                    "type": "best_fields",
                    "operator": "and"
                }
            }
        }
    else:
        raise ValueError("Invalid field specified for search.")

    # Execute search with highlighting
    search_results = es.search(
        index=index_name,
        body=es_query,
        size=10000
    )

    hits = search_results['hits']['hits']
    
    if len(hits) == 0:
        print("No results found")
        return {}

    # Format results
    results_dict = {}
    
    for hit in hits:
        source = hit['_source']
        title = source['title']  # Using title as identifier
        
        if title in results_dict:
            results_dict[title]['lines'].append(
                (source.get('line_index', ''), source.get('timecode', ''), source.get(field, ''))
            )
        else:
            results_dict[title] = {
                'filename': source.get('filename', ''),
                'title': title,
                'date': source.get('date', ''),
                'url': source.get('url', ''),
                'lines': [(source.get('line_index', ''), source.get('timecode', ''), source.get(field, ''))]
            }
    
    return results_dict

# take a line returned from the search results and generate a 
# link to the podcast episode with a query term enabling the 
# user to jump to 15s before the line in the episode audio
def generate_link(line, url):
    # get the timecode from the line
    pattern = r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})"
    matches = re.search(pattern, line)
    # get the link to the episode

    if matches:
        start_time = matches.group(1)
        print(start_time)
        hours, minutes, seconds_milliseconds = start_time.split(':')
        seconds, milliseconds = seconds_milliseconds.split(',')
        total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000
        # Round total_seconds to the nearest second
        total_seconds = round(total_seconds)
        link = url + "#t=" + str(total_seconds) + ".0"
    else:
        print("regex failed")
        link = url
    return link

def main():
    if len(sys.argv) < 3:
        print("Usage: search_script.py <query> <field>")
        print("Field can be one of: text, title, description, date, all")
        print("Examples:")
        print('  - Simple search: search_script.py "machine learning" text')
        print('  - Phrase search: search_script.py "\\"exact phrase\\"" text')
        print('  - Date search: search_script.py "2023-01-01" date')
        print('  - Multi-field search: search_script.py "AI" all')
        return
    
    query = sys.argv[1]
    field = sys.argv[2].lower()

    valid_query, error_message = validate_query(query)
    if not valid_query:
        print(error_message)
        return

    final_results = search(query, field)
    
    total_files = len(final_results)
    print(f"Number of matching files: {total_files}\n")

    total_lines = sum(len(episode_dict['lines']) for episode_dict in final_results.values())
    print(f"A total of {total_lines} lines matched the query in {total_files} files.\n")

    for title, episode_dict in final_results.items():
        matching_lines_count = len(episode_dict['lines'])
        print(f"There are {matching_lines_count} matching lines in episode titled \"{title}\" which was published on {episode_dict['date']}.\n")

        if matching_lines_count == 0:
            print("No matching lines found\n")
        else:
            print("Matching lines:")
            url = episode_dict['url']
            for line_index, timecode, line in episode_dict['lines']:
                match_line = f"Line {line_index} ({timecode}): {line}"
                link = generate_link(match_line, url)
                print(f"Line {line_index} ({timecode}): {line}. Listen here: {link}")
            print("\n")

if __name__ == "__main__":
    main()
