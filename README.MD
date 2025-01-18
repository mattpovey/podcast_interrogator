# Podcast Interrogator

A system for downloading, transcribing, and semantically searching podcast content. It provides a modern web interface for exploring podcast content through full-text search, semantic search, and AI-powered question answering.

## Overview

The system operates in two modes:

1. **Development Mode**: For configuring the application for a podcast, downloading episodes, generating transcripts, and building search indices
2. **Production Mode**: For deploying the web frontend as a containerized application using pre-built data volumes

## Development Mode Setup

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- ffmpeg
- whisper.cpp (for transcription)
- PostgreSQL
- Elasticsearch
- ChromaDB
- OpenAI-compatible LLM API access (e.g., OpenAI, SambaNova, etc.)

### Configuration

1. Create and activate a Python virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy and configure environment files:
```bash
cp .env.template .env
cp frontend/.env.template frontend/.env
```

4. Edit configuration files:
- `.env`: Set API keys and database credentials
- `config.py`: Configure podcast-specific settings
- `frontend/app/config/app_settings.py`: Configure application settings

5. Configure LLM Provider:
In `frontend/.env`, set up your preferred OpenAI-compatible LLM provider:

For OpenAI:
```bash
LLM_PROVIDER=OpenAI
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4-turbo-preview
LLM_API_KEY=your_api_key_here
```

For SambaNova:
```bash
LLM_PROVIDER=SambaNova
LLM_API_BASE=https://api.sambanova.ai/v1
LLM_MODEL=sambanova-model-name
LLM_API_KEY=your_api_key_here
```

For other providers, use their respective API base URLs and model names.

### Processing Pipeline

1. **Download and Transcribe Episodes**:
```bash
python fetchtoTscript.py
```
This will:
- Download podcast episodes from the RSS feed
- Convert audio to WAV format
- Generate transcripts using whisper.cpp
- Store episode metadata in PostgreSQL

2. **Build Search Indices**:
```bash
python index_es.py     # Build Elasticsearch index
python index_chroma.py # Build vector database
```

3. **Test Development Server**:
```bash
cd frontend
flask run
```

## Production Mode Deployment

### Prerequisites

- Docker and Docker Compose
- Data volumes from development environment

### Initial Deployment

1. Export data volumes from development:
```bash
cd frontend/vol_export
./export_vols.sh
```

2. Transfer volume archives to production server:
- `esdata.tar.gz`: Elasticsearch index
- `pgdata.tar.gz`: PostgreSQL data
- `chroma-data.tar.gz`: Vector database
- `app-data.tar.gz`: Application data

3. On production server:
```bash
# Import data volumes
cd frontend/vol_export
./import_vols.sh

# Start services
docker compose up -d
```

### Updates

1. On development machine:
- Process new episodes
- Update indices
- Export updated volumes

2. On production server:
- Stop services
- Import new volumes
- Restart services

## Architecture

- **Frontend**: Flask web application
- **Search**: 
  - Elasticsearch for full-text search
  - ChromaDB for semantic search
- **Database**: PostgreSQL for episode metadata
- **AI**: SambaNova for question answering

## Environment Variables

Key variables that must be set in `.env`:
- `ELASTICSEARCH_URL`
- `ELASTICSEARCH_USER`
- `ELASTICSEARCH_PASSWORD`
- `CHROMADB_HOST`
- `CHROMADB_PORT`
- `LLM_PROVIDER`
- `LLM_API_KEY`
- `LLM_API_BASE`
- `LLM_MODEL`
- `DOCKER_PREFIX` (defaults to 'podcast-search')

## Version History

### Current Version (January 2025)
- Containerized deployment
- Elasticsearch for full-text search
- ChromaDB for semantic search
- Support for any OpenAI-compatible LLM provider
- Volume-based updates

### Original Version (October 2023)
- Local development only
- Whoosh for text search
- Basic ChromaDB integration
- Support for GPT and Mistral
- Manual updates required
- No containerization

## License

[Insert License Information] 