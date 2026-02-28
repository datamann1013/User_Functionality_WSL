import { useState, useEffect, useRef, useCallback } from 'react';

// Helper to format file sizes
function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Get API base URL - use proxy in production
function getApiBase() {
  const path = window.location.pathname;
  if (path.startsWith('/api/proxy/RuneMesh_Drop')) {
    return '/api/proxy/RuneMesh_Drop';
  }
  return '';
}

// Escape HTML
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
}

function App() {
  const [interfaceUrl, setInterfaceUrl] = useState('');
  const [interfaces, setInterfaces] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);
  const [uploadError, setUploadError] = useState('');
  const [uploading, setUploading] = useState(false);

  const [downloadCode, setDownloadCode] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [downloadError, setDownloadError] = useState('');
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  const [transfers, setTransfers] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);
  const downloadInputRef = useRef(null);

  // Load available network interfaces
  useEffect(() => {
    async function loadInterfaces() {
      try {
        const res = await fetch(`${getApiBase()}/interfaces`);
        const data = await res.json();
        if (data.candidates && data.candidates.length) {
          setInterfaces(data.candidates);
          setInterfaceUrl(data.candidates[0]);
        }
      } catch (e) {
        console.error('Failed to load interfaces:', e);
      }
    }
    loadInterfaces();
  }, []);

  // Load saved transfers from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('runemesh_transfers');
      if (saved) {
        setTransfers(JSON.parse(saved));
      }
    } catch (e) {
      console.error('Failed to load transfers:', e);
    }
  }, []);

  // Save transfers to localStorage
  const saveTransfers = useCallback((newTransfers) => {
    setTransfers(newTransfers);
    try {
      localStorage.setItem('runemesh_transfers', JSON.stringify(newTransfers));
    } catch (e) {
      console.error('Failed to save transfers:', e);
    }
  }, []);

  // Handle file drop
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      setSelectedFile(files[0]);
      setUploadResult(null);
      setUploadError('');
    }
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const handleFileSelect = useCallback((e) => {
    const files = e.target.files;
    if (files.length > 0) {
      setSelectedFile(files[0]);
      setUploadResult(null);
      setUploadError('');
    }
  }, []);

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setUploadError('');
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile, selectedFile.name);

      let url = `${getApiBase()}/upload`;
      if (interfaceUrl) {
        url += `?external_base=${encodeURIComponent(interfaceUrl)}`;
      }

      const res = await fetch(url, { method: 'POST', body: formData });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);

      const data = await res.json();
      setUploadResult(data);

      // Add to transfers list
      const newTransfer = {
        id: data.file_id,
        name: data.filename,
        size: selectedFile.size,
        type: 'sent',
        url: data.download_url,
        time: new Date().toISOString(),
      };
      saveTransfers([newTransfer, ...transfers].slice(0, 20));

    } catch (e) {
      setUploadError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const handleCopyLink = () => {
    if (uploadResult?.download_url) {
      navigator.clipboard.writeText(uploadResult.download_url);
    }
  };

  const handleDownload = async () => {
    if (!downloadCode.trim()) return;

    setDownloading(true);
    setDownloadError('');
    setDownloadProgress(0);
    setDownloadSuccess(false);

    try {
      // Parse the code - could be full URL or just file_id
      let fileId = downloadCode.trim();
      let token = '';

      // Check if it's a full URL
      const urlMatch = downloadCode.match(/\/download\/([^\?]+)/);
      if (urlMatch) {
        fileId = urlMatch[1];
      }

      // Extract token from URL if present
      const tokenMatch = downloadCode.match(/token=([^&\s]+)/);
      if (tokenMatch) {
        token = tokenMatch[1];
      }

      if (!fileId) {
        throw new Error('Invalid file code');
      }

      // Build download URL
      let downloadUrl = `${getApiBase()}/download/${fileId}`;
      if (token) {
        downloadUrl += `?token=${token}`;
      }

      // Download with progress
      const xhr = new XMLHttpRequest();
      xhr.open('GET', downloadUrl, true);
      xhr.responseType = 'blob';

      xhr.onprogress = (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          setDownloadProgress(pct);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          const blob = xhr.response;
          const filename = fileId; // Default filename
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = filename;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);

          setDownloadSuccess(true);

          // Add to transfers list
          const newTransfer = {
            id: fileId,
            name: filename,
            size: blob.size,
            type: 'received',
            time: new Date().toISOString(),
          };
          saveTransfers([newTransfer, ...transfers].slice(0, 20));

          // Clear after success
          setTimeout(() => {
            setDownloadCode('');
            setDownloadProgress(0);
            setDownloadSuccess(false);
          }, 3000);
        } else {
          setDownloadError(`Download failed: ${xhr.status}`);
        }
        setDownloading(false);
      };

      xhr.onerror = () => {
        setDownloadError('Download failed: Network error');
        setDownloading(false);
      };

      xhr.send();

    } catch (e) {
      setDownloadError(e.message);
      setDownloading(false);
    }
  };

  const handleClearUpload = () => {
    setSelectedFile(null);
    setUploadResult(null);
    setUploadError('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="app">
      {/* Top Bar */}
      <div className="top-bar">
        <div className="brand">
          <span className="brand-mark">[</span>
          <span className="brand-name">RuneMesh_Drop</span>
          <span className="brand-mark">]</span>
        </div>
        <div className="top-bar-spacer" />
        <div className="top-bar-status">
          <span className="status-dot online"></span>
          <span>Ready</span>
        </div>
      </div>

      {/* Main Content */}
      <div className="main-content">
        {/* Send Panel */}
        <div className="panel send-panel">
          <div className="panel-header">
            <span className="panel-title">Send File</span>
          </div>
          <div className="panel-body">
            {/* Interface Selector */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                Network Interface
              </label>
              <select
                className="input"
                value={interfaceUrl}
                onChange={(e) => setInterfaceUrl(e.target.value)}
                style={{ appearance: 'none', cursor: 'pointer' }}
              >
                <option value="">Auto-detect</option>
                {interfaces.map(iface => (
                  <option key={iface} value={iface}>{iface}</option>
                ))}
              </select>
            </div>

            {/* Drop Zone */}
            {!uploadResult ? (
              <div
                className={`drop-zone ${dragOver ? 'drag-over' : ''}`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="drop-zone-icon">+</div>
                <div className="drop-zone-text">Drop file here</div>
                <div className="drop-zone-hint">or click to browse</div>
                <input
                  ref={fileInputRef}
                  type="file"
                  style={{ display: 'none' }}
                  onChange={handleFileSelect}
                />
              </div>
            ) : null}

            {/* Selected File */}
            {selectedFile && !uploadResult && (
              <div className="file-info">
                <div className="file-info-header">
                  <span className="file-icon">[*]</span>
                  <div>
                    <div className="file-name">{selectedFile.name}</div>
                    <div className="file-size">{formatFileSize(selectedFile.size)}</div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                  <button className="btn btn-primary" onClick={handleUpload} disabled={uploading}>
                    {uploading ? 'Uploading...' : 'Generate QR Code'}
                  </button>
                  <button className="btn" onClick={handleClearUpload}>Clear</button>
                </div>
              </div>
            )}

            {/* Upload Error */}
            {uploadError && (
              <div className="message error">{uploadError}</div>
            )}

            {/* Upload Result */}
            {uploadResult && (
              <div>
                <div className="file-info">
                  <div className="file-info-header">
                    <span className="file-icon">[OK]</span>
                    <div>
                      <div className="file-name">{uploadResult.filename}</div>
                      <div className="file-size">Ready to share</div>
                    </div>
                  </div>
                </div>

                {/* QR Code */}
                <div className="qr-display">
                  <div
                    dangerouslySetInnerHTML={{ __html: uploadResult.qr_svg }}
                  />
                </div>

                {/* Download Link */}
                <div className="download-link">
                  <div className="download-link-label">Share Link</div>
                  <div className="download-link-row">
                    <input
                      className="download-link-input"
                      type="text"
                      value={uploadResult.download_url}
                      readOnly
                    />
                    <button className="copy-btn" onClick={handleCopyLink}>Copy</button>
                  </div>
                </div>

                {/* Reset */}
                <button
                  className="btn"
                  style={{ marginTop: 16, width: '100%' }}
                  onClick={handleClearUpload}
                >
                  Send Another File
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Receive Panel */}
        <div className="panel receive-panel">
          <div className="panel-header">
            <span className="panel-title">Receive File</span>
          </div>
          <div className="panel-body">
            {/* Manual Code Entry */}
            <div className="code-entry">
              <div className="code-entry-label">Enter File Code or URL</div>
              <div className="code-entry-row">
                <input
                  ref={downloadInputRef}
                  className="code-entry-input"
                  type="text"
                  placeholder="Paste URL or file code..."
                  value={downloadCode}
                  onChange={(e) => setDownloadCode(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleDownload()}
                />
                <button
                  className="btn btn-primary"
                  onClick={handleDownload}
                  disabled={downloading || !downloadCode.trim()}
                >
                  {downloading ? '...' : 'Get'}
                </button>
              </div>
            </div>

            {/* Download Progress */}
            {downloading && (
              <div className="download-progress">
                <div className="progress-bar-track">
                  <div className="progress-bar" style={{ width: `${downloadProgress}%` }} />
                </div>
                <div className="progress-label">{downloadProgress}% complete</div>
              </div>
            )}

            {/* Download Error */}
            {downloadError && (
              <div className="message error">{downloadError}</div>
            )}

            {/* Download Success */}
            {downloadSuccess && (
              <div className="message success">File downloaded successfully!</div>
            )}
          </div>
        </div>

        {/* Recent Transfers Panel */}
        <div className="panel recent-panel">
          <div className="panel-header">
            <span className="panel-title">Recent</span>
          </div>
          <div className="panel-body">
            {transfers.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">[-]</div>
                <div className="empty-text">No transfers yet</div>
              </div>
            ) : (
              <div className="transfers-list">
                {transfers.map(transfer => (
                  <div
                    key={transfer.id}
                    className="transfer-item"
                    onClick={() => {
                      if (transfer.type === 'received') {
                        setDownloadCode(transfer.url || transfer.id);
                      } else {
                        setDownloadCode(transfer.url || transfer.id);
                      }
                    }}
                  >
                    <span className="transfer-icon">
                      {transfer.type === 'sent' ? '[->]' : '[<-]'}
                    </span>
                    <div className="transfer-info">
                      <div className="transfer-name">{transfer.name}</div>
                      <div className="transfer-meta">
                        <span>{formatFileSize(transfer.size)}</span>
                        <span>{new Date(transfer.time).toLocaleTimeString()}</span>
                      </div>
                    </div>
                    <span className={`transfer-status ${transfer.type}`}>
                      {transfer.type}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
