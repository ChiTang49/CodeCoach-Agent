'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Send, User, Bot, Loader2, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatInterfaceProps {
  sessionId: string;
  userId: string;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ sessionId, userId }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const prevSessionIdRef = useRef<string>(sessionId);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load session messages when session changes
  useEffect(() => {
    if (isMounted && sessionId !== prevSessionIdRef.current) {
      // Session changed, load messages for new session
      loadSessionMessages();
      prevSessionIdRef.current = sessionId;
    }
  }, [sessionId, isMounted]);

  const loadSessionMessages = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/sessions/${sessionId}`);
      if (response.ok) {
        const session = await response.json();
        if (session && session.messages && session.messages.length > 0) {
          setMessages(session.messages);
        } else {
          // New session, show welcome message
          setMessages([
            { role: 'assistant', content: 'Hello! I am CodeCoach. How can I help you master algorithms today?' }
          ]);
        }
      }
    } catch (error) {
      console.error('Failed to load session messages:', error);
      setMessages([
        { role: 'assistant', content: 'Hello! I am CodeCoach. How can I help you master algorithms today?' }
      ]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          message: userMessage, 
          userId: userId,
          sessionId: sessionId
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const data = await response.json();
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
    } catch (error: any) {
      console.error('Error:', error);
      const errorMessage = error instanceof Error ? error.message : "Connection failed";
      setMessages(prev => [...prev, { role: 'assistant', content: `❌ Backend Error: ${errorMessage}\n\nPlease check server logs.` }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full w-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-green-500/20 to-emerald-500/20 flex items-center justify-center mb-6">
                <Sparkles className="w-8 h-8 text-green-400" />
              </div>
              <h2 className="text-2xl font-semibold text-gray-200 mb-2">
                Ready to Learn
              </h2>
              <p className="text-gray-500 max-w-md">
                Ask me anything about algorithms, data structures, or coding problems.
              </p>
            </div>
          )}
          
          {messages.map((msg, index) => (
            <div
              key={index}
              className="flex gap-4 group"
            >
              <div
                className={`h-8 w-8 rounded-full flex items-center justify-center shrink-0 ${
                  msg.role === 'user' 
                    ? 'bg-gradient-to-br from-blue-500 to-blue-600' 
                    : 'bg-gradient-to-br from-green-500 to-emerald-600'
                }`}
              >
                {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
              </div>
              <div className="flex-1 space-y-2 pt-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-gray-300">
                    {msg.role === 'user' ? 'You' : 'CodeCoach'}
                  </span>
                </div>
                <div className="text-gray-200 leading-relaxed prose prose-invert max-w-none">
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeHighlight]}
                    components={{
                      code: ({ node, inline, className, children, ...props }: any) => {
                        return inline ? (
                          <code className="bg-gray-800 px-1.5 py-0.5 rounded text-sm text-green-400" {...props}>
                            {children}
                          </code>
                        ) : (
                          <code className={className} {...props}>
                            {children}
                          </code>
                        );
                      },
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          ))}
          
          {isLoading && (
            <div className="flex gap-4">
              <div className="h-8 w-8 rounded-full bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center shrink-0">
                <Bot size={16} />
              </div>
              <div className="flex-1 pt-1">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm font-semibold text-gray-300">CodeCoach</span>
                </div>
                <div className="flex items-center gap-2 text-gray-400">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Thinking...</span>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-800 bg-gray-950/50 backdrop-blur">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <form onSubmit={handleSubmit} className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about algorithms, data structures, or coding problems..."
              className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-5 py-3 text-sm text-gray-200 focus:outline-none focus:border-green-500 focus:ring-2 focus:ring-green-500/20 transition-all placeholder-gray-500"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white px-5 py-3 rounded-xl transition-all flex items-center justify-center shadow-lg shadow-green-900/30 disabled:shadow-none"
            >
              <Send size={18} />
            </button>
          </form>
          <p className="text-xs text-gray-600 text-center mt-3">
            CodeCoach may make mistakes. Please verify important information.
          </p>
        </div>
      </div>
    </div>
  );
}

export default ChatInterface;
