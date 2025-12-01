# Voice Agent Frontend

Complete frontend application for the AI Voice Agent system.

## Features

- **Landing Page**: Welcome page with feature overview
- **Login**: Simple authentication (admin/admin)
- **Dashboard**: 
  - **RAG Section**: Upload, view, and delete documents
  - **Conversation Section**: View conversation history

## Access

After starting docker-compose, access at: **http://localhost:3001**

## Login Credentials

- Username: `admin`
- Password: `admin`

## File Structure

```
frontend/
├── index.html    # Main HTML file
├── styles.css    # Styling
├── app.js        # JavaScript logic
└── README.md     # This file
```

## API Endpoints Used

The frontend calls these API endpoints:

- `GET /api/documents` - List documents
- `POST /api/documents/upload` - Upload document
- `DELETE /api/documents/{id}` - Delete document
- `GET /api/conversations` - List conversations
- `GET /api/conversations/{id}` - Get conversation details
