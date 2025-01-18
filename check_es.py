import os
from elasticsearch import Elasticsearch

# Set up Elasticsearch connection
elastic_password = os.getenv("ELASTIC_PASSWORD")
es = Elasticsearch(
    hosts=["http://127.0.0.1:9200"],
    basic_auth=("elastic", elastic_password)
)

def check_index(index_name):
    try:
        # Get the index mapping (schema)
        mapping = es.indices.get_mapping(index=index_name)
        print(f"Schema for index '{index_name}':")
        print(mapping)

        # Get the first few records
        print(f"\nFirst few records in index '{index_name}':")
        response = es.search(index=index_name, body={"query": {"match_all": {}}}, size=5)
        
        for hit in response['hits']['hits']:
            print(hit['_source'])  # Print the document source

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    index_name = "rihpodcast"  # Change this to your index name
    check_index(index_name) 