'use client';

import React, { useEffect, useState } from 'react';
import { Brain, Calendar, Star, Trash2, RefreshCw } from 'lucide-react';

interface Memory {
  id: string;
  content: string;
  importance: number;
  timestamp: string;
  type: string;
}

export default function MemoryList() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [showConfirm, setShowConfirm] = useState(false);
  const [clearing, setClearing] = useState(false);

  useEffect(() => {
    fetchMemories();
  }, []);

  const fetchMemories = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8000/api/memories?userId=demo_user');
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

  const clearMemories = async () => {
    try {
      setClearing(true);
      const response = await fetch('http://localhost:8000/api/memories?userId=demo_user', {
        method: 'DELETE',
      });
      if (response.ok) {
        setMemories([]);
        setShowConfirm(false);
        alert('✅ 记忆已清空');
      } else {
        alert('❌ 清空失败');
      }
    } catch (error) {
      console.error('Failed to clear memories', error);
      alert('❌ 清空失败');
    } finally {
      setClearing(false);
    }
  };

  const deleteMemory = async (memoryId: string) => {
    if (!confirm('确认删除这条记忆吗？')) return;
    
    try {
      const response = await fetch(`http://localhost:8000/api/memories/${memoryId}?userId=demo_user`, {
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

  if (loading) {
    return <div className="text-gray-400 p-8">Loading memories...</div>;
  }

  return (
    <div className="p-6 h-full overflow-y-auto">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
          <Brain className="text-purple-400" />
          Agent Long-term Memory
        </h2>
        <div className="flex gap-2">
          <button 
            onClick={fetchMemories}
            className="px-3 py-1.5 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-all flex items-center gap-1"
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            刷新
          </button>
          <button 
            onClick={() => setShowConfirm(true)}
            className="px-3 py-1.5 text-sm text-red-400 hover:text-red-300 hover:bg-red-900/20 rounded-lg transition-all flex items-center gap-1"
            disabled={memories.length === 0}
          >
            <Trash2 size={14} />
            清空记忆
          </button>
        </div>
      </div>

      {/* 确认对话框 */}
      {showConfirm && (
        <div className="mb-4 bg-red-900/20 border border-red-500/30 rounded-lg p-4">
          <p className="text-red-300 mb-3">⚠️ 确认要清空所有学习记忆吗？此操作不可撤销！</p>
          <div className="flex gap-2">
            <button
              onClick={clearMemories}
              disabled={clearing}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors disabled:opacity-50"
            >
              {clearing ? '清空中...' : '✅ 确认清空'}
            </button>
            <button
              onClick={() => setShowConfirm(false)}
              disabled={clearing}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
            >
              ❌ 取消
            </button>
          </div>
        </div>
      )}

      <div className="grid gap-4">
        {memories.length === 0 ? (
          <div className="text-center py-12 text-gray-500 border border-dashed border-gray-800 rounded-lg">
            No memories stored yet. Start chatting to build context!
          </div>
        ) : (
          memories.map((mem) => (
            <div 
              key={mem.id} 
              className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-purple-500/30 transition-all group"
            >
              <div className="flex justify-between items-start mb-2">
                <div className="flex items-center gap-2">
                   <span className="text-xs font-mono px-2 py-0.5 rounded bg-gray-800 text-gray-400">
                     {mem.type}
                   </span>
                   <span className="text-xs text-gray-500 flex items-center gap-1">
                     <Calendar size={12} />
                     {new Date(mem.timestamp).toLocaleString()}
                   </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1 text-yellow-500/80" title="Importance">
                    <Star size={12} fill="currentColor" />
                    <span className="text-xs font-bold">{mem.importance.toFixed(2)}</span>
                  </div>
                  <button
                    onClick={() => deleteMemory(mem.id)}
                    className="text-red-400/60 hover:text-red-300 group-hover:text-red-400 p-1 rounded hover:bg-red-900/20 transition-all"
                    title="删除记忆"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              <p className="text-gray-300 text-sm leading-relaxed">
                {mem.content}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
