import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { request, supabase } from '@/lib/api';
import { toast } from 'sonner';

const WorkspaceContext = createContext(null);
export const useWorkspace = () => useContext(WorkspaceContext);

export const WorkspaceProvider = ({ children }) => {
  const [workspace, setWorkspace] = useState(null);
  const [scenario, setScenario] = useState(null);
  const [scenarios, setScenarios] = useState([]);
  const [user, setUser] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [theme, setTheme] = useState(localStorage.getItem('syntrix-theme') || 'dark');
  const [options, setOptions] = useState({ budget: 150000, policy: 'business-priority', strategies: ['supplier', 'inventory', 'rerouting', 'priority', 'combined'] });
  useEffect(() => { document.documentElement.dataset.theme = theme; document.documentElement.classList.toggle('dark', theme === 'dark'); localStorage.setItem('syntrix-theme', theme); }, [theme]);
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const data = await request('/sample/workspace');
      setWorkspace(data); setScenario(data.scenario); setScenarios([data.scenario]);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, value) => setSession(value));
    return () => subscription.unsubscribe();
  }, []);
  useEffect(() => {
    if (!session) { setUser(null); return; }
    let cancelled = false;
    request('/me').then(async identity => {
      if (cancelled) return;
      setUser(identity);
      const saved = await request('/scenarios');
      if (!cancelled) setScenarios(old => [...saved, ...old.filter(s => s.id === 'sample-s2')]);
    }).catch(e => { if (!cancelled) { setUser(null); toast.error(e.message); } });
    return () => { cancelled = true; };
  }, [session]);
  const canEdit = !user || ['ADMIN', 'ANALYST'].includes(user.role);
  async function run(config) {
    const data = await request(user ? '/scenarios' : '/sample/simulate', { method: 'POST', body: config });
    setScenario(data); setScenarios(old => [data, ...old].slice(0, 50));
    return data;
  }
  async function optimize(newOptions) {
    const isSaved = user && scenario.owner_id !== 'sample';
    const data = await request(isSaved ? `/scenarios/${scenario.id}/optimize` : '/sample/optimize', { method: 'POST', body: isSaved ? newOptions : { scenario: scenario.config, options: newOptions } });
    setOptions(newOptions); setScenario(data);
    setScenarios(old => old.map(s => s.id === scenario.id ? data : s));
    return data;
  }
  async function selectPlan(planId) {
    if (user && scenario.owner_id !== 'sample') await request(`/scenarios/${scenario.id}/select`, { method: 'POST', body: { plan_id: planId } });
    setScenario(old => ({ ...old, selected_plan: planId }));
    setScenarios(old => old.map(item => item.id === scenario.id ? { ...item, selected_plan: planId } : item));
    toast.success('Recovery plan selected');
  }
  async function signOut() {
    await supabase.auth.signOut(); setUser(null); await load();
  }
  return <WorkspaceContext.Provider value={{ workspace, scenario, setScenario, scenarios, user, loading, error, load, theme, setTheme, canEdit, run, optimize, options, selectPlan, signOut }}>{children}</WorkspaceContext.Provider>;
};
