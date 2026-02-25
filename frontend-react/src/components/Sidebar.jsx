import { FileText, Search } from 'lucide-react';

export function Sidebar({ sessions, currentSessionId, onNewSession, onSelectSession }) {
    return (
        <aside className="sidebar">
            <div className="sidebar-top-actions">
                <button className="btn-sidebar-item" onClick={onNewSession}>
                    <FileText className="sidebar-icon" size={20} />
                    <span>New chat</span>
                </button>
                <button className="btn-sidebar-item" onClick={() => alert('Search feature coming soon!')}>
                    <Search className="sidebar-icon" size={20} />
                    <span>Search chats</span>
                </button>
            </div>

            <div className="sidebar-divider">Your chats</div>
            
            <div className="session-list">
                {sessions.map(s => (
                    <div 
                        key={s.session_id} 
                        className={`session-item ${s.session_id === currentSessionId ? 'active' : ''}`}
                        onClick={() => onSelectSession(s.session_id)}
                    >
                        {s.title || `Session: ${s.session_id}`}
                    </div>
                ))}
            </div>
        </aside>
    );
}
