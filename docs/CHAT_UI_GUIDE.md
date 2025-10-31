# ChatGPT-Style Chat UI Guide

## Overview

The PVCFC RAG system now includes a modern ChatGPT-style chat interface for natural multi-turn conversations with technical documents.

## Features

### Chat Experience

- **Message Bubbles**: User (blue, right) and Bot (gray, left)
- **Typing Indicator**: Animated dots (●●●) while bot is responding
- **Auto-scroll**: Automatically scrolls to newest message
- **Smart History**: Shows last 20 messages with "Load earlier" option
- **Citations**: Expandable under each bot response
- **Metadata**: Hover over messages to see model, confidence, timestamp

### Design

- **Clean & Minimal**: ChatGPT-inspired design
- **Light Mode**: White background (#FFFFFF)
- **User Messages**: Blue (#0084FF), right-aligned
- **Bot Messages**: Light gray (#F7F7F8), left-aligned
- **No Avatars**: Clean bubble-only design
- **Responsive**: Works on desktop (1920x1080, 1366x768)

## How to Use

### 1. Start the Application

```powershell
# Make sure Redis is running
docker-compose up -d redis

# Start Streamlit
cd streamlit_app
streamlit run app.py
```

### 2. Navigate to Chat

- Open browser: http://localhost:8501
- Sidebar: Click "💬 Chat" (default page)

### 3. Start Chatting

**First Message:**
```
You: K06101 là gì?
```

**Follow-up:**
```
You: Áp suất của nó?
Bot: (understands "nó" = K06101 from context)
```

### 4. View Citations

Click "📚 Citations (N)" under bot messages to see sources.

### 5. New Conversation

Click "🔄 New Conversation" in sidebar to start fresh.

## UI Components

### Message Bubbles

**User Message** (Right, Blue):
```
                    ┌─────────────────┐
                    │ Your question   │
                    └─────────────────┘
```

**Bot Message** (Left, Gray):
```
┌────────────────────────────┐
│ Bot response with answer   │
│                            │
│ 📚 Citations (2)           │ ← Click to expand
└────────────────────────────┘
```

### Typing Indicator

While bot is responding:
```
●●●  (bouncing animation)
```

### Input Box

Fixed at bottom of screen:
```
┌─────────────────────────────────────┐
│ Type your message...                │
│                                 📤  │
└─────────────────────────────────────┘
```

- Type and press Enter to send
- Or click 📤 Send button
- Disabled during response

### Message History

- Shows last 20 messages
- Older messages: Click "↑ Load earlier messages"
- Auto-scrolls to bottom on new message
- Manual scroll up: Shows "↓" button to jump to bottom

## Advanced Features

### Hover Metadata

Hover over any message to see:
- Time (HH:MM)
- Model used (for bot messages)
- Confidence score

### Expandable Citations

Each citation shows:
- Document filename
- Page number
- Confidence score
- TODO: "View Page" button (future)

### Error Handling

- **API Offline**: Red banner, Send button disabled
- **Timeout**: Error message, retry available
- **Conversation Expired**: Auto-starts new conversation

## Comparison: Chat vs Advanced Mode

### Chat Mode (Default)
- ✅ Clean, minimal interface
- ✅ Focus on conversation flow
- ✅ Easy for non-technical users
- ✅ ChatGPT-like experience

### Advanced Mode (Power Users)
- ✅ Full parameter control
- ✅ Debug information
- ✅ Retrieval details
- ✅ Metrics visualization
- ✅ Timeline charts

**Access Advanced Mode**: Sidebar → "🔬 Advanced"

## Configuration

No configuration needed - chat UI uses global settings from sidebar:

- API Base URL
- Language (vi/en)
- Vision enabled/disabled
- Health status

## Keyboard Shortcuts

- **Enter**: Send message
- **Shift+Enter**: New line in message (TODO: implement)
- **Esc**: Clear input (TODO: implement)

## Technical Details

### Components

- `streamlit_app/components/chat_interface.py` - Main chat component
- `streamlit_app/components/typing_indicator.py` - Typing dots
- `streamlit_app/styles/chat_bubbles.css` - Styling

### Session State

```python
st.session_state.conversation_id       # Current conversation
st.session_state.conversation_history  # List of messages
st.session_state.is_processing        # Bot responding?
st.session_state.message_offset       # Pagination offset
```

### Message Structure

```python
{
    "role": "user" | "assistant",
    "content": "Message text",
    "citations": [...],        # Bot only
    "metadata": {              # Bot only
        "model": "gemini-2.5-pro",
        "confidence": 0.95
    },
    "timestamp": "2025-10-20T10:30:00"
}
```

## Performance

- **Message Limit**: 20 displayed (prevents lag)
- **Auto-scroll**: Smooth with 300ms delay
- **Typing Indicator**: Pure CSS (no JS overhead)
- **Pagination**: Lazy load older messages

## Browser Compatibility

Tested on:
- ✅ Chrome 120+
- ✅ Edge 120+
- ✅ Firefox 120+

## Known Limitations

1. **No Streaming**: Messages appear complete (not word-by-word)
   - TODO: Add SSE streaming in future

2. **No Edit**: Cannot edit sent messages
   - Design decision: Matches ChatGPT free tier

3. **No Delete**: Cannot delete messages
   - Use "New Conversation" instead

4. **Fixed Layout**: No responsive mobile (yet)
   - Optimized for desktop only

## Troubleshooting

### Issue: Messages don't auto-scroll

**Solution**: Refresh page (Ctrl+R)

### Issue: Typing indicator stuck

**Solution**: Click "New Conversation" to reset

### Issue: Citations don't expand

**Solution**: Check browser console for errors

### Issue: Input box not sticky

**Solution**: Check CSS loaded (View Source → chat_bubbles.css)

## Future Enhancements

Planned for Phase 2:

- [ ] Streaming responses (word-by-word)
- [ ] Message editing
- [ ] Conversation search
- [ ] Export conversation
- [ ] Dark mode support
- [ ] Mobile responsive design
- [ ] Keyboard shortcuts
- [ ] Message reactions (👍 👎)
- [ ] Copy message button
- [ ] Code syntax highlighting

## Feedback

The chat UI is designed to be:
- **Familiar**: Like ChatGPT (users already know how to use)
- **Clean**: Minimal distractions
- **Functional**: Citations + metadata when needed
- **Fast**: Optimized for smooth interactions

Enjoy chatting with your documents! 💬
