import React from 'react';

const EditModelsModal = ({ isOpen, onClose, models, onUpdateModel }) => {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Edit Models</h3>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>
        
        <div className="modal-body">
          <div className="models-editor">
            {models.map(model => (
              <div key={model.id} className="model-editor-item">
                <div className="model-field">
                  <label>Name:</label>
                  <input 
                    type="text" 
                    value={model.name} 
                    onChange={(e) => onUpdateModel(model.id, 'name', e.target.value)}
                  />
                </div>
                <div className="model-field">
                  <label>Icon:</label>
                  <input 
                    type="text" 
                    value={model.icon} 
                    onChange={(e) => onUpdateModel(model.id, 'icon', e.target.value)}
                  />
                </div>
                <div className="model-field">
                  <label>State:</label>
                  <select 
                    value={model.state} 
                    onChange={(e) => onUpdateModel(model.id, 'state', e.target.value)}
                  >
                    <option value="online">Online</option>
                    <option value="busy">Busy</option>
                    <option value="offline">Offline</option>
                  </select>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={onClose}>
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
};

export default EditModelsModal;
