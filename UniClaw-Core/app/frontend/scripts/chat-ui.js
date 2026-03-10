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

    // Configure connection
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

    if (typeof element.render === 'function') {
        element.render();
    }
}

/**
 * Configure request and response interceptors
 */
function configureInterceptors(element) {
    element.requestInterceptor = async (request) => {
        console.log('[ChatUI] Request intercepted:', request);

        const body = parseRequestBody(request.body);
        const messageText = extractMessageText(body);

        let sessionKey = getSessionKey();
        if (!sessionKey) {
            sessionKey = await initSession();
        }

        request.body = {
            session_key: sessionKey || '',
            message: messageText || '',
            timeout_seconds: 600
        };

        return request;
    };

    element.responseInterceptor = (response) => {
        const payload = parseResponseBody(response);
        const runId = payload?.run_id || payload?.runId || payload?.id;

        if (!runId || typeof runId !== 'string') {
            console.warn('[ChatUI] Missing run_id in /api/agent/run response:', response);
            if (payload?.detail) {
                console.warn('[ChatUI] /api/agent/run validation detail:', payload.detail);
            }
            return response;
        }

        handleStreamingResponse(runId).catch((err) => {
            console.error('[ChatUI] Streaming failed:', err);
        });

        return { text: '' };
    };
}

function parseRequestBody(raw) {
    if (!raw) return {};
    if (typeof raw === 'object') return raw;
    if (typeof raw !== 'string') return { text: String(raw) };
    try {
        return JSON.parse(raw);
    } catch {
        return { text: raw };
    }
}

function parseResponseBody(raw) {
    if (!raw) return {};
    if (typeof raw === 'object') return raw;
    if (typeof raw !== 'string') return {};
    try {
        return JSON.parse(raw);
    } catch {
        return {};
    }
}

/**
 * Configure i18n attributes
 */
function configureI18nAttributes(element) {
    if (!isLocaleLoaded()) {
        console.warn('[ChatUI] Locale not loaded, skipping i18n config');
        return;
    }

    const introMessage = t('chat.introMessage');
    element.introMessage = { text: introMessage };

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
 * Extract message text from request body
 */
function extractMessageText(body) {
    if (!body) return '';

    if (typeof body === 'string') return body;

    if (body.messages && Array.isArray(body.messages) && body.messages.length > 0) {
        const lastMessage = body.messages[body.messages.length - 1] || {};
        if (typeof lastMessage === 'string') return lastMessage;
        if (lastMessage.text) return String(lastMessage.text);
        if (lastMessage.content) return String(lastMessage.content);
    }

    if (body.message) return String(body.message);
    if (body.text) return String(body.text);
    if (body.input) return String(body.input);

    return '';
}

/**
 * Handle streaming response
 */
async function handleStreamingResponse(runId) {
    console.log('[ChatUI] Handling streaming response for run:', runId);

    let aiMessageContent = '';
    const canUpdateMessage = !!(chatElement && typeof chatElement.updateMessage === 'function');
    let aiMessageIndex = null;
    let hasRenderedDelta = false;

    if (chatElement && canUpdateMessage) {
        chatElement.addMessage({ text: '', role: 'ai' });
        const messages = chatElement.getMessages ? chatElement.getMessages() : [];
        aiMessageIndex = messages.length - 1;
    }

    return new Promise((resolve, reject) => {
        currentStreamHandler = createStreamHandler(runId, {
            onStart: () => {
                console.log('[ChatUI] Stream started');
            },
            onDelta: (data) => {
                if (data.content) {
                    aiMessageContent += data.content;
                    if (canUpdateMessage) {
                        updateAiMessage(aiMessageContent, aiMessageIndex, canUpdateMessage);
                        hasRenderedDelta = true;
                    }
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
                finalizeAiMessage(aiMessageContent, aiMessageIndex, canUpdateMessage, hasRenderedDelta);
                currentStreamHandler = null;
                resolve({ text: aiMessageContent });
            },
            onError: (error) => {
                console.error('[ChatUI] Stream error:', error);
                appendErrorMessage(error?.message || 'Stream error');
                currentStreamHandler = null;
                reject(error);
            }
        });

        currentStreamHandler.start();
    });
}

function appendErrorMessage(message) {
    if (!chatElement) return;
    if (typeof chatElement.addErrorMessage === 'function') {
        chatElement.addErrorMessage(message);
        return;
    }
    chatElement.addMessage({ text: `Error: ${message}`, role: 'ai' });
}

/**
 * Update AI message (streaming)
 */
function updateAiMessage(content, messageIndex, canUpdateMessage) {
    if (!chatElement) return;
    if (!canUpdateMessage) return;

    if (messageIndex !== null) {
        try {
            chatElement.updateMessage({ text: content, role: 'ai' }, messageIndex);
            return;
        } catch {
            // fallback below
        }
    }
}

/**
 * Finalize AI message
 */
function finalizeAiMessage(content, messageIndex, canUpdateMessage, hasRenderedDelta) {
    if (!chatElement) return;

    if (canUpdateMessage && messageIndex !== null) {
        try {
            chatElement.updateMessage({ text: content, role: 'ai' }, messageIndex);
            return;
        } catch {
            // fallback below
        }
    }

    if (hasRenderedDelta) {
        return;
    }

    chatElement.addMessage({ text: content, role: 'ai' });
}

/**
 * Show tool execution indicator
 */
function showToolIndicator(toolName) {
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
