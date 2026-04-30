import { useState, useRef, useEffect } from 'react';
import { Send } from 'lucide-react';

export interface ChatMessage {
    role: string;
    content: string;
}

import { useStore } from '../store/useStore';

export function ChatPanel() {
    const messages = useStore(state => state.messages);
    const isWaiting = useStore(state => state.isWaiting);
    const currentStreamText = useStore(state => state.currentStreamText);
    const failedMessage = useStore(state => state.failedMessage);
    const onSendMessage = useStore(state => state.handleSendMessage);
    const setFailedMessage = useStore(state => state.setFailedMessage);
    const onClearFailedMessage = () => setFailedMessage('');
    const [inputText, setInputText] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom of chat
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, currentStreamText]);

    // Recover stranded text on API failure
    useEffect(() => {
        if (failedMessage && onClearFailedMessage) {
            setInputText(failedMessage);
            onClearFailedMessage();
            if (textareaRef.current) {
                textareaRef.current.style.height = 'auto';
            }
        }
    }, [failedMessage, onClearFailedMessage]);

    const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        setInputText(e.target.value);
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
        }
    };

    const handleSend = () => {
        if (!inputText.trim() || isWaiting) return;
        onSendMessage(inputText.trim());
        setInputText('');
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <section className="chat-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', flex: 1 }}>
            <div className="chat-messages" style={{ flex: 1, overflowY: 'auto' }}>
                
                {/* Show the briefing only if no one has spoken yet (ignores the 'Session started' system message) */}
                {messages.filter(msg => msg.role !== 'system').length === 0 && (
                    <div className="welcome-screen" style={{ flex: 'none', padding: '10px 0 30px 0', borderBottom: '1px solid var(--border)', marginBottom: '20px' }}>
                        <div className="welcome-content" style={{ marginTop: 0, margin: '0 auto' }}>
                            <div className="welcome-icon" style={{ fontSize: '48px' }}>🩺</div>
                            <h2>Clinical Interview Simulation</h2>
                            <p>
                                You are about to interview <strong>James</strong>, a 21-year-old
                                university student visiting the psychiatric outpatient clinic for
                                the first time.
                            </p>
                            <div className="scenario-card">
                                <div className="scenario-header">📋 Scenario Briefing</div>
                                <ul style={{textAlign: 'left', marginTop: '10px', fontSize: '0.9rem', color: 'var(--text-secondary)'}}>
                                    <li>Patient was brought by his girlfriend</li>
                                    <li>First psychiatric visit — likely reluctant</li>
                                    <li>Your goal: build rapport, take history, assess risk, form diagnosis</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                )}
                {messages.map((msg, idx) => (
                    <div key={idx} className={`message ${msg.role}`}>
                        {msg.role === 'system' && <div className="message-avatar">⚙️</div>}
                        {msg.role === 'patient' && <div className="message-avatar">🧑</div>}
                        {msg.role === 'student' && <div className="message-avatar">🩺</div>}
                        
                        <div className="message-bubble">
                            {msg.content.split('\n').map((line: string, i: number) => {
                                // Split the line by markdown bold (**text**) or italic (*text*)
                                const parts = line.split(/(\*\*.*?\*\*|\*.*?\*)/g);
                                return (
                                    <span key={i}>
                                        {parts.map((part, j) => {
                                            if (part.startsWith('**') && part.endsWith('**')) {
                                                return <strong key={j}>{part.slice(2, -2)}</strong>;
                                            }
                                            if (part.startsWith('*') && part.endsWith('*')) {
                                                return <em key={j} style={{ color: 'var(--text-secondary)' }}>{part.slice(1, -1)}</em>;
                                            }
                                            return <span key={j}>{part}</span>;
                                        })}
                                        <br />
                                    </span>
                                );
                            })}
                        </div>
                    </div>
                ))}
                
                {currentStreamText && (
                    <div className="message patient">
                        <div className="message-avatar">🧑</div>
                        <div className="message-bubble">
                            {currentStreamText.split('\n').map((line: string, i: number) => {
                                const parts = line.split(/(\*\*.*?\*\*|\*.*?\*)/g);
                                return (
                                    <span key={i}>
                                        {parts.map((part, j) => {
                                            if (part.startsWith('**') && part.endsWith('**')) {
                                                return <strong key={j}>{part.slice(2, -2)}</strong>;
                                            }
                                            if (part.startsWith('*') && part.endsWith('*')) {
                                                return <em key={j} style={{ color: 'var(--text-secondary)' }}>{part.slice(1, -1)}</em>;
                                            }
                                            return <span key={j}>{part}</span>;
                                        })}
                                        <br />
                                    </span>
                                );
                            })}
                        </div>
                    </div>
                )}

                {isWaiting && !currentStreamText && (
                    <div className="typing-indicator">
                        <div className="dot"></div><div className="dot"></div><div className="dot"></div>
                    </div>
                )}
                
                <div ref={messagesEndRef} />
            </div>

            <div className="input-bar" style={{ flexShrink: 0 }}>
                <textarea 
                    ref={textareaRef}
                    placeholder={isWaiting ? "Wait for patient response..." : "Type your response to James..."}
                    value={inputText}
                    onChange={handleInput}
                    onKeyDown={handleKeyDown}
                    disabled={isWaiting}
                    rows={1}
                />
                <button 
                    className="btn-send"
                    title="Send Message"
                    onClick={handleSend}
                    disabled={!inputText.trim() || isWaiting}
                >
                    <Send size={18} />
                </button>
            </div>
        </section>
    );
}
