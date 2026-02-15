import { useState, useRef, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  PaperAirplaneIcon,
  SparklesIcon,
  DocumentTextIcon,
  UserCircleIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDate } from '@/lib/utils'
import type { QueryResponse } from '@/types'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: QueryResponse['sources']
  timestamp: Date
}

export default function QueryPage() {
  const [searchParams] = useSearchParams()
  const contractId = searchParams.get('contract')

  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [selectedContract, setSelectedContract] = useState<string | undefined>(
    contractId || undefined
  )

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Fetch contracts for selector
  const { data: contractsData } = useQuery({
    queryKey: ['contracts-list'],
    queryFn: () => api.getContracts({ page: 1, page_size: 100 }),
  })

  // Fetch selected contract details
  const { data: contract } = useQuery({
    queryKey: ['contract', selectedContract],
    queryFn: () => api.getContract(selectedContract!),
    enabled: !!selectedContract,
  })

  // Query mutation
  const queryMutation = useMutation({
    mutationFn: (question: string) =>
      api.query({
        question,
        contract_id: selectedContract,
      }),
    onSuccess: (response) => {
      const assistantMessage: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: response.answer,
        sources: response.sources,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, assistantMessage])
    },
    onError: (error: any) => {
      const errorMessage: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error.response?.data?.detail || 'Unknown error'}`,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    },
  })

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || queryMutation.isPending) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMessage])
    queryMutation.mutate(input.trim())
    setInput('')
  }

  const suggestedQuestions = [
    'What are the key terms and conditions?',
    'Are there any liability limitations?',
    'What are the termination clauses?',
    'What obligations do we have?',
    'When does the contract expire?',
  ]

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-gray-200">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Contract Q&A</h1>
          <p className="mt-1 text-sm text-gray-500">
            Ask questions about your contracts using AI
          </p>
        </div>
        <div className="w-64">
          <select
            value={selectedContract || ''}
            onChange={(e) => setSelectedContract(e.target.value || undefined)}
            className="input text-sm"
          >
            <option value="">All contracts</option>
            {contractsData?.contracts.map((c) => (
              <option key={c.id} value={c.id}>
                {c.filename}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Selected contract info */}
      {contract && (
        <div className="py-3 px-4 bg-primary-50 border-b border-primary-100 flex items-center gap-3">
          <DocumentTextIcon className="h-5 w-5 text-primary-600" />
          <div className="flex-1">
            <p className="text-sm font-medium text-primary-900">{contract.filename}</p>
            <p className="text-xs text-primary-600">
              {contract.counterparty || 'Unknown counterparty'} • {contract.contract_type?.toUpperCase() || 'Unknown type'}
            </p>
          </div>
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto py-4 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-4">
            <SparklesIcon className="h-12 w-12 text-primary-400 mb-4" />
            <h2 className="text-lg font-medium text-gray-900">Ask me anything</h2>
            <p className="text-sm text-gray-500 mt-2 max-w-md">
              I can help you understand your contracts, find specific clauses,
              identify obligations, and answer questions about terms and conditions.
            </p>
            <div className="mt-6 flex flex-wrap gap-2 justify-center max-w-lg">
              {suggestedQuestions.map((question, idx) => (
                <button
                  key={idx}
                  onClick={() => setInput(question)}
                  className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-full text-gray-700 transition-colors"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  'flex gap-3',
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                )}
              >
                {message.role === 'assistant' && (
                  <div className="shrink-0 w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
                    <SparklesIcon className="h-4 w-4 text-primary-600" />
                  </div>
                )}
                <div
                  className={cn(
                    'max-w-2xl rounded-xl px-4 py-3',
                    message.role === 'user'
                      ? 'bg-primary-600 text-white'
                      : 'bg-gray-100 text-gray-900'
                  )}
                >
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>

                  {/* Sources */}
                  {message.sources && message.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-200">
                      <p className="text-xs font-medium text-gray-500 mb-2">Sources:</p>
                      <div className="space-y-2">
                        {message.sources.map((source, idx) => (
                          <div
                            key={idx}
                            className="text-xs bg-white rounded p-2 border border-gray-200"
                          >
                            <p className="font-medium text-gray-700">
                              {source.filename}
                              {source.chunk_index !== undefined && ` (Section ${source.chunk_index + 1})`}
                            </p>
                            <p className="text-gray-500 mt-1 line-clamp-2">
                              {source.excerpt}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <p className={cn(
                    'text-xs mt-2',
                    message.role === 'user' ? 'text-primary-200' : 'text-gray-400'
                  )}>
                    {formatDate(message.timestamp.toISOString())}
                  </p>
                </div>
                {message.role === 'user' && (
                  <div className="shrink-0 w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
                    <UserCircleIcon className="h-5 w-5 text-gray-500" />
                  </div>
                )}
              </div>
            ))}
            {queryMutation.isPending && (
              <div className="flex gap-3">
                <div className="shrink-0 w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
                  <SparklesIcon className="h-4 w-4 text-primary-600" />
                </div>
                <div className="bg-gray-100 rounded-xl px-4 py-3">
                  <LoadingSpinner size="sm" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input area */}
      <div className="pt-4 border-t border-gray-200">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about your contracts..."
            className="input flex-1"
            disabled={queryMutation.isPending}
          />
          <button
            type="submit"
            disabled={!input.trim() || queryMutation.isPending}
            className="btn-primary px-6"
          >
            {queryMutation.isPending ? (
              <LoadingSpinner size="sm" className="border-white border-t-transparent" />
            ) : (
              <PaperAirplaneIcon className="h-5 w-5" />
            )}
          </button>
        </form>
      </div>
    </div>
  )
}
