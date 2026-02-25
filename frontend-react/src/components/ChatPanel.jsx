import { useState, useRef, useEffect } from 'react';
import { Send, LogOut } from 'lucide-react';

export function ChatPanel({ 
    messages, 
    isWaiting, 
    currentStreamText, 
    onSendMessage,
    onLogout
}) {
    const [inputText, setInputText] = useState('');
    const textareaRef = useRef(null);
    const messagesEndRef = useRef(null);

    // Auto-scroll to bottom of chat
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, currentStreamText]);

    const handleInput = (e) => {
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

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <section className="chat-panel">
            {messages.length === 0 && !currentStreamText && (
                <div className="welcome-screen">
                    <div className="welcome-content">
                        <div className="welcome-icon">🩺</div>
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

            <div className="chat-messages">
                {messages.map((msg, idx) => (
                    <div key={idx} className={`message ${msg.role === 'student' ? 'user-message' : 'system-message'}`}>
                        {msg.role === 'system' && <div className="avatar">⚙️</div>}
                        {msg.role === 'patient' && <div className="avatar">🧑</div>}
                        <div className="bubble">
                            {/* React completely neutralizes XSS here by safely evaluating msg.content */}
                            {msg.content.split('\n').map((line, i) => (
                                <span key={i}>
                                    {line}
                                    <br />
                                </span>
                            ))}
                        </div>
                    </div>
                ))}
                
                {currentStreamText && (
                    <div className="message system-message">
                        <div className="avatar">🧑</div>
                        <div className="bubble">
                            {currentStreamText.split('\n').map((line, i) => (
                                <span key={i}>
                                    {line}
                                    <br />
                                </span>
                            ))}
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

            <div className="input-bar">
                <textarea 
                    ref={textareaRef}
                    placeholder={isWaiting ? "Wait for patient response..." : "Type your response to James..."}
                    value={inputText}
                    onChange={handleInput}
                    onKeyDown={handleKeyDown}
                    disabled={isWaiting}
                    rows="1"
                />
                <button 
                    className="btn-send"
                    onClick={handleSend}
                    disabled={!inputText.trim() || isWaiting}
                >
                    <Send size={18} />
                </button>
            </div>
        </section>
    );
}
