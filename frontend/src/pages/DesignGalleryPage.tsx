/* Dev-only gallery of the Direction B primitives (eval-redesign Phase 1).
   Mounted at /design in dev builds; removed in Phase 7. */
import { useState } from 'react'
import {
  ArrowUpTrayIcon, BuildingOffice2Icon, DocumentTextIcon, FunnelIcon,
  MagnifyingGlassIcon, MoonIcon, PencilSquareIcon, PlusIcon, SunIcon, TrashIcon,
} from '@heroicons/react/24/outline'
import {
  AiTag, Avatar, Bar, Button, Checkbox, Chip, Confidence, ConfirmDialog, DropdownMenu,
  Drawer, EmptyState, Field, IconButton, Pill, Select, Stat, Switch, Table, Tabs, Tag,
  Tooltip, useToast,
} from '@/components/ui'
import { useTheme } from '@/contexts/ThemeContext'

interface DemoRow {
  id: string
  name: string
  counterparty: string
  status: string
  value: number
  confidence: number | null
}

const DEMO_ROWS: DemoRow[] = [
  { id: 'CT-2041', name: 'Master services agreement', counterparty: 'Northwind GmbH', status: 'Active', value: 480000, confidence: 0.97 },
  { id: 'CT-2042', name: 'Cloud hosting order form', counterparty: 'Contoso SAS', status: 'Renewal due', value: 120000, confidence: 0.82 },
  { id: 'CT-2043', name: 'Data processing agreement', counterparty: 'Fabrikam BV', status: 'In review', value: 0, confidence: 0.41 },
  { id: 'CT-2044', name: 'NDA — mutual', counterparty: 'Litware Ltd', status: 'Lapsed', value: 0, confidence: null },
]

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="col" style={{ gap: 12 }}>
      <div className="sec-t">{title}</div>
      <div className="row" style={{ gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>{children}</div>
    </section>
  )
}

