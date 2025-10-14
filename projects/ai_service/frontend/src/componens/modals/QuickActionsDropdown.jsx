import React from 'react';

const QuickActionsDropdown = ({ onClose, onAction }) => {
  const actions = [
    { id: 'clear', label: 'Clear Chat', icon: '🗑️' },
    { id: 'export', label: 'Export Chat', icon: '📥' },
    { id: 'settings', label: 'Settings', icon: '⚙️' },
    { id: 'help', label: 'Help', icon: '❓' }
  ];

  const handleAction = (actionId) => {
    onAction(actionId);
    onClose();
  };

  return (
    <div className="quick-actions-overlay" onClick={onClose}>
      <div className="quick-actions-dropdown" onClick={e => e.stopPropagation()}>
        <div className="dropdown-header">
          <h4>Quick Actions</h4>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>
        
        <div className="dropdown-actions">
          {actions.map(action => (
            <button
              key={action.id}
              className="action-item"
              onClick={() => handleAction(action.id)}
            >
              <span className="action-icon">{action.icon}</span>
              <span className="action-label">{action.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default QuickActionsDropdown;
