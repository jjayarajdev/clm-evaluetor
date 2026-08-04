/* Surveys — Direction B redesign.
   Instances and templates as Tables: send-status Pills, response rates as
   Bars, template preview in a Drawer, and survey/template composition moved
   from modals into Drawers. Data fetching and every pre-existing mutation
   (create template, create instance, send) are unchanged from the
   pre-redesign page. The template Drawer additionally supports an edit mode
   (rename, description, intro/closing text, frequency, active flag) plus
   question add / inline edit / delete, and templates can be deactivated
   (the backend delete is a soft delete) from the table. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ClipboardDocumentListIcon,
  InboxArrowDownIcon,
  PaperAirplaneIcon,
  PencilSquareIcon,
  PlusIcon,
  SquaresPlusIcon,
  TrashIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  Bar,
  Button,
  Checkbox,
  ConfirmDialog,
  Drawer,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Select,
  Switch,
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
  SurveyTemplateUpdate,
  SurveyInstanceCreate,
  SurveyQuestion,
  SurveyQuestionCreate,
  SurveyQuestionUpdate,
  SurveyType,
  SurveyFrequency,
  SurveyInstanceStatus,
  QuestionType,
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

const QUESTION_TYPES: QuestionType[] = [
  'rating', 'rating_5', 'nps', 'single_choice', 'multiple_choice', 'text', 'text_long', 'yes_no',
]

const FREQUENCIES: SurveyFrequency[] = ['one_time', 'monthly', 'quarterly', 'semi_annual', 'annual']

/* The backend returns `text` / `sequence`; older frontend typings used
   `question_text` / `display_order`. Read both so either shape renders. */
const questionText = (q: SurveyQuestion) => q.question_text ?? q.text ?? ''
const questionOrder = (q: SurveyQuestion) => q.display_order ?? q.sequence ?? 0

