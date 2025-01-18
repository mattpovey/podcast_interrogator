from elasticsearch import Elasticsearch
import re
import sys

# Initialize Elasticsearch client
es = Elasticsearch(
    hosts=["http://127.0.0.1:9200"],  # URL to the Elasticsearch instance
    basic_auth=("elastic", "UX9Rghbvu0tBGNUFMqzb")
)

def validate_query(query):
    # Check if the query contains only letters, spaces, and logical operators (AND, OR, NOT)
    if not re.match("^[a-zA-Z\s()]+(AND|OR|NOT)?$", query):
        return False, "Invalid characters in the query. Only letters, spaces, and logical operators (AND, OR, NOT) are allowed."

    # Check if the query has no more than 6 terms
    terms = re.findall(r'\b\w+\b', query)
    if len(terms) > 6:
        return False, "The query contains too many terms. A maximum of 6 terms are allowed."

    return True, ""

def search(query, scope, search_type, index_name="rihpodcast"):
    print(f"The scope of this search is: {scope}")
    
    # Build the elasticsearch query based on search type
    if search_type == "phrase":
        print(f"Searching for phrase: \"{query}\"...\n")
        es_query = {
            "query": {
                "match_phrase": {
                    scope: query
                }
            }
        }
    elif search_type in ["boolean", "combined"]:
        print(f"Searching for complex query: \"{query}\"...\n")
        es_query = {
            "query": {
                "query_string": {
                    "query": query,
                    "fields": [scope] if search_type == "boolean" else ["*"],
                    "default_operator": "AND"
                }
            }
        }
    else:  # simple search
        print(f"Searching for: \"{query}\"...\n")
        es_query = {
            "query": {
                "match": {
                    scope: {
                        "query": query,
                        "operator": "and"
                    }
                }
            }
        }

    # Execute search
    search_results = es.search(
        index=index_name,
        body=es_query,
        size=10000  # Adjust this value based on your needs
    )

    hits = search_results['hits']['hits']
    
    if len(hits) == 0:
        print("No results found")
        return {}

    # Format results similar to original code
    results_dict = {}
    
    for hit in hits:
        source = hit['_source']
        episode_number = source['episode']
        
        if episode_number in results_dict:
            results_dict[episode_number]['lines'].append(
                (source['line_index'], source['timecode'], source['text'])
            )
        else:
            results_dict[episode_number] = {
                'filename': source['filename'],
                'title': source['title'],
                'date': source['date'],
                'url': source['url'],
                'lines': [(source['line_index'], source['timecode'], source['text'])]
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
        link = url + "?t=" + str(total_seconds) + ".0"
    else:
        print("regex failed")
        link = url
    return link

def main():
    if len(sys.argv) < 4:
        print("Usage: search_script.py <query> <scope> <search_type>")
        print("Scope can be one of: title, text or date (YYYY-MM-DD)")
        print("Search type can be one of: simple, phrase, boolean or combined")
        print("A combined function allows you to search for a phrase in combination with other terms in a boolean query")
        return
    
    query = sys.argv[1]
    scope = sys.argv[2]
    search_type = sys.argv[3]

    valid_query, error_message = validate_query(query)
    if not valid_query:
        print(error_message)
        return

    final_results = search(query, scope, search_type)
    
    total_files = len(final_results)
    print(f"Number of matching files: {total_files}\n")

    total_lines = sum(len(episode_dict['lines']) for episode_dict in final_results.values())
    print(f"A total of {total_lines} lines matched the query in {total_files} files.\n")

    for episode_number, episode_dict in final_results.items():
        #print(f"Episode number {episode_number} titled \"{episode_dict['title']}\" which was published on {episode_dict['date']}.\n")
        #print(f"Filename: {episode_dict['filename']}")
        #print(f"Link: {episode_dict['url']}")
              
        matching_lines_count = len(episode_dict['lines'])
        print(f"There are {matching_lines_count} matching lines in episode number {episode_number} titled \"{episode_dict['title']}\" which was published on {episode_dict['date']}.\n")

        if matching_lines_count == 0:
            print("No matching lines found\n")
        else:
            print("Matching lines:")
            url = episode_dict['url']
            for line_index, timecode, line in episode_dict['lines']:
                match_line = f"Line {line_index} ({timecode}): {line}"
                link = generate_link(match_line, url)
                print(f"Line {line_index} ({timecode}): {line}. Listen here: {url} {link}")
            print("\n")


if __name__ == "__main__":
    main()
