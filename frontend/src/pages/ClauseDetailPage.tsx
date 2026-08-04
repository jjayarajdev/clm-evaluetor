/* Clause detail — Direction B redesign.
   Back link + header with mono id, risk Pill and type Tag → AI-extracted full
   text card → risk-analysis banner → related clauses as bordered rows →
   source-contract sidebar. Read-only page: query and navigation unchanged. */
import { useTranslation } from 'react-i18next'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  ChatBubbleLeftRightIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  HashtagIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Button, Pill, Tag, AiTag } from '@/components/ui'
import type { PillTone } from '@/components/ui'

const CLAUSE_TYPE_LABELS: Record<string, string> = {
  confidentiality: 'Confidentiality',
  indemnification: 'Indemnification',
  limitation_of_liability: 'Limitation of Liability',
  termination: 'Termination',
  warranty: 'Warranty',
  force_majeure: 'Force Majeure',
  governing_law: 'Governing Law',
  dispute_resolution: 'Dispute Resolution',
  payment_terms: 'Payment Terms',
  intellectual_property: 'Intellectual Property',
  data_protection: 'Data Protection',
  non_compete: 'Non-Compete',
  non_solicitation: 'Non-Solicitation',
  assignment: 'Assignment',
  notice: 'Notice',
  sla: 'SLA',
  auto_renewal: 'Auto-Renewal',
  other: 'Other',
}

const RISK_TONE: Record<string, PillTone> = {
  low: 'ok',
  medium: 'wa',
  high: 'da',
  critical: 'da',
}

