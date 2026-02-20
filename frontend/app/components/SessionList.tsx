'use client';

import React, { useEffect, useState } from 'react';
import { Plus, MessageSquare, Trash2, MoreVertical } from 'lucide-react';

interface Session {
  id: string;
  title: string;
  userId: string;
  createdAt: string;
  updatedAt: string;
  preview: string | null;
}

interface SessionListProps {
  currentSessionId: string | null;
  onSessionSelect: (sessionId: string) => void;
  onNewSession: () => void;
  userId: string;
}

const SessionList: React.FC<SessionListProps> = ({
  currentSessionId,
  onSessionSelect,
  onNewSession,
  userId
}) => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const fetchSessions = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/sessions?userId=${userId}`);
      if (response.ok) {
        const data = await response.json();
        setSessions(data);
      }
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isMounted) {
      fetchSessions();
      // Refresh sessions every 5 seconds
      const interval = setInterval(fetchSessions, 5000);
      return () => clearInterval(interval);
    }
  }, [userId, isMounted]);

  const handleDelete = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this chat?')) return;
    
    try {
      const response = await fetch(`http://localhost:8000/api/sessions/${sessionId}`, {
        method: 'DELETE',
      });
      if (response.ok) {
        setSessions(sessions.filter(s => s.id !== sessionId));
        if (currentSessionId === sessionId) {
          onNewSession();
        }
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(hours / 24);

    if (hours < 1) return 'Just now';
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="flex flex-col h-full">
      {/* New Chat Button */}
      <div className="p-3 border-b border-gray-800">
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white rounded-lg transition-all font-medium text-sm shadow-lg shadow-green-900/50"
        >
          <Plus size={18} />
          New Chat
        </button>
      </div>

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto p-2">
        {isLoading ? (
          <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
            Loading...
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-gray-500 text-sm p-4 text-center">
            <MessageSquare className="w-8 h-8 mb-2 opacity-50" />
            <p>No chats yet</p>
            <p className="text-xs mt-1">Start a new conversation</p>
          </div>
        ) : (
          <div className="space-y-1">
            {sessions.map((session) => (
              <div
                key={session.id}
                onMouseEnter={() => setHoveredId(session.id)}
                onMouseLeave={() => setHoveredId(null)}
                onClick={() => onSessionSelect(session.id)}
                className={`group relative flex items-start gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all ${
                  currentSessionId === session.id
                    ? 'bg-green-600/10 border border-green-600/20'
                    : 'hover:bg-gray-800/50'
                }`}
              >
                <MessageSquare 
                  size={16} 
                  className={`mt-1 shrink-0 ${
                    currentSessionId === session.id ? 'text-green-400' : 'text-gray-500'
                  }`}
                />
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium truncate ${
                    currentSessionId === session.id ? 'text-green-400' : 'text-gray-300'
                  }`}>
                    {session.title}
                  </p>
                  {session.preview && (
                    <p className="text-xs text-gray-500 truncate mt-0.5">
                      {session.preview}
                    </p>
                  )}
                  <p className="text-xs text-gray-600 mt-1">
                    {formatDate(session.updatedAt)}
                  </p>
                </div>
                {hoveredId === session.id && (
                  <button
                    onClick={(e) => handleDelete(session.id, e)}
                    className="absolute right-2 top-2 p-1.5 rounded-md hover:bg-red-600/20 text-gray-500 hover:text-red-400 transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SessionList;
