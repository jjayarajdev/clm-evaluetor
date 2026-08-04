/* Surveys — Direction B redesign.
   Instances and templates as Tables: send-status Pills, response rates as
   Bars, template preview in a Drawer, and survey/template composition moved
   from modals into Drawers. Data fetching and every mutation (create
   template, create instance, send) are unchanged from the pre-redesign page. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ClipboardDocumentListIcon,
  InboxArrowDownIcon,
  PaperAirplaneIcon,
  PlusIcon,
  SquaresPlusIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  Bar,
  Button,
  Drawer,
  EmptyState,
  Field,
  Pill,
  Select,
  Table,
  Tabs,
  Tag,
  useToast,
} from '@/components/ui'
import type { PillTone, TableColumn } from '@/components/ui'
import type {
  SurveyTemplate,
  SurveyInstance,
  SurveyTemplateCreate,
  SurveyInstanceCreate,
  SurveyType,
  SurveyInstanceStatus,
} from '@/types/governance'

const STATUS_TONE: Record<SurveyInstanceStatus, PillTone> = {
  draft: 'n',
  scheduled: 'in',
  sent: 'p',
  in_progress: 'wa',
  completed: 'ok',
  expired: 'wa',
  cancelled: 'n',
}

export default function SurveysPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<'templates' | 'instances'>('instances')
  const [showCreateTemplate, setShowCreateTemplate] = useState(false)
  const [showCreateInstance, setShowCreateInstance] = useState(false)
  const [preview, setPreview] = useState<SurveyTemplate | null>(null)
  const [templateForm, setTemplateForm] = useState<Partial<SurveyTemplateCreate>>({
    survey_type: 'satisfaction',
  })
  const [instanceForm, setInstanceForm] = useState<Partial<SurveyInstanceCreate>>({})

  const { data: templates = [], isLoading: loadingTemplates } = useQuery({
    queryKey: ['survey-templates'],
    queryFn: () => api.getSurveyTemplates(),
  })

  const { data: instances = [], isLoading: loadingInstances } = useQuery({
    queryKey: ['survey-instances'],
    queryFn: () => api.getSurveyInstances(),
  })

  const { data: relationships = [] } = useQuery({
    queryKey: ['relationships'],
    queryFn: () => api.getRelationships(),
  })

  const createTemplateMutation = useMutation({
    mutationFn: (data: SurveyTemplateCreate) => api.createSurveyTemplate(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['survey-templates'] })
      setShowCreateTemplate(false)
      setTemplateForm({ survey_type: 'satisfaction' })
      toast({ text: t('governance.templateCreated', { defaultValue: 'Template created' }) })
    },
  })

  const createInstanceMutation = useMutation({
    mutationFn: (data: SurveyInstanceCreate) => api.createSurveyInstance(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['survey-instances'] })
      setShowCreateInstance(false)
      setInstanceForm({})
      toast({ text: t('governance.surveyCreated', { defaultValue: 'Survey created' }) })
    },
  })

  const sendMutation = useMutation({
    mutationFn: (id: string) => api.sendSurvey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['survey-instances'] })
      toast({ text: t('governance.surveySent', { defaultValue: 'Survey sent' }) })
    },
  })

  const isLoading = loadingTemplates || loadingInstances

  const instanceColumns: TableColumn<SurveyInstance>[] = [
    {
      key: 'name',
      header: t('nav.surveys'),
      sortable: true,
      sortValue: i => i.template_name || i.title || i.period || '',
      render: i => (
        <span>
          <span style={{ display: 'block', fontWeight: 500 }}>
            {i.template_name || i.title || i.period || t('governance.untitledSurvey')}
          </span>
          {i.relationship_name && (
            <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-sm)', marginTop: 2 }}>
              {i.relationship_name}
            </span>
          )}
        </span>
      ),
    },
    {
      key: 'period',
      header: t('governance.period'),
      width: 100,
      sortable: true,
      sortValue: i => i.period,
      render: i => i.period ? <span className="num nw muted">{i.period}</span> : <span className="faint">--</span>,
    },
    {
      key: 'due_date',
      header: t('governance.dueDate'),
      width: 120,
      align: 'right',
      sortable: true,
      sortValue: i => i.due_date,
      render: i =>
        i.due_date
          ? <span className="num nw muted">{new Date(i.due_date).toLocaleDateString()}</span>
          : <span className="faint">--</span>,
    },
    {
      key: 'responses',
      header: t('governance.responses', { defaultValue: 'Responses' }),
      width: 150,
      sortable: true,
      sortValue: i => i.response_rate ?? (i.target_respondents ? (i.actual_respondents / i.target_respondents) * 100 : null),
      render: i => {
        const rate = i.response_rate ?? (i.target_respondents ? (i.actual_respondents / i.target_respondents) * 100 : null)
        if (rate == null) return <span className="faint">--</span>
        return (
          <span className="row" style={{ gap: 8 }}>
            <Bar value={rate} width={54} tone={rate >= 100 ? 'var(--ok)' : undefined} />
            <span className="mono num faint" style={{ fontSize: 'var(--fs-sm)' }}>
              {i.actual_respondents}/{i.target_respondents}
            </span>
          </span>
        )
      },
    },
    {
      key: 'status',
      header: t('common.status'),
      width: 120,
      sortable: true,
      render: i => (
        <Pill tone={STATUS_TONE[i.status] || 'n'}>
          {t(`governance.surveyStatus.${i.status}`, { defaultValue: i.status })}
        </Pill>
      ),
    },
    {
      key: 'actions',
      header: t('common.actions'),
      width: 100,
      align: 'right',
      render: i =>
        i.status === 'draft' ? (
          <Button
            size="sm"
            icon={PaperAirplaneIcon}
            disabled={sendMutation.isPending}
            onClick={() => sendMutation.mutate(i.id)}
          >
            {t('governance.send')}
          </Button>
        ) : (
          <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
            {i.sent_at ? new Date(i.sent_at).toLocaleDateString() : ''}
          </span>
        ),
    },
  ]

  const templateColumns: TableColumn<SurveyTemplate>[] = [
    {
      key: 'name',
      header: t('governance.template'),
      sortable: true,
      render: tm => (
        <span>
          <span style={{ display: 'block', fontWeight: 500 }}>{tm.name}</span>
          {tm.description && (
            <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-sm)', marginTop: 2, maxWidth: 420 }}>
              {tm.description}
            </span>
          )}
        </span>
      ),
    },
    {
      key: 'survey_type',
      header: t('governance.type'),
      width: 130,
      sortable: true,
      render: tm => <Tag>{t(`governance.surveyTypes.${tm.survey_type}`, { defaultValue: tm.survey_type })}</Tag>,
    },
    {
      key: 'questions',
      header: t('governance.questions', { defaultValue: 'Questions' }),
      width: 110,
      align: 'right',
      sortable: true,
      sortValue: tm => tm.question_count ?? tm.questions?.length ?? 0,
      render: tm => (
        <span className="num faint">
          {t('governance.questionsCount', { count: tm.question_count ?? tm.questions?.length ?? 0 })}
        </span>
      ),
    },
    {
      key: 'is_active',
      header: t('common.status'),
      width: 110,
      sortable: true,
      sortValue: tm => (tm.is_active ? 0 : 1),
      render: tm => (
        <Pill tone={tm.is_active ? 'ok' : 'n'}>
          {tm.is_active ? t('status.active') : t('status.inactive')}
        </Pill>
      ),
    },
  ]

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', padding: '64px 0' }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>{t('nav.surveys')}</h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>{t('governance.surveysSubtitle')}</p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          {tab === 'templates' && (
            <Button variant="primary" icon={SquaresPlusIcon} onClick={() => setShowCreateTemplate(true)}>
              {t('governance.newTemplate')}
            </Button>
          )}
          {tab === 'instances' && (
            <Button variant="primary" icon={PlusIcon} onClick={() => setShowCreateInstance(true)}>
              {t('governance.newSurvey')}
            </Button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <Tabs
        tabs={[
          { value: 'instances', label: t('nav.surveys'), icon: InboxArrowDownIcon, count: instances.length },
          { value: 'templates', label: t('governance.templates', { defaultValue: 'Templates' }), icon: SquaresPlusIcon, count: templates.length },
        ]}
        value={tab}
        onChange={setTab}
      />

      {/* Instances */}
      {tab === 'instances' && (
        <Table
          columns={instanceColumns}
          rows={instances}
          rowKey={i => i.id}
          minWidth={720}
          empty={
            <EmptyState
              icon={InboxArrowDownIcon}
              title={t('governance.noSurveyInstances')}
              action={
                <Button variant="primary" size="sm" icon={PlusIcon} onClick={() => setShowCreateInstance(true)}>
                  {t('governance.newSurvey')}
                </Button>
              }
            />
          }
        />
      )}

      {/* Templates */}
      {tab === 'templates' && (
        <Table
          columns={templateColumns}
          rows={templates}
          rowKey={tm => tm.id}
          onRowClick={tm => setPreview(tm)}
          selectedKey={preview?.id ?? null}
          minWidth={680}
          empty={
            <EmptyState
              icon={ClipboardDocumentListIcon}
              title={t('governance.noSurveyTemplates')}
              action={
                <Button variant="primary" size="sm" icon={SquaresPlusIcon} onClick={() => setShowCreateTemplate(true)}>
                  {t('governance.newTemplate')}
                </Button>
              }
            />
          }
        />
      )}

      {/* Template preview drawer */}
      <Drawer
        open={!!preview}
        title={preview?.name || ''}
        sub={preview ? t(`governance.surveyTypes.${preview.survey_type}`, { defaultValue: preview.survey_type }) : undefined}
        onClose={() => setPreview(null)}
      >
        {preview && (
          <div className="col" style={{ gap: 18 }}>
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              <Pill tone={preview.is_active ? 'ok' : 'n'}>
                {preview.is_active ? t('status.active') : t('status.inactive')}
              </Pill>
              <Tag>{t('governance.questionsCount', { count: preview.question_count ?? preview.questions?.length ?? 0 })}</Tag>
              {preview.frequency && <Tag>{preview.frequency}</Tag>}
              {preview.is_anonymous && (
                <Tag>{t('governance.anonymous', { defaultValue: 'Anonymous' })}</Tag>
              )}
            </div>
            {preview.description && (
              <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.55 }}>{preview.description}</p>
            )}
            {preview.intro_text && (
              <div>
                <div className="sec-t" style={{ marginBottom: 6 }}>
                  {t('governance.introText', { defaultValue: 'Introduction' })}
                </div>
                <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.55 }}>{preview.intro_text}</p>
              </div>
            )}
            {preview.questions && preview.questions.length > 0 && (
              <div>
                <div className="sec-t" style={{ marginBottom: 8 }}>
                  {t('governance.questions', { defaultValue: 'Questions' })}
                </div>
                <div className="col" style={{ gap: 8 }}>
                  {[...preview.questions]
                    .sort((a, b) => a.display_order - b.display_order)
                    .map((q, n) => (
                      <div key={q.id} className="card card-p col" style={{ gap: 8 }}>
                        <div className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
                          <span className="faint mono" style={{ fontSize: 'var(--fs-sm)' }}>{n + 1}</span>
                          <span className="grow" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{q.question_text}</span>
                        </div>
                        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                          <Tag>{q.question_type}</Tag>
                          {q.kpi_id ? (
                            <Tag>{t('governance.linkedToKpi', { defaultValue: 'Linked to KPI' })}</Tag>
                          ) : (
                            <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
                              {t('governance.notLinkedToKpi', { defaultValue: 'not linked to a KPI' })}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            )}
            {preview.closing_text && (
              <div>
                <div className="sec-t" style={{ marginBottom: 6 }}>
                  {t('governance.closingText', { defaultValue: 'Closing' })}
                </div>
                <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.55 }}>{preview.closing_text}</p>
              </div>
            )}
          </div>
        )}
      </Drawer>

      {/* Create template drawer */}
      <Drawer
        open={showCreateTemplate}
        title={t('governance.newSurveyTemplate')}
        onClose={() => setShowCreateTemplate(false)}
        footer={
          <>
            <Button
              variant="primary"
              className="grow"
              disabled={!templateForm.name || createTemplateMutation.isPending}
              onClick={() => {
                if (!templateForm.name) return
                createTemplateMutation.mutate(templateForm as SurveyTemplateCreate)
              }}
            >
              {createTemplateMutation.isPending ? t('governance.creating') : t('governance.create')}
            </Button>
            <Button variant="ghost" className="grow" onClick={() => setShowCreateTemplate(false)}>
              {t('common.cancel')}
            </Button>
          </>
        }
      >
        <div className="col" style={{ gap: 14 }}>
          <Field
            label={`${t('governance.name')} *`}
            value={templateForm.name || ''}
            autoFocus
            onChange={e => setTemplateForm({ ...templateForm, name: e.target.value })}
          />
          <Select
            label={t('governance.type')}
            value={templateForm.survey_type || 'satisfaction'}
            onChange={e => setTemplateForm({ ...templateForm, survey_type: e.target.value as SurveyType })}
            options={[
              { value: 'satisfaction', label: t('governance.surveyTypes.satisfaction') },
              { value: 'performance', label: t('governance.surveyTypes.performance') },
              { value: 'relationship', label: t('governance.surveyTypes.relationship') },
              { value: 'custom', label: t('governance.surveyTypes.custom') },
            ]}
          />
          <div>
            <label className="lbl">{t('governance.description')}</label>
            <div className="inp" style={{ height: 'auto', padding: '8px 10px' }}>
              <textarea
                rows={3}
                style={{ resize: 'vertical' }}
                value={templateForm.description || ''}
                onChange={e => setTemplateForm({ ...templateForm, description: e.target.value })}
              />
            </div>
          </div>
        </div>
      </Drawer>

      {/* Create instance drawer */}
      <Drawer
        open={showCreateInstance}
        title={t('governance.newSurveyInstance')}
        onClose={() => setShowCreateInstance(false)}
        footer={
          <>
            <Button
              variant="primary"
              className="grow"
              disabled={!instanceForm.template_id || !instanceForm.relationship_id || !instanceForm.period || createInstanceMutation.isPending}
              onClick={() => {
                if (!instanceForm.template_id || !instanceForm.relationship_id || !instanceForm.period) return
                createInstanceMutation.mutate(instanceForm as SurveyInstanceCreate)
              }}
            >
              {createInstanceMutation.isPending ? t('governance.creating') : t('governance.create')}
            </Button>
            <Button variant="ghost" className="grow" onClick={() => setShowCreateInstance(false)}>
              {t('common.cancel')}
            </Button>
          </>
        }
      >
        <div className="col" style={{ gap: 14 }}>
          <Select
            label={`${t('governance.template')} *`}
            value={instanceForm.template_id || ''}
            onChange={e => setInstanceForm({ ...instanceForm, template_id: e.target.value })}
            options={[
              { value: '', label: t('governance.selectTemplate') },
              ...templates.map(tm => ({ value: tm.id, label: tm.name })),
            ]}
          />
          <Select
            label={`${t('governance.relationship')} *`}
            value={instanceForm.relationship_id || ''}
            onChange={e => setInstanceForm({ ...instanceForm, relationship_id: e.target.value })}
            options={[
              { value: '', label: t('governance.selectRelationship') },
              ...relationships.map(rel => ({
                value: rel.id,
                label: `${rel.org_a?.name || rel.org_a_id} ↔ ${rel.org_b?.name || rel.org_b_id}`,
              })),
            ]}
          />
          <Field
            label={`${t('governance.period')} *`}
            value={instanceForm.period || ''}
            placeholder={t('governance.periodPlaceholder')}
            onChange={e => setInstanceForm({ ...instanceForm, period: e.target.value })}
          />
          <Field
            label={t('governance.dueDate')}
            type="date"
            value={instanceForm.due_date || ''}
            onChange={e => setInstanceForm({ ...instanceForm, due_date: e.target.value })}
          />
        </div>
      </Drawer>
    </div>
  )
}
