'use client';

import React, { useState, useEffect } from 'react';
import { Terminal, Menu, X } from 'lucide-react';
import ChatInterface from './components/ChatInterface';
import SessionList from './components/SessionList';
import CompactMemory from './components/CompactMemory';

export default function Home() {
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [userId] = useState('demo_user');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isMounted, setIsMounted] = useState(false);

  // Prevent hydration mismatch
  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Create initial session on mount
  useEffect(() => {
    if (isMounted) {
      createNewSession();
    }
  }, [isMounted]);

  const createNewSession = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId, title: 'New Chat' }),
      });
      if (response.ok) {
        const session = await response.json();
        setCurrentSessionId(session.id);
      }
    } catch (error) {
      console.error('Failed to create session:', error);
    }
  };

  const handleSessionSelect = (sessionId: string) => {
    setCurrentSessionId(sessionId);
  };

  return (
    <main className="flex h-screen bg-gray-950 text-white overflow-hidden">
      {/* Sidebar */}
      <aside 
        className={`${
          sidebarOpen ? 'w-72' : 'w-0'
        } transition-all duration-300 border-r border-gray-800 bg-gray-950 flex flex-col overflow-hidden`}
      >
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <div className="font-mono font-bold tracking-wider text-green-400 flex items-center gap-2">
            <Terminal className="h-5 w-5" />
            CODECOACH
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-1 hover:bg-gray-800 rounded transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <SessionList
          currentSessionId={currentSessionId}
          onSessionSelect={handleSessionSelect}
          onNewSession={createNewSession}
          userId={userId}
        />

        <CompactMemory userId={userId} sessionId={currentSessionId} />

        <div className="p-4 border-t border-gray-800 bg-gray-900/30">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-full bg-gradient-to-tr from-green-500 to-blue-600"></div>
            <div>
              <div className="text-sm font-medium">Demo User</div>
              <div className="text-xs text-green-400">Online</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <section className="flex-1 flex flex-col relative overflow-hidden">
        {/* Top Bar */}
        <header className="h-14 border-b border-gray-800 bg-gray-950/80 backdrop-blur flex items-center px-4 justify-between z-10">
          <div className="flex items-center gap-3">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
              >
                <Menu size={20} />
              </button>
            )}
            <h1 className="text-lg font-semibold text-gray-200">
              CodeCoach Agent
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden md:flex gap-4 text-xs text-gray-500 font-mono">
              <span>DeepSeek Chat</span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                ACTIVE
              </span>
            </div>
          </div>
        </header>

        {/* Chat Viewport */}
        <div className="flex-1 overflow-hidden relative">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-green-900/10 via-gray-900/0 to-gray-900/0 pointer-events-none" />
          
          <div className="h-full flex flex-col">
            {currentSessionId ? (
              <ChatInterface sessionId={currentSessionId} userId={userId} />
            ) : (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center text-gray-500">
                  <Terminal className="w-16 h-16 mx-auto mb-4 opacity-30" />
                  <p className="text-lg font-medium mb-2">Welcome to CodeCoach</p>
                  <p className="text-sm">Create a new chat to get started</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
