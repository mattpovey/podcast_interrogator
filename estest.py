from elasticsearch import Elasticsearch

# Connect to Elasticsearch
es = Elasticsearch(
    hosts=["http://127.0.0.1:9200"],  # URL to the Elasticsearch instance
    basic_auth=("elastic", "UX9Rghbvu0tBGNUFMqzb")
)

# Check connection
if es.ping():
    print("Connected to Elasticsearch")
else:
    print("Could not connect to Elasticsearch")