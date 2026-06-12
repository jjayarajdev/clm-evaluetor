import React, { useEffect, useRef, useState, useMemo } from 'react'
import * as d3 from 'd3'
import { useQuery } from '@tanstack/react-query'
import {
  InformationCircleIcon,
  ExclamationTriangleIcon,
  MagnifyingGlassIcon,
  ArrowPathIcon,
  Square3Stack3DIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'

interface KGNode extends d3.SimulationNodeDatum {
  id: string
  name: string
  type: string
  color: string
  properties: any
  confidence: number
}

interface KGLink extends d3.SimulationLinkDatum<KGNode> {
  id: string
  source: string | KGNode
  target: string | KGNode
  type: string
}

const TYPE_COLORS: Record<string, string> = {
  party: '#8b9cf7',        // Indigo
  clause: '#f472b6',       // Pink
  obligation: '#fbbf24',   // Amber
  term: '#10b981',         // Emerald
  date: '#3b82f6',         // Blue
  amount: '#f87171',       // Red
  jurisdiction: '#a78bfa', // Violet
  sla_metric: '#2dd4bf',   // Teal
}

export default function KnowledgeGraphTab({ contractId, tenantId }: { contractId: string, tenantId: string }) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [selectedNode, setSelectedNode] = useState<any>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterTypes, setFilterTypes] = useState<string[]>([])

  const { data: graph, isLoading, error, refetch } = useQuery({
    queryKey: ['contract-graph', contractId],
    queryFn: () => api.getContractGraph(contractId),
    enabled: !!contractId,
  })

  // Inconsistencies from contract metadata
  const { data: contract } = useQuery({
    queryKey: ['contract', contractId],
    queryFn: () => api.getContract(contractId),
    enabled: !!contractId,
  })

  const inconsistencies = useMemo(() => {
    return (contract?.schema_data as any)?._graph_inconsistencies || []
  }, [contract])

  useEffect(() => {
    if (!graph || !svgRef.current) return

    const width = svgRef.current.clientWidth || 800
    const height = 500
    
    // Clear previous graph
    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3.select(svgRef.current)
      .attr('viewBox', [0, 0, width, height])
      .attr('style', 'max-width: 100%; height: auto;')

    const g = svg.append('g')

    // Add zoom behavior
    svg.call(d3.zoom<SVGSVGElement, unknown>()
      .extent([[0, 0], [width, height]])
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      }))

    const nodes: KGNode[] = graph.entities.map((e: any) => ({
      id: e.id,
      name: e.name,
      type: e.entity_type,
      color: TYPE_COLORS[e.entity_type] || '#94a3b8',
      properties: e.properties,
      confidence: e.confidence,
    }))

    const links: KGLink[] = graph.relationships.map((r: any) => ({
      id: r.id,
      source: r.source_entity_id,
      target: r.target_entity_id,
      type: r.relationship_type,
    }))

    // Filter by type if needed
    let filteredNodes = nodes
    if (filterTypes.length > 0) {
      filteredNodes = nodes.filter(n => filterTypes.includes(n.type))
    }

    // Filter by search
    if (searchTerm) {
      filteredNodes = filteredNodes.filter(n => 
        n.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        n.type.toLowerCase().includes(searchTerm.toLowerCase())
      )
    }

    const filteredNodeIds = new Set(filteredNodes.map(n => n.id))
    const filteredLinks = links.filter(l => 
      filteredNodeIds.has(typeof l.source === 'string' ? l.source : (l.source as KGNode).id) &&
      filteredNodeIds.has(typeof l.target === 'string' ? l.target : (l.target as KGNode).id)
    )

    const simulation = d3.forceSimulation<KGNode>(filteredNodes)
      .force('link', d3.forceLink<KGNode, KGLink>(filteredLinks).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('x', d3.forceX(width / 2).strength(0.1))
      .force('y', d3.forceY(height / 2).strength(0.1))

    // Define arrow markers for relationships
    svg.append('defs').selectAll('marker')
      .data(['arrow'])
      .enter().append('marker')
      .attr('id', d => d)
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('fill', '#94a3b8')
      .attr('d', 'M0,-5L10,0L0,5')

    const link = g.append('g')
      .selectAll('line')
      .data(filteredLinks)
      .join('line')
      .attr('stroke', '#334155')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', 1.5)
      .attr('marker-end', 'url(#arrow)')

    const node = g.append('g')
      .selectAll('.node')
      .data(filteredNodes)
      .join('g')
      .attr('class', 'node')
      .call(d3.drag<SVGGElement, KGNode>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended) as any)
      .on('click', (event, d) => {
        setSelectedNode(d)
        event.stopPropagation()
      })

    node.append('circle')
      .attr('r', 8)
      .attr('fill', d => d.color)
      .attr('stroke', '#1e293b')
      .attr('stroke-width', 1.5)

    node.append('text')
      .attr('dy', 20)
      .attr('text-anchor', 'middle')
      .attr('fill', '#94a3b8')
      .style('font-size', '10px')
      .style('pointer-events', 'none')
      .text(d => d.name.length > 20 ? d.name.substring(0, 17) + '...' : d.name)

    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as any).x)
        .attr('y1', d => (d.source as any).y)
        .attr('x2', d => (d.target as any).x)
        .attr('y2', d => (d.target as any).y)

      node
        .attr('transform', d => `translate(${d.x},${d.y})`)
    })

    function dragstarted(event: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart()
      event.subject.fx = event.subject.x
      event.subject.fy = event.subject.y
    }

    function dragged(event: any) {
      event.subject.fx = event.x
      event.subject.fy = event.y
    }

    function dragended(event: any) {
      if (!event.active) simulation.alphaTarget(0)
      event.subject.fx = null
      event.subject.fy = null
    }

    return () => {
      simulation.stop()
    }
  }, [graph, searchTerm, filterTypes])

  if (isLoading) return <LoadingSpinner />
  if (error) return (
    <div className="p-8 text-center">
      <ExclamationTriangleIcon className="h-12 w-12 text-red-500 mx-auto mb-4" />
      <h3 className="text-lg font-medium text-gray-900">Failed to load Knowledge Graph</h3>
      <p className="text-gray-500 mt-2">There was an error retrieving the graph data for this contract.</p>
      <button 
        onClick={() => refetch()}
        className="btn-primary mt-4"
      >
        <ArrowPathIcon className="h-4 w-4 mr-2" />
        Retry
      </button>
    </div>
  )

  const hasGraphData = graph && graph.entities && graph.entities.length > 0

  return (
    <div className="flex flex-col h-[700px] bg-gray-50 rounded-lg overflow-hidden border border-gray-200">
      {/* Toolbar */}
      <div className="bg-white border-bottom border-gray-200 p-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 flex-1">
          <div className="relative flex-1 max-w-xs">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search entities..."
              className="pl-9 pr-4 py-2 bg-gray-50 border border-gray-300 rounded-md w-full text-sm focus:ring-indigo-500 focus:border-indigo-500"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          
          <div className="flex gap-1 overflow-x-auto pb-1 no-scrollbar">
            {Object.keys(TYPE_COLORS).map(type => (
              <button
                key={type}
                onClick={() => {
                  setFilterTypes(prev => 
                    prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
                  )
                }}
                className={cn(
                  "px-3 py-1 rounded-full text-xs font-medium border transition-colors whitespace-nowrap",
                  filterTypes.includes(type)
                    ? "bg-indigo-100 text-indigo-700 border-indigo-200"
                    : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                )}
              >
                {type.charAt(0).toUpperCase() + type.slice(1).replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button 
            onClick={() => refetch()}
            className="p-2 text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-full transition-colors"
            title="Refresh Graph"
          >
            <ArrowPathIcon className="h-5 w-5" />
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Main Graph Area */}
        <div className="flex-1 relative bg-[#0f172a] overflow-hidden">
          {!hasGraphData ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-400 p-8 text-center">
              <Square3Stack3DIcon className="h-16 w-16 mb-4 opacity-20" />
              <h3 className="text-xl font-medium text-gray-300">No Graph Data</h3>
              <p className="mt-2 max-w-md">
                The knowledge graph hasn't been extracted for this contract yet. 
                Run deep analysis to build the entity relationship map.
              </p>
              <button 
                onClick={() => api.extractKnowledgeGraph(contractId).then(() => refetch())}
                className="btn-primary mt-6"
              >
                Extract Knowledge Graph
              </button>
            </div>
          ) : (
            <svg ref={svgRef} className="w-full h-full" onClick={() => setSelectedNode(null)} />
          )}

          {/* Legend */}
          {hasGraphData && (
            <div className="absolute bottom-4 left-4 bg-slate-900/80 backdrop-blur-sm border border-slate-700 rounded-lg p-3 text-[10px] text-slate-400 pointer-events-none">
              <p className="font-semibold text-slate-300 mb-2 uppercase tracking-wider">Entity Types</p>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                {Object.entries(TYPE_COLORS).map(([type, color]) => (
                  <div key={type} className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                    <span>{type.charAt(0).toUpperCase() + type.slice(1).replace('_', ' ')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar / Detail Panel */}
        <div className="w-80 bg-white border-l border-gray-200 flex flex-col overflow-hidden">
          <div className="p-4 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <InformationCircleIcon className="h-4 w-4 text-indigo-500" />
              {selectedNode ? 'Entity Details' : 'Graph Insights'}
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
            {selectedNode ? (
              <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
                <div>
                  <div 
                    className="inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider mb-1"
                    style={{ backgroundColor: `${selectedNode.color}20`, color: selectedNode.color }}
                  >
                    {selectedNode.type}
                  </div>
                  <h4 className="text-lg font-bold text-gray-900 leading-tight">{selectedNode.name}</h4>
                  <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      Confidence: 
                      <span className={cn(
                        "font-medium",
                        selectedNode.confidence > 0.8 ? "text-green-600" : "text-amber-600"
                      )}>
                        {(selectedNode.confidence * 100).toFixed(0)}%
                      </span>
                    </span>
                  </div>
                </div>

                {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
                  <div className="space-y-2">
                    <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Properties</p>
                    <div className="bg-gray-50 rounded-md border border-gray-100 p-3 space-y-2">
                      {Object.entries(selectedNode.properties).map(([key, val]: [string, any]) => (
                        <div key={key} className="text-sm">
                          <span className="text-gray-500 font-medium block text-[11px] mb-0.5">{key.replace('_', ' ')}</span>
                          <span className="text-gray-900 break-words">{String(val)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                <div className="pt-4 border-t border-gray-100">
                  <p className="text-xs text-gray-400 italic">
                    ID: {selectedNode.id}
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Inconsistencies Section */}
                {inconsistencies.length > 0 && (
                  <div className="space-y-3">
                    <p className="text-[10px] font-bold text-red-500 uppercase tracking-widest flex items-center gap-2">
                      <ExclamationTriangleIcon className="h-3 w-3" />
                      Graph Verification Issues ({inconsistencies.length})
                    </p>
                    <div className="space-y-2">
                      {inconsistencies.map((inc: any, idx: number) => (
                        <div key={idx} className="bg-red-50 border border-red-100 rounded-md p-3">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[10px] font-bold text-red-600 uppercase">{inc.field} Mismatch</span>
                            <span className={cn(
                              "text-[9px] px-1.5 py-0.5 rounded font-bold uppercase",
                              inc.severity === 'high' ? "bg-red-600 text-white" : "bg-red-200 text-red-700"
                            )}>
                              {inc.severity}
                            </span>
                          </div>
                          <p className="text-xs text-red-800 leading-normal">{inc.description}</p>
                          {inc.suggested_correction && (
                            <div className="mt-2 pt-2 border-t border-red-200 flex flex-col gap-1">
                              <span className="text-[10px] text-red-400 font-medium uppercase">Graph Evidence</span>
                              <span className="text-xs font-bold text-red-900">{inc.suggested_correction}</span>
                              <button className="text-[10px] text-red-600 font-bold hover:underline self-start mt-1">
                                Update Metadata
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="space-y-3">
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Graph Statistics</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-gray-50 rounded-lg p-3 text-center border border-gray-100">
                      <div className="text-xl font-bold text-indigo-600">{graph.stats.total_entities}</div>
                      <div className="text-[10px] text-gray-400 uppercase">Entities</div>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-3 text-center border border-gray-100">
                      <div className="text-xl font-bold text-indigo-600">{graph.stats.total_relationships}</div>
                      <div className="text-[10px] text-gray-400 uppercase">Links</div>
                    </div>
                  </div>
                </div>

                <div className="bg-indigo-50 rounded-lg p-4 border border-indigo-100">
                  <h5 className="text-xs font-bold text-indigo-900 mb-2">Knowledge Graph Tip</h5>
                  <p className="text-xs text-indigo-800 leading-relaxed">
                    The knowledge graph maps explicit structural connections. Mismatches with metadata often reveal 
                    errors in manual tagging or LLM metadata extraction that can be corrected using the graph's structural evidence.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
