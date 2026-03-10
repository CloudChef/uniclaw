/**
 * DeepChat UI Configuration and Interaction
 * Configure DeepChat component integration with Uniclaw API
 */

import { getSessionKey, initSession } from './session-manager.js';
import { createStreamHandler } from './stream-handler.js';
import { buildApiUrl } from './config.js';
import { t, isLocaleLoaded } from './i18n.js';

let chatElement = null;
let currentStreamHandler = null;

/**
 * Initialize DeepChat component
 * @param {HTMLElement} element - DeepChat DOM element
 */
export async function initChat(element) {
    chatElement = element;
    
    // Ensure session is initialized
    await initSession();
    
    // Configure connection (for non-streaming fallback)
    configureChatConnection(element);
    
    // Configure interceptors
    configureInterceptors(element);
    
    // Configure i18n attributes
    configureI18nAttributes(element);
    
    console.log('[ChatUI] Initialized');
}

/**
 * Configure chat connection
 */
function configureChatConnection(element) {
    element.connect = {
        url: buildApiUrl('/api/agent/run'),
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    };
}

/**
 * Configure i18n attributes
 */
function configureI18nAttributes(element) {
    if (!isLocaleLoaded()) {
        console.warn('[ChatUI] Locale not loaded, skipping i18n config');
        return;
    }
    
    // Set introMessage
    const introMessage = t('chat.introMessage');
    element.introMessage = { text: introMessage };
    
    // Set placeholder
    const placeholder = t('chat.placeholder');
    element.textInput = {
        placeholder: {
            text: placeholder,
            style: { color: '#999' }
        },
        styles: {
            container: {
                borderRadius: '24px',
                border: '1px solid #ddd',
                padding: '12px 20px',
                backgroundColor: '#ffffff',
                boxShadow: '0 2px 6px rgba(0,0,0,0.05)'
            },
            text: { fontSize: '15px' }
        }
    };
}

/**
 * Configure request and response interceptors
 */
function configureInterceptors(element) {
    // Request interceptor: convert DeepChat format to Uniclaw API format
    element.requestInterceptor = async (request) => {
        console.log('[ChatUI] Request intercepted:', request);
        
        // Extract message text
        const messageText = extractMessageText(request.body);
        
        // Get session key
        const sessionKey = getSessionKey();
        if (!sessionKey) {
            console.error('[ChatUI] No session key');
            throw new Error('Session not initialized');
        }

        // Let DeepChat send the single authoritative POST /api/agent/run request.
        request.body = {
            session_key: sessionKey,
            message: messageText
        };
        return request;
    };
    
    // Response interceptor
    element.responseInterceptor = async (response) => {
        if (response?.run_id) {
            startStreamingRun(response.run_id);
            return { text: '...' };
        }
        return response;
    };
}

/**
 * Extract message text from request body
 */
function extractMessageText(body) {
    if (!body) return '';
    
    if (typeof body === 'string') {
        try {
            const parsed = JSON.parse(body);
            if (parsed.messages) {
                const last = parsed.messages[parsed.messages.length - 1];
                return last.text || last.content || '';
            }
            return parsed.message || parsed.text || '';
        } catch (e) {
            return body;
        }
    }
    
    if (body.messages) {
        const last = body.messages[body.messages.length - 1];
        return last.text || last.content || '';
    }
    
    return body.message || body.text || '';
}

/**
 * Start streaming for an existing run
 */
function startStreamingRun(runId) {
    console.log('[ChatUI] Started run:', runId);
    
    // Create AI message placeholder
    let aiMessageContent = '';
    currentStreamHandler = createStreamHandler(runId, {
        onStart: () => {
            console.log('[ChatUI] Stream started');
        },
        onDelta: (data) => {
            if (data.content) {
                aiMessageContent += data.content;
                updateAiMessage(aiMessageContent);
            }
        },
        onToolStart: (data) => {
            console.log('[ChatUI] Tool start:', data.tool_name);
            showToolIndicator(data.tool_name);
        },
        onToolEnd: (data) => {
            console.log('[ChatUI] Tool end:', data.tool_name);
            hideToolIndicator();
        },
        onEnd: () => {
            console.log('[ChatUI] Stream ended');
            finalizeAiMessage(aiMessageContent);
            currentStreamHandler = null;
        },
        onError: (error) => {
            console.error('[ChatUI] Stream error:', error);
            currentStreamHandler = null;
        }
    });

    currentStreamHandler.start();
}

/**
 * Update AI message (streaming)
 */
function updateAiMessage(content) {
    if (!chatElement) return;

    chatElement.addMessage({ text: content, role: 'ai', overwrite: true });
}

/**
 * Finalize AI message
 */
function finalizeAiMessage(content) {
    if (!chatElement) return;
    chatElement.addMessage({ text: content, role: 'ai', overwrite: true });
}

/**
 * Show tool execution indicator
 */
function showToolIndicator(toolName) {
    // Can use DOM manipulation to show loading indicator
    console.log('[ChatUI] Executing tool:', toolName);
}

/**
 * Hide tool indicator
 */
function hideToolIndicator() {
    // Hide loading indicator
}

/**
 * Abort current stream
 */
export function abortCurrentStream() {
    if (currentStreamHandler) {
        currentStreamHandler.abort();
        currentStreamHandler = null;
    }
}

/**
 * Get DeepChat element
 */
export function getChatElement() {
    return chatElement;
}

export default {
    initChat,
    abortCurrentStream,
    getChatElement,
    configureI18nAttributes
};
