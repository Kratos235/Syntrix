import '@/App.css';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import { Loader2, RotateCcw } from 'lucide-react';
import { WorkspaceProvider, useWorkspace } from '@/context/Workspace';
import { Layout, Brand } from '@/components/Layout';
import Dashboard from '@/pages/Dashboard';
import NetworkPage from '@/pages/NetworkPage';
import Simulator from '@/pages/Simulator';
import Impact from '@/pages/Impact';
import Recovery from '@/pages/Recovery';
import Results from '@/pages/Results';
import Comparison from '@/pages/Comparison';
import Timeline from '@/pages/Timeline';
import Reports from '@/pages/Reports';
import Login from '@/pages/Login';

function WorkspaceRoutes() {
  const { loading, error, load, theme } = useWorkspace();
  if (loading) return <div className="loading-screen"><Brand/><Loader2 className="spin" size={24}/><p>Connecting your supply network…</p></div>;
  if (error) return <div className="loading-screen"><Brand/><h2>Workspace unavailable</h2><p role="alert" data-testid="workspace-error">{error}</p><button className="primary-button" data-testid="workspace-retry" onClick={load}><RotateCcw size={16}/>Try again</button></div>;
  return <><Routes><Route path="/login" element={<Login/>}/><Route element={<Layout/>}><Route index element={<Dashboard/>}/><Route path="network" element={<NetworkPage/>}/><Route path="simulator" element={<Simulator/>}/><Route path="impact" element={<Impact/>}/><Route path="recovery" element={<Recovery/>}/><Route path="results" element={<Results/>}/><Route path="comparison" element={<Comparison/>}/><Route path="timeline" element={<Timeline/>}/><Route path="reports" element={<Reports/>}/><Route path="*" element={<div className="empty-state"><h1>Page not found</h1><Link data-testid="not-found-home" className="primary-button" to="/">Return to dashboard</Link></div>}/></Route></Routes><Toaster theme={theme} position="bottom-right" richColors/></>;
}

export default function App() {
  return <BrowserRouter><WorkspaceProvider><WorkspaceRoutes/></WorkspaceProvider></BrowserRouter>;
}
