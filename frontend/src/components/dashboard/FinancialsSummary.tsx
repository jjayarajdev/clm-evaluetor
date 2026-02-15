import { useQuery } from '@tanstack/react-query'
import {
  BanknotesIcon,
  CurrencyDollarIcon,
  ReceiptPercentIcon,
  ExclamationTriangleIcon,
  CalendarIcon,
} from '@heroicons/react/24/outline'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'

const FEE_TYPE_LABELS: Record<string, string> = {
  base_fee: 'Base Fee',
  per_unit: 'Per Unit',
  per_hour: 'Hourly',
  per_day: 'Daily',
  percentage: 'Percentage',
  milestone: 'Milestone',
  recurring_monthly: 'Monthly',
  recurring_annual: 'Annual',
  one_time: 'One-Time',
  retainer: 'Retainer',
  success_fee: 'Success Fee',
  licensing_fee: 'Licensing',
  maintenance_fee: 'Maintenance',
  support_fee: 'Support',
  other: 'Other',
}

const FEE_TYPE_COLORS: Record<string, string> = {
  base_fee: 'bg-blue-100 text-blue-800',
  per_unit: 'bg-green-100 text-green-800',
  per_hour: 'bg-purple-100 text-purple-800',
  recurring_monthly: 'bg-amber-100 text-amber-800',
  recurring_annual: 'bg-orange-100 text-orange-800',
  one_time: 'bg-cyan-100 text-cyan-800',
  milestone: 'bg-indigo-100 text-indigo-800',
  other: 'bg-gray-100 text-gray-800',
}

const PENALTY_TYPE_LABELS: Record<string, string> = {
  late_payment: 'Late Payment',
  late_delivery: 'Late Delivery',
  non_compliance: 'Non-Compliance',
  breach: 'Breach',
  early_termination: 'Early Termination',
  sla_violation: 'SLA Violation',
  quality_failure: 'Quality Failure',
  other: 'Other',
}

interface Financial {
  id: string
  fee_type: string
  fee_description: string | null
  fee_amount: number | null
  currency: string
  quantity: number | null
  unit_price: number | null
  payment_terms: string | null
  payment_terms_days: number | null
  invoicing_frequency: string | null
  is_penalty: boolean
  penalty_type: string | null
  penalty_trigger: string | null
  penalty_amount: number | null
  penalty_percentage: number | null
  section_reference: string | null
}

interface FinancialsResponse {
  financials: Financial[]
  total_value: number
  currency: string
  by_fee_type: Record<string, number>
  penalties: Financial[]
  total_penalties: number
}

interface Props {
  contractId: string
}

function formatCurrency(amount: number | null, currency: string = 'USD'): string {
  if (amount === null) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount)
}

