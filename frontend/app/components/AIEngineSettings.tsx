'use client';

import React, { useState, useEffect } from 'react';
import { X, Check, Loader2, Zap } from 'lucide-react';

interface AIEngine {
  id: string;
  name: string;
  model: string;
  available: boolean;
}

interface AIEngineSettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AIEngineSettings({ isOpen, onClose }: AIEngineSettingsProps) {
  const [engines, setEngines] = useState<AIEngine[]>([]);
  const [currentEngine, setCurrentEngine] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchEngines();
    }
  }, [isOpen]);

  const fetchEngines = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:8000/api/ai-engines');
      if (response.ok) {
        const data = await response.json();
        setEngines(data.engines);
        setCurrentEngine(data.current);
      } else {
        setError('Failed to fetch AI engines');
      }
    } catch (err) {
      setError('Failed to connect to server');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const switchEngine = async (engineId: string) => {
    if (engineId === currentEngine) return;
    
    setSwitching(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:8000/api/ai-engines/switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ engineId }),
      });
      
      if (response.ok) {
        const data = await response.json();
        setCurrentEngine(engineId);
        // Refresh page to reload with new engine
        setTimeout(() => {
          window.location.reload();
        }, 500);
      } else {
        const data = await response.json();
        setError(data.detail || 'Failed to switch engine');
      }
    } catch (err) {
      setError('Failed to switch engine');
      console.error(err);
    } finally {
      setSwitching(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-green-400" />
            <h2 className="text-lg font-semibold text-white">AI Engine</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-800 rounded-lg transition-colors"
          >
            <X size={20} className="text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-green-400" />
            </div>
          ) : (
            <>
              <p className="text-sm text-gray-400 mb-4">
                Select the AI engine for chat responses. Switching will reload the page.
              </p>

              {error && (
                <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
                  {error}
                </div>
              )}

              <div className="space-y-2">
                {engines.map((engine) => (
                  <button
                    key={engine.id}
                    onClick={() => engine.available && switchEngine(engine.id)}
                    disabled={!engine.available || switching}
                    className={`
                      w-full p-4 rounded-lg border text-left transition-all
                      ${engine.id === currentEngine
                        ? 'bg-green-500/10 border-green-500/50 shadow-sm'
                        : engine.available
                        ? 'bg-gray-800/50 border-gray-700 hover:border-gray-600 hover:bg-gray-800'
                        : 'bg-gray-800/30 border-gray-700/50 opacity-50 cursor-not-allowed'
                      }
                      ${switching ? 'cursor-wait' : ''}
                    `}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-white">{engine.name}</span>
                          {!engine.available && (
                            <span className="text-xs px-2 py-0.5 bg-gray-700 text-gray-400 rounded">
                              Not Configured
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-gray-400 mt-1 font-mono">
                          {engine.model}
                        </div>
                      </div>
                      {engine.id === currentEngine && (
                        <Check size={20} className="text-green-400 flex-shrink-0" />
                      )}
                      {switching && engine.id !== currentEngine && (
                        <Loader2 size={20} className="animate-spin text-gray-400 flex-shrink-0" />
                      )}
                    </div>
                  </button>
                ))}
              </div>

              <div className="mt-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                <p className="text-xs text-blue-300">
                  💡 Configure API keys in <code className="px-1 py-0.5 bg-gray-800 rounded text-green-400">.env</code> file to enable more engines
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
