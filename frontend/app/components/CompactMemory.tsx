'use client';

import React, { useEffect, useState } from 'react';
import { Brain, RefreshCw, Trash2 } from 'lucide-react';

interface Memory {
  id: string;
  content: string;
  importance: number;
  timestamp: string;
  type: string;
}

interface CompactMemoryProps {
  userId: string;
  sessionId: string | null;
}

const CompactMemory: React.FC<CompactMemoryProps> = ({ userId, sessionId }) => {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const fetchMemories = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const response = await fetch(
        `http://localhost:8000/api/memories?userId=${userId}&sessionId=${sessionId}`
      );
      if (response.ok) {
        const data = await response.json();
        setMemories(data);
      }
    } catch (error) {
      console.error('Failed to fetch memories', error);
    } finally {
      setLoading(false);
    }
  };

  const deleteMemory = async (memoryId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('确认删除这条记忆吗？')) return;
    
    try {
      const response = await fetch(`http://localhost:8000/api/memories/${memoryId}?userId=${userId}&sessionId=${sessionId}`, {
        method: 'DELETE',
      });
      if (response.ok) {
        setMemories(memories.filter(m => m.id !== memoryId));
        alert('✅ 记忆已删除');
      } else {
        alert('❌ 删除失败');
      }
    } catch (error) {
      console.error('Failed to delete memory', error);
      alert('❌ 删除失败');
    }
  };

  useEffect(() => {
    if (sessionId && isMounted) {
      fetchMemories();
    }
  }, [sessionId, isMounted]);

  if (!isMounted) {
    return (
      <div className="border-t border-gray-800 bg-gray-900/30">
        <div className="w-full flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Brain size={16} className="text-purple-400" />
            <span>Memory Bank</span>
            <span className="text-xs bg-gray-800 px-1.5 py-0.5 rounded">0</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="border-t border-gray-800 bg-gray-900/30">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-800/30 transition-colors"
      >
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Brain size={16} className="text-purple-400" />
          <span>Memory Bank</span>
          <span className="text-xs bg-gray-800 px-1.5 py-0.5 rounded">
            {memories.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              fetchMemories();
            }}
            className="p-1 hover:bg-gray-700 rounded transition-colors"
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <svg
            className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </button>

      {expanded && (
        <div className="max-h-64 overflow-y-auto px-3 pb-3 space-y-2">
          {memories.length === 0 ? (
            <div className="text-center py-6 text-gray-500 text-xs">
              No memories yet
            </div>
          ) : (
            memories.slice(0, 5).map((mem) => (
              <div
                key={mem.id}
                className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-2 hover:border-purple-500/30 transition-all group"
              >
                <div className="flex justify-between items-start mb-1">
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-900 text-gray-500">
                    {mem.type}
                  </span>
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] text-yellow-500/80">★ {mem.importance.toFixed(1)}</span>
                    <button
                      onClick={(e) => deleteMemory(mem.id, e)}
                      className="text-red-400/60 hover:text-red-300 p-0.5 rounded hover:bg-red-900/20 transition-all"
                      title="删除记忆"
                    >
                      <Trash2 size={10} />
                    </button>
                  </div>
                </div>
                <p className="text-xs text-gray-300 line-clamp-2 leading-relaxed">
                  {mem.content}
                </p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default CompactMemory;