export default function ClauseDetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const clauseTypeLabel = (type: string) =>
    t(`clauses.${type}`, {
      defaultValue: t(`clause.type.${type}`, {
        defaultValue: CLAUSE_TYPE_LABELS[type] || type,
      }),
    })

  const { data: clause, isLoading, error } = useQuery({
    queryKey: ['clause', id],
    queryFn: () => api.getClauseDetail(id!),
    enabled: !!id,
  })

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !clause) {
    return (
      <div className="col" style={{ alignItems: 'center', gap: 8, padding: '48px 0' }}>
        <p style={{ color: 'var(--da)' }}>{t('clause.notFound')}</p>
        <Link to="/dashboard">{t('clause.backToDashboard')}</Link>
      </div>
    )
  }

  const riskBanner =
    clause.risk_level === 'high' || clause.risk_level === 'critical'
      ? 'banner-da'
      : clause.risk_level === 'medium'
        ? 'banner-wa'
        : 'banner-in'

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Back link + header */}
      <div>
        <Link
          to="/dashboard"
          className="row"
          style={{ gap: 4, width: 'fit-content', fontSize: 'var(--fs-sm)', color: 'var(--m)' }}
        >
          <ArrowLeftIcon style={{ width: 14, height: 14 }} aria-hidden />
          {t('clause.backToDashboard')}
        </Link>
        <div className="row" style={{ gap: 12, alignItems: 'flex-start', marginTop: 10, flexWrap: 'wrap' }}>
          <div className="grow" style={{ minWidth: 240 }}>
            <div className="row" style={{ gap: 7, marginBottom: 5, flexWrap: 'wrap' }}>
              <span className="mono faint" style={{ fontSize: 'var(--fs-xs)' }}>{clause.id.slice(0, 8)}</span>
              {clause.risk_level && (
                <Pill tone={RISK_TONE[clause.risk_level] || 'n'}>
                  {t('contract.riskLabel', {
                    level: t(`risk.${clause.risk_level}`, { defaultValue: clause.risk_level }),
                  })}
                </Pill>
              )}
              <Tag>{clauseTypeLabel(clause.clause_type)}</Tag>
            </div>
            <h1 style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, letterSpacing: '-.4px', lineHeight: 1.25 }}>
              {t('clause.clauseFrom', { filename: clause.contract_filename })}
            </h1>
            <div className="row muted" style={{ gap: 8, marginTop: 8, fontSize: 'var(--fs-md)', flexWrap: 'wrap' }}>
              {clause.page_number != null && (
                <Tag icon={DocumentTextIcon}>{t('clause.page', { number: clause.page_number })}</Tag>
              )}
              {clause.section_number && (
                <Tag icon={HashtagIcon}>{t('clause.section', { number: clause.section_number })}</Tag>
              )}
              {clause.contract_type && <Tag>{clause.contract_type.toUpperCase()}</Tag>}
            </div>
          </div>
          <div className="row" style={{ gap: 8, flexShrink: 0 }}>
            <Button
              variant="secondary"
              icon={ChatBubbleLeftRightIcon}
              onClick={() => navigate(`/query?clause=${clause.id}&contract=${clause.contract_id}`)}
            >
              {t('clause.askAi')}
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
        {/* Main content */}
        <div className="lg:col-span-2 col" style={{ gap: 16 }}>
          {/* Full clause text — AI-extracted */}
          <div className="card card-p">
            <div className="row" style={{ gap: 8, marginBottom: 10 }}>
              <span className="sec-t">{t('clause.fullClauseText')}</span>
              <AiTag />
              <span className="grow" />
              {clause.page_number != null && (
                <span className="mono faint" style={{ fontSize: 'var(--fs-xs)' }}>
                  p.{clause.page_number}
                  {clause.section_number ? ` · ${clause.section_number}` : ''}
                </span>
              )}
            </div>
            <div
              style={{
                padding: 14,
                borderRadius: 'var(--r-md)',
                background: 'var(--s2)',
                fontSize: 'var(--fs-md)',
                lineHeight: 1.65,
                whiteSpace: 'pre-wrap',
              }}
            >
              {clause.text}
            </div>
          </div>

          {/* Risk analysis */}
          {clause.risk_reason && (
            <div className="card card-p">
              <div className="row" style={{ gap: 8, marginBottom: 10 }}>
                <span className="sec-t">{t('clause.riskAnalysis')}</span>
                <AiTag />
              </div>
              <div className={`banner ${riskBanner}`}>
                <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
                <span className="grow">{clause.risk_reason}</span>
              </div>
            </div>
          )}

          {/* Related clauses — bordered rows */}
          {clause.related_clauses && clause.related_clauses.length > 0 && (
            <div className="card" style={{ padding: '4px 0' }}>
              <div className="sec-t" style={{ padding: '10px 16px', borderBottom: '1px solid var(--b)' }}>
                {t('clause.otherClauses', { count: clause.related_clauses.length })}
              </div>
              {clause.related_clauses.map((related, n, arr) => (
                <Link
                  key={related.id}
                  to={`/clauses/${related.id}`}
                  className="row"
                  style={{
                    gap: 12,
                    alignItems: 'flex-start',
                    padding: '12px 16px',
                    borderBottom: n < arr.length - 1 ? '1px solid var(--b)' : 0,
                    color: 'inherit',
                  }}
                >
                  <div className="grow" style={{ minWidth: 0 }}>
                    <div className="row" style={{ gap: 8, marginBottom: 4 }}>
                      <Tag>{clauseTypeLabel(related.clause_type)}</Tag>
                      {related.page_number != null && (
                        <span className="mono faint" style={{ fontSize: 'var(--fs-xs)' }}>
                          {t('clause.page', { number: related.page_number })}
                        </span>
                      )}
                    </div>
                    <p className="muted line-clamp-2" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.5 }}>
                      {related.text}
                    </p>
                  </div>
                  {related.risk_level && (
                    <Pill tone={RISK_TONE[related.risk_level] || 'n'}>
                      {t(`risk.${related.risk_level}`, { defaultValue: related.risk_level })}
                    </Pill>
                  )}
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="col" style={{ gap: 16 }}>
          <div className="card card-p">
            <div className="sec-t" style={{ marginBottom: 10 }}>{t('clause.sourceContract')}</div>
            <div className="col" style={{ gap: 12 }}>
              <div>
                <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 2 }}>
                  {t('clause.document')}
                </div>
                <div style={{ fontSize: 'var(--fs-md)', fontWeight: 500, overflowWrap: 'anywhere' }}>
                  {clause.contract_filename}
                </div>
              </div>
              {clause.counterparty && (
                <div>
                  <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 2 }}>
                    {t('contracts.counterparty')}
                  </div>
                  <div style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{clause.counterparty}</div>
                </div>
              )}
              {clause.contract_type && (
                <div>
                  <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 2 }}>
                    {t('clause.contractType')}
                  </div>
                  <div style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                    {clause.contract_type.toUpperCase()}
                  </div>
                </div>
              )}
              <div className="divider" />
              <Button
                variant="primary"
                style={{ width: '100%' }}
                onClick={() => navigate(`/contracts/${clause.contract_id}`)}
              >
                {t('clause.viewFullContract')}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
