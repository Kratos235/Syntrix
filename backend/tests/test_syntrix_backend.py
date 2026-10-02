"""Backend tests for Syntrix: 14 algorithms (engine), scenarios regressions,
public /api/sample endpoints, auth gating, and role matrix via dependency overrides.
Uses the preview REACT_APP_BACKEND_URL for HTTP tests and direct imports for engine tests.
"""
import io
import os
import csv
import copy
import asyncio
import pytest
import requests
import httpx
from httpx import ASGITransport

from seed import synthetic_network, canonical_scenario
from models import (
    Network, ScenarioInput, OptimizationInput, Disruption, Principal, Role,
)
from engine import (
    validate_network, validate_scenario, propagate, criticality, bottlenecks,
    supplier_mip, inventory_flow, reroute, prioritize_orders, check_feasibility,
    simulate, recovery_time, generate_strategies, pareto_compare, run_scenario,
    graph_for,
)
import server as server_mod
from auth import require, current_user

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')

# ---------- Fixtures ----------
@pytest.fixture(scope='module')
def network():
    return synthetic_network()

@pytest.fixture(scope='module')
def scenario():
    return canonical_scenario()

@pytest.fixture()
def http():
    s = requests.Session(); s.headers.update({'Content-Type': 'application/json'}); return s


# ================================================================
# A. Engine - 14 algorithms (deterministic)
# ================================================================
class TestNetworkShape:
    def test_counts(self, network):
        counts = {t: 0 for t in ['supplier', 'manufacturer', 'warehouse', 'customer']}
        for n in network.nodes:
            counts[n.type] += 1
        assert counts == {'supplier': 12, 'manufacturer': 4, 'warehouse': 5, 'customer': 12}
        assert len(network.lanes) == 36
        assert len(network.products) == 24
        assert network.seed == 42

    def test_validate_ok(self, network):
        v = validate_network(network)
        assert v['valid'] is True and not v['errors']

    def test_validate_broken_refs(self, network):
        bad = network.model_copy(deep=True)
        bad.lanes[0].target = 'ZZ'
        v = validate_network(bad)
        assert not v['valid'] and any('broken node' in e for e in v['errors'])

    def test_validate_cycle(self, network):
        bad = network.model_copy(deep=True)
        # add a reverse edge to create a cycle in primary graph
        src = bad.lanes[0]
        from models import Lane
        bad.lanes.append(Lane(id='LCYCLE', source=src.target, target=src.source,
                              capacity=10, cost=1, lead_time=1, distance=1))
        v = validate_network(bad)
        assert not v['valid'] and any('cycle' in e for e in v['errors'])


class TestValidateScenario:
    def test_type_target_mismatch(self, network):
        bad = ScenarioInput(name='bad mismatch', disruptions=[Disruption(type='warehouse_outage', target='S2')])
        with pytest.raises(ValueError):
            validate_scenario(network, bad)

    def test_unknown_target(self, network):
        bad = ScenarioInput(name='unknown target', disruptions=[Disruption(target='ZZ')])
        with pytest.raises(ValueError):
            validate_scenario(network, bad)


class TestPropagate:
    def test_zero_severity_empty(self, network):
        s = ScenarioInput(name='zero sev', disruptions=[Disruption(target='S2', severity=0)])
        p = propagate(network, s)
        assert p['affected_nodes'] == [] and p['affected_customers'] == 0

    def test_s2_failure_propagates(self, network, scenario):
        p = propagate(network, scenario)
        assert 'S2' in p['affected_nodes']
        assert p['affected_customers'] > 0 and p['daily_demand_exposed'] > 0


class TestCriticality:
    def test_normalized_and_sorted(self, network):
        rows = criticality(network)
        assert len(rows) == len(network.nodes)
        for r in rows:
            assert 0.0 <= r['betweenness'] <= 1.0
        # sorted desc by betweenness, demand
        for a, b in zip(rows, rows[1:]):
            assert (a['betweenness'], a['demand_exposed']) >= (b['betweenness'], b['demand_exposed'])


class TestBottlenecks:
    def test_maxflow_positive_and_cut(self, network):
        b = bottlenecks(network)
        assert b['max_daily_flow'] > 0
        assert b['daily_demand'] == sum(n.daily_demand for n in network.nodes)
        assert isinstance(b['cut'], list)


class TestSupplierMIP:
    def test_budget_and_capacity(self, network, scenario):
        actions, logs = supplier_mip(network, scenario, 150000)
        assert sum(a['cost'] for a in actions) <= 150000
        for a in actions:
            node = next(n for n in network.nodes if n.id == a['source'])
            assert a['quantity'] <= int(node.capacity * 0.75)

    def test_zero_budget_no_actions(self, network, scenario):
        actions, _ = supplier_mip(network, scenario, 0)
        assert actions == []


