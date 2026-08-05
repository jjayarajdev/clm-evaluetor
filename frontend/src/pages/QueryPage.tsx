/* Ask AI (Query) page — Direction B redesign.
   Full-height chat: session-history rail, scrollable thread, composer pinned
   at the bottom. User messages right-aligned violet-tinted, AI answers in
   cards with AiTag + citation chips linking to contracts. Session CRUD,
   query mutation flow, contract scoping, clause auto-analysis, markdown and
   visualization rendering are unchanged from the pre-redesign page. */
import { useState, useRef, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowPathIcon,
  ArrowRightIcon,
  CalendarDaysIcon,
  ChartBarIcon,
  ChatBubbleLeftRightIcon,
  ClipboardDocumentListIcon,
  ClockIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  FolderIcon,
  PaperAirplaneIcon,
  PlusIcon,
  SparklesIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import {
  BarChart, Bar as RBar, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend,
} from 'recharts'
import ReactMarkdown from 'react-markdown'
import api from '@/lib/api'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import {
  Button, IconButton, Pill, AiTag, Chip, Select, Confidence, Avatar, Tooltip, EmptyState,
} from '@/components/ui'
import type { QueryResponse, Visualization, ChatSession, ChatMessageOut } from '@/types'
import type { IconType } from '@/components/ui'

// --------------- Types ---------------

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: QueryResponse['sources']
  followUps?: string[]
  visualizations?: Visualization[]
  confidence?: number
  answerSource?: QueryResponse['answer_source']
}

// --------------- Constants ---------------

// Token-var series palette so charts stay dark-mode correct.
const PIE_COLORS = [
  'var(--p)', 'var(--in)', 'var(--ok)', 'var(--wa)',
  'var(--da)', 'var(--p-b)', 'var(--in-b)', 'var(--m)',
]

const CHART_TOOLTIP_STYLE: React.CSSProperties = {
  background: 'var(--s)',
  border: '1px solid var(--b)',
  borderRadius: 'var(--r-md)',
  boxShadow: 'var(--sh-md)',
  color: 'var(--t)',
  fontSize: 'var(--fs-sm)',
}

const SUGGESTED_QUESTIONS: { key: string; icon: IconType }[] = [
  { key: 'query.suggested.renewals', icon: CalendarDaysIcon },
  { key: 'query.suggested.highRisk', icon: ExclamationTriangleIcon },
  { key: 'query.suggested.slas', icon: ChartBarIcon },
  { key: 'query.suggested.obligations', icon: ClipboardDocumentListIcon },
  { key: 'query.suggested.contractCount', icon: FolderIcon },
  { key: 'query.suggested.autoRenewal', icon: ArrowPathIcon },
]

// Markdown spacing/typography (colors inherit token vars from body).
const MD_CLASS = [
  'leading-relaxed',
  '[&>*:first-child]:mt-0 [&>*:last-child]:mb-0',
  '[&_p]:my-1.5',
  '[&_ul]:my-1.5 [&_ul]:list-disc [&_ul]:pl-5',
  '[&_ol]:my-1.5 [&_ol]:list-decimal [&_ol]:pl-5',
  '[&_li]:my-0.5',
  '[&_strong]:font-semibold',
  '[&_h1]:mt-3 [&_h1]:mb-1 [&_h1]:font-semibold',
  '[&_h2]:mt-3 [&_h2]:mb-1 [&_h2]:font-semibold',
  '[&_h3]:mt-2 [&_h3]:mb-1 [&_h3]:font-semibold',
  '[&_code]:font-mono',
].join(' ')

// --------------- Helpers ---------------

function groupSessionsByDate(sessions: ChatSession[]) {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const weekAgo = new Date(today.getTime() - 7 * 86400000)
  const monthAgo = new Date(today.getTime() - 30 * 86400000)

  const groups: { label: string; sessions: ChatSession[] }[] = [
    { label: 'query.groups.today', sessions: [] },
    { label: 'query.groups.yesterday', sessions: [] },
    { label: 'query.groups.previous7Days', sessions: [] },
    { label: 'query.groups.previous30Days', sessions: [] },
    { label: 'query.groups.older', sessions: [] },
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
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {data.cards.map((card, i) => (
        <div key={i} className="card relative overflow-hidden p-4">
          {/* accent color is backend-provided data */}
          <div className="absolute top-0 left-0 w-full h-1" style={{ backgroundColor: card.color }} />
          <p className="num" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 700, letterSpacing: '-0.01em', color: card.color }}>
            {card.value}
          </p>
          <p className="faint mt-1" style={{ fontSize: 'var(--fs-xs)', fontWeight: 500 }}>{card.label}</p>
        </div>
      ))}
    </div>
  )
}

