import React from 'react';

const ModelManager = ({ 
  models, 
  selectedModel, 
  onModelSelect, 
  sidebarOpen, 
  onToggleSidebar 
}) => {
  if (!sidebarOpen) {
    return (
      <div className="sidebar-collapsed">
        <button 
          className="sidebar-toggle"
          onClick={onToggleSidebar}
          title="Open Models"
        >
          🤖
        </button>
      </div>
    );
  }

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h3>🤖 Models</h3>
        <button 
          className="sidebar-toggle"
          onClick={onToggleSidebar}
          title="Close Models"
        >
          ✕
        </button>
      </div>
      
      <div className="models-list">
        {models.map(model => (
          <div 
            key={model.id}
            className={`model-item ${selectedModel === model.id ? 'selected' : ''}`}
            onClick={() => onModelSelect(model.id)}
          >
            <div className="model-icon">{model.icon}</div>
            <div className="model-info">
              <div className="model-name">{model.name}</div>
              <div className="model-version">v{model.version}</div>
            </div>
            <div className={`model-status ${model.state}`}>
              {model.state === 'online' ? '🟢' : model.state === 'busy' ? '🟡' : '🔴'}
            </div>
          </div>
        ))}
      </div>
      
      <div className="sidebar-footer">
        <button className="add-model-btn">
          + Add Model
        </button>
      </div>
    </div>
  );
};

export default ModelManager;