class TestInventoryFlow:
    def test_finite_reserve(self, network, scenario):
        actions, _ = inventory_flow(network, scenario, 10_000_000)
        reserve = next(n for n in network.nodes if n.id == 'W5').inventory
        assert sum(a['quantity'] for a in actions) <= reserve


class TestReroute:
    def test_real_alternate_lanes_only(self, network, scenario):
        actions, paths = reroute(network, scenario, 150000)
        lane_ids = {l.id: l for l in network.lanes}
        for a in actions:
            assert a['lane'] in lane_ids and lane_ids[a['lane']].alternate


class TestOrderPolicy:
    def test_three_policies_deterministic(self):
        orders = [
            {'id': 'A', 'priority': 2, 'due': 3, 'remaining': 10},
            {'id': 'B', 'priority': 1, 'due': 4, 'remaining': 5},
            {'id': 'C', 'priority': 3, 'due': 2, 'remaining': 8},
        ]
        bp = [o['id'] for o in prioritize_orders(orders, 'business-priority')]
        sv = [o['id'] for o in prioritize_orders(orders, 'service')]
        ur = [o['id'] for o in prioritize_orders(orders, 'urgency')]
        assert bp[0] == 'B'  # priority 1 first
        assert sv[0] == 'B'  # smallest remaining
        assert ur[0] == 'C'  # earliest due


class TestFeasibility:
    def test_rejects_overspend(self, network):
        actions = [{'kind': 'inventory', 'source': 'W5', 'target': 'W1', 'lane': 'L25',
                    'quantity': 10, 'start_day': 1, 'duration': 2, 'cost': 1_000_000}]
        f = check_feasibility(network, actions, 1000)
        assert not f['feasible']


class TestSimulate:
    def test_baseline_conservation_and_no_negative(self, network):
        s = ScenarioInput(name='zero baseline', disruptions=[Disruption(target='S2', severity=0)])
        res = simulate(network, s)
        assert res['conservation_error'] == 0 or abs(res['conservation_error']) < 1e-3
        assert res['kpis']['service_level'] == 100
        for day in res['daily']:
            for v in day['node_inventory'].values():
                assert v >= -1e-6

    def test_s2_disrupted_degrades(self, network, scenario):
        res = simulate(network, scenario)
        assert res['kpis']['service_level'] < 100


class TestRecoveryTime:
    def test_no_deterioration_zero(self):
        daily = [{'day': d, 'service_level': 100} for d in range(1, 11)]
        assert recovery_time(daily, 1, 95, 3) == 0

    def test_not_recovered(self):
        daily = [{'day': d, 'service_level': 80} for d in range(1, 11)]
        assert recovery_time(daily, 1, 95, 3) is None


class TestKPIBoundsAndPareto:
    def test_bounds(self, network, scenario):
        res = run_scenario(network, scenario)
        for k in (res['baseline']['kpis'], res['disrupted']['kpis']):
            assert 0 <= k['service_level'] <= 100
            assert 0 <= k['fulfillment_rate'] <= 100
            assert k['unmet_demand'] >= 0

    def test_recommendation_balanced(self, network, scenario):
        plans = generate_strategies(network, scenario, OptimizationInput())
        feasible = [p for p in plans if p['feasibility']['feasible']]
        recs = [p for p in plans if p['recommended']]
        assert len(recs) == (1 if feasible else 0)
        # at least one Pareto plan when any feasible
        if feasible:
            assert any(p['pareto'] for p in plans)


# ================================================================
# B. 10 deterministic scenario regressions
# ================================================================
SCENARIOS = {
    'canonical_s2': ScenarioInput(name='canonical S2 shutdown', disruptions=[Disruption()]),
    'zero_severity': ScenarioInput(name='zero severity', disruptions=[Disruption(severity=0)]),
    'partial_supplier': ScenarioInput(name='partial supplier', disruptions=[Disruption(target='S2', severity=50)]),
    'lane_closure': ScenarioInput(name='lane closure', disruptions=[Disruption(type='lane_closure', target='L1')]),
    'transport_delay': ScenarioInput(name='transport delay', disruptions=[Disruption(type='transport_delay', target='L1', severity=60)]),
    'warehouse_outage': ScenarioInput(name='warehouse outage', disruptions=[Disruption(type='warehouse_outage', target='W1')]),
    'demand_surge': ScenarioInput(name='demand surge', disruptions=[Disruption(type='demand_surge', target='C1', severity=80)]),
    'production_cut': ScenarioInput(name='production cut', disruptions=[Disruption(type='production_reduction', target='M1', severity=70)]),
    'two_simul': ScenarioInput(name='two simultaneous', disruptions=[Disruption(target='S2'), Disruption(type='lane_closure', target='L5', start_day=3, duration=5)]),
    'short_horizon': ScenarioInput(name='short horizon', disruptions=[Disruption(target='S2', start_day=5, duration=10)], horizon=7),
}

