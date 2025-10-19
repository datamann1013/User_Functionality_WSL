import React, { useState, useEffect } from 'react';

const ModelManager = ({ isOpen, onClose }) => {
  const [availableModels, setAvailableModels] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [downloadingModels, setDownloadingModels] = useState(new Set());
  const [newModelName, setNewModelName] = useState('');

  // API base URL
  const API_BASE =
    process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5000';

  // Popular Ollama models
  const popularModels = [
    {
      name: 'llama3.2:1b',
      description: 'Fast 1B parameter model (currently default)',
      size: '1.3GB',
    },
    {
      name: 'llama3.2:3b',
      description: 'Balanced 3B parameter model',
      size: '2.0GB',
    },
    {
      name: 'llama3.1:8b',
      description: 'High quality 8B parameter model',
      size: '4.7GB',
    },
    { name: 'codellama:7b', description: 'Code-focused model', size: '3.8GB' },
    {
      name: 'mistral:7b',
      description: 'Fast and efficient model',
      size: '4.1GB',
    },
    {
      name: 'phi3:mini',
      description: 'Compact high-performance model',
      size: '2.3GB',
    },
    {
      name: 'qwen2:0.5b',
      description: 'Ultra-fast small model',
      size: '0.4GB',
    },
    { name: 'gemma:2b', description: "Google's Gemma 2B model", size: '1.4GB' },
  ];

  useEffect(() => {
    if (isOpen) {
      fetchAvailableModels();
    }
  }, [isOpen]);

  const fetchAvailableModels = async () => {
    setIsLoading(true);
    setError('');

    try {
      // Get models from Ollama service
      const response = await fetch(`${API_BASE}/api/models`);
      if (response.ok) {
        const data = await response.json();
        setAvailableModels(data.models || []);
      } else {
        const errorData = await response.json().catch(() => ({}));
        if (response.status === 503) {
          setError(
            'AI service is not available. Please make sure the AI service is running and try again.'
          );
        } else {
          setError(
            errorData.error ||
              'Unable to load AI models. Please check your connection and try again.'
          );
        }
      }
    } catch (error) {
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        setError(
          'Cannot connect to AI service. Please make sure the service is running.'
        );
      } else {
        setError(
          'Connection error: Unable to fetch available models. Please try again.'
        );
      }
    } finally {
      setIsLoading(false);
    }
  };

  const downloadModel = async modelName => {
    if (downloadingModels.has(modelName)) return;

    setDownloadingModels(prev => new Set([...prev, modelName]));
    setError('');

    try {
      const response = await fetch(
        `${API_BASE}/api/models/download/${encodeURIComponent(modelName)}`,
        {
          method: 'POST',
        }
      );

      if (response.ok) {
        // Refresh available models after download
        await fetchAvailableModels();
        setError(
          `✅ Successfully downloaded ${modelName}! You can now use this model in your agents.`
        );
      } else {
        const errorData = await response.json().catch(() => ({}));
        if (response.status === 404) {
          setError(
            `Model "${modelName}" not found. Please check the model name and try again.`
          );
        } else if (response.status === 507) {
          setError(
            `Not enough disk space to download "${modelName}". Please free up space and try again.`
          );
        } else if (response.status === 503) {
          setError(
            'AI service is not available. Please make sure Ollama is running and try again.'
          );
        } else {
          setError(
            errorData.error ||
              `Failed to download "${modelName}". Please check your internet connection and try again.`
          );
        }
      }
    } catch (error) {
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        setError(
          'Cannot connect to AI service. Please make sure the service is running.'
        );
      } else {
        setError(
          `Connection error while downloading "${modelName}". Please check your internet connection and try again.`
        );
      }
    } finally {
      setDownloadingModels(prev => {
        const newSet = new Set(prev);
        newSet.delete(modelName);
        return newSet;
      });
    }
  };

  const downloadCustomModel = async () => {
    if (!newModelName.trim()) {
      setError(
        'Please enter a model name (e.g., "llama3.1:8b" or "mistral:7b")'
      );
      return;
    }

    await downloadModel(newModelName.trim());
    setNewModelName('');
  };

  const handleKeyPress = e => {
    if (e.key === 'Enter') {
      downloadCustomModel();
    }
  };

  if (!isOpen) return null;

  return (
    <div className='modal-overlay' onClick={onClose}>
      <div
        className='modal-content large-modal'
        onClick={e => e.stopPropagation()}
      >
        <div className='modal-header'>
          <h2>Model Management</h2>
          <button className='modal-close' onClick={onClose}>
            ×
          </button>
        </div>

        {error && (
          <div
            className={`error-message ${error.startsWith('✅') ? 'success-message' : ''}`}
          >
            {error}
          </div>
        )}

        <div className='model-manager-content'>
          {/* Currently Available Models */}
          <div className='models-section'>
            <h3>Downloaded Models ({availableModels.length})</h3>
            {isLoading ? (
              <div className='loading-indicator'>Loading models...</div>
            ) : availableModels.length > 0 ? (
              <div className='models-grid'>
                {availableModels.map(model => (
                  <div key={model} className='model-card downloaded'>
                    <div className='model-info'>
                      <div className='model-name'>{model}</div>
                      <div className='model-status'>✅ Ready to use</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className='empty-state'>
                No models downloaded yet. Download some models below to get
                started.
              </div>
            )}
          </div>

          {/* Popular Models to Download */}
          <div className='models-section'>
            <h3>Popular Models</h3>
            <div className='models-grid'>
              {popularModels.map(model => {
                const isDownloaded = availableModels.includes(model.name);
                const isDownloading = downloadingModels.has(model.name);

                return (
                  <div
                    key={model.name}
                    className={`model-card ${isDownloaded ? 'downloaded' : 'available'}`}
                  >
                    <div className='model-info'>
                      <div className='model-name'>{model.name}</div>
                      <div className='model-description'>
                        {model.description}
                      </div>
                      <div className='model-size'>Size: {model.size}</div>
                    </div>
                    <div className='model-actions'>
                      {isDownloaded ? (
                        <span className='status-badge downloaded'>
                          ✅ Downloaded
                        </span>
                      ) : (
                        <button
                          onClick={() => downloadModel(model.name)}
                          disabled={isDownloading}
                          className='download-btn'
                        >
                          {isDownloading ? '⏳ Downloading...' : '📥 Download'}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Custom Model Download */}
          <div className='models-section'>
            <h3>Download Custom Model</h3>
            <div className='custom-download'>
              <input
                type='text'
                value={newModelName}
                onChange={e => setNewModelName(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder='Enter model name (e.g., llama3.1:70b)'
                className='model-input'
              />
              <button
                onClick={downloadCustomModel}
                disabled={
                  !newModelName.trim() ||
                  downloadingModels.has(newModelName.trim())
                }
                className='download-btn'
              >
                Download
              </button>
            </div>
            <div className='download-hint'>
              Find more models at{' '}
              <a
                href='https://ollama.ai/library'
                target='_blank'
                rel='noopener noreferrer'
              >
                ollama.ai/library
              </a>
            </div>
          </div>
        </div>

        <div className='modal-actions'>
          <button onClick={onClose} className='cancel-btn'>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default ModelManager;
