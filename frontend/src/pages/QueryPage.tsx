import { useState, useRef, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  PaperAirplaneIcon,
  SparklesIcon,
  DocumentTextIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  XMarkIcon,
  PlusIcon,
  ChatBubbleLeftRightIcon,
  TrashIcon,
  ClockIcon,
} from '@heroicons/react/24/outline'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend,
} from 'recharts'
import api from '@/lib/api'
import { cn } from '@/lib/utils'
import type { QueryResponse, Visualization, ChatSession, ChatMessageOut } from '@/types'
import ReactMarkdown from 'react-markdown'

// --------------- Types ---------------

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: QueryResponse['sources']
  followUps?: string[]
  visualizations?: Visualization[]
}

// --------------- Constants ---------------

const PIE_COLORS = ['#7c3aed', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#64748b']

const SUGGESTED_QUESTIONS = [
  { text: 'What are my contracts up for renewal?', icon: '\u{1F4C5}' },
  { text: 'Show me my high risk contracts', icon: '\u{26A0}\u{FE0F}' },
  { text: 'What are my SLAs?', icon: '\u{1F4CA}' },
  { text: 'What obligations do we have?', icon: '\u{1F4CB}' },
  { text: 'How many contracts do I have?', icon: '\u{1F4C1}' },
  { text: 'Which contracts have auto-renewal?', icon: '\u{1F504}' },
]

// --------------- Helpers ---------------

function groupSessionsByDate(sessions: ChatSession[]) {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const weekAgo = new Date(today.getTime() - 7 * 86400000)
  const monthAgo = new Date(today.getTime() - 30 * 86400000)

  const groups: { label: string; sessions: ChatSession[] }[] = [
    { label: 'Today', sessions: [] },
    { label: 'Yesterday', sessions: [] },
    { label: 'Previous 7 days', sessions: [] },
    { label: 'Previous 30 days', sessions: [] },
    { label: 'Older', sessions: [] },
  ]

  for (const session of sessions) {
    const d = new Date(session.updated_at)
    if (d >= today) groups[0].sessions.push(session)
    else if (d >= yesterday) groups[1].sessions.push(session)
    else if (d >= weekAgo) groups[2].sessions.push(session)
    else if (d >= monthAgo) groups[3].sessions.push(session)
    else groups[4].sessions.push(session)
  }

  return groups.filter(g => g.sessions.length > 0)
}

function mapApiMessage(m: ChatMessageOut): Message {
  return {
    id: m.id,
    role: m.role,
    content: m.content,
    sources: m.sources as Message['sources'],
    followUps: m.follow_ups,
    visualizations: m.visualizations as Visualization[] | undefined,
  }
}

// --------------- Visualization Components ---------------

function StatCards({ data }: { data: { cards: { label: string; value: string; color: string }[] } }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 mb-2">
      {data.cards.map((card, i) => (
        <div
          key={i}
          className="relative overflow-hidden rounded-xl border border-gray-100 bg-white p-4 shadow-sm"
        >
          <div className="absolute top-0 left-0 w-full h-1" style={{ backgroundColor: card.color }} />
          <p className="text-2xl font-bold tracking-tight" style={{ color: card.color }}>
            {card.value}
          </p>
          <p className="text-xs font-medium text-gray-500 mt-1">{card.label}</p>
        </div>
      ))}
    </div>
  )
}

