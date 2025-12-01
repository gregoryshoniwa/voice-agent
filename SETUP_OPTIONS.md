# Setup Options: With or Without n8n

## Option 1: Direct Frontend (Simpler) ⭐ Recommended for Basic Use

**Architecture:**
```
Frontend → Voice Agent API → Services (Whisper, Ollama, Supabase, Piper)
```

**Pros:**
- ✅ Simpler setup
- ✅ Faster response (no n8n overhead)
- ✅ Easier to debug
- ✅ Less moving parts
- ✅ Direct control

**Cons:**
- ❌ No workflow automation
- ❌ Less flexible for complex logic
- ❌ No built-in integrations

**When to use:**
- Simple voice agent interface
- Direct user interaction
- Basic Q&A functionality
- You want full control in your frontend

**Setup:**
1. Use the frontend in `frontend/index.html`
2. Point it to Voice Agent API at `http://localhost:3001`
3. That's it! No n8n needed.

---

## Option 2: Via n8n (More Flexible)

**Architecture:**
```
Frontend → n8n Webhook → Voice Agent API → Services
```

**Pros:**
- ✅ Workflow automation
- ✅ Custom business logic
- ✅ Integration with other services
- ✅ Conditional routing
- ✅ Monitoring and logging
- ✅ Scheduled tasks
- ✅ Error handling workflows

**Cons:**
- ❌ More complex setup
- ❌ Additional latency
- ❌ More moving parts to maintain

**When to use:**
- Need workflow automation
- Want to integrate with other services (email, Slack, etc.)
- Need conditional logic based on queries
- Want to log/store conversations
- Need scheduled tasks or triggers

**Setup:**
1. Import n8n workflows from `n8n-workflows/`
2. Configure webhooks
3. Point frontend to n8n webhook instead of direct API

---

## Hybrid Approach (Best of Both)

You can use both:
- **Frontend** for direct user interaction
- **n8n** for background processing, logging, integrations

Example:
```javascript
// Frontend calls API directly for speed
const response = await fetch('http://localhost:3001/voice-agent/process', ...);

// But also notify n8n for logging/integrations
await fetch('http://localhost:5678/webhook/log-conversation', {
    method: 'POST',
    body: JSON.stringify({ query, answer, timestamp })
});
```

---

## Recommendation

**Start with Option 1 (Direct Frontend)** if you:
- Want to get started quickly
- Need a simple voice agent interface
- Don't need complex workflows yet

**Add n8n later** if you need:
- Workflow automation
- Service integrations
- Complex business logic
- Monitoring and analytics

---

## Quick Start: Direct Frontend

1. **Start services:**
   ```bash
   docker compose -f docker-compose.full.yaml --env-file supabase-project/.env up -d
   ```

2. **Open frontend:**
   ```bash
   cd frontend
   python -m http.server 8080
   # Or use any static file server
   ```

3. **Access:** http://localhost:8080

4. **That's it!** No n8n configuration needed.

The frontend calls the Voice Agent API directly at `http://localhost:3001`.