export default function SurveysPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<'templates' | 'instances'>('instances')
  const [showCreateTemplate, setShowCreateTemplate] = useState(false)
  const [showCreateInstance, setShowCreateInstance] = useState(false)
  const [preview, setPreview] = useState<SurveyTemplate | null>(null)
  const [editMode, setEditMode] = useState(false)
  const [editForm, setEditForm] = useState<SurveyTemplateUpdate>({})
  const [editingQuestionId, setEditingQuestionId] = useState<string | null>(null)
  const [questionForm, setQuestionForm] = useState<SurveyQuestionUpdate>({})
  const [showAddQuestion, setShowAddQuestion] = useState(false)
  const [newQuestion, setNewQuestion] = useState<{ text: string; question_type: QuestionType }>({ text: '', question_type: 'rating' })
  const [deleteTemplateTarget, setDeleteTemplateTarget] = useState<SurveyTemplate | null>(null)
  const [deleteQuestionTarget, setDeleteQuestionTarget] = useState<SurveyQuestion | null>(null)
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

  /* The list endpoint omits questions — fetch the full template while the
     drawer is open so the preview (and question editing) has them. */
  const { data: previewDetail, isLoading: loadingDetail } = useQuery({
    queryKey: ['survey-template', preview?.id],
    queryFn: () => api.getSurveyTemplate(preview!.id),
    enabled: !!preview,
  })
  const tpl = preview ? { ...preview, ...(previewDetail?.id === preview.id ? previewDetail : undefined) } : null

  const invalidateTemplates = () => {
    queryClient.invalidateQueries({ queryKey: ['survey-templates'] })
    queryClient.invalidateQueries({ queryKey: ['survey-template'] })
  }

  const createTemplateMutation = useMutation({
    mutationFn: (data: SurveyTemplateCreate) => api.createSurveyTemplate(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['survey-templates'] })
      setShowCreateTemplate(false)
      setTemplateForm({ survey_type: 'satisfaction' })
      toast({ text: t('governance.templateCreated', { defaultValue: 'Template created' }) })
    },
  })

  const updateTemplateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: SurveyTemplateUpdate }) => api.updateSurveyTemplate(id, data),
    onSuccess: (updated) => {
      invalidateTemplates()
      setEditMode(false)
      setPreview(p => (p && p.id === updated.id ? { ...p, ...updated } : p))
      toast({ text: t('governance.templateUpdated', { defaultValue: 'Template updated' }) })
    },
    onError: (err: Error) => {
      toast({ text: err.message || t('governance.updateFailed', { defaultValue: 'Update failed' }), error: true })
    },
  })

  const deleteTemplateMutation = useMutation({
    mutationFn: (id: string) => api.deleteSurveyTemplate(id),
    onSuccess: (_res, id) => {
      invalidateTemplates()
      setDeleteTemplateTarget(null)
      setPreview(p => (p && p.id === id ? null : p))
      setEditMode(false)
      toast({ text: t('governance.templateDeactivated', { defaultValue: 'Template deactivated' }) })
    },
    onError: (err: Error) => {
      setDeleteTemplateTarget(null)
      toast({ text: err.message || t('governance.deleteFailed', { defaultValue: 'Delete failed' }), error: true })
    },
  })

  const addQuestionMutation = useMutation({
    mutationFn: ({ templateId, data }: { templateId: string; data: SurveyQuestionCreate }) =>
      api.addSurveyQuestion(templateId, data),
    onSuccess: () => {
      invalidateTemplates()
      setNewQuestion({ text: '', question_type: 'rating' })
      setShowAddQuestion(false)
      toast({ text: t('governance.questionAdded', { defaultValue: 'Question added' }) })
    },
    onError: (err: Error) => {
      toast({ text: err.message || t('governance.updateFailed', { defaultValue: 'Update failed' }), error: true })
    },
  })

  const updateQuestionMutation = useMutation({
    mutationFn: ({ templateId, questionId, data }: { templateId: string; questionId: string; data: SurveyQuestionUpdate }) =>
      api.updateSurveyQuestion(templateId, questionId, data),
    onSuccess: () => {
      invalidateTemplates()
      setEditingQuestionId(null)
      toast({ text: t('governance.questionUpdated', { defaultValue: 'Question updated' }) })
    },
    onError: (err: Error) => {
      toast({ text: err.message || t('governance.updateFailed', { defaultValue: 'Update failed' }), error: true })
    },
  })

  const deleteQuestionMutation = useMutation({
    mutationFn: ({ templateId, questionId }: { templateId: string; questionId: string }) =>
      api.deleteSurveyQuestion(templateId, questionId),
    onSuccess: () => {
      invalidateTemplates()
      setDeleteQuestionTarget(null)
      toast({ text: t('governance.questionDeleted', { defaultValue: 'Question deleted' }) })
    },
    onError: (err: Error) => {
      setDeleteQuestionTarget(null)
      toast({ text: err.message || t('governance.deleteFailed', { defaultValue: 'Delete failed' }), error: true })
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

  const closePreview = () => {
    setPreview(null)
    setEditMode(false)
    setEditingQuestionId(null)
    setShowAddQuestion(false)
  }

  /* Backend TemplateUpdate accepts: name, description, frequency,
     introduction_text, closing_text, allow_anonymous, require_all_questions,
     is_active. (survey_type is NOT accepted — kept read-only.) */
  const startEdit = (template: SurveyTemplate) => {
    setPreview(template)
    setEditForm({
      name: template.name,
      description: template.description ?? '',
      frequency: (template.frequency as SurveyFrequency) || undefined,
      introduction_text: template.introduction_text ?? template.intro_text ?? '',
      closing_text: template.closing_text ?? '',
      is_active: template.is_active,
    })
    setEditingQuestionId(null)
    setShowAddQuestion(false)
    setEditMode(true)
  }

  const saveTemplate = () => {
    if (!tpl || !editForm.name?.trim() || updateTemplateMutation.isPending) return
    updateTemplateMutation.mutate({ id: tpl.id, data: { ...editForm, name: editForm.name.trim() } })
  }

  const startEditQuestion = (q: SurveyQuestion) => {
    setEditingQuestionId(q.id)
    setQuestionForm({
      text: questionText(q),
      question_type: q.question_type,
      is_required: q.is_required ?? true,
    })
  }

  const saveQuestion = () => {
    if (!tpl || !editingQuestionId || !questionForm.text?.trim() || updateQuestionMutation.isPending) return
    updateQuestionMutation.mutate({
      templateId: tpl.id,
      questionId: editingQuestionId,
      data: { ...questionForm, text: questionForm.text.trim() },
    })
  }

  const questionTypeOptions = QUESTION_TYPES.map(v => ({
    value: v,
    label: t(`governance.questionTypes.${v}`, { defaultValue: v.replace(/_/g, ' ') }),
  }))

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
      render: tm => tm.survey_type
        ? <Tag>{t(`governance.surveyTypes.${tm.survey_type}`, { defaultValue: tm.survey_type })}</Tag>
        : <span className="faint">--</span>,
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
    {
      key: 'actions',
      header: t('common.actions'),
      width: 90,
      align: 'right',
      render: tm => (
        <span
          className="row"
          style={{ gap: 4, justifyContent: 'flex-end' }}
          onClick={e => e.stopPropagation()}
        >
          <IconButton
            size="sm"
            icon={PencilSquareIcon}
            label={t('common.edit')}
            onClick={() => startEdit(tm)}
          />
          <IconButton
            size="sm"
            icon={TrashIcon}
            label={t('common.delete')}
            onClick={() => setDeleteTemplateTarget(tm)}
          />
        </span>
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

  const sortedQuestions = tpl?.questions ? [...tpl.questions].sort((a, b) => questionOrder(a) - questionOrder(b)) : []

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
          onRowClick={tm => { setPreview(tm); setEditMode(false) }}
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

      {/* Template preview / edit drawer */}
      <Drawer
        open={!!tpl}
        title={editMode ? t('governance.editTemplate', { defaultValue: 'Edit template' }) : tpl?.name || ''}
        sub={tpl?.survey_type ? t(`governance.surveyTypes.${tpl.survey_type}`, { defaultValue: tpl.survey_type }) : undefined}
        onClose={closePreview}
        footer={
          tpl ? (
            editMode ? (
              <>
                <Button
                  variant="primary"
                  className="grow"
                  disabled={!editForm.name?.trim() || updateTemplateMutation.isPending}
                  onClick={saveTemplate}
                >
                  {updateTemplateMutation.isPending
                    ? t('common.saving', { defaultValue: 'Saving…' })
                    : t('common.save', { defaultValue: 'Save' })}
                </Button>
                <Button variant="ghost" className="grow" onClick={() => setEditMode(false)}>
                  {t('common.cancel')}
                </Button>
              </>
            ) : (
              <>
                <Button variant="secondary" className="grow" icon={PencilSquareIcon} onClick={() => startEdit(tpl)}>
                  {t('common.edit')}
                </Button>
                <Button
                  variant="danger-ghost"
                  className="grow"
                  icon={TrashIcon}
                  onClick={() => setDeleteTemplateTarget(tpl)}
                >
                  {t('common.delete')}
                </Button>
              </>
            )
          ) : undefined
        }
      >
        {tpl && !editMode && (
          <div className="col" style={{ gap: 18 }}>
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              <Pill tone={tpl.is_active ? 'ok' : 'n'}>
                {tpl.is_active ? t('status.active') : t('status.inactive')}
              </Pill>
              <Tag>{t('governance.questionsCount', { count: tpl.question_count ?? tpl.questions?.length ?? 0 })}</Tag>
              {tpl.frequency && <Tag>{tpl.frequency}</Tag>}
              {(tpl.is_anonymous ?? tpl.allow_anonymous) && (
                <Tag>{t('governance.anonymous', { defaultValue: 'Anonymous' })}</Tag>
              )}
            </div>
            {tpl.description && (
              <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.55 }}>{tpl.description}</p>
            )}
            {(tpl.intro_text ?? tpl.introduction_text) && (
              <div>
                <div className="sec-t" style={{ marginBottom: 6 }}>
                  {t('governance.introText', { defaultValue: 'Introduction' })}
                </div>
                <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.55 }}>
                  {tpl.intro_text ?? tpl.introduction_text}
                </p>
              </div>
            )}
            {tpl.questions && tpl.questions.length > 0 && (
              <div>
                <div className="sec-t" style={{ marginBottom: 8 }}>
                  {t('governance.questions', { defaultValue: 'Questions' })}
                </div>
                <div className="col" style={{ gap: 8 }}>
                  {sortedQuestions.map((q, n) => (
                    <div key={q.id} className="card card-p col" style={{ gap: 8 }}>
                      <div className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
                        <span className="faint mono" style={{ fontSize: 'var(--fs-sm)' }}>{n + 1}</span>
                        <span className="grow" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{questionText(q)}</span>
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
            {tpl.closing_text && (
              <div>
                <div className="sec-t" style={{ marginBottom: 6 }}>
                  {t('governance.closingText', { defaultValue: 'Closing' })}
                </div>
                <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.55 }}>{tpl.closing_text}</p>
              </div>
            )}
          </div>
        )}

        {tpl && editMode && (
          <div className="col" style={{ gap: 18 }}>
            <div className="col" style={{ gap: 14 }}>
              <Field
                label={`${t('governance.name')} *`}
                value={editForm.name || ''}
                autoFocus
                onChange={e => setEditForm({ ...editForm, name: e.target.value })}
              />
              {tpl.survey_type && (
                <div>
                  <label className="lbl">{t('governance.type')}</label>
                  <div className="row" style={{ gap: 8 }}>
                    <Tag>{t(`governance.surveyTypes.${tpl.survey_type}`, { defaultValue: tpl.survey_type })}</Tag>
                    <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
                      {t('governance.typeNotEditable', { defaultValue: 'Type cannot be changed after creation' })}
                    </span>
                  </div>
                </div>
              )}
              <div>
                <label className="lbl">{t('governance.description')}</label>
                <div className="inp" style={{ height: 'auto', padding: '8px 10px' }}>
                  <textarea
                    rows={3}
                    style={{ resize: 'vertical' }}
                    value={editForm.description || ''}
                    onChange={e => setEditForm({ ...editForm, description: e.target.value })}
                  />
                </div>
              </div>
              <Select
                label={t('governance.frequency', { defaultValue: 'Frequency' })}
                value={editForm.frequency || 'quarterly'}
                onChange={e => setEditForm({ ...editForm, frequency: e.target.value as SurveyFrequency })}
                options={FREQUENCIES.map(f => ({
                  value: f,
                  label: t(`governance.frequencies.${f}`, { defaultValue: f.replace(/_/g, ' ') }),
                }))}
              />
              <div>
                <label className="lbl">{t('governance.introText', { defaultValue: 'Introduction' })}</label>
                <div className="inp" style={{ height: 'auto', padding: '8px 10px' }}>
                  <textarea
                    rows={2}
                    style={{ resize: 'vertical' }}
                    value={editForm.introduction_text || ''}
                    onChange={e => setEditForm({ ...editForm, introduction_text: e.target.value })}
                  />
                </div>
              </div>
              <div>
                <label className="lbl">{t('governance.closingText', { defaultValue: 'Closing' })}</label>
                <div className="inp" style={{ height: 'auto', padding: '8px 10px' }}>
                  <textarea
                    rows={2}
                    style={{ resize: 'vertical' }}
                    value={editForm.closing_text || ''}
                    onChange={e => setEditForm({ ...editForm, closing_text: e.target.value })}
                  />
                </div>
              </div>
              <Switch
                checked={editForm.is_active ?? true}
                onChange={checked => setEditForm({ ...editForm, is_active: checked })}
                label={t('status.active')}
              />
            </div>

            {/* Questions editor */}
            <div>
              <div className="row" style={{ marginBottom: 8, gap: 8 }}>
                <div className="sec-t grow">{t('governance.questions', { defaultValue: 'Questions' })}</div>
                <Button size="sm" icon={PlusIcon} onClick={() => setShowAddQuestion(v => !v)}>
                  {t('governance.addQuestion', { defaultValue: 'Add question' })}
                </Button>
              </div>
              {showAddQuestion && (
                <div className="card card-p col" style={{ gap: 10, marginBottom: 8 }}>
                  <Field
                    label={`${t('governance.questionText', { defaultValue: 'Question text' })} *`}
                    value={newQuestion.text}
                    autoFocus
                    onChange={e => setNewQuestion({ ...newQuestion, text: e.target.value })}
                  />
                  <Select
                    label={t('governance.type')}
                    value={newQuestion.question_type}
                    onChange={e => setNewQuestion({ ...newQuestion, question_type: e.target.value as QuestionType })}
                    options={questionTypeOptions}
                  />
                  <div className="row" style={{ gap: 8 }}>
                    <Button
                      size="sm"
                      variant="primary"
                      disabled={!newQuestion.text.trim() || addQuestionMutation.isPending}
                      onClick={() => addQuestionMutation.mutate({
                        templateId: tpl.id,
                        data: { text: newQuestion.text.trim(), question_type: newQuestion.question_type },
                      })}
                    >
                      {t('common.add', { defaultValue: 'Add' })}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setShowAddQuestion(false)}>
                      {t('common.cancel')}
                    </Button>
                  </div>
                </div>
              )}
              {loadingDetail && !tpl.questions ? (
                <div className="row" style={{ justifyContent: 'center', padding: '16px 0' }}>
                  <LoadingSpinner size="sm" />
                </div>
              ) : (
                <div className="col" style={{ gap: 8 }}>
                  {sortedQuestions.map((q, n) =>
                    editingQuestionId === q.id ? (
                      <div key={q.id} className="card card-p col" style={{ gap: 10 }}>
                        <Field
                          label={`${t('governance.questionText', { defaultValue: 'Question text' })} *`}
                          value={questionForm.text || ''}
                          autoFocus
                          onChange={e => setQuestionForm({ ...questionForm, text: e.target.value })}
                        />
                        <Select
                          label={t('governance.type')}
                          value={questionForm.question_type || 'rating'}
                          onChange={e => setQuestionForm({ ...questionForm, question_type: e.target.value as QuestionType })}
                          options={questionTypeOptions}
                        />
                        <Checkbox
                          checked={questionForm.is_required ?? true}
                          onChange={checked => setQuestionForm({ ...questionForm, is_required: checked })}
                          label={t('governance.required', { defaultValue: 'Required' })}
                        />
                        <div className="row" style={{ gap: 8 }}>
                          <Button
                            size="sm"
                            variant="primary"
                            disabled={!questionForm.text?.trim() || updateQuestionMutation.isPending}
                            onClick={saveQuestion}
                          >
                            {t('common.save', { defaultValue: 'Save' })}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setEditingQuestionId(null)}>
                            {t('common.cancel')}
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div key={q.id} className="card card-p col" style={{ gap: 8 }}>
                        <div className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
                          <span className="faint mono" style={{ fontSize: 'var(--fs-sm)' }}>{n + 1}</span>
                          <span className="grow" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{questionText(q)}</span>
                          <IconButton
                            size="sm"
                            icon={PencilSquareIcon}
                            label={t('common.edit')}
                            onClick={() => startEditQuestion(q)}
                          />
                          <IconButton
                            size="sm"
                            icon={TrashIcon}
                            label={t('common.delete')}
                            onClick={() => setDeleteQuestionTarget(q)}
                          />
                        </div>
                        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                          <Tag>{q.question_type}</Tag>
                          {q.kpi_id && <Tag>{t('governance.linkedToKpi', { defaultValue: 'Linked to KPI' })}</Tag>}
                        </div>
                      </div>
                    )
                  )}
                  {sortedQuestions.length === 0 && !showAddQuestion && (
                    <p className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
                      {t('governance.noQuestionsYet', { defaultValue: 'No questions yet — add the first one.' })}
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </Drawer>

      {/* Delete-template confirmation (backend soft delete: deactivation) */}
      {deleteTemplateTarget && (
        <ConfirmDialog
          open
          title={t('governance.deleteTemplate', { defaultValue: 'Delete template' })}
          body={t('governance.deleteTemplatePrompt', {
            defaultValue: 'Delete "{{name}}"? This deactivates the template (soft delete).',
            name: deleteTemplateTarget.name,
          })}
          affected={[
            t('governance.deleteTemplateAffected', {
              defaultValue: 'The template is deactivated: it disappears from this list and can no longer be used for new surveys',
            }),
          ]}
          safe={[
            t('governance.deleteTemplateSafe', {
              defaultValue: 'Surveys already created from it and their responses — they keep working',
            }),
          ]}
          confirmLabel={deleteTemplateMutation.isPending ? t('common.deleting') : t('common.delete')}
          cancelLabel={t('common.cancel')}
          onCancel={() => { if (!deleteTemplateMutation.isPending) setDeleteTemplateTarget(null) }}
          onConfirm={() => { if (!deleteTemplateMutation.isPending) deleteTemplateMutation.mutate(deleteTemplateTarget.id) }}
        />
      )}

      {/* Delete-question confirmation */}
      {deleteQuestionTarget && tpl && (
        <ConfirmDialog
          open
          title={t('governance.deleteQuestion', { defaultValue: 'Delete question' })}
          body={questionText(deleteQuestionTarget)}
          affected={[
            t('governance.deleteQuestionAffected', {
              defaultValue: 'The question is removed from this template and will not appear in new surveys',
            }),
          ]}
          safe={[
            t('governance.deleteQuestionSafe', {
              defaultValue: 'Answers already collected in submitted responses',
            }),
          ]}
          confirmLabel={deleteQuestionMutation.isPending ? t('common.deleting') : t('common.delete')}
          cancelLabel={t('common.cancel')}
          onCancel={() => { if (!deleteQuestionMutation.isPending) setDeleteQuestionTarget(null) }}
          onConfirm={() => {
            if (!deleteQuestionMutation.isPending) {
              deleteQuestionMutation.mutate({ templateId: tpl.id, questionId: deleteQuestionTarget.id })
            }
          }}
        />
      )}

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
          {templates.length === 0 && (
            <div className="banner banner-in" style={{ flexDirection: 'column', gap: 10, alignItems: 'flex-start' }}>
              <span>
                {t('governance.templateRequiredBanner', {
                  defaultValue: 'A survey needs a template, and there are none yet. Create a template first, then come back to send a survey.',
                })}
              </span>
              <Button
                size="sm"
                variant="secondary"
                icon={SquaresPlusIcon}
                onClick={() => {
                  setShowCreateInstance(false)
                  setTab('templates')
                  setShowCreateTemplate(true)
                }}
              >
                {t('governance.newTemplate')}
              </Button>
            </div>
          )}
          <Select
            label={`${t('governance.template')} *`}
            value={instanceForm.template_id || ''}
            disabled={templates.length === 0}
            hint={templates.length === 0
              ? t('governance.templateRequiredHint', { defaultValue: 'Disabled — no survey templates exist yet.' })
              : undefined}
            onChange={e => setInstanceForm({ ...instanceForm, template_id: e.target.value })}
            options={[
              {
                value: '',
                label: templates.length === 0
                  ? t('governance.noTemplatesYet', { defaultValue: 'No templates available' })
                  : t('governance.selectTemplate'),
              },
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