function BarViz({ data, title }: { data: { name: string; count: number; fill: string }[]; title: string }) {
  return (
    <div className="mt-4 mb-2 rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
      <p className="text-sm font-semibold text-gray-800 mb-4">{title}</p>
      <ResponsiveContainer width="100%" height={Math.max(180, data.length * 40)}>
        <BarChart data={data} layout="vertical" margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: '#374151' }} width={120} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{ borderRadius: 12, border: '1px solid #e5e7eb', boxShadow: '0 4px 12px rgba(0,0,0,0.08)', fontSize: 13 }}
            cursor={{ fill: 'rgba(124, 58, 237, 0.04)' }}
          />
          <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={24}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.fill || '#7c3aed'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function PieViz({ data, title }: { data: { name: string; value: number }[]; title: string }) {
  return (
    <div className="mt-4 mb-2 rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
      <p className="text-sm font-semibold text-gray-800 mb-4">{title}</p>
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={85}
            paddingAngle={3}
            dataKey="value"
            strokeWidth={0}
            label={({ name, value }) => `${name} (${value})`}
          >
            {data.map((_entry, i) => (
              <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ borderRadius: 12, border: '1px solid #e5e7eb', boxShadow: '0 4px 12px rgba(0,0,0,0.08)', fontSize: 13 }}
          />
          <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

function TableViz({ data, title }: { data: { columns: string[]; rows: string[][] }; title: string }) {
  if (!data.columns || !data.rows || data.rows.length === 0) return null
  return (
    <div className="mt-4 mb-2 rounded-xl border border-gray-100 bg-white shadow-sm overflow-hidden">
      <p className="text-sm font-semibold text-gray-800 px-5 pt-4 pb-2">{title}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50/60">
              {data.columns.map((col, i) => (
                <th key={i} className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, ri) => (
              <tr key={ri} className="border-b border-gray-50 last:border-0 hover:bg-violet-50/30 transition-colors">
                {row.map((cell, ci) => (
                  <td key={ci} className={cn(
                    'px-4 py-2.5 text-gray-700 whitespace-nowrap',
                    ci === 0 && 'font-medium text-gray-900',
                  )}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function VisualizationRenderer({ viz }: { viz: Visualization }) {
  switch (viz.chart_type) {
    case 'stat_cards':
      return <StatCards data={viz.data} />
    case 'bar':
      return <BarViz data={viz.data} title={viz.title} />
    case 'pie':
      return <PieViz data={viz.data} title={viz.title} />
    case 'table':
      return <TableViz data={viz.data} title={viz.title} />
    default:
      return null
  }
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-1 py-2">
      <span className="w-2 h-2 rounded-full bg-violet-400 animate-bounce [animation-delay:0ms]" />
      <span className="w-2 h-2 rounded-full bg-violet-400 animate-bounce [animation-delay:150ms]" />
      <span className="w-2 h-2 rounded-full bg-violet-400 animate-bounce [animation-delay:300ms]" />
    </div>
  )
}

function SourcesCollapsible({ sources }: { sources?: QueryResponse['sources'] }) {
  const [open, setOpen] = useState(false)
  if (!sources || sources.length === 0) return null

  return (
    <div className="mt-4">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-400 hover:text-gray-600 transition-colors"
      >
        <ChevronDownIcon className={cn('h-3.5 w-3.5 transition-transform', open && 'rotate-180')} />
        {sources.length} source{sources.length !== 1 && 's'}
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {sources.map((source, idx) => (
            <div
              key={idx}
              className="text-xs rounded-lg p-3 bg-gray-50 border border-gray-100"
            >
              <p className="font-medium text-gray-600">
                {source.filename}
                {source.chunk_index !== undefined && (
                  <span className="text-gray-400 ml-1">Section {source.chunk_index + 1}</span>
                )}
              </p>
              {source.excerpt && (
                <p className="text-gray-400 mt-1 line-clamp-2 leading-relaxed">{source.excerpt}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// --------------- Chat History Sidebar ---------------

function ChatHistorySidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  isLoading,
}: {
  sessions: ChatSession[]
  activeSessionId: string | null
  onSelectSession: (id: string) => void
  onNewChat: () => void
  onDeleteSession: (id: string) => void
  isLoading: boolean
}) {
  const groups = groupSessionsByDate(sessions)

  return (
    <div className="w-[280px] shrink-0 border-r border-gray-200 bg-white flex flex-col h-full">
      {/* New Chat button */}
      <div className="p-3 border-b border-gray-100">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl border border-gray-200 bg-white text-gray-700 hover:bg-violet-50 hover:border-violet-200 hover:text-violet-700 transition-all shadow-sm"
        >
          <PlusIcon className="h-4 w-4" />
          New Chat
        </button>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-5 h-5 border-2 border-violet-200 border-t-violet-600 rounded-full animate-spin" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-12 px-4">
            <ChatBubbleLeftRightIcon className="h-8 w-8 text-gray-300 mx-auto mb-2" />
            <p className="text-xs text-gray-400">No conversations yet</p>
            <p className="text-[11px] text-gray-300 mt-1">Start a new chat to get going</p>
          </div>
        ) : (
          groups.map((group) => (
            <div key={group.label} className="mb-2">
              <p className="px-3 py-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                {group.label}
              </p>
              {group.sessions.map((session) => (
                <div
                  key={session.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectSession(session.id)}
                  onKeyDown={(e) => e.key === 'Enter' && onSelectSession(session.id)}
                  className={cn(
                    'group relative w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left cursor-pointer transition-all duration-100',
                    session.id === activeSessionId
                      ? 'bg-violet-50 text-violet-700'
                      : 'text-gray-600 hover:bg-gray-50'
                  )}
                >
                  <ChatBubbleLeftRightIcon className="h-3.5 w-3.5 shrink-0 opacity-40" />
                  <span className="flex-1 text-[13px] truncate leading-snug">{session.title}</span>
                  {session.message_count > 0 && (
                    <span className={cn(
                      'text-[10px] tabular-nums shrink-0 transition-opacity',
                      session.id === activeSessionId ? 'text-violet-400' : 'text-gray-300',
                      'group-hover:opacity-0'
                    )}>
                      {session.message_count}
                    </span>
                  )}
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onDeleteSession(session.id)
                    }}
                    className="absolute right-3 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-50 hover:text-red-500 transition-all"
                    title="Delete conversation"
                  >
                    <TrashIcon className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// --------------- Main Page ---------------

export default function QueryPage() {
  const [searchParams] = useSearchParams()
  const contractId = searchParams.get('contract')
  const clauseId = searchParams.get('clause')
  const queryClient = useQueryClient()

  // State
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [selectedContract, setSelectedContract] = useState<string | undefined>(
    contractId || undefined
  )
  const [loadingSession, setLoadingSession] = useState(false)
  const [clauseAutoSubmitted, setClauseAutoSubmitted] = useState(false)

  // Refs
  const activeSessionRef = useRef<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Keep ref in sync
  useEffect(() => {
    activeSessionRef.current = activeSessionId
  }, [activeSessionId])

  // Fetch clause detail if clause param is present
  const { data: clauseDetail } = useQuery({
    queryKey: ['clause-detail', clauseId],
    queryFn: () => api.getClauseDetail(clauseId!),
    enabled: !!clauseId,
  })

  // Queries
  const { data: sessions = [], isLoading: sessionsLoading } = useQuery({
    queryKey: ['chat-sessions'],
    queryFn: () => api.getChatSessions(),
  })

  const { data: contractsData } = useQuery({
    queryKey: ['contracts-list'],
    queryFn: () => api.getContracts({ page: 1, page_size: 100 }),
  })

  const selectedContractName = contractsData?.contracts.find(c => c.id === selectedContract)?.filename

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input when switching sessions
  useEffect(() => {
    if (!loadingSession) inputRef.current?.focus()
  }, [activeSessionId, loadingSession])

  // --------------- Handlers ---------------

  const handleNewChat = useCallback(() => {
    setActiveSessionId(null)
    activeSessionRef.current = null
    setMessages([])
    setInput('')
    setSelectedContract(contractId || undefined)
  }, [contractId])

  const handleSelectSession = useCallback(async (sessionId: string) => {
    if (sessionId === activeSessionRef.current) return
    setLoadingSession(true)
    try {
      const detail = await api.getChatSession(sessionId)
      setActiveSessionId(sessionId)
      activeSessionRef.current = sessionId
      setMessages(detail.messages.map(mapApiMessage))
      if (detail.contract_id) {
        setSelectedContract(detail.contract_id)
      }
    } catch (err) {
      console.error('Failed to load session:', err)
    } finally {
      setLoadingSession(false)
    }
  }, [])

  const handleDeleteSession = useCallback(async (sessionId: string) => {
    try {
      await api.deleteChatSession(sessionId)
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      if (activeSessionRef.current === sessionId) {
        setActiveSessionId(null)
        activeSessionRef.current = null
        setMessages([])
      }
    } catch (err) {
      console.error('Failed to delete session:', err)
    }
  }, [queryClient])

  const submitQuestion = useCallback(async (question: string) => {
    if (!question.trim() || isSubmitting) return

    const q = question.trim()
    setInput('')
    setIsSubmitting(true)

    // Optimistically add user message
    const userMsg: Message = { id: `u-${Date.now()}`, role: 'user', content: q }
    setMessages(prev => [...prev, userMsg])

    try {
      // 1. Create session if needed
      let sessionId = activeSessionRef.current
      if (!sessionId) {
        const session = await api.createChatSession(undefined, selectedContract || undefined)
        sessionId = session.id
        activeSessionRef.current = sessionId
        setActiveSessionId(sessionId)
      }

      // 2. Save user message to backend
      await api.addChatMessage(sessionId, { role: 'user', content: q })

      // 3. Query the AI
      const response = await api.query({ question: q, contract_id: selectedContract })

      // 4. Save assistant message to backend
      await api.addChatMessage(sessionId, {
        role: 'assistant',
        content: response.answer,
        sources: response.sources as unknown[],
        follow_ups: response.follow_up_questions,
        visualizations: response.visualizations as unknown[],
      })

      // 5. Add assistant message to UI
      const assistantMsg: Message = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        sources: response.sources,
        followUps: response.follow_up_questions,
        visualizations: response.visualizations,
      }
      setMessages(prev => [...prev, assistantMsg])

      // 6. Refresh sessions list
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    } catch (error: any) {
      const errorMsg: Message = {
        id: `e-${Date.now()}`,
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error.response?.data?.detail || error.message || 'Unknown error'}`,
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setIsSubmitting(false)
    }
  }, [isSubmitting, selectedContract, queryClient])

  // Auto-submit clause question when clause detail is loaded
  useEffect(() => {
    if (clauseDetail && !clauseAutoSubmitted && !isSubmitting) {
      setClauseAutoSubmitted(true)
      // Scope to the clause's contract
      if (clauseDetail.contract_id) {
        setSelectedContract(clauseDetail.contract_id)
      }
      // Build a contextual question — phrased to avoid triggering structured intent keywords
      // like "obligations", "risk", "renewal" which would bypass RAG and return portfolio stats
      const clauseType = clauseDetail.clause_type?.replace(/_/g, ' ') || 'clause'
      const truncatedText = clauseDetail.text.length > 500
        ? clauseDetail.text.slice(0, 500) + '...'
        : clauseDetail.text
      const question = `[CLAUSE ANALYSIS] Analyze the following ${clauseType} clause from contract "${clauseDetail.contract_filename}". What does it mean in plain language? What are the key terms, responsibilities, and potential concerns?\n\n"${truncatedText}"`
      submitQuestion(question)
    }
  }, [clauseDetail, clauseAutoSubmitted, isSubmitting, submitQuestion])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    submitQuestion(input)
  }

  const hasMessages = messages.length > 0

  // --------------- Render ---------------

  return (
    <div className="flex -mx-4 sm:-mx-6 lg:-mx-8 -mt-6 -mb-6 h-[calc(100vh-3.5rem)] bg-gray-50">
      {/* Chat History Sidebar */}
      <ChatHistorySidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        isLoading={sessionsLoading}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Loading session overlay */}
        {loadingSession && (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex items-center gap-3 text-gray-400">
              <ClockIcon className="h-5 w-5 animate-pulse" />
              <span className="text-sm">Loading conversation...</span>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!loadingSession && !hasMessages && (
          <div className="flex-1 flex flex-col items-center justify-center px-4">
            <div className="relative mb-8">
              <div className="absolute inset-0 blur-3xl opacity-20 bg-gradient-to-r from-violet-400 via-blue-400 to-violet-400 rounded-full scale-150" />
              <div className="relative w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 to-violet-700 flex items-center justify-center shadow-lg shadow-violet-200">
                <SparklesIcon className="h-8 w-8 text-white" />
              </div>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
              Contract Intelligence
            </h1>
            <p className="text-gray-500 mt-2 max-w-md text-center text-sm leading-relaxed">
              Ask anything about your contracts &mdash; renewals, risks, obligations, SLAs, or specific clauses.
            </p>

            {selectedContract && selectedContractName && (
              <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-violet-50 border border-violet-100 text-xs font-medium text-violet-700">
                <DocumentTextIcon className="h-3.5 w-3.5" />
                Scoped to: {selectedContractName}
                <button onClick={() => setSelectedContract(undefined)} className="ml-1 hover:text-violet-900">
                  <XMarkIcon className="h-3.5 w-3.5" />
                </button>
              </div>
            )}

            <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 max-w-2xl w-full">
              {SUGGESTED_QUESTIONS.map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => submitQuestion(q.text)}
                  disabled={isSubmitting}
                  className="group flex items-center gap-3 text-left px-4 py-3 rounded-xl border border-gray-150 bg-white hover:border-violet-200 hover:bg-violet-50/50 transition-all duration-150 shadow-sm hover:shadow disabled:opacity-50"
                >
                  <span className="text-base">{q.icon}</span>
                  <span className="text-sm text-gray-700 group-hover:text-violet-700 transition-colors leading-snug">
                    {q.text}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {!loadingSession && hasMessages && (
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-4xl mx-auto px-6 py-6 space-y-6">
              {messages.map((message) => (
                <div key={message.id}>
                  {message.role === 'user' && (
                    <div className="flex justify-end mb-1">
                      <div className="max-w-2xl px-4 py-2.5 rounded-2xl rounded-br-md bg-violet-600 text-white shadow-sm">
                        <p className="text-sm leading-relaxed">{message.content}</p>
                      </div>
                    </div>
                  )}

                  {message.role === 'assistant' && (
                    <div className="flex gap-3">
                      <div className="shrink-0 mt-1">
                        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-violet-700 flex items-center justify-center">
                          <SparklesIcon className="h-3.5 w-3.5 text-white" />
                        </div>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="prose prose-sm max-w-none text-gray-800 prose-headings:font-semibold prose-headings:text-gray-900 prose-headings:tracking-tight prose-strong:text-gray-900 prose-strong:font-semibold prose-li:text-gray-700 prose-p:leading-relaxed prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5">
                          <ReactMarkdown>{message.content}</ReactMarkdown>
                        </div>

                        {message.visualizations && message.visualizations.length > 0 && (
                          <div>
                            {message.visualizations.map((viz, idx) => (
                              <VisualizationRenderer key={idx} viz={viz} />
                            ))}
                          </div>
                        )}

                        <SourcesCollapsible sources={message.sources} />

                        {message.followUps && message.followUps.length > 0 && (
                          <div className="mt-4 flex flex-wrap gap-2">
                            {message.followUps.map((q, idx) => (
                              <button
                                key={idx}
                                onClick={() => submitQuestion(q)}
                                disabled={isSubmitting}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-gray-200 text-gray-600 rounded-full hover:border-violet-300 hover:text-violet-700 hover:bg-violet-50 transition-all duration-150 shadow-sm disabled:opacity-50"
                              >
                                <ChevronRightIcon className="h-3 w-3" />
                                {q}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {isSubmitting && (
                <div className="flex gap-3">
                  <div className="shrink-0 mt-1">
                    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-violet-700 flex items-center justify-center">
                      <SparklesIcon className="h-3.5 w-3.5 text-white" />
                    </div>
                  </div>
                  <TypingIndicator />
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>
        )}

        {/* Input Bar */}
        {!loadingSession && (
          <div className={cn(
            'border-t border-gray-100 bg-white/80 backdrop-blur-sm',
            hasMessages ? 'py-3 px-4' : 'py-4 px-4'
          )}>
            <div className="max-w-4xl mx-auto">
              {hasMessages && selectedContract && selectedContractName && (
                <div className="mb-2 flex items-center">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-violet-50 text-xs font-medium text-violet-600">
                    <DocumentTextIcon className="h-3 w-3" />
                    {selectedContractName}
                    <button onClick={() => setSelectedContract(undefined)} className="ml-0.5 hover:text-violet-800">
                      <XMarkIcon className="h-3 w-3" />
                    </button>
                  </span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="relative">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about your contracts..."
                  className="w-full pl-4 pr-14 py-3 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-violet-100 focus:border-violet-400 focus:bg-white transition-all placeholder:text-gray-400"
                  disabled={isSubmitting}
                />
                <button
                  type="submit"
                  disabled={!input.trim() || isSubmitting}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-violet-600 text-white hover:bg-violet-700 disabled:bg-gray-200 disabled:text-gray-400 transition-all duration-150"
                >
                  <PaperAirplaneIcon className="h-4 w-4" />
                </button>
              </form>

              {!hasMessages && !selectedContract && contractsData && contractsData.contracts.length > 0 && (
                <div className="mt-2 flex items-center justify-center">
                  <select
                    value={selectedContract || ''}
                    onChange={(e) => setSelectedContract(e.target.value || undefined)}
                    className="text-xs text-gray-400 bg-transparent border-none focus:ring-0 cursor-pointer hover:text-gray-600 transition-colors py-1 text-center appearance-none"
                  >
                    <option value="">Searching all contracts</option>
                    {contractsData.contracts.map((c) => (
                      <option key={c.id} value={c.id}>
                        Scoped to: {c.filename}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
