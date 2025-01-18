# Index a set of podcast transcripts using Whoosh
# The text files are transcriptions of a podcast and are stored in the srt 
# format with snippets of text attached to time-codes. Each file is the 
# transcript of a single episode. This script will only perform the indexing
# of the text files. The search functionality is provided a separate script

# 20230406 - Updated version with more metadata. 
# 20250105 - Updated to use Elasticsearch instead of Whoosh
# 20250105 - Updated to use PostgreSQL instead of CSV
# 20250105 - Updated to use title as primary identifier instead of episode number
# 20250105 - Updated to handle filenames without episode numbers
# 20250105 - Updated to drop and recreate index on each run

# Import the required modules
import os
import re
import srt
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import datetime
from libPodSemSearch import get_db_connection
from dotenv import load_dotenv
from config import (
    tscript_dir,
)
from frontend.app.config.app_settings import ELASTICSEARCH_INDEX

# Replace Whoosh-specific imports with Elasticsearch setup
es = Elasticsearch(
    hosts=["http://127.0.0.1:9200"],  # URL to the Elasticsearch instance
    basic_auth=("elastic", "UX9Rghbvu0tBGNUFMqzb")
)

def ep_metadata(directory):
    # Scan the directory containing the transcript files and create a dict of
    # the files and their metadata. 
    metadata = {}
    n_files = 0
    n_srtLines = 0
    skipped_files = []

    # Get the metadata from the database
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        for filename in os.listdir(tscript_dir):
            # Check that the file is not a directory
            if os.path.isfile(os.path.join(tscript_dir, filename)):
                try:
                    with open(os.path.join(tscript_dir, filename), 'r') as f:
                        ###############################################################
                        # THE FIRST SECTION WORKS ON THE FILE SYSTEM FILENAME
                        ###############################################################

                        # Extract the date and title from the filename using a regex
                        # New format: YYYYMMDD_TITLE.srt
                        match = re.search(r"^(\d{8})_(.*)\.srt$", filename)
                        if match is None:
                            print(f"Warning: {filename} does not match the expected filename format")
                            skipped_files.append((filename, "Invalid filename format"))
                            continue

                        # Get the episode metadata from the database using the filename
                        cursor.execute("""
                            SELECT title, description, url 
                            FROM episodes 
                            WHERE filename = %s
                        """, (filename,))
                        db_record = cursor.fetchone()
                        
                        if not db_record:
                            print(f"Warning: No database record found for {filename}")
                            skipped_files.append((filename, "No database record"))
                            continue
                            
                        title, description, ep_url = db_record

                        # Extract date from filename
                        date = match.group(1)
                        
                        # Add all metadata except that associated with lines of text
                        # in the srt file to the metadata dict
                        metadata[title] = {
                            'filename': filename,
                            'description': description,
                            'title': title,
                            'date': date,
                            'url': ep_url,
                            'text': []
                        }
                        ###############################################################
                        # BUT THE LINES ARE EXTRACTED FROM SRT FILES
                        ###############################################################
                        n = 0
                        try:
                            with open(os.path.join(tscript_dir, filename), 'r') as f_srt:
                                # Try to detect if this is a valid SRT file
                                content = f_srt.read()
                                if not content.strip().startswith('1'):
                                    raise srt.SRTParseError("File does not appear to be in SRT format", 0, 0, content[:100])
                                
                                # Reset file pointer and parse
                                f_srt.seek(0)
                                srt_lines = list(srt.parse(f_srt))
                                
                                for line in srt_lines:
                                    index = str(line.index)
                                    tc_start = srt.timedelta_to_srt_timestamp(line.start)
                                    tc_end = srt.timedelta_to_srt_timestamp(line.end)
                                    line_content = line.content
                                    timecode = tc_start + " --> " + tc_end
                                    metadata[title]['text'].append((index, timecode, line_content))
                                    n += 1
                                n_srtLines += n
                                n_files += 1
                        except (srt.SRTParseError, ValueError) as e:
                            print(f"Warning: Failed to parse {filename} as SRT: {str(e)}")
                            skipped_files.append((filename, f"SRT parse error: {str(e)}"))
                            if title in metadata:
                                del metadata[title]
                            continue
                except Exception as e:
                    print(f"Error processing file {filename}: {str(e)}")
                    skipped_files.append((filename, f"Processing error: {str(e)}"))
                    continue

        print(f"{n_files} files were successfully processed.")
        print(f"{n_srtLines} lines were processed.")
        if skipped_files:
            print("\nSkipped files:")
            for filename, reason in skipped_files:
                print(f"- {filename}: {reason}")
    finally:
        cursor.close()
        connection.close()
    
    return metadata

def create_es_index(index_name=ELASTICSEARCH_INDEX):
    """Create a fresh Elasticsearch index, dropping the existing one if it exists."""
    # Drop existing index if it exists
    if es.indices.exists(index=index_name):
        print(f"Dropping existing index: {index_name}")
        es.indices.delete(index=index_name)
    
    # Create the index with the appropriate mappings
    print(f"Creating new index: {index_name}")
    mapping = {
        "mappings": {
            "properties": {
                "title": {"type": "keyword"},  # Changed to keyword for exact matches
                "description": {"type": "text"},
                "date": {"type": "date"},
                "text": {"type": "text"},
                "line_index": {"type": "keyword"},
                "timecode": {"type": "keyword"},
                "url": {"type": "keyword"},
                "filename": {"type": "keyword"}
            }
        }
    }
    
    es.indices.create(index=index_name, body=mapping)
    return index_name

def index_files(index_name, metadata):
    def generate_actions():
        # Generate the actions for the bulk indexing
        for title, data in metadata.items():
            for line_index, timecode, line in data['text']:
                # Convert date string to ISO format for Elasticsearch
                date_str = data['date']
                date_obj = datetime.datetime.strptime(date_str, "%Y%m%d")
                
                yield {
                    "_index": index_name,
                    "_id": f"{title}_{line_index}",  # Using title instead of episode number
                    "_source": {
                        "title": title,
                        "description": data['description'],
                        "date": date_obj.isoformat(),
                        "text": line,
                        "line_index": line_index,
                        "timecode": timecode,
                        "url": data['url'],
                        "filename": data['filename']
                    }
                }

    # Perform bulk indexing
    success, failed = bulk(es, generate_actions())
    print(f"Indexed {success} documents. Failed: {failed}")

def main():
    # Fetch metadata (unchanged)
    print("Fetching metadata...")
    metadata = ep_metadata(tscript_dir)

    # Create/verify index
    print("Creating/verifying Elasticsearch index...")
    index_name = create_es_index()
    print(f"Index created: {index_name}")
    # Index the files
    print("Indexing files...")
    index_files(index_name, metadata)

if __name__ == '__main__':
    main()






