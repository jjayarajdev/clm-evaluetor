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

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

interface ContractPdfViewerProps {
  contractId: string
  mimeType?: string | null
  highlightPage?: number | null
  highlightText?: string | null
  onPageChange?: (page: number) => void
  onPageFound?: (page: number) => void
}

function normalize(text: string): string {
  return text.toLowerCase().replace(/\s+/g, ' ').trim()
}

// ─── Text highlight logic ───────────────────────────────────────────

function applyHighlight(container: HTMLElement, highlightText: string | null): boolean {
  // Try both possible selectors for the text layer
  const layer =
    container.querySelector('.react-pdf__Page__textContent') ||
    container.querySelector('.textLayer')
  if (!layer) return false

  // In pdfjs v5, text spans may have role="presentation" — query all spans
  const spans = Array.from(layer.querySelectorAll('span')) as HTMLElement[]

  // Clear previous highlight overlays
  container.querySelectorAll('.clause-highlight-overlay').forEach((el) => el.remove())

  if (!highlightText) return true
  if (spans.length === 0) return false

  // Build concatenated text with offset tracking
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

  // Build normalized text with position map
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

  // Progressive prefix matching
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

  // Map back to original positions
  const origStart = normToOrig[matchNormStart] ?? 0
  const endIdx = Math.min(matchNormStart + matchNormLen - 1, normToOrig.length - 1)
  const origEnd = (normToOrig[endIdx] ?? origText.length) + 1

  // Create highlight overlays on top of matching spans
  // pdfjs text spans are transparent (color: transparent) with position: absolute,
  // so we create visible overlay divs positioned to match each span's bounding box.
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

// ─── Main Component ─────────────────────────────────────────────────

export default function ContractPdfViewer({
  contractId,
  mimeType,
  highlightPage,
  highlightText,
  onPageChange,
  onPageFound,
}: ContractPdfViewerProps) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [numPages, setNumPages] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [scale, setScale] = useState(1.0)
  const [textLayerRendered, setTextLayerRendered] = useState(0) // counter to trigger highlight
  const pageContainerRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const pdfDocRef = useRef<any>(null)
  const highlightTextRef = useRef<string | null>(null)
  highlightTextRef.current = highlightText || null

  // Load file — request PDF conversion for DOCX files
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    const isDocx = mimeType && (mimeType.includes('wordprocessingml') || mimeType.includes('msword'))

    api.downloadContractFile(contractId, !!isDocx)
      .then((blob) => {
        if (cancelled) return
        const url = URL.createObjectURL(blob)
        setPdfUrl(url)
        setLoading(false)
      })
      .catch(() => {
        if (cancelled) return
        setError('Failed to load document')
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [contractId, mimeType])

  // Cleanup blob URL on unmount
  useEffect(() => {
    return () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl)
    }
  }, [pdfUrl])

  // Jump to highlighted page
  useEffect(() => {
    if (highlightPage && highlightPage >= 1 && highlightPage <= numPages) {
      setCurrentPage(highlightPage)
    }
  }, [highlightPage, numPages])

  // Search all pages for text when no page is specified
  useEffect(() => {
    if (!highlightText || highlightPage || !pdfDocRef.current) return

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
        } catch {
          // skip
        }
      }
    }

    searchPages()
    return () => { cancelled = true }
  }, [highlightText, highlightPage, numPages])

  // Apply text highlighting — triggered by text layer render or highlight change
  const doHighlight = useCallback(() => {
    const container = pageContainerRef.current
    if (!container || !highlightTextRef.current) return

    // Retry up to 5 times with increasing delays for text layer population
    let attempt = 0
    const maxAttempts = 5

    const tryHighlight = () => {
      attempt++
      const success = applyHighlight(container, highlightTextRef.current)
      if (!success && attempt < maxAttempts) {
        setTimeout(tryHighlight, attempt * 200)
      }
    }

    tryHighlight()
  }, [])

  // When text layer finishes rendering, apply highlighting
  const onRenderTextLayerSuccess = useCallback(() => {
    setTextLayerRendered((n) => n + 1)
  }, [])

  // React to text layer render completion
  useEffect(() => {
    if (textLayerRendered > 0) {
      // Small delay to ensure DOM is fully updated
      const timer = setTimeout(doHighlight, 100)
      return () => clearTimeout(timer)
    }
  }, [textLayerRendered, doHighlight])

  // React to highlight text changes (when text layer is already rendered)
  useEffect(() => {
    if (!highlightText) {
      // Clear highlights
      const container = pageContainerRef.current
      if (container) applyHighlight(container, null)
      return
    }

    // Delay to allow page transition to complete
    const timer = setTimeout(doHighlight, 300)
    return () => clearTimeout(timer)
  }, [highlightText, currentPage, doHighlight])

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
            className={highlightText ? 'shadow-lg ring-2 ring-yellow-400 ring-offset-2' : 'shadow-lg'}
          />
        </Document>
      </div>
    </div>
  )
}
