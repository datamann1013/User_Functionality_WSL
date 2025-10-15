import React, { useState, useEffect } from 'react';

const CreateAgentModal = ({ isOpen, onClose, onAgentCreated }) => {
  const [formData, setFormData] = useState({
    name: '',
    avatar_image: '',
    model_name: 'llama3.2:1b',
    temperature: 0.7,
    top_p: 0.9,
    system_prompt: 'You are a helpful AI assistant.',
    max_tokens: 2048
  });
  
  const [availableModels, setAvailableModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  // Predefined avatar options
  const avatarOptions = [
    '🤖', '👨‍💻', '👩‍💻', '🧠', '⚡', '🚀', '💡', '🎯', '🔬', '📊',
    '🎨', '📝', '💬', '🌟', '🔥', '💎', '🎪', '🎭', '🎪', '🦄'
  ];

  // Common model options (will be supplemented by API)
  const commonModels = [
    'llama3.2:1b',
    'llama3.2:3b', 
    'llama3.1:8b',
    'codellama:7b',
    'mistral:7b',
    'gemma:2b',
    'phi3:mini'
  ];

  useEffect(() => {
    if (isOpen) {
      fetchAvailableModels();
    }
  }, [isOpen]);

  const fetchAvailableModels = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/models');
      if (response.ok) {
        const data = await response.json();
        setAvailableModels(data.models || []);
      }
    } catch (error) {
      console.error('Failed to fetch models:', error);
      setAvailableModels(commonModels);
    }
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
    
    // Clear field error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({
        ...prev,
        [field]: null
      }));
    }
  };

  const validateForm = () => {
    const newErrors = {};
    
    if (!formData.name.trim()) {
      newErrors.name = 'Agent name is required';
    }
    
    if (!formData.model_name) {
      newErrors.model_name = 'Model selection is required';
    }
    
    if (formData.temperature < 0 || formData.temperature > 2) {
      newErrors.temperature = 'Temperature must be between 0 and 2';
    }
    
    if (formData.top_p < 0 || formData.top_p > 1) {
      newErrors.top_p = 'Top P must be between 0 and 1';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setLoading(true);
    
    try {
      const response = await fetch('http://localhost:5000/api/agents', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        const newAgent = await response.json();
        onAgentCreated(newAgent);
        onClose();
        
        // Reset form
        setFormData({
          name: '',
          avatar_image: '',
          model_name: 'llama3.2:1b',
          temperature: 0.7,
          top_p: 0.9,
          system_prompt: 'You are a helpful AI assistant.',
          max_tokens: 2048
        });
      } else {
        const error = await response.json();
        setErrors({ submit: error.error || 'Failed to create agent' });
      }
    } catch (error) {
      setErrors({ submit: 'Network error occurred' });
    }
    
    setLoading(false);
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Create New Agent</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        
        <form onSubmit={handleSubmit} className="agent-form">
          {/* Agent Name */}
          <div className="form-group">
            <label htmlFor="name">Agent Name *</label>
            <input
              id="name"
              type="text"
              value={formData.name}
              onChange={(e) => handleInputChange('name', e.target.value)}
              placeholder="Enter agent name"
              className={errors.name ? 'error' : ''}
            />
            {errors.name && <span className="error-text">{errors.name}</span>}
          </div>

          {/* Avatar Selection */}
          <div className="form-group">
            <label>Avatar</label>
            <div className="avatar-grid">
              {avatarOptions.map((emoji, index) => (
                <button
                  key={index}
                  type="button"
                  className={`avatar-option ${formData.avatar_image === emoji ? 'selected' : ''}`}
                  onClick={() => handleInputChange('avatar_image', emoji)}
                >
                  {emoji}
                </button>
              ))}
            </div>
          </div>

          {/* Model Selection */}
          <div className="form-group">
            <label htmlFor="model">AI Model *</label>
            <select
              id="model"
              value={formData.model_name}
              onChange={(e) => handleInputChange('model_name', e.target.value)}
              className={errors.model_name ? 'error' : ''}
            >
              <option value="">Select a model</option>
              {[...new Set([...commonModels, ...availableModels])].map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
            {errors.model_name && <span className="error-text">{errors.model_name}</span>}
          </div>

          {/* System Prompt */}
          <div className="form-group">
            <label htmlFor="system_prompt">System Prompt</label>
            <textarea
              id="system_prompt"
              value={formData.system_prompt}
              onChange={(e) => handleInputChange('system_prompt', e.target.value)}
              placeholder="Describe the agent's personality and behavior"
              rows={3}
            />
          </div>

          {/* Advanced Settings */}
          <div className="form-group">
            <label className="section-label">Advanced Settings</label>
            
            <div className="form-row">
              <div className="form-col">
                <label htmlFor="temperature">Temperature: {formData.temperature}</label>
                <input
                  id="temperature"
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={formData.temperature}
                  onChange={(e) => handleInputChange('temperature', parseFloat(e.target.value))}
                />
                <small>Controls randomness (0 = focused, 2 = creative)</small>
                {errors.temperature && <span className="error-text">{errors.temperature}</span>}
              </div>
              
              <div className="form-col">
                <label htmlFor="top_p">Top P: {formData.top_p}</label>
                <input
                  id="top_p"
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={formData.top_p}
                  onChange={(e) => handleInputChange('top_p', parseFloat(e.target.value))}
                />
                <small>Controls diversity (0 = narrow, 1 = diverse)</small>
                {errors.top_p && <span className="error-text">{errors.top_p}</span>}
              </div>
            </div>

            <div className="form-col">
              <label htmlFor="max_tokens">Max Tokens</label>
              <input
                id="max_tokens"
                type="number"
                min="128"
                max="8192"
                value={formData.max_tokens}
                onChange={(e) => handleInputChange('max_tokens', parseInt(e.target.value))}
              />
              <small>Maximum response length</small>
            </div>
          </div>

          {errors.submit && (
            <div className="error-message">{errors.submit}</div>
          )}

          <div className="form-actions">
            <button type="button" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button type="submit" disabled={loading} className="primary">
              {loading ? 'Creating...' : 'Create Agent'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CreateAgentModal;