export default function FinancialsSummary({ contractId }: Props) {
  const { data, isLoading, error } = useQuery<FinancialsResponse>({
    queryKey: ['financials', contractId],
    queryFn: async () => {
      const response = await fetch(`/api/dashboard/financials/${contractId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })
      if (!response.ok) throw new Error('Failed to fetch financials')
      return response.json()
    },
    enabled: !!contractId,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <LoadingSpinner size="md" />
      </div>
    )
  }

  if (error || !data || data.financials.length === 0) {
    return (
      <div className="card">
        <div className="card-body text-center py-8">
          <BanknotesIcon className="h-12 w-12 text-gray-300 mx-auto mb-3" />
          <p className="text-sm text-gray-500">
            No financial terms extracted yet. Run analysis to extract fees and payment terms.
          </p>
        </div>
      </div>
    )
  }

  const fees = data.financials.filter(f => !f.is_penalty)
  const penalties = data.financials.filter(f => f.is_penalty)

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Total Contract Value */}
        <div className="card">
          <div className="card-body">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-green-100 rounded-lg">
                <CurrencyDollarIcon className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Total Value</p>
                <p className="text-2xl font-bold text-gray-900">
                  {formatCurrency(data.total_value, data.currency)}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Fee Items Count */}
        <div className="card">
          <div className="card-body">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-blue-100 rounded-lg">
                <ReceiptPercentIcon className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Fee Items</p>
                <p className="text-2xl font-bold text-gray-900">{fees.length}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Penalties */}
        <div className="card">
          <div className="card-body">
            <div className="flex items-center gap-3">
              <div className={cn(
                "p-3 rounded-lg",
                penalties.length > 0 ? "bg-red-100" : "bg-gray-100"
              )}>
                <ExclamationTriangleIcon className={cn(
                  "h-6 w-6",
                  penalties.length > 0 ? "text-red-600" : "text-gray-400"
                )} />
              </div>
              <div>
                <p className="text-sm text-gray-500">Penalties</p>
                <p className="text-2xl font-bold text-gray-900">
                  {penalties.length > 0 ? formatCurrency(data.total_penalties, data.currency) : 'None'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Fee Breakdown */}
      <div className="card">
        <div className="card-header">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <BanknotesIcon className="h-5 w-5 text-primary-600" />
            Fee Structure
          </h3>
        </div>
        <div className="card-body p-0">
          <div className="divide-y divide-gray-100">
            {fees.map((fee) => (
              <div key={fee.id} className="p-4 hover:bg-gray-50">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={cn(
                        "text-xs px-2 py-0.5 rounded-full",
                        FEE_TYPE_COLORS[fee.fee_type] || FEE_TYPE_COLORS.other
                      )}>
                        {FEE_TYPE_LABELS[fee.fee_type] || fee.fee_type}
                      </span>
                      {fee.section_reference && (
                        <span className="text-xs text-gray-400">
                          Section {fee.section_reference}
                        </span>
                      )}
                    </div>
                    {fee.fee_description && (
                      <p className="text-sm text-gray-700 mb-2">
                        {fee.fee_description}
                      </p>
                    )}
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      {fee.quantity && fee.unit_price && (
                        <span>
                          {fee.quantity} x {formatCurrency(fee.unit_price, fee.currency)}
                        </span>
                      )}
                      {fee.payment_terms && (
                        <span className="flex items-center gap-1">
                          <CalendarIcon className="h-3.5 w-3.5" />
                          {fee.payment_terms.replace('_', ' ')}
                          {fee.payment_terms_days && ` (${fee.payment_terms_days} days)`}
                        </span>
                      )}
                      {fee.invoicing_frequency && (
                        <span>Invoiced: {fee.invoicing_frequency}</span>
                      )}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-lg font-semibold text-gray-900">
                      {formatCurrency(fee.fee_amount, fee.currency)}
                    </p>
                    <p className="text-xs text-gray-500">{fee.currency}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Penalties */}
      {penalties.length > 0 && (
        <div className="card border-red-200">
          <div className="card-header bg-red-50">
            <h3 className="text-lg font-semibold text-red-900 flex items-center gap-2">
              <ExclamationTriangleIcon className="h-5 w-5 text-red-600" />
              Penalties & Late Fees
            </h3>
          </div>
          <div className="card-body p-0">
            <div className="divide-y divide-gray-100">
              {penalties.map((penalty) => (
                <div key={penalty.id} className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-800">
                          {PENALTY_TYPE_LABELS[penalty.penalty_type || 'other'] || penalty.penalty_type}
                        </span>
                      </div>
                      {penalty.penalty_trigger && (
                        <p className="text-sm text-gray-700">
                          <span className="font-medium">Trigger:</span> {penalty.penalty_trigger}
                        </p>
                      )}
                    </div>
                    <div className="text-right shrink-0">
                      {penalty.penalty_amount && (
                        <p className="text-lg font-semibold text-red-700">
                          {formatCurrency(penalty.penalty_amount, penalty.currency)}
                        </p>
                      )}
                      {penalty.penalty_percentage && (
                        <p className="text-lg font-semibold text-red-700">
                          {penalty.penalty_percentage}%
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
