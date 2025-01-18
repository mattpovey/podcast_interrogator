document.addEventListener('DOMContentLoaded', function() {
    // Handle suggestion box clicks for all search types
    const suggestionBoxes = document.querySelectorAll('.suggestion-box');
    suggestionBoxes.forEach(box => {
        box.addEventListener('click', function() {
            const prompt = this.getAttribute('data-prompt');
            // Find the closest form and get its ID
            const form = this.closest('form');
            if (!form) return;
            
            // Map form IDs to their corresponding input IDs
            const inputMap = {
                'elastic-search-form': 'elastic-query',
                'semantic-search-form': 'semantic-query',
                'rag-search-form': 'rag-query'
            };
            
            const inputId = inputMap[form.id];
            if (inputId) {
                const input = document.getElementById(inputId);
                if (input) {
                    input.value = prompt;
                    input.focus();
                }
            }
        });
    });

    // Handle Elasticsearch search
    const elasticForm = document.getElementById('elastic-search-form');
    const elasticResults = document.getElementById('elastic-results');
    if (elasticForm && elasticResults) {
        let currentPage = 1;

        function performSearch(page = 1) {
            const submitButton = elasticForm.querySelector('button[type="submit"]');
            const spinner = elasticForm.querySelector('.fa-spinner');
            submitButton.disabled = true;
            spinner.classList.remove('d-none');
            
            const query = document.getElementById('elastic-query').value;
            const field = "text";
            
            elasticResults.innerHTML = '<div class="loading">Searching...</div>';
            
            fetch('/api/search/elastic', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `query=${encodeURIComponent(query)}&field=${encodeURIComponent(field)}&page=${page}`
            })
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    currentPage = page;
                    displayElasticResults(data, elasticResults);
                } else {
                    elasticResults.innerHTML = `<div class="error-message">${data.error}</div>`;
                }
            })
            .catch(error => {
                console.error('Search error:', error);
                elasticResults.innerHTML = '<div class="error-message">An error occurred while searching.</div>';
            })
            .finally(() => {
                submitButton.disabled = false;
                spinner.classList.add('d-none');
            });
        }

        elasticForm.addEventListener('submit', function(e) {
            e.preventDefault();
            currentPage = 1;
            performSearch(currentPage);
        });

        // Function to create pagination controls
        function createPaginationControls(pagination) {
            const totalPages = pagination.total_pages;
            if (totalPages <= 1) return '';

            let controls = '<div class="pagination justify-content-center mt-4">';
            
            // Previous button
            controls += `
                <button class="btn btn-outline-primary me-2" 
                        onclick="window.scrollTo(0, 0); performSearch(${currentPage - 1})"
                        ${!pagination.has_prev ? 'disabled' : ''}>
                    Previous
                </button>`;

            // Page indicator
            controls += `
                <span class="btn btn-outline-secondary me-2">
                    Page ${pagination.current_page} of ${totalPages}
                </span>`;

            // Next button
            controls += `
                <button class="btn btn-outline-primary"
                        onclick="window.scrollTo(0, 0); performSearch(${currentPage + 1})"
                        ${!pagination.has_next ? 'disabled' : ''}>
                    Next
                </button>`;

            controls += '</div>';
            return controls;
        }

        // Update display function to handle pagination
        function displayElasticResults(data, elasticResults) {
            if (!data.hits || !data.hits.hits || data.hits.hits.length === 0) {
                elasticResults.innerHTML = '<div class="alert alert-info">No results found.</div>';
                return;
            }

            // Group results by episode title
            const episodeResults = {};
            let totalMentions = data.pagination.total_hits;
            data.hits.hits.forEach(hit => {
                const source = hit._source;
                const highlight = hit.highlight;
                const title = source.title;

                if (!episodeResults[title]) {
                    episodeResults[title] = {
                        title: title,
                        date: source.date,
                        url: source.url,
                        matches: []
                    };
                }

                // Add each highlighted fragment as a separate match
                if (highlight && highlight.text) {
                    highlight.text.forEach((fragment, index) => {
                        episodeResults[title].matches.push({
                            text: fragment,
                            timecode: source.timecode,
                            line_index: source.line_index,
                            full_text: source.text
                        });
                    });
                } else {
                    // If no highlight, use the full text
                    episodeResults[title].matches.push({
                        text: source.text,
                        timecode: source.timecode,
                        line_index: source.line_index,
                        full_text: source.text
                    });
                }
            });

            // Convert grouped results to HTML
            const resultsHtml = Object.values(episodeResults).map(episode => {
                const matchesHtml = episode.matches.map(match => {
                    const displayText = match.text || match.full_text;
                    const seconds = timecodeToSeconds(match.timecode);
                    const audioUrl = episode.url ? `${episode.url}#t=${seconds}.0` : '';
                    
                    return `
                        <div class="match-item">
                            ${match.timecode ? `<div class="timecode">Time: ${match.timecode}</div>` : ''}
                            <p class="search-result-text">${displayText}</p>
                            ${audioUrl ? `<a href="${audioUrl}" target="_blank" class="btn btn-sm btn-outline-primary">Listen to this section</a>` : ''}
                        </div>
                    `;
                }).join('');

                return `
                    <div class="result-item">
                        <h5>${episode.title}</h5>
                        ${episode.date ? `<div class="date">Date: ${episode.date}</div>` : ''}
                        <div class="matches">
                            ${matchesHtml}
                        </div>
                        ${episode.url ? `<a href="${episode.url}" target="_blank" class="btn btn-sm btn-outline-primary">Listen to Episode</a>` : ''}
                    </div>
                `;
            }).join('');

            // Calculate the range of results being shown
            const startResult = (data.pagination.current_page - 1) * data.pagination.page_size + 1;
            const endResult = Math.min(startResult + data.pagination.page_size - 1, data.pagination.total_hits);

            elasticResults.innerHTML = `
                <div class="alert alert-info mb-4">
                    Found ${totalMentions} mention${totalMentions !== 1 ? 's' : ''} across all episodes
                    <br>
                    <small>Showing results ${startResult}-${endResult}</small>
                </div>
                ${resultsHtml}
                ${createPaginationControls(data.pagination)}
            `;

            // Make performSearch available to the pagination buttons
            window.performSearch = performSearch;
        }
    }

    // Handle Semantic search
    const semanticForm = document.getElementById('semantic-search-form');
    const semanticResults = document.getElementById('semantic-results');

    if (semanticForm && semanticResults) {
        semanticForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const submitButton = semanticForm.querySelector('button[type="submit"]');
            const spinner = semanticForm.querySelector('.fa-spinner');
            submitButton.disabled = true;
            spinner.classList.remove('d-none');
            
            const query = document.getElementById('semantic-query').value;
            const n_results = document.getElementById('semantic-num-results').value;
            
            semanticResults.innerHTML = '<div class="loading">Searching...</div>';
            
            try {
                const response = await fetch('/api/search/semantic', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `query=${encodeURIComponent(query)}&n_results=${encodeURIComponent(n_results)}`
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    displaySemanticResults(data, semanticResults);
                } else {
                    semanticResults.innerHTML = `<div class="error-message">${data.error}</div>`;
                }
            } catch (error) {
                console.error('Search error:', error);
                semanticResults.innerHTML = '<div class="error-message">An error occurred while searching.</div>';
            } finally {
                submitButton.disabled = false;
                spinner.classList.add('d-none');
            }
        });
    }

    // Handle RAG search
    const ragForm = document.getElementById('rag-search-form');
    const ragResults = document.getElementById('rag-results');
    if (ragForm && ragResults) {
        // Helper function to scroll to an element smoothly
        function scrollToElement(element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        // Helper function to format time duration
        function formatDuration(ms) {
            if (ms < 1000) return `${ms}ms`;
            return `${(ms / 1000).toFixed(2)}s`;
        }

        ragForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const submitButton = ragForm.querySelector('button[type="submit"]');
            const spinner = ragForm.querySelector('.fa-spinner');
            submitButton.disabled = true;
            spinner.classList.remove('d-none');
            
            const query = document.getElementById('rag-query').value;
            
            // Initialize timing tracking
            const timings = {
                start: Date.now(),
                phases: {},
                lastPhaseStart: Date.now()
            };
            
            // Create progress container with conditional progress elements
            ragResults.innerHTML = `
                <div class="progress-container">
                    <div class="progress-status alert alert-info">
                        <div class="spinner-border spinner-border-sm" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <span class="status-message ms-2">Processing your question...</span>
                    </div>
                    <div class="search-queries mt-3 d-none">
                        <h5>Search Queries:</h5>
                        <div class="queries-list"></div>
                    </div>
                    <div class="timings mt-3 d-none">
                        <h5>Process Timings:</h5>
                        <div class="timings-list"></div>
                    </div>
                </div>
                <div class="search-results mt-4"></div>
            `;
            
            // Scroll to the progress container initially
            const progressContainer = ragResults.querySelector('.progress-container');
            scrollToElement(progressContainer);
            
            const progressStatus = ragResults.querySelector('.progress-status');
            const searchQueries = ragResults.querySelector('.search-queries');
            const searchResults = ragResults.querySelector('.search-results');
            const timingsList = ragResults.querySelector('.timings-list');
            
            try {
                // Create EventSource for SSE with POST request
                const response = await fetch('/api/search/rag', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Accept': 'text/event-stream'
                    },
                    body: `query=${encodeURIComponent(query)}`
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (true) {
                    const {value, done} = await reader.read();
                    if (done) break;
                    
                    buffer += decoder.decode(value, {stream: true});
                    const lines = buffer.split('\n\n');
                    buffer = lines.pop() || '';

                    for (const line of lines) {
                        if (!line.trim()) continue;  // Skip empty lines
                        
                        // Parse the event data
                        const eventData = line.split('\n');
                        if (eventData.length < 2) continue;  // Skip malformed events
                        
                        const eventType = eventData[0].replace('event: ', '');
                        const jsonData = eventData[1].replace('data: ', '');
                        
                        try {
                            const data = JSON.parse(jsonData);

                            switch (eventType) {
                                case 'progress':
                                    const statusMessage = progressStatus.querySelector('.status-message');
                                    statusMessage.textContent = data.message;
                                    scrollToElement(progressStatus);
                                    
                                    // Record timing for the previous phase
                                    if (data.phase && data.phase !== 'init') {
                                        const now = Date.now();
                                        const duration = now - timings.lastPhaseStart;
                                        timings.phases[data.phase] = duration;
                                        timings.lastPhaseStart = now;
                                    }
                                    
                                    if (data.phase === 'query_gen_complete' && data.queries) {
                                        searchQueries.classList.remove('d-none');
                                        const queriesList = searchQueries.querySelector('.queries-list');
                                        queriesList.innerHTML = `
                                            <div class="card">
                                                <div class="card-body">
                                                    <ol class="mb-0">
                                                        <li><strong>${data.queries.query1}</strong><br><small class="text-muted">${data.queries.explanation1}</small></li>
                                                        <li><strong>${data.queries.query2}</strong><br><small class="text-muted">${data.queries.explanation2}</small></li>
                                                        <li><strong>${data.queries.query3}</strong><br><small class="text-muted">${data.queries.explanation3}</small></li>
                                                    </ol>
                                                </div>
                                            </div>
                                        `;
                                        scrollToElement(searchQueries);
                                    }
                                    break;

                                case 'error':
                                    throw new Error(data.message || 'Unknown error occurred');

                                case 'complete':
                                    // Display timings if enabled and timing data is provided
                                    if (data.show_progress && data.timings) {
                                        const timingsDiv = ragResults.querySelector('.timings');
                                        timingsDiv.classList.remove('d-none');
                                        timingsList.innerHTML = `
                                            <div class="card">
                                                <div class="card-body">
                                                    <ul class="list-unstyled mb-0">
                                                        ${Object.entries(data.timings.phases).map(([phase, duration]) => `
                                                            <li><strong>${phase}:</strong> ${formatDuration(duration)}</li>
                                                        `).join('')}
                                                        <li class="mt-2 pt-2 border-top"><strong>Total Time:</strong> ${formatDuration((Date.now() - timings.start))}</li>
                                                    </ul>
                                                </div>
                                            </div>
                                        `;
                                    }
                                    
                                    displayRagResults(data, searchResults);
                                    progressStatus.classList.remove('alert-info');
                                    progressStatus.classList.add('alert-success');
                                    progressStatus.innerHTML = '<i class="fas fa-check-circle"></i> <span class="ms-2">Search complete!</span>';
                                    
                                    // Scroll to the answer section
                                    const answerSection = searchResults.querySelector('.card');
                                    if (answerSection) {
                                        scrollToElement(answerSection);
                                    }
                                    break;
                            }
                        } catch (error) {
                            console.error('Error parsing event data:', error);
                        }
                    }
                }
                
            } catch (error) {
                console.error('Search error:', error);
                ragResults.innerHTML = `
                    <div class="alert alert-danger">
                        <h5>An error occurred while processing your question</h5>
                        <p>Details: ${error.message || 'Unknown error'}</p>
                        <p>Please try again or contact support if the problem persists.</p>
                    </div>
                `;
                scrollToElement(ragResults.querySelector('.alert-danger'));
            } finally {
                submitButton.disabled = false;
                spinner.classList.add('d-none');
            }
        });
    }

    // Function to convert timecode to seconds
    function timecodeToSeconds(timecode) {
        if (!timecode) return 0;
        
        // Handle different timecode formats
        let match = timecode.match(/(\d{2}):(\d{2}):(\d{2})(?:,(\d{3}))?/);
        if (!match) return 0;
        
        const hours = parseInt(match[1]);
        const minutes = parseInt(match[2]);
        const seconds = parseInt(match[3]);
        const milliseconds = match[4] ? parseInt(match[4]) : 0;
        
        return Math.floor(hours * 3600 + minutes * 60 + seconds + milliseconds / 1000);
    }

    // Display Elasticsearch results
    function displayElasticResults(data, elasticResults) {
        if (!data.hits || data.hits.length === 0) {
            elasticResults.innerHTML = '<div class="alert alert-info">No results found.</div>';
            return;
        }

        // Group results by episode title
        const episodeResults = {};
        let totalMentions = 0;
        data.hits.forEach(hit => {
            const source = hit._source;
            const highlight = hit.highlight;
            const title = source.title;

            if (!episodeResults[title]) {
                episodeResults[title] = {
                    title: title,
                    date: source.date,
                    url: source.url,
                    matches: []
                };
            }

            // Add each highlighted fragment as a separate match
            if (highlight && highlight.text) {
                highlight.text.forEach((fragment, index) => {
                    totalMentions++;
                    episodeResults[title].matches.push({
                        text: fragment,
                        timecode: source.timecode,
                        line_index: source.line_index,
                        full_text: source.text
                    });
                });
            } else {
                // If no highlight, use the full text
                totalMentions++;
                episodeResults[title].matches.push({
                    text: source.text,
                    timecode: source.timecode,
                    line_index: source.line_index,
                    full_text: source.text
                });
            }
        });

        // Convert grouped results to HTML
        const resultsHtml = Object.values(episodeResults).map(episode => {
            const matchesHtml = episode.matches.map(match => {
                // Use the highlighted text if available, otherwise use the full text
                const displayText = match.text || match.full_text;
                const seconds = timecodeToSeconds(match.timecode);
                const audioUrl = episode.url ? `${episode.url}#t=${seconds}.0` : '';
                
                return `
                    <div class="match-item">
                        ${match.timecode ? `<div class="timecode">Time: ${match.timecode}</div>` : ''}
                        <p class="search-result-text">${displayText}</p>
                        ${audioUrl ? `<a href="${audioUrl}" target="_blank" class="btn btn-sm btn-outline-primary">Listen to this section</a>` : ''}
                    </div>
                `;
            }).join('');

            return `
                <div class="result-item">
                    <h5>${episode.title}</h5>
                    ${episode.date ? `<div class="date">Date: ${episode.date}</div>` : ''}
                    <div class="matches">
                        ${matchesHtml}
                    </div>
                    ${episode.url ? `<a href="${episode.url}" target="_blank" class="btn btn-sm btn-outline-primary">Listen to Episode</a>` : ''}
                </div>
            `;
        }).join('');

        elasticResults.innerHTML = `
            <div class="alert alert-info mb-4">
                Found ${totalMentions} mention${totalMentions !== 1 ? 's' : ''} across ${Object.keys(episodeResults).length} episode${Object.keys(episodeResults).length !== 1 ? 's' : ''}
            </div>
            ${resultsHtml}
        `;
    }

    // Display Semantic results
    function displaySemanticResults(data, semanticResults) {
        if (!data.documents || !data.documents[0] || data.documents[0].length === 0) {
            semanticResults.innerHTML = '<div class="alert alert-info">No results found.</div>';
            return;
        }

        const resultsHtml = data.documents[0].map((doc, index) => {
            const metadata = data.metadatas[0][index] || {};
            const distance = data.distances[0][index];
            const relevanceScore = Math.round((1 - distance) * 100);
            
            // Calculate the audio URL with correct timestamp
            const seconds = timecodeToSeconds(metadata.start_timecode);
            const audioUrl = metadata.url ? `${metadata.url}#t=${seconds}.0` : '';
            
            return `
                <div class="result-item">
                    <div class="mb-2">
                        <strong>Relevance Score:</strong> ${relevanceScore}%
                        ${metadata.title ? `<br><strong>Episode:</strong> ${metadata.title}` : ''}
                        ${metadata.date ? `<br><strong>Date:</strong> ${metadata.date}` : ''}
                        ${metadata.start_timecode ? `<br><strong>Time:</strong> ${metadata.start_timecode}` : ''}
                    </div>
                    <p class="search-result-text">${doc}</p>
                    ${audioUrl ? `<a href="${audioUrl}" target="_blank" class="btn btn-sm btn-outline-primary">Listen to this section</a>` : ''}
                    ${metadata.url ? `<a href="${metadata.url}" target="_blank" class="btn btn-sm btn-outline-secondary ms-2">Full Episode</a>` : ''}
                </div>
            `;
        }).join('');

        semanticResults.innerHTML = `
            <div class="alert alert-info mb-4">
                Found ${data.documents[0].length} relevant passages
            </div>
            ${resultsHtml}
        `;
    }

    // Function to format RAG results
    function formatResults(results, queryNum) {
        if (!results || !results.documents || !results.documents[0] || results.documents[0].length === 0) {
            return `<div class="alert alert-info">No results found for search ${queryNum}</div>`;
        }

        return results.documents[0].map((doc, index) => {
            const metadata = results.metadatas[0][index] || {};
            const distance = results.distances[0][index];
            const relevanceScore = Math.round((1 - distance) * 100);
            
            // Calculate the audio URL with correct timestamp
            const seconds = timecodeToSeconds(metadata.start_timecode);
            const audioUrl = metadata.url ? `${metadata.url}#t=${seconds}.0` : '';
            
            return `
                <div class="result-item">
                    <div class="mb-2">
                        <strong>Relevance Score:</strong> ${relevanceScore}%
                        ${metadata.title ? `<br><strong>Episode:</strong> ${metadata.title}` : ''}
                        ${metadata.date ? `<br><strong>Date:</strong> ${metadata.date}` : ''}
                        ${metadata.start_timecode ? `<br><strong>Time:</strong> ${metadata.start_timecode}` : ''}
                    </div>
                    <p class="search-result-text">${doc}</p>
                    ${audioUrl ? `<a href="${audioUrl}" target="_blank" class="btn btn-sm btn-outline-primary">Listen to this section</a>` : ''}
                    ${metadata.url ? `<a href="${metadata.url}" target="_blank" class="btn btn-sm btn-outline-secondary ms-2">Full Episode</a>` : ''}
                </div>
            `;
        }).join('');
    }

    // Display RAG results
    function displayRagResults(data, ragResults) {
        if (!data || !data.llm_response) {
            ragResults.innerHTML = '<div class="alert alert-danger">Invalid response from server</div>';
            return;
        }

        // Configure marked for safe rendering
        marked.setOptions({
            breaks: true,  // Convert \n to <br>
            sanitize: true // Sanitize HTML input
        });

        // Create the results container
        const resultsHtml = `
            <div class="card mb-4">
                <div class="card-header">
                    <h5 class="mb-0">Answer from <a href="${data.model_info?.provider_url || '#'}" target="_blank">${data.model_info?.provider || 'AI'}</a> using ${data.model_info?.model || 'Unknown Model'}</h5>
                </div>
                <div class="card-body">
                    <div class="answer-text">
                        ${marked.parse(data.llm_response)}
                    </div>
                </div>
            </div>

            <div class="card mb-4">
                <div class="card-header">
                    <h5 class="mb-0">First Search Results</h5>
                </div>
                <div class="card-body">
                    ${formatResults(data.results1, 1)}
                </div>
            </div>

            <div class="card mb-4">
                <div class="card-header">
                    <h5 class="mb-0">Second Search Results</h5>
                </div>
                <div class="card-body">
                    ${formatResults(data.results2, 2)}
                </div>
            </div>

            <div class="card mb-4">
                <div class="card-header">
                    <h5 class="mb-0">Third Search Results</h5>
                </div>
                <div class="card-body">
                    ${formatResults(data.results3, 3)}
                </div>
            </div>
        `;

        ragResults.innerHTML = resultsHtml;
    }
}); 