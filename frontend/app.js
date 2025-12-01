const API_URL = window.location.origin + '/api';
const AUTH_KEY = 'voice_agent_auth';

// State
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let currentConversationId = null;

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

    // Load data for the section
    if (section === 'rag') {
        loadDocuments();
    } else if (section === 'history') {
        loadConversations();
    }
}

// ==================== CHAT FUNCTIONALITY ====================

function handleChatSubmit(event) {
    event.preventDefault();
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    input.value = '';
    sendMessage(message);
}

async function sendMessage(message) {
    const messagesContainer = document.getElementById('chatMessages');
    const statusDiv = document.getElementById('chatStatus');
    const sendBtn = document.getElementById('sendBtn');
    
    // Clear welcome message if present
    const welcomeMsg = messagesContainer.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }
    
    // Add user message
    addChatMessage(message, 'user');
    
    // Show typing indicator
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'typing-indicator';
    typingIndicator.innerHTML = '<span></span><span></span><span></span>';
    messagesContainer.appendChild(typingIndicator);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    // Update status
    statusDiv.textContent = 'Processing...';
    statusDiv.className = 'chat-status processing';
    sendBtn.disabled = true;
    
    try {
        const response = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                conversation_id: currentConversationId
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to get response');
        }
        
        const data = await response.json();
        
        // Remove typing indicator
        typingIndicator.remove();
        
        // Add assistant message
        addChatMessage(data.answer, 'assistant', data.context_count);
        
        // Update conversation ID
        if (data.conversation_id) {
            currentConversationId = data.conversation_id;
        }
        
        // Update status
        statusDiv.textContent = 'Ready';
        statusDiv.className = 'chat-status';
        
    } catch (error) {
        console.error('Chat error:', error);
        typingIndicator.remove();
        addChatMessage('Sorry, I encountered an error. Please try again.', 'error');
        statusDiv.textContent = 'Error';
        statusDiv.className = 'chat-status error';
    } finally {
        sendBtn.disabled = false;
    }
}

function addChatMessage(content, type, contextCount = null) {
    const messagesContainer = document.getElementById('chatMessages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}`;
    
    let html = `<div class="message-content">${escapeHtml(content)}</div>`;
    html += `<div class="message-time">${new Date().toLocaleTimeString()}</div>`;
    
    if (type === 'assistant' && contextCount !== null) {
        html += `<div class="context-info">📚 Based on ${contextCount} document(s)</div>`;
    }
    
    messageDiv.innerHTML = html;
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Voice Recording
async function toggleVoiceRecording() {
    const btn = document.getElementById('voiceBtn');
    
    if (!isRecording) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };
            
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                await sendVoiceMessage(audioBlob);
                stream.getTracks().forEach(track => track.stop());
            };
            
            mediaRecorder.start();
            isRecording = true;
            btn.classList.add('recording');
            btn.querySelector('.voice-text').textContent = 'Recording... Click to Stop';
            
        } catch (error) {
            console.error('Microphone access denied:', error);
            alert('Please allow microphone access to use voice input.');
        }
    } else {
        mediaRecorder.stop();
        isRecording = false;
        btn.classList.remove('recording');
        btn.querySelector('.voice-text').textContent = 'Hold to Speak';
    }
}

async function sendVoiceMessage(audioBlob) {
    const messagesContainer = document.getElementById('chatMessages');
    const statusDiv = document.getElementById('chatStatus');
    
    // Clear welcome message if present
    const welcomeMsg = messagesContainer.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }
    
    // Show processing indicator
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'typing-indicator';
    typingIndicator.innerHTML = '<span></span><span></span><span></span>';
    messagesContainer.appendChild(typingIndicator);
    
    statusDiv.textContent = 'Processing voice...';
    statusDiv.className = 'chat-status processing';
    
    try {
        // Convert blob to base64
        const base64Audio = await blobToBase64(audioBlob);
        
        const response = await fetch(`${API_URL}/voice-chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                audio_data: base64Audio,
                conversation_id: currentConversationId
            })
        });
        
        if (!response.ok) {
            throw new Error('Voice processing failed');
        }
        
        const data = await response.json();
        
        typingIndicator.remove();
        
        // Add user's transcribed message
        if (data.user_text) {
            addChatMessage(data.user_text, 'user');
        }
        
        // Add assistant response
        addChatMessage(data.answer, 'assistant', data.context_count);
        
        // Update conversation ID
        if (data.conversation_id) {
            currentConversationId = data.conversation_id;
        }
        
        statusDiv.textContent = 'Ready';
        statusDiv.className = 'chat-status';
        
    } catch (error) {
        console.error('Voice chat error:', error);
        typingIndicator.remove();
        addChatMessage('Sorry, I couldn\'t process your voice. Please try again or type your question.', 'error');
        statusDiv.textContent = 'Error';
        statusDiv.className = 'chat-status error';
    }
}

function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
            const base64 = reader.result.split(',')[1];
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

// ==================== DOCUMENT MANAGEMENT ====================

async function loadDocuments() {
    const listDiv = document.getElementById('documentsList');
    listDiv.innerHTML = '<div class="loading">Loading documents...</div>';

    try {
        console.log('Fetching documents from:', `${API_URL}/documents`);
        const response = await fetch(`${API_URL}/documents`);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('API error:', response.status, errorText);
            throw new Error(`API error: ${response.status}`);
        }

        const documents = await response.json();
        console.log('Documents received:', documents);
        
        if (!documents || documents.length === 0) {
            listDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📄</div>
                    <p>No documents uploaded yet</p>
                    <p>Click "Upload Document" to get started</p>
                    <p style="font-size: 12px; margin-top: 10px; color: #999;">
                        If you've uploaded documents, check that the RAG indexer has processed them.
                    </p>
                </div>
            `;
            return;
        }

        listDiv.innerHTML = documents.map(doc => `
            <div class="document-item">
                <div class="document-info">
                    <div class="document-name">${doc.file_name || doc.name || 'Unnamed'}</div>
                    <div class="document-meta">
                        Type: ${doc.file_type || doc.type || 'Unknown'} | 
                        Indexed: ${formatDate(doc.indexed_at || doc.created_at)}
                    </div>
                </div>
                <button class="btn-danger" onclick="deleteDocument('${doc.id}')">Delete</button>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading documents:', error);
        listDiv.innerHTML = `
            <div class="error-message show">
                Error loading documents: ${error.message}<br>
                <small>Check browser console (F12) for details.</small>
            </div>
        `;
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

        statusDiv.textContent = `Successfully uploaded ${files.length} file(s)! Processing will begin shortly.`;
        statusDiv.className = 'status-message show success';
        
        // Clear file input
        event.target.value = '';
        
        // Reload documents after a delay (to allow for processing)
        setTimeout(() => {
            loadDocuments();
            statusDiv.classList.remove('show');
        }, 3000);
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

// ==================== CONVERSATION MANAGEMENT ====================

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
                    <p>Start a conversation in the Chat tab to see it here</p>
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
                        <div>${escapeHtml(msg.content)}</div>
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

// ==================== UTILITIES ====================

function formatDate(timestamp) {
    if (!timestamp) return 'Unknown';
    // Handle both Unix timestamps and ISO strings
    const date = typeof timestamp === 'number' 
        ? new Date(timestamp * 1000) 
        : new Date(timestamp);
    return date.toLocaleString();
}
