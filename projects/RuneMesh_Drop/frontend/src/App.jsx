import { useState, useEffect, useRef, useCallback } from 'react';

function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function getApiBase() {
  if (window.location.pathname.startsWith('/api/proxy/RuneMesh_Drop')) {
    return '/api/proxy/RuneMesh_Drop';
  }
  return '';
}

// Matches the Panel component pattern used in RuneGuard_Dashboard
function Panel({ title, lastUpdated, children, className }) {
  const timeStr = lastUpdated
    ? lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : null;
  return (
    <div className={`panel ${className ?? ''}`}>
      <div className="panel-header">
        <span className="panel-title">{title}</span>
        {timeStr && <span className="panel-updated">updated {timeStr}</span>}
      </div>
      <div className="panel-body">{children}</div>
    </div>
  );
}

export default function App() {
  const [serverOnline, setServerOnline] = useState(false);
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

  // Load available network interfaces and track server connectivity
  useEffect(() => {
    async function loadInterfaces() {
      try {
        const res = await fetch(`${getApiBase()}/interfaces`);
        const data = await res.json();
        if (data.candidates && data.candidates.length) {
          setInterfaces(data.candidates);
          setInterfaceUrl(data.candidates[0]);
        }
        setServerOnline(true);
      } catch (e) {
        console.error('Failed to load interfaces:', e);
        setServerOnline(false);
      }
    }
    loadInterfaces();
  }, []);

  // Load saved transfers from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('runemesh_transfers');
      if (saved) setTransfers(JSON.parse(saved));
    } catch (e) {
      console.error('Failed to load transfers:', e);
    }
  }, []);

  const saveTransfers = useCallback((next) => {
    setTransfers(next);
    try {
      localStorage.setItem('runemesh_transfers', JSON.stringify(next));
    } catch (e) {
      console.error('Failed to save transfers:', e);
    }
  }, []);

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

  const handleDragOver  = useCallback((e) => { e.preventDefault(); setDragOver(true); }, []);
  const handleDragLeave = useCallback((e) => { e.preventDefault(); setDragOver(false); }, []);

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
      if (interfaceUrl) url += `?external_base=${encodeURIComponent(interfaceUrl)}`;
      const res = await fetch(url, { method: 'POST', body: formData });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      const data = await res.json();
      setUploadResult(data);
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
    if (uploadResult?.download_url) navigator.clipboard.writeText(uploadResult.download_url);
  };

  const handleDownload = async () => {
    if (!downloadCode.trim()) return;
    setDownloading(true);
    setDownloadError('');
    setDownloadProgress(0);
    setDownloadSuccess(false);
    try {
      let fileId = downloadCode.trim();
      const urlMatch = downloadCode.match(/\/download\/([^?]+)/);
      if (urlMatch) fileId = urlMatch[1];
      const tokenMatch = downloadCode.match(/token=([^&\s]+)/);
      const token = tokenMatch ? tokenMatch[1] : '';
      if (!fileId) throw new Error('Invalid file code');

      let downloadUrl = `${getApiBase()}/download/${fileId}`;
      if (token) downloadUrl += `?token=${token}`;

      const xhr = new XMLHttpRequest();
      xhr.open('GET', downloadUrl, true);
      xhr.responseType = 'blob';

      xhr.onprogress = (e) => {
        if (e.lengthComputable) setDownloadProgress(Math.round((e.loaded / e.total) * 100));
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          // Extract real filename from Content-Disposition if the server sent one
          const cd = xhr.getResponseHeader('Content-Disposition');
          let filename = fileId;
          if (cd) {
            const match = cd.match(/filename[^;=\n]*=(['"]?)([^'"\n]*)\1/);
            if (match && match[2]) filename = decodeURIComponent(match[2].trim());
          }

          const blob = xhr.response;
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = filename;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);

          setDownloadSuccess(true);
          const newTransfer = {
            id: fileId,
            name: filename,
            size: blob.size,
            type: 'received',
            time: new Date().toISOString(),
          };
          saveTransfers([newTransfer, ...transfers].slice(0, 20));
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
        setDownloadError('Download failed: network error');
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
    if (fileInputRef.current) fileInputRef.current.value = '';
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
          <span className={`status-dot ${serverOnline ? 'online' : 'error'}`} />
          <span>{serverOnline ? 'Ready' : 'Offline'}</span>
        </div>
      </div>

      {/* Main Content */}
      <div className="main-content">

        {/* Send Panel */}
        <Panel title="Send File" className="send-panel">
          {/* Interface Selector */}
          <div className="section">
            <label className="section-label">Network Interface</label>
            <select
              className="input"
              value={interfaceUrl}
              onChange={(e) => setInterfaceUrl(e.target.value)}
            >
              <option value="">Auto-detect</option>
              {interfaces.map(iface => (
                <option key={iface} value={iface}>{iface}</option>
              ))}
            </select>
          </div>

          {/* Drop Zone */}
          {!uploadResult && (
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
          )}

          {/* Selected File (pre-upload) */}
          {selectedFile && !uploadResult && (
            <div className="file-info">
              <div className="file-info-header">
                <span className="file-icon">[*]</span>
                <div>
                  <div className="file-name">{selectedFile.name}</div>
                  <div className="file-size">{formatFileSize(selectedFile.size)}</div>
                </div>
              </div>
              <div className="btn-row">
                <button className="btn btn-primary" onClick={handleUpload} disabled={uploading}>
                  {uploading ? 'Uploading...' : 'Generate QR Code'}
                </button>
                <button className="btn" onClick={handleClearUpload}>Clear</button>
              </div>
            </div>
          )}

          {uploadError && <div className="message error">{uploadError}</div>}

          {/* Upload Result — QR + share link */}
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

              <div className="qr-display">
                <div dangerouslySetInnerHTML={{ __html: uploadResult.qr_svg }} />
              </div>

              <div className="download-link">
                <span className="section-label">Share Link</span>
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

              <button className="btn btn-full" onClick={handleClearUpload}>
                Send Another File
              </button>
            </div>
          )}
        </Panel>

        {/* Receive Panel */}
        <Panel title="Receive File" className="receive-panel">
          <div className="code-entry">
            <label className="section-label">Enter File Code or URL</label>
            <div className="code-entry-row">
              <input
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

          {downloading && (
            <div className="download-progress">
              <div className="progress-bar-track">
                <div className="progress-bar" style={{ width: `${downloadProgress}%` }} />
              </div>
              <div className="progress-label">{downloadProgress}% complete</div>
            </div>
          )}

          {downloadError   && <div className="message error">{downloadError}</div>}
          {downloadSuccess && <div className="message success">File downloaded successfully!</div>}
        </Panel>

        {/* Recent Transfers Panel */}
        <Panel title="Recent" className="recent-panel">
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
                  onClick={() => setDownloadCode(transfer.url || transfer.id)}
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
        </Panel>

      </div>
    </div>
  );
}