export default function DesignGalleryPage() {
  const { theme, toggle } = useTheme()
  const { toast } = useToast()
  const [tab, setTab] = useState('all')
  const [chipOn, setChipOn] = useState(true)
  const [checked, setChecked] = useState(true)
  const [switched, setSwitched] = useState(true)
  const [menuOpen, setMenuOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)

  return (
    <div className="scroll" style={{ height: '100vh', background: 'var(--pg)' }}>
      <div className="col" style={{ maxWidth: 1040, margin: '0 auto', padding: 32, gap: 32 }}>
        <div className="row">
          <div className="grow">
            <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>Design gallery</h1>
            <p className="muted">Direction B primitives — dev-only route, removed in Phase 7.</p>
          </div>
          <IconButton icon={theme === 'dark' ? SunIcon : MoonIcon} label="Toggle theme" onClick={toggle} />
        </div>

        <Section title="Buttons">
          <Button variant="primary" icon={PlusIcon}>New contract</Button>
          <Button variant="secondary" icon={ArrowUpTrayIcon}>Upload</Button>
          <Button variant="ghost">Cancel</Button>
          <Button variant="danger" icon={TrashIcon}>Delete</Button>
          <Button variant="danger-ghost">Remove link</Button>
          <Button variant="primary" size="sm">Small</Button>
          <Button variant="secondary" size="lg">Large</Button>
          <Button variant="primary" disabled>Disabled</Button>
          <IconButton icon={PencilSquareIcon} label="Edit" />
          <IconButton icon={FunnelIcon} label="Filter" active />
        </Section>

        <Section title="Pills, tags & chips">
          <Pill>Active</Pill>
          <Pill>Renewal due</Pill>
          <Pill>Breached</Pill>
          <Pill>In review</Pill>
          <Pill>Open</Pill>
          <Pill tone="n" dot={false}>Draft</Pill>
          <Tag icon={BuildingOffice2Icon}>EMEA</Tag>
          <Tag>MSA</Tag>
          <AiTag />
          <AiTag>AI extracted</AiTag>
          <Chip on={chipOn} icon={FunnelIcon} onClick={() => setChipOn(!chipOn)}>High risk</Chip>
          <Chip onClick={() => toast({ text: 'Chip clicked' })}>Expiring soon</Chip>
        </Section>

        <Section title="Confidence & bars">
          <Confidence value={0.97} />
          <Confidence value={0.82} />
          <Confidence value={0.41} />
          <Confidence value={null} />
          <Bar value={65} width={120} />
        </Section>

        <Section title="Form controls">
          <Field label="Search" icon={MagnifyingGlassIcon} placeholder="Search contracts…" containerStyle={{ width: 240 }} />
          <Field label="With error" error="Required field" placeholder="Contract name" containerStyle={{ width: 200 }} />
          <Select
            label="Status"
            options={[
              { value: 'all', label: 'All statuses' },
              { value: 'active', label: 'Active' },
              { value: 'lapsed', label: 'Lapsed' },
            ]}
            containerStyle={{ width: 180 }}
          />
          <Checkbox checked={checked} onChange={setChecked} label="Include archived" />
          <Checkbox mixed label="Some selected" />
          <Switch checked={switched} onChange={setSwitched} label="Auto-renew alerts" />
        </Section>

        <Section title="Tabs">
          <Tabs
            tabs={[
              { value: 'all', label: 'All', count: 128, icon: DocumentTextIcon },
              { value: 'active', label: 'Active', count: 96 },
              { value: 'review', label: 'In review', count: 12 },
            ]}
            value={tab}
            onChange={setTab}
            style={{ width: '100%' }}
          />
        </Section>

        <Section title="Stats">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: 12, width: '100%' }}>
            <Stat icon={DocumentTextIcon} label="Contracts" value="128" sub="+12 this month" />
            <Stat label="Renewal due" value="7" sub="3 within 30 days" subTone="var(--wa)" active />
            <Stat label="Open obligations" value="23" sub="4 overdue" subTone="var(--da)" onClick={() => toast({ text: 'Stat clicked' })} />
          </div>
        </Section>

        <Section title="Tooltips & menus">
          <Tooltip label="Plain tooltip">
            <Button variant="secondary">Hover me</Button>
          </Tooltip>
          <Tooltip
            rich
            subhead="Provenance"
            label="Extracted from §4.2 'Term and termination', page 12. Model: gpt-4o."
            footer="conf 0.94 · reviewed by legal"
          >
            <span style={{ borderBottom: '1px dashed var(--b2)', cursor: 'help' }}>Rich provenance</span>
          </Tooltip>
          <span style={{ position: 'relative' }}>
            <Button variant="secondary" onClick={() => setMenuOpen(!menuOpen)}>Menu</Button>
            {menuOpen && (
              <DropdownMenu
                items={[
                  { value: 'edit', label: 'Edit', icon: PencilSquareIcon, kb: 'E' },
                  { value: 'export', label: 'Export' },
                  { sep: true },
                  { value: 'delete', label: 'Delete', icon: TrashIcon, danger: true },
                ]}
                onSelect={(v) => toast({ text: `Selected ${v}` })}
                onClose={() => setMenuOpen(false)}
                align="left"
              />
            )}
          </span>
        </Section>

        <Section title="Overlays">
          <Button variant="danger" onClick={() => setConfirmOpen(true)}>Open confirm</Button>
          <Button variant="secondary" onClick={() => setDrawerOpen(true)}>Open drawer</Button>
          <Button variant="ghost" onClick={() => toast({ text: 'Contract linked', action: { label: 'Undo', run: () => toast({ text: 'Undone', error: true }) } })}>
            Show toast
          </Button>
        </Section>

        <Section title="Table">
          <Table<DemoRow>
            columns={[
              { key: 'id', header: 'ID', nowrap: true, render: (r) => <span className="mono">{r.id}</span>, sortable: true, sortValue: (r) => r.id },
              { key: 'name', header: 'Contract', sortable: true },
              { key: 'counterparty', header: 'Counterparty', sortable: true },
              { key: 'status', header: 'Status', render: (r) => <Pill>{r.status}</Pill> },
              { key: 'value', header: 'Value', align: 'right', sortable: true, sortValue: (r) => r.value, render: (r) => (r.value ? `€${r.value.toLocaleString()}` : '—') },
              { key: 'confidence', header: 'Confidence', render: (r) => <Confidence value={r.confidence} /> },
            ]}
            rows={DEMO_ROWS}
            rowKey={(r) => r.id}
            selectedKey={selected}
            onRowClick={(r) => setSelected(r.id)}
            className="grow"
          />
        </Section>

        <Section title="Empty state">
          <div className="card grow">
            <EmptyState
              icon={DocumentTextIcon}
              title="No contracts yet"
              body="Upload your first contract and the AI pipeline will extract metadata, clauses, obligations and risks."
              action={<Button variant="primary" icon={ArrowUpTrayIcon}>Upload contract</Button>}
            />
          </div>
        </Section>

        <ConfirmDialog
          open={confirmOpen}
          title="Delete contract CT-2041?"
          body="This permanently removes the contract record from this workspace."
          affected={['Extracted metadata, clauses and obligations', 'Links to 2 child contracts (children are kept)']}
          safe={['The uploaded source document in storage', 'Audit history']}
          onConfirm={() => { setConfirmOpen(false); toast({ text: 'Deleted CT-2041' }) }}
          onCancel={() => setConfirmOpen(false)}
        />
        <Drawer
          open={drawerOpen}
          title="Master services agreement"
          sub="CT-2041 · Northwind GmbH"
          onClose={() => setDrawerOpen(false)}
          footer={<><span className="grow" /><Button variant="ghost" onClick={() => setDrawerOpen(false)}>Close</Button><Button variant="primary">Save</Button></>}
        >
          <div className="col" style={{ gap: 14 }}>
            <Field label="Contract name" defaultValue="Master services agreement" />
            <Select label="Status" options={[{ value: 'active', label: 'Active' }, { value: 'lapsed', label: 'Lapsed' }]} />
            <div>
              <label className="lbl">Extraction confidence</label>
              <Confidence value={0.97} width={80} />
            </div>
            <div className="row"><Avatar name="Marie Dubois" /> <span>Marie Dubois — owner</span></div>
          </div>
        </Drawer>
      </div>
    </div>
  )
}
