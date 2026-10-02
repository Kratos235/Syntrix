import { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import { Plus, Minus, Maximize2 } from 'lucide-react';
import { useWorkspace } from '@/context/Workspace';

export const typeColors = { supplier: '#6faaf3', manufacturer: '#a6b4c8', warehouse: '#eab657', customer: '#66bd9b' };

export const NetworkGraph = ({ compact = false, filter = 'all', search = '', onSelect, day }) => {
  const { workspace, scenario, theme } = useWorkspace();
  const container = useRef(null);
  const graph = useRef(null);
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  useEffect(() => {
    if (!workspace || !container.current) return;
    const network = workspace.network;
    const origins = new Set(scenario?.impact.origins || []);
    const impacted = new Set(scenario?.impact.affected_nodes || []);
    const groups = ['supplier', 'manufacturer', 'warehouse', 'customer'];
    const elements = [];
    const seen = new Set();
    network.nodes.forEach(node => {
      if (filter !== 'all' && node.type !== filter) return;
      if (search && !`${node.id} ${node.name} ${node.location}`.toLowerCase().includes(search.toLowerCase())) return;
      seen.add(node.id);
      const peers = network.nodes.filter(n => n.type === node.type);
      const i = peers.findIndex(n => n.id === node.id);
      const group = groups.indexOf(node.type);
      const y = node.id === 'W5' ? 450 : node.type === 'supplier' || node.type === 'customer' ? i*35 + 30 : i*105 + 64;
      const isActive = day === undefined || scenario.config.disruptions.some(d => day >= d.start_day && day < d.start_day + d.duration);
      elements.push({ data: { id: node.id, label: compact ? node.id : `${node.id} · ${node.name}`, color: origins.has(node.id) && isActive ? '#ee776f' : typeColors[node.type], shape: { supplier: 'diamond', manufacturer: 'round-rectangle', warehouse: 'round-rectangle', customer: 'ellipse' }[node.type], size: node.type === 'manufacturer' ? 24 : 18, affected: impacted.has(node.id), origin: origins.has(node.id) && isActive }, position: { x: group*255+50, y } });
    });
    network.lanes.forEach(lane => {
      if (seen.has(lane.source) && seen.has(lane.target)) elements.push({ data: { id: lane.id, source: lane.source, target: lane.target, alternate: lane.alternate, risk: origins.has(lane.source) } });
    });
    const cy = cytoscape({ container: container.current, elements, layout: { name: 'preset', padding: compact ? 25 : 40 }, minZoom: .2, maxZoom: 3, wheelSensitivity: .15, userZoomingEnabled: !compact, boxSelectionEnabled: false,
      style: [
        { selector: 'node', style: { 'background-color': 'data(color)', 'background-opacity': .15, 'border-color': 'data(color)', 'border-width': 1.5, 'shape': 'data(shape)', 'width': 'data(size)', 'height': 'data(size)', 'label': 'data(label)', 'font-size': compact ? 9 : 10, 'font-family': 'DM Sans', 'color': theme === 'dark' ? '#a4afc1' : '#475569', 'text-valign': 'bottom', 'text-margin-y': 7, 'text-wrap': 'wrap', 'text-max-width': 120 } },
        { selector: 'node[?origin]', style: { 'background-opacity': .4, 'border-width': 2.5, 'width': 26, 'height': 26, 'color': '#ee776f' } },
        { selector: 'edge', style: { 'width': 1, 'line-color': theme === 'dark' ? '#334154' : '#b5c0cf', 'target-arrow-color': theme === 'dark' ? '#48566b' : '#a4afc1', 'target-arrow-shape': 'triangle', 'arrow-scale': .65, 'curve-style': 'bezier', 'opacity': .8 } },
        { selector: 'edge[?alternate]', style: { 'line-style': 'dashed', 'opacity': .24 } },
        { selector: 'edge[?risk]', style: { 'line-color': '#d07965', 'target-arrow-color': '#d07965', 'width': 1.5 } },
        { selector: ':selected', style: { 'border-width': 3, 'border-color': '#f4b84d' } },
      ] });
    cy.on('tap', 'node', event => selectRef.current?.(network.nodes.find(n => n.id === event.target.id())));
    graph.current = cy;
    const observer = new ResizeObserver(() => { cy.resize(); cy.fit(undefined, compact ? 25 : 40); });
    observer.observe(container.current);
    return () => { observer.disconnect(); cy.destroy(); };
  }, [workspace, scenario, compact, filter, search, theme, day]);
  return <div className={`network-frame ${compact ? 'compact' : ''}`}>
    <div className="echelon-labels" aria-hidden="true"><span>SUPPLIERS</span><span>MANUFACTURING</span><span>DISTRIBUTION</span><span>CUSTOMERS</span></div>
    <div ref={container} className="cytoscape-canvas" data-testid={compact ? 'dashboard-network-canvas' : 'network-canvas'} role="img" aria-label="Interactive supply-chain network. Select a node to inspect dependencies." />
    <div className="graph-controls">
      {!compact && <><button data-testid="network-zoom-in" title="Zoom in" onClick={() => graph.current?.zoom(graph.current.zoom()*1.2)}><Plus size={14} /></button><button data-testid="network-zoom-out" title="Zoom out" onClick={() => graph.current?.zoom(graph.current.zoom()/1.2)}><Minus size={14} /></button></>}
      <button data-testid={compact ? 'dashboard-network-fit' : 'network-fit'} title="Fit network" onClick={() => graph.current?.fit(undefined, 35)}><Maximize2 size={14} /></button>
    </div>
  </div>;
};

export const NetworkLegend = () => <div className="network-legend">{Object.entries(typeColors).map(([name, color]) => <span key={name}><i style={{ background: color }} />{name}</span>)}<span><i style={{ background: '#ee776f' }} />Disrupted</span></div>;
