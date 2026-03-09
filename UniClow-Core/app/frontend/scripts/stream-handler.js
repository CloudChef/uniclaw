/**
 * SSE Stream Response Handler
 * Handle streaming events from Agent runs
 * 
 * Backend SSE event types:
 * - lifecycle: { phase: 'start' | 'end' | 'error' | 'timeout' }
 * - assistant: { text: string, is_delta: boolean }
 * - tool: { tool: string, phase: 'start' | 'update' | 'end', result?: string }
 * - error: { message: string, code?: string }
 * - heartbeat: { timestamp: string }
 */

import { buildApiUrl } from './config.js';

/**
 * Backend SSE event types
 */
export const EventTypes = {
    LIFECYCLE: 'lifecycle',
    ASSISTANT: 'assistant',
    TOOL: 'tool',
    ERROR: 'error',
    HEARTBEAT: 'heartbeat'
};

/**
 * Create stream response handler
 * @param {string} runId - Agent run ID
 * @param {object} callbacks - Event callback functions
 * @returns {object} Controller { start, abort }
 */
export function createStreamHandler(runId, callbacks = {}) {
    let eventSource = null;
    let aborted = false;
    
    const {
        onStart = () => {},
        onDelta = () => {},
        onToolStart = () => {},
        onToolEnd = () => {},
        onEnd = () => {},
        onError = () => {}
    } = callbacks;
    
    /**
     * Start stream connection
     */
    function start() {
        if (eventSource || aborted) return;
        
        // Backend endpoint: /api/agent/runs/{run_id}/stream
        const url = buildApiUrl(`/api/agent/runs/${runId}/stream`);
        eventSource = new EventSource(url, { withCredentials: true });
        
        eventSource.onopen = () => {
            console.log('[Stream] Connected:', runId);
        };
        
        eventSource.onerror = (error) => {
            console.error('[Stream] Connection error:', error);
            // Only call onError when connection completely fails
            if (eventSource && eventSource.readyState === EventSource.CLOSED) {
                onError({ message: 'Connection closed unexpectedly' });
                close();
            }
        };
        
        // Listen for lifecycle events
        eventSource.addEventListener(EventTypes.LIFECYCLE, (e) => {
            const data = parseEventData(e.data);
            console.log('[Stream] Lifecycle:', data.phase);
            
            if (data.phase === 'start') {
                onStart(data);
            } else if (data.phase === 'end') {
                onEnd(data);
                close();
            } else if (data.phase === 'error' || data.phase === 'timeout') {
                onError({ message: data.error || 'Lifecycle error' });
                close();
            }
        });
        
        // Listen for assistant events
        eventSource.addEventListener(EventTypes.ASSISTANT, (e) => {
            const data = parseEventData(e.data);
            // Backend sends { text: string, is_delta: boolean }
            onDelta({ content: data.text, is_delta: data.is_delta });
        });
        
        // Listen for tool events
        eventSource.addEventListener(EventTypes.TOOL, (e) => {
            const data = parseEventData(e.data);
            // Backend sends { tool: string, phase: string, result?: string }
            if (data.phase === 'start') {
                onToolStart({ tool_name: data.tool });
            } else if (data.phase === 'end') {
                onToolEnd({ tool_name: data.tool, result: data.result });
            }
        });
        
        // Listen for error events
        eventSource.addEventListener(EventTypes.ERROR, (e) => {
            const data = parseEventData(e.data);
            onError({ message: data.message, code: data.code });
            close();
        });
        
        // Listen for heartbeat events (optional, for keeping connection alive)
        eventSource.addEventListener(EventTypes.HEARTBEAT, (e) => {
            console.log('[Stream] Heartbeat received');
        });
    }
    
    /**
     * Parse event data
     */
    function parseEventData(data) {
        try {
            return JSON.parse(data);
        } catch (e) {
            console.warn('[Stream] Failed to parse event data:', data);
            return { raw: data };
        }
    }
    
    /**
     * Close connection
     */
    function close() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
            console.log('[Stream] Closed:', runId);
        }
    }
    
    /**
     * Abort stream
     */
    function abort() {
        aborted = true;
        close();
        console.log('[Stream] Aborted:', runId);
    }
    
    return {
        start,
        abort,
        isConnected: () => eventSource !== null && eventSource.readyState === EventSource.OPEN
    };
}

/**
 * Simplified stream request
 * @param {string} runId - Run ID
 * @param {function} onChunk - Content callback
 * @param {function} onComplete - Completion callback
 * @returns {function} Abort function
 */
export function streamResponse(runId, onChunk, onComplete) {
    let content = '';
    
    const handler = createStreamHandler(runId, {
        onDelta: (data) => {
            // Backend sends { content: text, is_delta: boolean }
            if (data.content) {
                content += data.content;
                onChunk(data.content, content);
            }
        },
        onEnd: () => {
            onComplete(content);
        },
        onError: (error) => {
            console.error('[Stream] Error:', error.message || error);
            onComplete(content, error);
        }
    });
    
    handler.start();
    return () => handler.abort();
}

export default {
    EventTypes,
    createStreamHandler,
    streamResponse
};
