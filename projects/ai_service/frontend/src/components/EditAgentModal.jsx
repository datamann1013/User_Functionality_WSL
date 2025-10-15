import React, { useState, useEffect } from 'react';

const EditAgentModal = ({ isOpen, onClose, agent, onAgentUpdated, onAgentDeleted }) => {
  const [formData, setFormData] = useState({
    name: '',
    model_name: '',
    temperature: 0.7,
    top_p: 0.9,
    system_prompt: '',
    max_tokens: 2048,
    avatar_image: '🤖'
  });
  const [availableModels, setAvailableModels] = useState(['llama3.2:1b']);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // API base URL
  const API_BASE = process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5000';

  useEffect(() => {
    if (isOpen && agent) {
      setFormData({
        name: agent.name || '',
        model_name: agent.model_name || 'llama3.2:1b',
        temperature: agent.temperature || 0.7,
        top_p: agent.top_p || 0.9,
        system_prompt: agent.system_prompt || '',
        max_tokens: agent.max_tokens || 2048,
        avatar_image: agent.avatar_image || '🤖'
      });
      fetchAvailableModels();
    }
  }, [isOpen, agent]);

  const fetchAvailableModels = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/models`);
      if (response.ok) {
        const data = await response.json();
        setAvailableModels(data.models || ['llama3.2:1b']);
      }
    } catch (error) {
      console.error('Failed to fetch models:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      setError('Agent name is required');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE}/api/agents/${agent.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        const updatedAgent = await response.json();
        onAgentUpdated(updatedAgent);
        onClose();
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Failed to update agent');
      }
    } catch (error) {
      setError('Network error: ' + error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async () => {
    setIsLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE}/api/agents/${agent.id}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        onAgentDeleted(agent.id);
        onClose();
        setShowDeleteConfirm(false);
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Failed to delete agent');
      }
    } catch (error) {
      setError('Network error: ' + error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value, type } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'number' ? parseFloat(value) : value
    }));
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Edit Agent</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label htmlFor="name">Agent Name</label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              placeholder="Enter agent name..."
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="avatar_image">Avatar (emoji or text)</label>
            <input
              type="text"
              id="avatar_image"
              name="avatar_image"
              value={formData.avatar_image}
              onChange={handleInputChange}
              placeholder="🤖"
            />
          </div>

          <div className="form-group">
            <label htmlFor="model_name">AI Model</label>
            <select
              id="model_name"
              name="model_name"
              value={formData.model_name}
              onChange={handleInputChange}
              required
            >
              {availableModels.map(model => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="temperature">
                Temperature: {formData.temperature}
                <span className="param-hint">Controls randomness</span>
              </label>
              <input
                type="range"
                id="temperature"
                name="temperature"
                min="0"
                max="2"
                step="0.1"
                value={formData.temperature}
                onChange={handleInputChange}
              />
            </div>

            <div className="form-group">
              <label htmlFor="top_p">
                Top P: {formData.top_p}
                <span className="param-hint">Controls diversity</span>
              </label>
              <input
                type="range"
                id="top_p"
                name="top_p"
                min="0"
                max="1"
                step="0.1"
                value={formData.top_p}
                onChange={handleInputChange}
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="max_tokens">
              Max Tokens: {formData.max_tokens}
              <span className="param-hint">Maximum response length</span>
            </label>
            <input
              type="range"
              id="max_tokens"
              name="max_tokens"
              min="100"
              max="4096"
              step="100"
              value={formData.max_tokens}
              onChange={handleInputChange}
            />
          </div>

          <div className="form-group">
            <label htmlFor="system_prompt">System Prompt</label>
            <textarea
              id="system_prompt"
              name="system_prompt"
              value={formData.system_prompt}
              onChange={handleInputChange}
              placeholder="You are a helpful AI assistant..."
              rows={4}
            />
          </div>

          <div className="modal-actions">
            <div className="actions-left">
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(true)}
                disabled={isLoading}
                className="delete-btn"
              >
                🗑️ Delete Agent
              </button>
            </div>
            
            <div className="actions-right">
              <button
                type="button"
                onClick={onClose}
                disabled={isLoading}
                className="cancel-btn"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isLoading}
                className="save-btn"
              >
                {isLoading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </form>

        {/* Delete Confirmation Modal */}
        {showDeleteConfirm && (
          <div className="confirm-overlay">
            <div className="confirm-dialog">
              <h3>Delete Agent</h3>
              <p>Are you sure you want to delete "{agent?.name}"?</p>
              <p><strong>This action cannot be undone.</strong></p>
              <div className="confirm-actions">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={isLoading}
                  className="cancel-btn"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDelete}
                  disabled={isLoading}
                  className="delete-btn"
                >
                  {isLoading ? 'Deleting...' : 'Delete Agent'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default EditAgentModal;