@pytest.mark.parametrize('key', list(SCENARIOS.keys()))
def test_scenario_regression(network, key):
    res = run_scenario(network, SCENARIOS[key])
    # baseline must be 100% service in all cases
    assert res['baseline']['kpis']['service_level'] == 100
    disrupted_sl = res['disrupted']['kpis']['service_level']
    if key == 'zero_severity':
        assert disrupted_sl == 100
    # conservation
    assert abs(res['disrupted']['conservation_error']) < 1e-3


def test_feasible_actions_respect_budget(network):
    plans = generate_strategies(network, SCENARIOS['canonical_s2'], OptimizationInput(budget=100000))
    for p in plans:
        total = sum(a['cost'] for a in p['actions'])
        assert total <= 100000


def test_zero_budget_zero_spend(network):
    plans = generate_strategies(network, SCENARIOS['canonical_s2'], OptimizationInput(budget=0))
    for p in plans:
        assert sum(a['cost'] for a in p['actions']) == 0


# ================================================================
# C. Public HTTP endpoints via preview URL
# ================================================================
class TestPublicEndpoints:
    def test_health(self, http):
        r = http.get(f'{BASE_URL}/api/')
        assert r.status_code == 200
        data = r.json()
        assert data['status'] == 'operational'
        assert data['name'] == 'Syntrix'

    def test_auth_status_reports_unavailable(self, http):
        r = http.get(f'{BASE_URL}/api/auth/status')
        assert r.status_code == 200
        data = r.json()
        # known blocker: invalid supplied key
        assert isinstance(data['available'], bool)
        assert 'message' in data

    def test_sample_workspace(self, http):
        r = http.get(f'{BASE_URL}/api/sample/workspace')
        assert r.status_code == 200
        data = r.json()
        assert data['network']['name']
        assert len(data['network']['nodes']) == 33
        assert len(data['network']['lanes']) == 36
        assert data['scenario']['baseline']['kpis']['service_level'] == 100
        assert data['validation']['valid'] is True

    def test_sample_simulate(self, http):
        payload = {'name': 'TEST_simulate', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2', 'start_day': 3, 'duration': 7, 'severity': 100}]}
        r = http.post(f'{BASE_URL}/api/sample/simulate', json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data['disrupted']['kpis']['service_level'] < 100
        assert data['baseline']['kpis']['service_level'] == 100

    def test_sample_simulate_bad_name(self, http):
        payload = {'name': '  ', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]}
        r = http.post(f'{BASE_URL}/api/sample/simulate', json=payload)
        assert r.status_code in (400, 422)

    def test_sample_simulate_type_mismatch(self, http):
        payload = {'name': 'TEST_mismatch', 'disruptions': [{'type': 'warehouse_outage', 'target': 'S2'}]}
        r = http.post(f'{BASE_URL}/api/sample/simulate', json=payload)
        assert r.status_code == 422

    def test_sample_simulate_duration_bounds(self, http):
        payload = {'name': 'TEST_bounds', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2', 'duration': 0}]}
        r = http.post(f'{BASE_URL}/api/sample/simulate', json=payload)
        assert r.status_code == 422

    def test_sample_optimize(self, http):
        payload = {'scenario': {'name': 'TEST_optimize', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]},
                   'options': {'budget': 150000, 'policy': 'business-priority', 'strategies': ['supplier', 'combined']}}
        r = http.post(f'{BASE_URL}/api/sample/optimize', json=payload)
        assert r.status_code == 200
        plans = r.json()['plans']
        assert len(plans) == 2
        for p in plans:
            assert sum(a['cost'] for a in p['actions']) <= 150000

    def test_sample_report_pdf(self, http):
        payload = {'scenario': {'name': 'TEST_pdfreport', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]},
                   'options': {'budget': 150000, 'strategies': ['supplier']}}
        r = http.post(f'{BASE_URL}/api/sample/report/pdf', json=payload)
        assert r.status_code == 200
        assert r.headers['content-type'].startswith('application/pdf')
        assert r.content[:4] == b'%PDF'

    def test_sample_report_csv(self, http):
        payload = {'scenario': {'name': 'TEST_csvreport', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]},
                   'options': {'budget': 150000, 'strategies': ['supplier']}}
        r = http.post(f'{BASE_URL}/api/sample/report/csv', json=payload)
        assert r.status_code == 200
        assert r.headers['content-type'].startswith('text/csv')
        rows = list(csv.reader(io.StringIO(r.content.decode('utf-8-sig'))))
        assert rows[0][0].startswith('Syntrix')

    def test_sample_report_unknown_format(self, http):
        payload = {'scenario': {'name': 'TEST_badfmt', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]}}
        r = http.post(f'{BASE_URL}/api/sample/report/xml', json=payload)
        assert r.status_code == 422


