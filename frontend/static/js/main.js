let conversationLog = []; // For client-side display log
const userId = 'user_' + Math.random().toString(36).substr(2, 9); // Simple unique user ID for session

document.addEventListener('DOMContentLoaded', () => {
    // Initialize the interface
    setupInputHandlers();
    updateChatList();
    document.getElementById('input').focus();
    
    // Set initial welcome message (it's already in HTML, but we can update log)
    conversationLog.push({ 
        role: 'assistant', 
        content: "Hi! I'm your ArangoDB assistant. I can help you with database operations, queries, and more. What would you like to do today?" 
    });
});

function setupInputHandlers() {
    const inputElement = document.getElementById('input');
    const sendButton = document.getElementById('send');
    
    // Auto-resize textarea
    inputElement.addEventListener('input', () => {
        inputElement.style.height = 'auto';
        inputElement.style.height = Math.min(inputElement.scrollHeight, 150) + 'px';
        
        // Enable/disable send button based on content
        const hasContent = inputElement.value.trim().length > 0;
        sendButton.disabled = !hasContent;
    });
    
    // Initial state
    sendButton.disabled = true;
    
    // Keyboard handlers
    inputElement.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendButton.disabled) {
                sendMessage();
            }
        }
    });
    
    sendButton.addEventListener('click', sendMessage);
}

async function sendMessage() {
    const inputElement = document.getElementById('input');
    const sendButton = document.getElementById('send');
    const messageText = inputElement.value.trim();

    if (!messageText) return;

    // Disable input during processing
    inputElement.disabled = true;
    sendButton.disabled = true;
    
    // Add user message to UI
    appendMessage('user', messageText);
    inputElement.value = '';
    inputElement.style.height = 'auto'; // Reset height
    
    // Add to conversation log
    conversationLog.push({ role: 'user', content: messageText });
    updateChatList();

    // Show typing indicator
    showTypingIndicator();

    try {
        const response = await fetch(API_CHAT_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: messageText, user_id: userId })
        });

        hideTypingIndicator(); // Hide indicator once response starts or fails

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: "Unknown error fetching response." }));
            const errorMsg = `❌ **Error ${response.status}**: ${errorData.detail || "Failed to get response"}`;
            appendMessage('bot', errorMsg);
            conversationLog.push({ role: 'assistant', content: errorMsg });
            return;
        }

        const data = await response.json();
        appendMessage('bot', data.response);
        conversationLog.push({ role: 'assistant', content: data.response });
        updateChatList();

    } catch (error) {
        hideTypingIndicator(); // Ensure indicator is hidden on network error
        console.error('Error sending message:', error);
        const errorMsg = "❌ **Connection Error**: Sorry, I couldn't connect to the assistant. Please check your connection and try again.";
        appendMessage('bot', errorMsg);
        conversationLog.push({ role: 'assistant', content: errorMsg });
    } finally {
        // Re-enable input
        inputElement.disabled = false;
        inputElement.focus();
        // Ensure send button state is correct if input is now empty
        sendButton.disabled = inputElement.value.trim().length === 0;

    }
}

function appendMessage(sender, text) {
    const messagesContainer = document.getElementById('messages');
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('msg', sender === 'user' ? 'user' : 'bot');

    // Create avatar
    const avatar = document.createElement('div');
    avatar.classList.add('avatar', sender === 'user' ? 'user-avatar' : 'bot-avatar');
    
    const avatarIcon = document.createElement('i');
    avatarIcon.classList.add('fas', sender === 'user' ? 'fa-user' : 'fa-robot');
    avatar.appendChild(avatarIcon);

    // Create message content container
    const messageContent = document.createElement('div');
    messageContent.classList.add('message-content');

    const bubbleDiv = document.createElement('div');
    bubbleDiv.classList.add('bubble');
    
    const messageTextDiv = document.createElement('div');
    messageTextDiv.classList.add('message-text');
    
    // Use marked.js for markdown parsing
    const htmlText = parseMarkdown(text);
    messageTextDiv.innerHTML = htmlText;
    
    bubbleDiv.appendChild(messageTextDiv);
    messageContent.appendChild(bubbleDiv);
    
    // Append elements in correct order based on sender
    if (sender === 'user') {
        messageDiv.appendChild(messageContent);
        messageDiv.appendChild(avatar);
    } else {
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(messageContent);
    }
    
    messagesContainer.appendChild(messageDiv);
    
    // Smooth scroll to bottom
    setTimeout(() => {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }, 100);
    
    // Apply syntax highlighting if Prism is available
    if (window.Prism) {
        Prism.highlightAllUnder(messageDiv);
    }
}

function parseMarkdown(text) {
    if (window.marked) {
        // Configure marked (optional, but good for consistency)
        marked.setOptions({
            pedantic: false,
            gfm: true,        // Enable GitHub Flavored Markdown
            breaks: true,     // Convert GFM line breaks to <br>
            smartLists: true,
            smartypants: false,
            xhtml: false
            // We'll let Prism.highlightAllUnder handle syntax highlighting after DOM update
        });
        return marked.parse(text);
    }
    // Fallback to simple escaping if marked.js is not loaded
    const div = document.createElement('div');
    div.textContent = text; // Basic text escaping
    let html = div.innerHTML.replace(/\n/g, '<br>');
    // Simple inline code and bold for fallback
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    return html;
}

