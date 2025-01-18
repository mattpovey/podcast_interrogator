# RIH Search

A search application for Rest Is History podcast content, featuring full-text, semantic, and AI-powered search capabilities.

## Configuration

The application uses a combination of environment variables and configuration files to manage its settings:

### Environment Variables

Copy `.env.template` to `.env` and configure the following required variables:

```bash
# Required API Keys
SAMBANOVA_API_KEY=       # Your SambaNova API key
SEMANTIC_SEARCH_MODEL=   # Your semantic search model name

# Elasticsearch Configuration
ELASTICSEARCH_PASSWORD=   # Your Elasticsearch password
```

Other environment variables have default values but can be customized as needed. See `.env.template` for all available options.

### Application Settings

Non-sensitive configuration is stored in `app/config/app_settings.py`, including:

- UI Configuration
- Podcast Configuration
- Directory Settings
- ChromaDB Settings
- Transcript Server Configuration

### Search Examples

Example queries for different search types are configured in `app/config/search_examples.py`.

## Running with Docker

1. Copy `.env.template` to `.env` and configure the required variables
2. Run the application:
```bash
docker-compose up -d
```

## Development

For development:

1. Set `FLASK_ENV=development` in your `.env` file
2. Install dependencies: `pip install -r requirements.txt`
3. Run the Flask development server: `flask run`

## Security Notes

- Never commit `.env` files containing secrets
- Keep API keys and passwords secure
- Use environment variables for all sensitive information 