function BarViz({ data, title }: { data: { name: string; count: number; fill: string }[]; title: string }) {
  return (
    <div className="card card-p">
      <p className="mb-4" style={{ fontSize: 'var(--fs-sm)', fontWeight: 600 }}>{title}</p>
      <ResponsiveContainer width="100%" height={Math.max(180, data.length * 40)}>
        <BarChart data={data} layout="vertical" margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: 'var(--f)' }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: 'var(--m)' }} width={120} axisLine={false} tickLine={false} />
          <RTooltip contentStyle={CHART_TOOLTIP_STYLE} cursor={{ fill: 'var(--p-f)' }} />
          <RBar dataKey="count" radius={[0, 6, 6, 0]} barSize={24}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.fill || 'var(--p)'} />
            ))}
          </RBar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function PieViz({ data, title }: { data: { name: string; value: number }[]; title: string }) {
  return (
    <div className="card card-p">
      <p className="mb-4" style={{ fontSize: 'var(--fs-sm)', fontWeight: 600 }}>{title}</p>
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
          >
            {data.map((_entry, i) => (
              <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
            ))}
          </Pie>
          <RTooltip contentStyle={CHART_TOOLTIP_STYLE} />
          <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

function TableViz({ data, title }: { data: { columns: string[]; rows: string[][] }; title: string }) {
  if (!data.columns || !data.rows || data.rows.length === 0) return null
  return (
    <div className="tbl-w">
      <p className="px-4 pt-3 pb-1" style={{ fontSize: 'var(--fs-sm)', fontWeight: 600 }}>{title}</p>
      <table className="tbl" style={{ minWidth: 0 }}>
        <thead>
          <tr>
            {data.columns.map((col, i) => (
              <th key={i}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, ri) => (
            <tr key={ri}>
              {row.map((cell, ci) => (
                <td key={ci} style={ci === 0 ? { fontWeight: 500 } : undefined}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
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

// --------------- Message Pieces ---------------

function AiAvatar() {
  return (
    <span
      className="shrink-0"
      style={{
        width: 30, height: 30, borderRadius: 'var(--r-md)',
        background: 'var(--p)', color: 'var(--on-p)',
        display: 'grid', placeItems: 'center',
      }}
    >
      <SparklesIcon style={{ width: 16, height: 16 }} aria-hidden />
    </span>
  )
}

function SourceChips({
  sources,
  confidence,
}: {
  sources?: QueryResponse['sources']
  confidence?: number
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  if ((!sources || sources.length === 0) && confidence == null) return null

  return (
    <div className="row flex-wrap" style={{ gap: 8 }}>
      {sources?.map((source, idx) => {
        const label = source.filename || t('query.sourceFallback', { defaultValue: 'Source {{number}}', number: idx + 1 })
        const section =
          source.section_number ||
          (source.chunk_index !== undefined ? t('query.section', { number: source.chunk_index + 1 }) : undefined)
        return (
          <Tooltip
            key={idx}
            rich
            side="top"
            subhead={section ? `${label} · ${section}` : label}
            label={source.excerpt || t('query.citationHint', { defaultValue: 'Retrieved passage. Click through to open the contract.' })}
            footer={source.page_start != null ? t('query.citationPage', { defaultValue: 'page {{page}}', page: source.page_start }) : undefined}
          >
            <Chip
              icon={DocumentTextIcon}
              onClick={source.contract_id ? () => navigate(`/contracts/${source.contract_id}`) : undefined}
            >
              <span className="trunc" style={{ maxWidth: 220 }}>
                {label}
                {section ? ` ${section}` : ''}
              </span>
            </Chip>
          </Tooltip>
        )
      })}
      {confidence != null && (
        <span className="row" style={{ gap: 7, marginLeft: 4 }}>
          <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
            {t('query.answerConfidence', { defaultValue: 'answer confidence' })}
          </span>
          <Confidence value={confidence} width={40} />
        </span>
      )}
    </div>
  )
}

function ThinkingIndicator() {
  const { t } = useTranslation()
  return (
    <div className="row" style={{ gap: 12, alignItems: 'flex-start' }}>
      <AiAvatar />
      <span className="row pulse muted" style={{ gap: 8, fontSize: 'var(--fs-md)', minHeight: 30 }}>
        <ArrowPathIcon className="spin" style={{ width: 14, height: 14 }} aria-hidden />
        {t('query.thinking', { defaultValue: 'Retrieving across your contracts…' })}
      </span>
    </div>
  )
}

// --------------- Chat History Rail ---------------

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
  const { t } = useTranslation()
  const groups = groupSessionsByDate(sessions)

  return (
    <div
      className="col hidden md:flex w-[260px] shrink-0 h-full"
      style={{ background: 'var(--s)', borderRight: '1px solid var(--b)' }}
    >
      <div className="p-3" style={{ borderBottom: '1px solid var(--b)' }}>
        <Button icon={PlusIcon} className="w-full" onClick={onNewChat}>
          {t('query.newChat')}
        </Button>
      </div>

      <div className="scroll grow px-2 py-2">
        {isLoading ? (
          <div className="row justify-center py-8">
            <ArrowPathIcon className="spin" style={{ width: 18, height: 18, color: 'var(--f)' }} aria-hidden />
          </div>
        ) : sessions.length === 0 ? (
          <EmptyState
            icon={ChatBubbleLeftRightIcon}
            title={t('query.noConversations')}
            body={t('query.startNewChatHint')}
          />
        ) : (
          groups.map((group) => (
            <div key={group.label} className="mb-2">
              <p className="sec-t px-3 py-1.5">{t(group.label)}</p>
              {group.sessions.map((session) => {
                const active = session.id === activeSessionId
                return (
                  <div
                    key={session.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => onSelectSession(session.id)}
                    onKeyDown={(e) => e.key === 'Enter' && onSelectSession(session.id)}
                    className={cn(
                      'group relative w-full flex items-center gap-2 px-3 py-2 text-left cursor-pointer rounded-[var(--r-md)] transition-colors',
                      active ? 'bg-[var(--p-f)] text-[var(--p)]' : 'text-[var(--m)] hover:bg-[var(--s2)]'
                    )}
                  >
                    <ChatBubbleLeftRightIcon className="h-3.5 w-3.5 shrink-0 opacity-40" aria-hidden />
                    <span className="grow trunc" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.35 }}>
                      {session.title}
                    </span>
                    {session.message_count > 0 && (
                      <span className="faint num shrink-0 group-hover:opacity-0 transition-opacity" style={{ fontSize: 'var(--fs-2xs)' }}>
                        {session.message_count}
                      </span>
                    )}
                    <IconButton
                      icon={TrashIcon}
                      size="sm"
                      label={t('query.deleteConversation')}
                      className="absolute right-2 opacity-0 group-hover:opacity-100 hover:!text-[var(--da)] hover:!bg-[var(--da-f)]"
                      onClick={(e) => {
                        e.stopPropagation()
                        onDeleteSession(session.id)
                      }}
                    />
                  </div>
                )
              })}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// --------------- Main Page ---------------

export default function QueryPage() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const contractId = searchParams.get('contract')
  const clauseId = searchParams.get('clause')
  const queryClient = useQueryClient()
  const { user } = useAuth()

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

  const selectedContractName = contractsData?.items.find(c => c.id === selectedContract)?.filename

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
        confidence: response.confidence,
        answerSource: response.answer_source,
      }
      setMessages(prev => [...prev, assistantMsg])

      // 6. Refresh sessions list
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    } catch (error: any) {
      const errorMsg: Message = {
        id: `e-${Date.now()}`,
        role: 'assistant',
        content: t('query.errorMessage', { error: error.response?.data?.detail || error.message || t('query.unknownError') }),
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setIsSubmitting(false)
    }
  }, [isSubmitting, selectedContract, queryClient, t])

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
  const userName = user?.full_name || user?.username || ''

  const scopePill = selectedContract && selectedContractName && (
    <Pill tone="p" dot={false}>
      <DocumentTextIcon style={{ width: 12, height: 12 }} aria-hidden />
      <span className="trunc" style={{ maxWidth: 260 }}>
        {t('query.scopedTo', { name: selectedContractName })}
      </span>
      <button
        type="button"
        onClick={() => setSelectedContract(undefined)}
        className="row"
        style={{ marginLeft: 2, cursor: 'pointer', background: 'none', border: 0, color: 'inherit', padding: 0 }}
        aria-label={t('query.clearScope', { defaultValue: 'Clear contract scope' })}
      >
        <XMarkIcon style={{ width: 12, height: 12 }} aria-hidden />
      </button>
    </Pill>
  )

  // --------------- Render ---------------

  return (
    // Escape MainLayout's max-w-7xl padded wrapper to own the full viewport
    // below the 56px top bar; inner .scroll areas handle their own overflow.
    <div
      className="flex -mx-4 sm:-mx-6 lg:-mx-8 -mt-6 -mb-6 h-[calc(100vh-3.5rem)]"
      style={{ background: 'var(--pg)' }}
    >
      <ChatHistorySidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        isLoading={sessionsLoading}
      />

      {/* Main chat column */}
      <div className="col flex-1 min-w-0" style={{ minHeight: 0 }}>
        {/* Loading session overlay */}
        {loadingSession && (
          <div className="grow row justify-center">
            <span className="row pulse muted" style={{ gap: 10 }}>
              <ClockIcon style={{ width: 18, height: 18 }} aria-hidden />
              <span style={{ fontSize: 'var(--fs-md)' }}>{t('query.loadingConversation')}</span>
            </span>
          </div>
        )}

        {/* Empty state */}
        {!loadingSession && !hasMessages && (
          <div className="scroll grow">
            <div className="col items-center justify-center min-h-full px-6 py-10">
              <span
                style={{
                  width: 56, height: 56, borderRadius: 'var(--r-xl)',
                  background: 'var(--p)', color: 'var(--on-p)',
                  display: 'grid', placeItems: 'center', boxShadow: 'var(--sh-md)',
                }}
              >
                <SparklesIcon style={{ width: 26, height: 26 }} aria-hidden />
              </span>
              <h1 className="mt-5" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 700, letterSpacing: '-0.01em' }}>
                {t('query.title')}
              </h1>
              <p className="muted mt-2 max-w-md text-center" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.6 }}>
                {t('query.subtitle')}
              </p>

              {scopePill && <div className="mt-4">{scopePill}</div>}

              <div className="row flex-wrap justify-center mt-7 max-w-2xl" style={{ gap: 8 }}>
                {SUGGESTED_QUESTIONS.map((q) => (
                  <Chip
                    key={q.key}
                    icon={q.icon}
                    disabled={isSubmitting}
                    onClick={() => submitQuestion(t(q.key))}
                  >
                    {t(q.key)}
                  </Chip>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Thread */}
        {!loadingSession && hasMessages && (
          <div className="scroll grow">
            <div className="col mx-auto max-w-3xl px-6 py-6" style={{ gap: 20 }}>
              {messages.map((message) =>
                message.role === 'user' ? (
                  <div key={message.id} className="row" style={{ gap: 12, alignItems: 'flex-start', justifyContent: 'flex-end' }}>
                    <div
                      style={{
                        background: 'var(--p-f)', border: '1px solid var(--p-b)',
                        borderRadius: 'var(--r-lg)', padding: '10px 14px',
                        fontSize: 'var(--fs-md)', maxWidth: 560, whiteSpace: 'pre-wrap',
                      }}
                    >
                      {message.content}
                    </div>
                    <Avatar name={userName} size={30} />
                  </div>
                ) : (
                  <div key={message.id} className="row" style={{ gap: 12, alignItems: 'flex-start' }}>
                    <AiAvatar />
                    <div className="grow col" style={{ gap: 12, minWidth: 0 }}>
                      <div className="card card-p col" style={{ gap: 12 }}>
                        <div className="row" style={{ justifyContent: 'space-between' }}>
                          <AiTag>{t('query.aiAnswer', { defaultValue: 'AI answer' })}</AiTag>
                          {message.answerSource && (
                            <Tooltip
                              side="top"
                              label={
                                message.answerSource === 'portfolio_data'
                                  ? t('query.sourcePortfolioHint', { defaultValue: 'Answered from an exact query over your portfolio data.' })
                                  : message.answerSource === 'hybrid'
                                    ? t('query.sourceHybridHint', { defaultValue: 'Filtered your portfolio in the database, then searched the matching contracts’ text.' })
                                    : t('query.sourceDocumentsHint', { defaultValue: 'Answered from retrieved document text (may not cover your whole portfolio).' })
                              }
                            >
                              <Pill tone={message.answerSource === 'documents' ? 'n' : message.answerSource === 'hybrid' ? 'in' : 'ok'} dot>
                                {message.answerSource === 'portfolio_data'
                                  ? t('query.sourcePortfolio', { defaultValue: 'Portfolio data' })
                                  : message.answerSource === 'hybrid'
                                    ? t('query.sourceHybrid', { defaultValue: 'Filter + documents' })
                                    : t('query.sourceDocuments', { defaultValue: 'Documents' })}
                              </Pill>
                            </Tooltip>
                          )}
                        </div>
                        <div className={MD_CLASS} style={{ fontSize: 'var(--fs-md)' }}>
                          <ReactMarkdown>{message.content}</ReactMarkdown>
                        </div>

                        {message.visualizations && message.visualizations.length > 0 && (
                          <div className="col" style={{ gap: 12 }}>
                            {message.visualizations.map((viz, idx) => (
                              <VisualizationRenderer key={idx} viz={viz} />
                            ))}
                          </div>
                        )}

                        <SourceChips sources={message.sources} confidence={message.confidence} />
                      </div>

                      {message.followUps && message.followUps.length > 0 && (
                        <div className="row flex-wrap" style={{ gap: 8 }}>
                          {message.followUps.map((q, idx) => (
                            <Chip key={idx} icon={ArrowRightIcon} disabled={isSubmitting} onClick={() => submitQuestion(q)}>
                              {q}
                            </Chip>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )
              )}

              {isSubmitting && <ThinkingIndicator />}

              <div ref={messagesEndRef} />
            </div>
          </div>
        )}

        {/* Composer — pinned at the bottom */}
        {!loadingSession && (
          <div style={{ borderTop: '1px solid var(--b)', background: 'var(--s)' }}>
            <div className="mx-auto max-w-3xl px-6 py-4">
              {hasMessages && scopePill && <div className="row mb-2">{scopePill}</div>}

              <form onSubmit={handleSubmit}>
                <div className="inp" style={{ height: 44, borderRadius: 'var(--r-md)' }}>
                  <SparklesIcon style={{ width: 16, height: 16, flexShrink: 0, color: 'var(--p)' }} aria-hidden />
                  <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder={t('query.inputPlaceholder')}
                    style={{ fontSize: 'var(--fs-lg)' }}
                    disabled={isSubmitting}
                  />
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    icon={PaperAirplaneIcon}
                    disabled={!input.trim() || isSubmitting}
                  >
                    {t('query.askButton', { defaultValue: 'Ask' })}
                  </Button>
                </div>
              </form>

              {!hasMessages && !selectedContract && contractsData && contractsData.items.length > 0 ? (
                <div className="row justify-center mt-2">
                  <Select
                    aria-label={t('query.searchingAllContracts')}
                    value={selectedContract || ''}
                    onChange={(e) => setSelectedContract(e.target.value || undefined)}
                    containerStyle={{ width: 320, maxWidth: '100%' }}
                    options={[
                      { value: '', label: t('query.searchingAllContracts') },
                      ...contractsData.items.map((c) => ({
                        value: c.id,
                        label: t('query.scopedTo', { name: c.filename }),
                      })),
                    ]}
                  />
                </div>
              ) : (
                <p className="faint text-center mt-2" style={{ fontSize: 'var(--fs-sm)' }}>
                  {t('query.composerHint', { defaultValue: 'Sessions persist. Structured questions return a table or chart alongside the answer.' })}
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
