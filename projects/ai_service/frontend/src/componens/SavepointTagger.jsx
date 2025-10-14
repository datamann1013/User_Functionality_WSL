import React from 'react';

const SavepointTagger = ({ onSavepoint, disabled }) => {
  return (
    <div className="savepoint-tagger">
      <button 
        className="savepoint-btn"
        onClick={onSavepoint}
        disabled={disabled}
        title="Create savepoint"
      >
        📌 Savepoint
      </button>
    </div>
  );
};

export default SavepointTagger;
