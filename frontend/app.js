const API_URL = window.location.origin + '/api';
const AUTH_KEY = 'voice_agent_auth';

// Check authentication on load
window.addEventListener('DOMContentLoaded', () => {
    if (isAuthenticated()) {
        showDashboard();
        loadDocuments();
        loadConversations();
    } else {
        showLanding();
    }
});

// Navigation
function showLanding() {
    hideAllPages();
    document.getElementById('landingPage').classList.add('active');
}

function showLogin() {
    hideAllPages();
    document.getElementById('loginPage').classList.add('active');
    document.getElementById('loginError').classList.remove('show');
}

function showDashboard() {
    hideAllPages();
    document.getElementById('dashboardPage').classList.add('active');
}

function hideAllPages() {
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
}

// Authentication
function handleLogin(event) {
    event.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('loginError');

    if (username === 'admin' && password === 'admin') {
        localStorage.setItem(AUTH_KEY, 'true');
        showDashboard();
        loadDocuments();
        loadConversations();
    } else {
        errorDiv.textContent = 'Invalid username or password';
        errorDiv.classList.add('show');
    }
}

function isAuthenticated() {
    return localStorage.getItem(AUTH_KEY) === 'true';
}

function logout() {
    localStorage.removeItem(AUTH_KEY);
    showLanding();
}

// Section Navigation
function showSection(section) {
    // Update nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');

    // Show/hide sections
    document.querySelectorAll('.section').forEach(sec => {
        sec.classList.remove('active');
    });
    document.getElementById(section + 'Section').classList.add('active');
}

// Document Management
async function loadDocuments() {
    const listDiv = document.getElementById('documentsList');
    listDiv.innerHTML = '<div class="loading">Loading documents...</div>';

    try {
        const response = await fetch(`${API_URL}/documents`);
        if (!response.ok) throw new Error('Failed to load documents');

        const documents = await response.json();
        
        if (documents.length === 0) {
            listDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📄</div>
                    <p>No documents uploaded yet</p>
                    <p>Click "Upload Document" to get started</p>
                </div>
            `;
            return;
        }

        listDiv.innerHTML = documents.map(doc => `
            <div class="document-item">
                <div class="document-info">
                    <div class="document-name">${doc.file_name || doc.name}</div>
                    <div class="document-meta">
                        Type: ${doc.file_type || doc.type} | 
                        Uploaded: ${formatDate(doc.indexed_at || doc.created_at)}
                    </div>
                </div>
                <button class="btn-danger" onclick="deleteDocument('${doc.id}')">Delete</button>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading documents:', error);
        listDiv.innerHTML = '<div class="error-message show">Error loading documents</div>';
    }
}

async function handleFileUpload(event) {
    const files = event.target.files;
    if (files.length === 0) return;

    const statusDiv = document.getElementById('uploadStatus');
    statusDiv.textContent = `Uploading ${files.length} file(s)...`;
    statusDiv.className = 'status-message show';

    try {
        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch(`${API_URL}/documents/upload`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Failed to upload ${file.name}`);
            }
        }

        statusDiv.textContent = `Successfully uploaded ${files.length} file(s)!`;
        statusDiv.className = 'status-message show success';
        
        // Clear file input
        event.target.value = '';
        
        // Reload documents
        setTimeout(() => {
            loadDocuments();
            statusDiv.classList.remove('show');
        }, 2000);
    } catch (error) {
        console.error('Error uploading file:', error);
        statusDiv.textContent = `Error: ${error.message}`;
        statusDiv.className = 'status-message show error';
    }
}

async function deleteDocument(id) {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
        const response = await fetch(`${API_URL}/documents/${id}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Failed to delete document');

        loadDocuments();
    } catch (error) {
        console.error('Error deleting document:', error);
        alert('Error deleting document');
    }
}

// Conversation Management
async function loadConversations() {
    const listDiv = document.getElementById('conversationsList');
    listDiv.innerHTML = '<div class="loading">Loading conversations...</div>';

    try {
        const response = await fetch(`${API_URL}/conversations`);
        if (!response.ok) throw new Error('Failed to load conversations');

        const conversations = await response.json();
        
        if (conversations.length === 0) {
            listDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">💬</div>
                    <p>No conversations yet</p>
                    <p>Start a conversation to see it here</p>
                </div>
            `;
            return;
        }

        listDiv.innerHTML = conversations.map(conv => `
            <div class="conversation-item" data-conv-id="${conv.id}">
                <div class="conversation-info">
                    <div class="conversation-title">${conv.title || 'Conversation'}</div>
                    <div class="conversation-meta">
                        ${conv.message_count || 0} messages | 
                        ${formatDate(conv.created_at)}
                    </div>
                    <div class="conversation-details" id="details-${conv.id}" style="display: none;">
                        <div class="loading">Loading messages...</div>
                    </div>
                </div>
                <button class="btn-secondary" onclick="toggleConversationDetails('${conv.id}', this)">
                    Show Details
                </button>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading conversations:', error);
        listDiv.innerHTML = '<div class="error-message show">Error loading conversations</div>';
    }
}

async function toggleConversationDetails(convId, btn) {
    const details = document.getElementById(`details-${convId}`);
    const isHidden = details.style.display === 'none';
    
    if (isHidden) {
        // Load conversation details
        try {
            const response = await fetch(`${API_URL}/conversations/${convId}`);
            if (!response.ok) throw new Error('Failed to load conversation');
            
            const conversation = await response.json();
            
            if (conversation.messages && conversation.messages.length > 0) {
                details.innerHTML = conversation.messages.map(msg => `
                    <div class="message ${msg.role}">
                        <div>${msg.content}</div>
                        <div class="message-time">${formatDate(msg.created_at)}</div>
                    </div>
                `).join('');
            } else {
                details.innerHTML = '<div class="empty-state">No messages in this conversation</div>';
            }
            
            details.style.display = 'block';
            btn.textContent = 'Hide Details';
        } catch (error) {
            console.error('Error loading conversation:', error);
            details.innerHTML = '<div class="error-message show">Error loading conversation</div>';
        }
    } else {
        details.style.display = 'none';
        btn.textContent = 'Show Details';
    }
}

function refreshConversations() {
    loadConversations();
}

// Utility
function formatDate(timestamp) {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp * 1000 || timestamp);
    return date.toLocaleString();
}

