import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ClipboardDocumentListIcon,
  PlusIcon,
  XMarkIcon,
  PaperAirplaneIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type {
  SurveyTemplateCreate,
  SurveyInstanceCreate,
  SurveyType,
  SurveyInstanceStatus,
} from '@/types/governance'

const STATUS_COLORS: Record<SurveyInstanceStatus, string> = {
  draft: 'bg-gray-100 text-gray-700',
  scheduled: 'bg-blue-100 text-blue-700',
  sent: 'bg-indigo-100 text-indigo-700',
  in_progress: 'bg-yellow-100 text-yellow-700',
  completed: 'bg-green-100 text-green-700',
  expired: 'bg-orange-100 text-orange-700',
  cancelled: 'bg-gray-200 text-gray-500',
}

export default function SurveysPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<'templates' | 'instances'>('instances')
  const [showCreateTemplate, setShowCreateTemplate] = useState(false)
  const [showCreateInstance, setShowCreateInstance] = useState(false)
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
    },
  })

  const createInstanceMutation = useMutation({
    mutationFn: (data: SurveyInstanceCreate) => api.createSurveyInstance(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['survey-instances'] })
      setShowCreateInstance(false)
      setInstanceForm({})
    },
  })

  const sendMutation = useMutation({
    mutationFn: (id: string) => api.sendSurvey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['survey-instances'] })
    },
  })

  const isLoading = loadingTemplates || loadingInstances

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{t('nav.surveys')}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {t('governance.surveysSubtitle')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {tab === 'templates' && (
            <button
              onClick={() => setShowCreateTemplate(true)}
              className="btn-primary flex items-center gap-2"
            >
              <PlusIcon className="h-4 w-4" />
              {t('governance.newTemplate')}
            </button>
          )}
          {tab === 'instances' && (
            <button
              onClick={() => setShowCreateInstance(true)}
              className="btn-primary flex items-center gap-2"
            >
              <PlusIcon className="h-4 w-4" />
              {t('governance.newSurvey')}
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-6">
          <button
            onClick={() => setTab('instances')}
            className={cn(
              'pb-3 text-sm font-medium border-b-2 transition-colors',
              tab === 'instances'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            )}
          >
            {t('governance.surveyInstancesCount', { count: instances.length })}
          </button>
          <button
            onClick={() => setTab('templates')}
            className={cn(
              'pb-3 text-sm font-medium border-b-2 transition-colors',
              tab === 'templates'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            )}
          >
            {t('governance.templatesCount', { count: templates.length })}
          </button>
        </nav>
      </div>

      {/* Instances Tab */}
      {tab === 'instances' && (
        <div className="space-y-3">
          {instances.map((instance) => (
            <div key={instance.id} className="card card-body">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <ClipboardDocumentListIcon className="h-5 w-5 text-primary-500" />
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{instance.template_name || instance.title || instance.period || t('governance.untitledSurvey')}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={cn(
                        'px-2 py-0.5 rounded text-xs font-medium',
                        STATUS_COLORS[instance.status]
                      )}>
                        {t(`governance.surveyStatus.${instance.status}`, { defaultValue: instance.status })}
                      </span>
                      {instance.due_date && (
                        <span className="text-xs text-gray-400">
                          {t('governance.dueOn', { date: new Date(instance.due_date).toLocaleDateString() })}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {instance.status === 'draft' && (
                    <button
                      onClick={() => sendMutation.mutate(instance.id)}
                      disabled={sendMutation.isPending}
                      className="btn-secondary flex items-center gap-1 text-xs"
                    >
                      <PaperAirplaneIcon className="h-3.5 w-3.5" />
                      {t('governance.send')}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}

          {instances.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              <ClipboardDocumentListIcon className="h-12 w-12 mx-auto mb-3 text-gray-300" />
              <p className="text-sm">{t('governance.noSurveyInstances')}</p>
            </div>
          )}
        </div>
      )}

      {/* Templates Tab */}
      {tab === 'templates' && (
        <div className="space-y-3">
          {templates.map((tmpl) => (
            <div key={tmpl.id} className="card card-body">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <ClipboardDocumentListIcon className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{tmpl.name}</p>
                    {tmpl.description && (
                      <p className="text-xs text-gray-500 mt-0.5">{tmpl.description}</p>
                    )}
                    <div className="flex items-center gap-2 mt-1">
                      <span className="px-2 py-0.5 rounded text-xs font-medium bg-primary-100 text-primary-700 capitalize">
                        {t(`governance.surveyTypes.${tmpl.survey_type}`, { defaultValue: tmpl.survey_type })}
                      </span>
                      <span className="text-xs text-gray-400">
                        {t('governance.questionsCount', { count: tmpl.question_count ?? tmpl.questions?.length ?? 0 })}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}

          {templates.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              <ClipboardDocumentListIcon className="h-12 w-12 mx-auto mb-3 text-gray-300" />
              <p className="text-sm">{t('governance.noSurveyTemplates')}</p>
            </div>
          )}
        </div>
      )}

      {/* Create Template Modal */}
      {showCreateTemplate && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">{t('governance.newSurveyTemplate')}</h2>
              <button onClick={() => setShowCreateTemplate(false)} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.name')} *</label>
                <input
                  type="text"
                  value={templateForm.name || ''}
                  onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.type')}</label>
                <select
                  value={templateForm.survey_type || 'satisfaction'}
                  onChange={(e) => setTemplateForm({ ...templateForm, survey_type: e.target.value as SurveyType })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                >
                  <option value="satisfaction">{t('governance.surveyTypes.satisfaction')}</option>
                  <option value="performance">{t('governance.surveyTypes.performance')}</option>
                  <option value="relationship">{t('governance.surveyTypes.relationship')}</option>
                  <option value="custom">{t('governance.surveyTypes.custom')}</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.description')}</label>
                <textarea
                  value={templateForm.description || ''}
                  onChange={(e) => setTemplateForm({ ...templateForm, description: e.target.value })}
                  rows={2}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowCreateTemplate(false)} className="btn-secondary">{t('common.cancel')}</button>
              <button
                onClick={() => {
                  if (!templateForm.name) return
                  createTemplateMutation.mutate(templateForm as SurveyTemplateCreate)
                }}
                disabled={!templateForm.name || createTemplateMutation.isPending}
                className="btn-primary"
              >
                {createTemplateMutation.isPending ? t('governance.creating') : t('governance.create')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Instance Modal */}
      {showCreateInstance && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">{t('governance.newSurveyInstance')}</h2>
              <button onClick={() => setShowCreateInstance(false)} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.template')} *</label>
                <select
                  value={instanceForm.template_id || ''}
                  onChange={(e) => setInstanceForm({ ...instanceForm, template_id: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                >
                  <option value="">{t('governance.selectTemplate')}</option>
                  {templates.map((tmpl) => (
                    <option key={tmpl.id} value={tmpl.id}>{tmpl.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.relationship')} *</label>
                <select
                  value={instanceForm.relationship_id || ''}
                  onChange={(e) => setInstanceForm({ ...instanceForm, relationship_id: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                >
                  <option value="">{t('governance.selectRelationship')}</option>
                  {relationships.map((rel) => (
                    <option key={rel.id} value={rel.id}>
                      {rel.org_a?.name || rel.org_a_id} ↔ {rel.org_b?.name || rel.org_b_id}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.period')} *</label>
                <input
                  type="text"
                  value={instanceForm.period || ''}
                  onChange={(e) => setInstanceForm({ ...instanceForm, period: e.target.value })}
                  placeholder={t('governance.periodPlaceholder')}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.dueDate')}</label>
                <input
                  type="date"
                  value={instanceForm.due_date || ''}
                  onChange={(e) => setInstanceForm({ ...instanceForm, due_date: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowCreateInstance(false)} className="btn-secondary">{t('common.cancel')}</button>
              <button
                onClick={() => {
                  if (!instanceForm.template_id || !instanceForm.relationship_id || !instanceForm.period) return
                  createInstanceMutation.mutate(instanceForm as SurveyInstanceCreate)
                }}
                disabled={!instanceForm.template_id || !instanceForm.relationship_id || !instanceForm.period || createInstanceMutation.isPending}
                className="btn-primary"
              >
                {createInstanceMutation.isPending ? t('governance.creating') : t('governance.create')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
