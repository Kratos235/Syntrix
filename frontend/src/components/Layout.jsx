import { useState } from 'react';
import { NavLink, Outlet, Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Network, FlaskConical, ChartNoAxesCombined, Route, SlidersHorizontal, Columns3, History, FileText, ChevronDown, ChevronRight, PanelLeftClose, Menu, X, Sun, Moon, ArrowUpRight, LogOut, CircleHelp, Command, Layers, Check, ExternalLink } from 'lucide-react';
import { useWorkspace } from '@/context/Workspace';
import { Button } from '@/components/ui/button';

const sections = [
  ['OVERVIEW', [['/', 'Executive dashboard', LayoutDashboard], ['/network', 'Supply network', Network]]],
  ['RESILIENCE ENGINE', [['/simulator', 'Scenario simulator', FlaskConical], ['/impact', 'Impact analysis', ChartNoAxesCombined], ['/recovery', 'Recovery planner', Route], ['/results', 'Optimization results', SlidersHorizontal]]],
  ['INSIGHTS', [['/comparison', 'Scenario comparison', Columns3], ['/timeline', 'Simulation timeline', History], ['/reports', 'Reports & exports', FileText]]],
];

export const Brand = () => <div className="brand"><div className="brand-mark"><span/><span/><span/></div><span>syntrix<span className="brand-period">.</span></span></div>;

export const Layout = () => {
  const { user, signOut, theme, setTheme, scenario, scenarios, setScenario } = useWorkspace();
  const [mobile, setMobile] = useState(false);
  const [help, setHelp] = useState(false);
  const location = useLocation();
  const title = sections.flatMap(s => s[1]).find(s => s[0] === location.pathname)?.[1] || 'Workspace';
  return <div className="app-shell">
    {mobile && <button className="sidebar-backdrop" onClick={() => setMobile(false)} data-testid="close-navigation-overlay" aria-label="Close navigation"/>}
    <aside className={`sidebar ${mobile ? 'mobile-open' : ''}`}>
      <div className="sidebar-brand"><Link to="/" data-testid="brand-home"><Brand/></Link><button className="mobile-close icon-button" onClick={() => setMobile(false)} data-testid="close-navigation" aria-label="Close navigation"><X size={18}/></button></div>
      <div className="workspace-identity"><div className="workspace-icon"><Layers size={17}/></div><div><strong>Syntrix workspace</strong><span>Supply chain operations</span></div><ChevronDown size={13}/></div>
      <nav>{sections.map(([label, links]) => <div className="nav-section" key={label}><div className="nav-section-label">{label}</div>{links.map(([to, text, Icon]) => <NavLink end={to === '/'} to={to} key={to} data-testid={`nav-${to === '/' ? 'dashboard' : to.slice(1)}`} onClick={() => setMobile(false)} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}><Icon size={17}/><span>{text}</span>{to === '/simulator' && <span className="nav-small">RUN</span>}</NavLink>)}</div>)}</nav>
      <div className="sidebar-bottom"><div className="engine-status"><span className="status-dot"/><div><strong>Deterministic engine</strong><span>Graph + simulation powered</span></div><Check size={13}/></div><button className="support-link" data-testid="open-methodology" onClick={() => setHelp(true)}><CircleHelp size={16}/>Model & methodology<ArrowUpRight size={13}/></button><div className="profile"><div className="avatar">{user ? user.email.slice(0,2).toUpperCase() : 'SX'}</div><div><strong>{user ? user.email.split('@')[0] : 'Sample workspace'}</strong><span>{user ? user.role.toLowerCase() : 'Explore with synthetic data'}</span></div>{user ? <button className="icon-button" onClick={signOut} title="Sign out" data-testid="sign-out"><LogOut size={16}/></button> : <Link to="/login" title="Sign in" data-testid="sidebar-sign-in"><ArrowUpRight size={16}/></Link>}</div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumbs"><button className="mobile-toggle icon-button" data-testid="open-navigation" onClick={() => setMobile(true)} aria-label="Open navigation"><Menu size={20}/></button><span className="desktop-only">Workspace</span><ChevronRight size={13} className="desktop-only"/><strong>{title}</strong></div><div className="topbar-actions"><span className="sample-chip" data-testid="data-mode-label"><span/>Synthetic data</span><div className="topbar-divider"/><button className="icon-button" title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`} data-testid="theme-toggle" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? <Sun size={17}/> : <Moon size={17}/>}</button><button className="icon-button help-button" data-testid="topbar-help" title="Model information" onClick={() => setHelp(true)}><CircleHelp size={17}/></button></div></header>
      <main className="page-content"><Outlet/></main>
      <footer className="workspace-footer"><span><span className="status-dot"/>All calculations reproducible<span className="footer-dot">·</span>No AI-derived scores</span><span>Syntrix <b>v1.0</b></span></footer>
    </div>
    {help && <div className="modal-backdrop" onClick={() => setHelp(false)}><div className="modal" role="dialog" aria-modal="true" aria-label="Model and methodology" data-testid="methodology-modal" onClick={e => e.stopPropagation()}><div className="panel-heading"><h2>Transparent by design.</h2><button className="icon-button" data-testid="close-methodology" onClick={() => setHelp(false)} aria-label="Close"><X size={20}/></button></div><p>Every result comes from a deterministic graph, capacity-constrained allocation, and daily simulation—not a prediction or an AI score.</p><h3>What this model represents</h3><p>33 synthetic Indian supply-chain locations, 36 transport lanes, and a descriptive 24-product catalogue. Simulation uses pooled equivalent units with 1:1 production conversion, finite inventory, fixed lead times, and daily orders.</p><h3>Important boundaries</h3><p>Product-specific BOM explosion and multi-SKU allocation are not modelled. Recovery cost is committed procurement and transport spend. Initial shipments represent a steady-state pipeline. Public sample calculations are not saved after refresh.</p><h3>Recovery definition</h3><p>Service above the configured threshold for consecutive days after the last deterioration. “Not reached” means the simulation horizon was too short to establish recovery.</p><Button data-testid="methodology-done" className="primary-button" onClick={() => setHelp(false)}>Understood<Check size={16}/></Button></div></div>}
  </div>;
};
