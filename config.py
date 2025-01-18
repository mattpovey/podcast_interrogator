# PODCAST
pod_prefix="your_podcast_name"
feed_url = 'your_podcast_rss_feed_url'

# LLM Settings
max_tokens=240

# DIRECTORIES
tscript_dir=f'{pod_prefix}/transcripts'
audio_dir = f'{pod_prefix}/audio'
wav_dir = f'{pod_prefix}/wav'
index_dir = f'{pod_prefix}/indexdir'

# CHROMA
chromadb_name = f'{pod_prefix}/chroma.db'
chroma_collection = f'{pod_prefix}_{max_tokens}T_Collection'
collection_metadata = {"hnsw:space": "cosine", "model.max_seq_length": max_tokens}

# Transcript server configuration
TRANSCRIPT_SERVER_URL = "your_transcription_server_url"
TRANSCRIPT_SERVER_ENABLED = False
TRANSCRIPT_MODEL = "medium"
TRANSCRIPT_LANGUAGE = "en"
TRANSCRIPT_OUTPUT_FORMAT = "srt"
TRANSCRIPT_TRANSLATE = False




