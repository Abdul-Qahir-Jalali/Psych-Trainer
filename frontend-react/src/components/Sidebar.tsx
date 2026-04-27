import { useEffect, useState, useRef } from 'react';

import { SquarePen, Search, LogOut, Settings, PanelLeftClose } from 'lucide-react';
import { useStore } from '../store/useStore';
import { supabase } from '../lib/supabase';

export function Sidebar() {
    const sessions = useStore(state => state.sessions);
    const currentSessionId = useStore(state => state.currentSessionId);
    const onNewSession = useStore(state => state.handleNewSession);
    const onSelectSession = useStore(state => state.loadSession);
    const handleLogout = useStore(state => state.handleLogout);
    const setIsSidebarOpen = useStore(state => state.setIsSidebarOpen);
    const isSidebarOpen = useStore(state => state.isSidebarOpen);
    const [userEmail, setUserEmail] = useState<string>('User');
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    // Ref to track our profile section
    const profileRef = useRef<HTMLDivElement>(null);

    // Close menu when clicking outside
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
                setIsMenuOpen(false);
            }
        }
        if (isMenuOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isMenuOpen]);

    
    // Search Functionality State
    const [searchQuery, setSearchQuery] = useState('');
    const [isSearching, setIsSearching] = useState(false);

    // Real-time filtering logic
    const filteredSessions = sessions.filter(s => 
        (s.title || `Session: ${s.session_id}`).toLowerCase().includes(searchQuery.toLowerCase())
    );

    useEffect(() => {
        // Fetch the user data
        supabase.auth.getUser().then(({ data: { user } }) => {
            if (user) {
                const name = user.user_metadata?.full_name;
                setUserEmail(name || user.email || 'User');
            }
        });
    }, []);

    return (
        // Force the sidebar to fill the screen height so the profile stays at the bottom
        <aside className={`sidebar ${isSidebarOpen ? '' : 'closed'}`} style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 'calc(100vh - 75px)', position: 'relative' }}>
                    {/* ChatGPT-style Top Header & Close Sidebar Button */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', paddingLeft: '4px' }}>
                
                {/* Logo Text on the Left */}
                <span style={{ fontWeight: 700, fontSize: '15px', color: 'var(--text-primary)', letterSpacing: '0.5px' }}>
                    PsychTrainer
                </span>
                
                {/* Toggle Button on the Right */}
                <button 
                    onClick={() => setIsSidebarOpen(false)}
                    style={{ 
                        background: 'transparent', 
                        border: 'none', 
                        cursor: 'pointer', 
                        color: 'var(--text-primary)', 
                        padding: '6px',
                        borderRadius: 'var(--radius-sm)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'background 0.2s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                    title="Close sidebar"
                >
                    <PanelLeftClose size={20} strokeWidth={2} />
                </button>
            </div>


            <div className="sidebar-top-actions" style={{ gap: '4px' }}>
                {/* New Chat Button matching ChatGPT */}
                <button className="btn-sidebar-item" onClick={onNewSession} style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                    <SquarePen className="sidebar-icon" size={18} strokeWidth={2} />
                    <span>New chat</span>
                </button>
                
                {/* Functional Search Button/Input */}
                {!isSearching ? (
                    <button className="btn-sidebar-item" onClick={() => setIsSearching(true)} style={{ color: 'var(--text-primary)' }}>
                        <Search className="sidebar-icon" size={18} strokeWidth={2} />
                        <span>Search chats</span>
                    </button>
                ) : (
                    <div className="btn-sidebar-item" style={{ padding: '8px 12px', backgroundColor: 'var(--bg-hover)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Search size={16} style={{ color: 'var(--text-muted)' }} />
                        <input 
                            autoFocus
                            type="text" 
                            placeholder="Search chats..." 
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onBlur={() => { if (!searchQuery) setIsSearching(false); }}
                            style={{ border: 'none', background: 'transparent', outline: 'none', color: 'var(--text-primary)', width: '100%', fontSize: '14px' }}
                        />
                    </div>
                )}
            </div>

            <div className="sidebar-divider" style={{ padding: '16px 12px 8px', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>
                Recents
            </div>
            
            <div className="session-list" style={{ flex: 1, overflowY: 'auto' }}>
                {filteredSessions.length > 0 ? (
                    filteredSessions.map(s => (
                        <div 
                            key={s.session_id} 
                            className={`session-item ${s.session_id === currentSessionId ? 'active' : ''}`}
                            onClick={() => onSelectSession(s.session_id)}
                        >
                            {s.title || `Session: ${s.session_id}`}
                        </div>
                    ))
                ) : (
                    <div style={{ padding: '12px', fontSize: '13px', color: 'var(--text-muted)', textAlign: 'center' }}>
                        No chats found.
                    </div>
                )}
            </div>

                        {/* Wrapper that detects outside clicks */}
            <div ref={profileRef} style={{ marginTop: 'auto' }}>
                
                {/* ChatGPT-style Popover Menu */}
                {isMenuOpen && (
                    <div style={{
                        position: 'absolute',
                        bottom: '70px',
                        left: '12px',
                        right: '12px',
                        backgroundColor: 'var(--bg-card)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius-md)',
                        padding: '8px',
                        boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                        zIndex: 100
                    }}>
                        <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', marginBottom: '4px' }}>
                            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Logged in as</span>
                            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{userEmail}</div>
                        </div>
                        <button className="btn-sidebar-item" onClick={() => { alert('Settings coming soon!'); setIsMenuOpen(false); }}>
                            <Settings size={18} style={{marginRight: '8px', color: 'var(--text-secondary)'}} />
                            <span>Settings</span>
                        </button>
                        <button className="btn-sidebar-item" onClick={handleLogout} style={{ color: '#ef4444' }}>
                            <LogOut size={18} style={{marginRight: '8px'}} />
                            <span>Log out</span>
                        </button>
                    </div>
                )}

                {/* Clickable Profile Button at the Bottom */}
                <div style={{ padding: '12px 0 0 0', borderTop: '1px solid var(--border)' }}>
                    <div 
                        onClick={() => setIsMenuOpen(!isMenuOpen)}
                        style={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            padding: '10px',
                            cursor: 'pointer',
                            borderRadius: 'var(--radius-md)',
                            backgroundColor: isMenuOpen ? 'var(--bg-hover)' : 'transparent',
                            transition: 'background 0.2s'
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = isMenuOpen ? 'var(--bg-hover)' : 'transparent'}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', overflow: 'hidden' }}>
                            <div style={{ 
                                width: '32px', height: '32px', borderRadius: '50%', 
                                backgroundColor: 'var(--accent-primary)', 
                                color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                                fontWeight: 'bold', fontSize: '14px'
                            }}>
                                {userEmail.charAt(0).toUpperCase()}
                            </div>
                            <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {userEmail}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </aside>
    );
}