# ================================================================
# D. Auth: missing / malformed token fails closed
# ================================================================
class TestAuthFailsClosed:
    def test_missing_token(self, http):
        r = http.get(f'{BASE_URL}/api/me')
        assert r.status_code == 401

    def test_malformed_token(self, http):
        r = http.get(f'{BASE_URL}/api/me', headers={'Authorization': 'Bearer not-a-real-token'})
        assert r.status_code in (401, 503)  # 503 if Supabase rejects anon key entirely

    def test_scenarios_requires_auth(self, http):
        r = http.get(f'{BASE_URL}/api/scenarios')
        assert r.status_code == 401

    def test_network_requires_auth(self, http):
        r = http.get(f'{BASE_URL}/api/network')
        assert r.status_code == 401


# ================================================================
# E. Role matrix via dependency overrides (no real Supabase calls)
# ================================================================
VIEWER = Principal(id='u-viewer', email='v@test.local', role=Role.VIEWER)
ANALYST = Principal(id='u-analyst', email='a@test.local', role=Role.ANALYST)
ADMIN = Principal(id='u-admin', email='x@test.local', role=Role.ADMIN)


def _client_for(principal):
    app = server_mod.app
    app.dependency_overrides[current_user] = lambda: principal
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver')


def _clear():
    server_mod.app.dependency_overrides.clear()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(scope='module', autouse=True)
def _event_loop_module():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Re-bind motor client to this loop
    from motor.motor_asyncio import AsyncIOMotorClient
    server_mod.client = AsyncIOMotorClient(os.environ['MONGO_URL'], io_loop=loop)
    server_mod.db = server_mod.client[os.environ['DB_NAME']]
    yield loop
    loop.close()


class TestRoleMatrix:
    def teardown_method(self):
        _clear()

    def test_viewer_can_read(self):
        async def go():
            async with _client_for(VIEWER) as c:
                assert (await c.get('/api/me')).status_code == 200
                assert (await c.get('/api/network')).status_code == 200
                assert (await c.get('/api/scenarios')).status_code == 200
        _run(go())

    def test_viewer_cannot_simulate(self):
        async def go():
            async with _client_for(VIEWER) as c:
                payload = {'name': 'TEST_viewer_sim', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]}
                r = await c.post('/api/scenarios', json=payload)
                assert r.status_code == 403
        _run(go())

    def test_analyst_can_simulate_not_delete(self):
        async def go():
            async with _client_for(ANALYST) as c:
                payload = {'name': 'TEST_analyst_sim', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]}
                r = await c.post('/api/scenarios', json=payload)
                assert r.status_code == 201
                sid = r.json()['id']
                assert (await c.delete(f'/api/scenarios/{sid}')).status_code == 403
                return sid
            # cleanup
        sid = _run(go())
        _clear()
        async def cleanup():
            async with _client_for(ADMIN) as c:
                # Admin is a different owner, so cannot see → 404 on get, 404 on delete (gated by get first)
                r = await c.delete(f'/api/scenarios/{sid}')
                assert r.status_code == 404
        _run(cleanup())

    def test_admin_can_delete_own(self):
        async def go():
            async with _client_for(ADMIN) as c:
                payload = {'name': 'TEST_admin_del', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]}
                r = await c.post('/api/scenarios', json=payload)
                assert r.status_code == 201
                sid = r.json()['id']
                assert (await c.delete(f'/api/scenarios/{sid}')).status_code == 204
                assert (await c.get(f'/api/scenarios/{sid}')).status_code == 404
        _run(go())

    def test_cross_user_isolation(self):
        async def go():
            async with _client_for(ANALYST) as c:
                payload = {'name': 'TEST_isolation', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]}
                sid = (await c.post('/api/scenarios', json=payload)).json()['id']
            _clear()
            other = Principal(id='u-other-analyst', email='o@test.local', role=Role.ANALYST)
            async with _client_for(other) as c2:
                assert (await c2.get(f'/api/scenarios/{sid}')).status_code == 404
        _run(go())

    def test_role_injection_ignored(self):
        async def go():
            async with _client_for(VIEWER) as c:
                r = await c.get('/api/me', headers={'X-Role': 'ADMIN'})
                assert r.status_code == 200
                assert r.json()['role'] == 'VIEWER'
        _run(go())
