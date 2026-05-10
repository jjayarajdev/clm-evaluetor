import { useState, useEffect, useCallback, useRef } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/TextLayer.css'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  MagnifyingGlassMinusIcon,
  MagnifyingGlassPlusIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import type { HighlightRect } from '@/lib/api/contracts'

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

interface ContractPdfViewerProps {
  contractId: string
  mimeType?: string | null
  highlightPage?: number | null
  highlightText?: string | null
  // Rect-based highlighting (pixel-perfect)
  activeRects?: HighlightRect[] | null
  allHighlights?: Record<string, { clause_type: string; rects: HighlightRect[] }> | null
  pageDimensions?: Record<string, { width: number; height: number }> | null
  onHighlightClick?: (clauseId: string) => void
  onPageChange?: (page: number) => void
  onPageFound?: (page: number) => void
}

function normalize(text: string): string {
  return text.toLowerCase().replace(/\s+/g, ' ').trim()
}

// ─── Text highlight logic (fallback when no rects available) ────────

function applyHighlight(container: HTMLElement, highlightText: string | null): boolean {
  const layer =
    container.querySelector('.react-pdf__Page__textContent') ||
    container.querySelector('.textLayer')
  if (!layer) return false

  const spans = Array.from(layer.querySelectorAll('span')) as HTMLElement[]
  container.querySelectorAll('.clause-highlight-overlay').forEach((el) => el.remove())

  if (!highlightText) return true
  if (spans.length === 0) return false

  let origText = ''
  const offsets: { el: HTMLElement; start: number; end: number }[] = []
  for (const el of spans) {
    const text = el.textContent || ''
    if (text.length === 0) continue
    const start = origText.length
    origText += text
    offsets.push({ el, start, end: origText.length })
  }

  if (origText.length === 0) return false

  const normChars: string[] = []
  const normToOrig: number[] = []
  let lastWasSpace = false
  for (let i = 0; i < origText.length; i++) {
    const ch = origText[i]
    if (/\s/.test(ch)) {
      if (!lastWasSpace && normChars.length > 0) {
        normChars.push(' ')
        normToOrig.push(i)
        lastWasSpace = true
      }
    } else {
      normChars.push(ch.toLowerCase())
      normToOrig.push(i)
      lastWasSpace = false
    }
  }
  const normalizedPage = normChars.join('')
  const normalizedTarget = normalize(highlightText)

  const prefixLengths = [
    normalizedTarget.length,
    Math.min(300, normalizedTarget.length),
    Math.min(150, normalizedTarget.length),
    Math.min(80, normalizedTarget.length),
    Math.min(40, normalizedTarget.length),
  ]

  let matchNormStart = -1
  let matchNormLen = 0

  for (const len of prefixLengths) {
    if (len < 10) continue
    const search = normalizedTarget.substring(0, len)
    const idx = normalizedPage.indexOf(search)
    if (idx !== -1) {
      const fullIdx = normalizedPage.indexOf(normalizedTarget)
      if (fullIdx !== -1) {
        matchNormStart = fullIdx
        matchNormLen = normalizedTarget.length
      } else {
        matchNormStart = idx
        matchNormLen = len
      }
      break
    }
  }

  if (matchNormStart === -1) return true

  const origStart = normToOrig[matchNormStart] ?? 0
  const endIdx = Math.min(matchNormStart + matchNormLen - 1, normToOrig.length - 1)
  const origEnd = (normToOrig[endIdx] ?? origText.length) + 1

  let firstOverlay: HTMLElement | null = null
  const layerEl = layer as HTMLElement

  for (const { el, start, end } of offsets) {
    if (end > origStart && start < origEnd) {
      const rect = el.getBoundingClientRect()
      const layerRect = layerEl.getBoundingClientRect()

      const overlay = document.createElement('div')
      overlay.className = 'clause-highlight-overlay'
      overlay.style.position = 'absolute'
      overlay.style.left = `${rect.left - layerRect.left}px`
      overlay.style.top = `${rect.top - layerRect.top}px`
      overlay.style.width = `${rect.width}px`
      overlay.style.height = `${rect.height}px`
      overlay.style.backgroundColor = 'rgba(250, 204, 21, 0.4)'
      overlay.style.borderRadius = '2px'
      overlay.style.pointerEvents = 'none'
      overlay.style.zIndex = '3'
      overlay.style.mixBlendMode = 'multiply'
      layerEl.appendChild(overlay)

      if (!firstOverlay) firstOverlay = overlay
    }
  }

  if (firstOverlay) {
    firstOverlay.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  return true
}

// ─── Clause type colors for rect highlights ─────────────────────────

const CLAUSE_COLORS: Record<string, string> = {
  indemnification: 'rgba(239, 68, 68, 0.18)',
  limitation_of_liability: 'rgba(239, 68, 68, 0.18)',
  termination: 'rgba(249, 115, 22, 0.18)',
  confidentiality: 'rgba(59, 130, 246, 0.18)',
  intellectual_property: 'rgba(168, 85, 247, 0.18)',
  payment_terms: 'rgba(34, 197, 94, 0.18)',
  warranty: 'rgba(234, 179, 8, 0.18)',
  force_majeure: 'rgba(239, 68, 68, 0.18)',
  sla: 'rgba(6, 182, 212, 0.18)',
  service_level: 'rgba(6, 182, 212, 0.18)',
  governance: 'rgba(99, 102, 241, 0.18)',
}

const ACTIVE_COLOR = 'rgba(250, 204, 21, 0.5)'
const DEFAULT_COLOR = 'rgba(250, 204, 21, 0.12)'

// ─── Main Component ─────────────────────────────────────────────────

export default function ContractPdfViewer({
  contractId,
  mimeType,
  highlightPage,
  highlightText,
  activeRects,
  allHighlights,
  pageDimensions,
  onHighlightClick,
  onPageChange,
  onPageFound,
}: ContractPdfViewerProps) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [numPages, setNumPages] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [scale, setScale] = useState(1.0)
  const [renderedSize, setRenderedSize] = useState<{ width: number; height: number } | null>(null)
  const [textLayerRendered, setTextLayerRendered] = useState(0)
  const pageContainerRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const pdfDocRef = useRef<any>(null)
  const highlightTextRef = useRef<string | null>(null)
  highlightTextRef.current = highlightText || null

  const hasAllHighlights = allHighlights && Object.keys(allHighlights).length > 0
  const useRectHighlights = !!(activeRects || hasAllHighlights)

  // Load file
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    const isDocx = mimeType && (mimeType.includes('wordprocessingml') || mimeType.includes('msword'))

    api.downloadContractFile(contractId, !!isDocx)
      .then((blob) => {
        if (cancelled) return
        setPdfUrl(URL.createObjectURL(blob))
        setLoading(false)
      })
      .catch(() => {
        if (cancelled) return
        setError('Failed to load document')
        setLoading(false)
      })

    return () => { cancelled = true }
  }, [contractId, mimeType])

  useEffect(() => {
    return () => { if (pdfUrl) URL.revokeObjectURL(pdfUrl) }
  }, [pdfUrl])

  // Jump to highlighted page
  useEffect(() => {
    if (highlightPage && highlightPage >= 1 && highlightPage <= numPages) {
      setCurrentPage(highlightPage)
    }
  }, [highlightPage, numPages])

  // Search all pages for text when no page specified (fallback mode)
  useEffect(() => {
    if (!highlightText || highlightPage || !pdfDocRef.current || useRectHighlights) return

    const pdf = pdfDocRef.current
    const target = normalize(highlightText)
    if (target.length < 10) return

    const searchPrefix = target.substring(0, Math.min(80, target.length))
    let cancelled = false

    const searchPages = async () => {
      for (let p = 1; p <= pdf.numPages; p++) {
        if (cancelled) return
        try {
          const page = await pdf.getPage(p)
          const textContent = await page.getTextContent()
          const pageText = normalize(
            textContent.items.map((item: { str?: string }) => item.str || '').join('')
          )
          if (pageText.includes(searchPrefix)) {
            if (!cancelled) {
              setCurrentPage(p)
              onPageFound?.(p)
            }
            return
          }
        } catch { /* skip */ }
      }
    }

    searchPages()
    return () => { cancelled = true }
  }, [highlightText, highlightPage, numPages, useRectHighlights])

  // Text-layer fallback highlighting
  const doHighlight = useCallback(() => {
    if (useRectHighlights) return
    const container = pageContainerRef.current
    if (!container || !highlightTextRef.current) return

    let attempt = 0
    const tryHighlight = () => {
      attempt++
      const success = applyHighlight(container, highlightTextRef.current)
      if (!success && attempt < 5) setTimeout(tryHighlight, attempt * 200)
    }
    tryHighlight()
  }, [useRectHighlights])

  const onRenderTextLayerSuccess = useCallback(() => {
    setTextLayerRendered((n) => n + 1)
  }, [])

  useEffect(() => {
    if (textLayerRendered > 0 && !useRectHighlights) {
      const timer = setTimeout(doHighlight, 100)
      return () => clearTimeout(timer)
    }
  }, [textLayerRendered, doHighlight, useRectHighlights])

  useEffect(() => {
    if (useRectHighlights) return
    if (!highlightText) {
      const container = pageContainerRef.current
      if (container) applyHighlight(container, null)
      return
    }
    const timer = setTimeout(doHighlight, 300)
    return () => clearTimeout(timer)
  }, [highlightText, currentPage, doHighlight, useRectHighlights])

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const onDocumentLoadSuccess = useCallback((pdf: any) => {
    setNumPages(pdf.numPages)
    pdfDocRef.current = pdf
  }, [])

  const goToPage = (page: number) => {
    const p = Math.max(1, Math.min(page, numPages))
    setCurrentPage(p)
    onPageChange?.(p)
  }

  const zoom = (delta: number) => {
    setScale((s) => Math.max(0.5, Math.min(3.0, s + delta)))
  }

  // Compute rect overlays for the current page
  const currentPageOverlays = useCallback(() => {
    const pageKey = String(currentPage)
    const pageDim = pageDimensions?.[pageKey]
    if (!pageDim || !renderedSize) return []

    const scaleX = renderedSize.width / pageDim.width
    const scaleY = renderedSize.height / pageDim.height

    const overlays: {
      clauseId: string
      x: number; y: number; w: number; h: number
      isActive: boolean
      color: string
    }[] = []

    // Active rects (selected clause)
    if (activeRects) {
      for (const r of activeRects) {
        if (r.page === currentPage) {
          overlays.push({
            clauseId: '__active__',
            x: r.x0 * scaleX,
            y: r.y0 * scaleY,
            w: (r.x1 - r.x0) * scaleX,
            h: (r.y1 - r.y0) * scaleY,
            isActive: true,
            color: ACTIVE_COLOR,
          })
        }
      }
    }

    // All highlights (passive)
    if (allHighlights && !activeRects) {
      for (const [clauseId, data] of Object.entries(allHighlights)) {
        const color = CLAUSE_COLORS[data.clause_type] || DEFAULT_COLOR
        for (const r of data.rects) {
          if (r.page === currentPage) {
            overlays.push({
              clauseId,
              x: r.x0 * scaleX,
              y: r.y0 * scaleY,
              w: (r.x1 - r.x0) * scaleX,
              h: (r.y1 - r.y0) * scaleY,
              isActive: false,
              color,
            })
          }
        }
      }
    }

    return overlays
  }, [currentPage, pageDimensions, renderedSize, activeRects, allHighlights])

  const overlays = currentPageOverlays()

  // Scroll to first active overlay
  useEffect(() => {
    if (!activeRects || activeRects.length === 0) return
    const timer = setTimeout(() => {
      const el = pageContainerRef.current?.querySelector('[data-active-highlight="true"]')
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 150)
    return () => clearTimeout(timer)
  }, [activeRects, currentPage])

  // ── Render ──

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-50">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !pdfUrl) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-gray-50 text-gray-400 gap-2">
        <DocumentTextIcon className="h-10 w-10" />
        <p className="text-sm">Document preview not available</p>
        <p className="text-xs">The original file may not be accessible from this view</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-gray-100">
      {/* Toolbar */}
      <div className="flex-shrink-0 flex items-center justify-between px-3 py-2 bg-white border-b border-gray-200">
        <div className="flex items-center gap-1">
          <button
            onClick={() => goToPage(currentPage - 1)}
            disabled={currentPage <= 1}
            className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30"
          >
            <ChevronLeftIcon className="h-4 w-4" />
          </button>
          <span className="text-xs text-gray-600 min-w-[80px] text-center">
            {currentPage} / {numPages}
          </span>
          <button
            onClick={() => goToPage(currentPage + 1)}
            disabled={currentPage >= numPages}
            className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30"
          >
            <ChevronRightIcon className="h-4 w-4" />
          </button>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => zoom(-0.15)} className="p-1.5 rounded hover:bg-gray-100">
            <MagnifyingGlassMinusIcon className="h-4 w-4" />
          </button>
          <span className="text-xs text-gray-500 min-w-[40px] text-center">
            {Math.round(scale * 100)}%
          </span>
          <button onClick={() => zoom(0.15)} className="p-1.5 rounded hover:bg-gray-100">
            <MagnifyingGlassPlusIcon className="h-4 w-4" />
          </button>
          <button onClick={() => setScale(1.0)} className="p-1.5 rounded hover:bg-gray-100 text-xs text-gray-500 ml-1">
            Reset
          </button>
        </div>
      </div>

      {/* PDF Display */}
      <div className="flex-1 overflow-auto flex justify-center p-4" ref={pageContainerRef}>
        <div style={{ position: 'relative' }}>
          <Document
            file={pdfUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            loading={<LoadingSpinner size="lg" />}
            error={<p className="text-sm text-red-500">Failed to render PDF</p>}
          >
            <Page
              pageNumber={currentPage}
              scale={scale}
              renderTextLayer={true}
              renderAnnotationLayer={false}
              onRenderTextLayerSuccess={onRenderTextLayerSuccess}
              onRenderSuccess={(page) => {
                setRenderedSize({ width: page.width, height: page.height })
              }}
              className={
                activeRects ? 'shadow-lg ring-2 ring-yellow-400 ring-offset-2' :
                highlightText ? 'shadow-lg ring-2 ring-yellow-400 ring-offset-2' :
                'shadow-lg'
              }
            />
          </Document>

          {/* Rect-based highlight overlays */}
          {overlays.map((ov, i) => (
            <div
              key={`${ov.clauseId}-${i}`}
              data-active-highlight={ov.isActive ? 'true' : undefined}
              onClick={() => ov.clauseId !== '__active__' && onHighlightClick?.(ov.clauseId)}
              style={{
                position: 'absolute',
                left: `${ov.x}px`,
                top: `${ov.y}px`,
                width: `${ov.w}px`,
                height: `${ov.h}px`,
                backgroundColor: ov.color,
                cursor: ov.isActive ? 'default' : 'pointer',
                pointerEvents: 'auto',
                mixBlendMode: 'multiply',
                borderRadius: '2px',
                transition: 'background-color 0.2s',
                zIndex: ov.isActive ? 5 : 4,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