// Loading overlay functions are no longer needed
// function showLoadingOverlay() { ... }
// function hideLoadingOverlay() { ... }

// Chat history functions
function updateChatList() {
    const chatList = document.getElementById('chat-list');
    if (!chatList) return;
    
    chatList.innerHTML = '';
    
    // Create entry for current conversation
    if (conversationLog.length > 0) {
        const li = document.createElement('li');
        
        // Get first user message for preview
        const firstUserMsg = conversationLog.find(msg => msg.role === 'user');
        const preview = firstUserMsg ? firstUserMsg.content.substring(0, 30) + '...' : 'New Chat';
        const messageCount = Math.floor(conversationLog.length / 2); // Approximation of Q/A pairs
        
        li.innerHTML = `
            <div style="font-weight: 500; margin-bottom: 2px;">${preview}</div>
            <div style="font-size: 0.75rem; color: #666;">${messageCount > 0 ? messageCount : ''} ${messageCount === 1 ? 'exchange' : messageCount > 1 ? 'exchanges' : 'Empty Chat'}</div>
        `;
        
        li.onclick = () => renderFullConversationLog();
        chatList.appendChild(li);
    }
}

function renderFullConversationLog() {
    const messagesContainer = document.getElementById('messages');
    messagesContainer.innerHTML = '';
    
    // Re-render all messages
    conversationLog.forEach(msg => {
        const role = msg.role === 'user' ? 'user' : 'bot';
        appendMessage(role, msg.content);
    });
    
    console.log("Rendered full current conversation log.");
}

// Server history management
async function clearServerHistory() {
    try {
        const response = await fetch(`${API_CLEAR_URL}/${userId}`, { 
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: "Failed to clear history" }));
            throw new Error(errorData.detail || "Clear history request failed");
        }
        
        const data = await response.json();
        console.log('Server history cleared:', data.status);
        return true;
    } catch (error) {
        console.error('Error clearing server history:', error);
        appendMessage('bot', `❌ **Error clearing server history**: ${error.message}`);
        return false;
    }
}

// New chat functionality
async function startNewChat() {
    // Show a temporary "Starting new chat..." message if needed, or rely on quick UI update
    const tempIndicator = document.getElementById('typing-indicator');
    if (tempIndicator) tempIndicator.remove(); // Remove any stray indicator

    showTypingIndicator(); // Show briefly while clearing

    try {
        const serverCleared = await clearServerHistory();
        
        if (serverCleared) {
            // Clear the messages container
            const messagesContainer = document.getElementById('messages');
            messagesContainer.innerHTML = '';
            
            // Reset conversation log
            conversationLog = [];
            
            // Add welcome message
            const welcomeMsg = "Hi! I'm your ArangoDB assistant. I can help you with database operations, queries, and more. What would you like to do today?";
            appendMessage('bot', welcomeMsg);
            conversationLog.push({ role: 'assistant', content: welcomeMsg });
            
            updateChatList();
            
            // Focus input
            document.getElementById('input').focus();
            
        } else {
            appendMessage('bot', "❌ **Error**: Could not start a new chat cleanly due to server history clear failure.");
        }
    } finally {
        hideTypingIndicator();
    }
}

// Event listeners setup
document.addEventListener('DOMContentLoaded', () => {
    // New chat button
    const newChatBtn = document.getElementById('new-chat');
    if (newChatBtn) {
        newChatBtn.addEventListener('click', startNewChat);
    }
    
    // Handle window resize for responsive design
    window.addEventListener('resize', () => {
        const messagesContainer = document.getElementById('messages-container');
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    });
});

// Auto-scroll to bottom when new messages arrive
function scrollToBottom() {
    const messagesContainer = document.getElementById('messages-container');
    if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

// Utility function to format timestamps
function formatTimestamp(date = new Date()) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Add typing indicator (optional enhancement)
function showTypingIndicator() {
    const messagesContainer = document.getElementById('messages');
    // Remove any existing typing indicator first
    hideTypingIndicator();

    const typingDiv = document.createElement('div');
    typingDiv.classList.add('msg', 'bot', 'typing-indicator');
    typingDiv.id = 'typing-indicator'; // Give it an ID for easy removal
    
    const avatar = document.createElement('div');
    avatar.classList.add('avatar', 'bot-avatar');
    avatar.innerHTML = '<i class="fas fa-robot"></i>';
    
    const messageContent = document.createElement('div');
    messageContent.classList.add('message-content');
    
    const bubbleDiv = document.createElement('div');
    bubbleDiv.classList.add('bubble');
    bubbleDiv.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
    
    messageContent.appendChild(bubbleDiv);
    typingDiv.appendChild(avatar);
    typingDiv.appendChild(messageContent);
    
    messagesContainer.appendChild(typingDiv);
    scrollToBottom();
}

function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Export functions for potential use in other modules
window.chatInterface = {
    sendMessage,
    appendMessage,
    startNewChat,
    clearServerHistory,
    showTypingIndicator, // Expose for potential external calls if needed
    hideTypingIndicator  // Expose for potential external calls if needed
};