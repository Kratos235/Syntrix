"""Iteration-2 additional coverage for Syntrix:
A. Direct auth.current_user() via mocked httpx (role resolution, OWNER_EMAIL rules).
B. Role endpoint coverage not fully in iteration 1 (viewer export own, analyst optimize/select/export,
   cross-owner 404 on optimize/select/export/delete).
C. Consistency regression: scenario.optimization_options is persisted and used for reports/selectedplan.
D. Selected-plan report validation (bogus=422, selected name appears in CSV/PDF).
E. Transport-delay propagation offsets (arrival_day grows with severity).
"""
import os
import io
import csv
import asyncio
import pytest
import httpx
from httpx import ASGITransport, Response
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.security import HTTPAuthorizationCredentials

from seed import synthetic_network
from models import (
    ScenarioInput, OptimizationInput, Disruption, Principal, Role,
)
from engine import propagate
import server as server_mod
from auth import current_user


# ---------------------------------------------------------------------
# A. auth.current_user — direct unit tests via mocked httpx AsyncClient
# ---------------------------------------------------------------------
def _creds(token='t'):
    return HTTPAuthorizationCredentials(scheme='Bearer', credentials=token)


def _mock_httpx_user(json_body, status=200):
    """Context manager that patches httpx.AsyncClient so the GET /auth/v1/user
    inside auth.current_user returns the given JSON. Does NOT touch Supabase."""
    class FakeAsyncClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, headers=None):
            return Response(status_code=status, json=json_body)
    return patch('auth.httpx.AsyncClient', FakeAsyncClient)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestCurrentUserDirect:
    def test_missing_credentials_401(self):
        with pytest.raises(Exception) as exc:
            _run(current_user(credentials=None))
        assert exc.value.status_code == 401

    def test_invalid_token_rejected_by_supabase(self):
        with _mock_httpx_user({'msg': 'bad'}, status=401):
            with pytest.raises(Exception) as exc:
                _run(current_user(credentials=_creds()))
            assert exc.value.status_code == 401

    def test_missing_id_in_response_401(self):
        with _mock_httpx_user({'email': 'x@y.com'}):
            with pytest.raises(Exception) as exc:
                _run(current_user(credentials=_creds()))
            assert exc.value.status_code == 401

    def test_metadata_missing_defaults_viewer(self):
        with _mock_httpx_user({'id': 'u1', 'email': 'a@b.com'}):
            principal = _run(current_user(credentials=_creds()))
            assert principal.role == Role.VIEWER

    def test_valid_app_metadata_role_analyst(self):
        with _mock_httpx_user({'id': 'u1', 'email': 'a@b.com', 'app_metadata': {'role': 'ANALYST'}}):
            principal = _run(current_user(credentials=_creds()))
            assert principal.role == Role.ANALYST

    def test_valid_app_metadata_role_admin_without_owner_email(self):
        with _mock_httpx_user({'id': 'u1', 'email': 'notowner@b.com', 'email_confirmed_at': '2024-01-01', 'app_metadata': {'role': 'ADMIN'}}):
            principal = _run(current_user(credentials=_creds()))
            assert principal.role == Role.ADMIN

    def test_user_metadata_admin_is_ignored(self):
        with _mock_httpx_user({'id': 'u1', 'email': 'a@b.com', 'user_metadata': {'role': 'ADMIN'}}):
            principal = _run(current_user(credentials=_creds()))
            assert principal.role == Role.VIEWER  # only app_metadata counts

    def test_malformed_role_dict_falls_back_viewer(self):
        with _mock_httpx_user({'id': 'u1', 'email': 'a@b.com', 'app_metadata': {'role': {'x': 'ADMIN'}}}):
            principal = _run(current_user(credentials=_creds()))
            assert principal.role == Role.VIEWER

    def test_malformed_role_list_falls_back_viewer(self):
        with _mock_httpx_user({'id': 'u1', 'email': 'a@b.com', 'app_metadata': {'role': ['ADMIN']}}):
            principal = _run(current_user(credentials=_creds()))
            assert principal.role == Role.VIEWER

    def test_unknown_role_string_falls_back_viewer(self):
        with _mock_httpx_user({'id': 'u1', 'email': 'a@b.com', 'app_metadata': {'role': 'SUPERUSER'}}):
            principal = _run(current_user(credentials=_creds()))
            assert principal.role == Role.VIEWER

    def test_owner_email_confirmed_promotes_to_admin(self):
        owner = os.environ['OWNER_EMAIL']
        with _mock_httpx_user({'id': 'u1', 'email': owner, 'email_confirmed_at': '2024-01-01'}):
            principal = _run(current_user(credentials=_creds()))
            assert principal.role == Role.ADMIN

    def test_owner_email_unconfirmed_stays_viewer(self):
        owner = os.environ['OWNER_EMAIL']
        with _mock_httpx_user({'id': 'u1', 'email': owner}):
            principal = _run(current_user(credentials=_creds()))
            assert principal.role == Role.VIEWER

    def test_role_changes_reflected_next_call(self):
        """Successive calls re-read Supabase; a role flip is picked up on next call."""
        with _mock_httpx_user({'id': 'u1', 'email': 'a@b.com', 'app_metadata': {'role': 'ANALYST'}}):
            first = _run(current_user(credentials=_creds()))
            assert first.role == Role.ANALYST
        with _mock_httpx_user({'id': 'u1', 'email': 'a@b.com', 'app_metadata': {'role': 'VIEWER'}}):
            second = _run(current_user(credentials=_creds()))
            assert second.role == Role.VIEWER


# ---------------------------------------------------------------------
# B. Role endpoint coverage via dependency overrides + real Mongo
#    (optimize/select/delete 403 for viewer; viewer own-export OK;
#     analyst own optimize/select/export; cross-owner 404 everywhere)
# ---------------------------------------------------------------------
VIEWER = Principal(id='it2-viewer', email='v@test.local', role=Role.VIEWER)
VIEWER2 = Principal(id='it2-viewer-2', email='v2@test.local', role=Role.VIEWER)
ANALYST = Principal(id='it2-analyst', email='a@test.local', role=Role.ANALYST)
ANALYST2 = Principal(id='it2-analyst-2', email='a2@test.local', role=Role.ANALYST)
ADMIN = Principal(id='it2-admin', email='x@test.local', role=Role.ADMIN)


def _client_for(principal):
    app = server_mod.app
    app.dependency_overrides[current_user] = lambda: principal
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver')


def _clear():
    server_mod.app.dependency_overrides.clear()


@pytest.fixture(scope='module', autouse=True)
def _event_loop_module():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    from motor.motor_asyncio import AsyncIOMotorClient
    server_mod.client = AsyncIOMotorClient(os.environ['MONGO_URL'], io_loop=loop)
    server_mod.db = server_mod.client[os.environ['DB_NAME']]
    yield loop
    loop.close()


SIM_PAYLOAD = {'name': 'TEST_it2_scenario', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]}


class TestRoleEndpointCoverage:
    def teardown_method(self):
        _clear()

    def _create_as(self, principal, name='TEST_it2_scenario'):
        async def go():
            async with _client_for(principal) as c:
                r = await c.post('/api/scenarios', json={**SIM_PAYLOAD, 'name': name})
                assert r.status_code == 201, r.text
                return r.json()['id']
        sid = _run(go())
        _clear()
        return sid

    def test_viewer_optimize_select_delete_all_403(self):
        sid = self._create_as(ANALYST, 'TEST_it2_vdeny')
        async def go():
            async with _client_for(VIEWER) as c:
                r1 = await c.post(f'/api/scenarios/{sid}/optimize', json=OptimizationInput().model_dump())
                r2 = await c.post(f'/api/scenarios/{sid}/select', json={'plan_id': 'supplier'})
                r3 = await c.delete(f'/api/scenarios/{sid}')
                return r1.status_code, r2.status_code, r3.status_code
        s1, s2, s3 = _run(go())
        # viewer never gets past authorize() — 403 regardless of ownership
        assert (s1, s2, s3) == (403, 403, 403)

    def test_viewer_own_scenario_export_allowed(self):
        """Viewer cannot create but if a viewer somehow owns a scenario they can export it
        (export is read-only). Simulate by inserting a doc with the viewer as owner_id."""
        sid = self._create_as(ANALYST, 'TEST_it2_vexport')
        # Reassign ownership to viewer directly in Mongo
        async def reassign():
            await server_mod.db.scenarios.update_one({'_id': sid}, {'$set': {'owner_id': VIEWER.id}})
        _run(reassign())
        async def go():
            async with _client_for(VIEWER) as c:
                r_csv = await c.get(f'/api/scenarios/{sid}/report/csv')
                r_pdf = await c.get(f'/api/scenarios/{sid}/report/pdf')
                return r_csv, r_pdf
        r_csv, r_pdf = _run(go())
        assert r_csv.status_code == 200 and r_csv.headers['content-type'].startswith('text/csv')
        assert r_pdf.status_code == 200 and r_pdf.headers['content-type'].startswith('application/pdf')
        assert r_pdf.content[:4] == b'%PDF'

    def test_analyst_own_optimize_select_export(self):
        sid = self._create_as(ANALYST, 'TEST_it2_aflow')
        async def go():
            async with _client_for(ANALYST) as c:
                r_opt = await c.post(f'/api/scenarios/{sid}/optimize', json={'budget': 150000, 'policy': 'business-priority', 'strategies': ['supplier', 'priority']})
                assert r_opt.status_code == 200, r_opt.text
                plans = r_opt.json()['plans']
                feasible = next(p for p in plans if p['feasibility']['feasible'])
                r_sel = await c.post(f'/api/scenarios/{sid}/select', json={'plan_id': feasible['id']})
                assert r_sel.status_code == 200, r_sel.text
                assert r_sel.json()['selected_plan'] == feasible['id']
                r_csv = await c.get(f'/api/scenarios/{sid}/report/csv')
                r_pdf = await c.get(f'/api/scenarios/{sid}/report/pdf')
                return r_csv, r_pdf, feasible['name']
        r_csv, r_pdf, plan_name = _run(go())
        assert r_csv.status_code == 200
        rows = list(csv.reader(io.StringIO(r_csv.content.decode('utf-8-sig'))))
        assert any(row and row[0] == 'Selected recovery plan' and row[1] == plan_name for row in rows)
        assert r_pdf.status_code == 200
        assert r_pdf.headers['content-type'].startswith('application/pdf')
        assert r_pdf.content.startswith(b'%PDF')

    def test_cross_owner_optimize_select_export_delete_404(self):
        """Admin not owning the scenario cannot see or mutate it — must get 404 (not 403)."""
        sid = self._create_as(ANALYST, 'TEST_it2_cross')
        async def go():
            async with _client_for(ADMIN) as c:
                r_opt = await c.post(f'/api/scenarios/{sid}/optimize', json=OptimizationInput().model_dump())
                r_sel = await c.post(f'/api/scenarios/{sid}/select', json={'plan_id': 'supplier'})
                r_csv = await c.get(f'/api/scenarios/{sid}/report/csv')
                r_pdf = await c.get(f'/api/scenarios/{sid}/report/pdf')
                r_del = await c.delete(f'/api/scenarios/{sid}')
                return r_opt.status_code, r_sel.status_code, r_csv.status_code, r_pdf.status_code, r_del.status_code
        results = _run(go())
        assert results == (404, 404, 404, 404, 404)


# ---------------------------------------------------------------------
# C. Consistency: scenario.optimization_options is persisted; sample optimize
#    returns it; private optimize persists it; different options per scenario
#    are not cross-polluted.
# ---------------------------------------------------------------------
class TestOptimizationOptionsPersistence:
    def teardown_method(self):
        _clear()

    def test_private_optimize_persists_options_and_resets_selected_plan(self):
        async def go():
            async with _client_for(ANALYST) as c:
                r = await c.post('/api/scenarios', json={**SIM_PAYLOAD, 'name': 'TEST_it2_optpers'})
                sid = r.json()['id']
                opt_a = {'budget': 0, 'policy': 'business-priority', 'strategies': ['priority', 'supplier']}
                r1 = await c.post(f'/api/scenarios/{sid}/optimize', json=opt_a)
                assert r1.status_code == 200
                a = r1.json()
                assert a['optimization_options']['budget'] == 0
                assert a['optimization_options']['strategies'] == ['priority', 'supplier']
                assert a['selected_plan'] is None
                # Select priority plan
                priority_plan = next(p for p in a['plans'] if p['id'] == 'priority')
                r_sel = await c.post(f'/api/scenarios/{sid}/select', json={'plan_id': priority_plan['id']})
                assert r_sel.status_code == 200
                assert r_sel.json()['selected_plan'] == 'priority'
                # Re-optimize with different options
                opt_b = {'budget': 200000, 'policy': 'urgency', 'strategies': ['inventory', 'rerouting']}
                r2 = await c.post(f'/api/scenarios/{sid}/optimize', json=opt_b)
                b = r2.json()
                assert b['optimization_options']['budget'] == 200000
                assert b['optimization_options']['strategies'] == ['inventory', 'rerouting']
                assert b['selected_plan'] is None  # reset on re-optimize
                # Fetching the scenario fresh returns the persisted options
                r3 = await c.get(f'/api/scenarios/{sid}')
                assert r3.json()['optimization_options']['budget'] == 200000
        _run(go())

    def test_sample_optimize_returns_options_in_doc(self):
        async def go():
            async with _client_for(VIEWER) as c:
                # sample endpoints don't require auth but client works either way
                payload = {
                    'scenario': {'name': 'TEST_it2_sample_opt', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]},
                    'options': {'budget': 0, 'policy': 'business-priority', 'strategies': ['priority', 'supplier']},
                }
                r = await c.post('/api/sample/optimize', json=payload)
                data = r.json()
                assert data['optimization_options']['budget'] == 0
                assert data['optimization_options']['strategies'] == ['priority', 'supplier']
                # Only two plans produced for selected strategies
                plan_ids = sorted(p['id'] for p in data['plans'])
                assert plan_ids == ['priority', 'supplier']
        _run(go())


# ---------------------------------------------------------------------
# D. Selected-plan sample report validation (CSV/PDF)
# ---------------------------------------------------------------------
BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')


class TestSelectedPlanReports:
    def test_sample_report_with_valid_selected_plan_csv(self):
        import requests
        payload = {
            'scenario': {'name': 'TEST_it2_sel_csv', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]},
            'options': {'budget': 150000, 'strategies': ['supplier', 'priority']},
            'selected_plan': 'supplier',
        }
        r = requests.post(f'{BASE_URL}/api/sample/report/csv', json=payload)
        assert r.status_code == 200
        rows = list(csv.reader(io.StringIO(r.content.decode('utf-8-sig'))))
        sel_rows = [row for row in rows if row and row[0] == 'Selected recovery plan']
        assert sel_rows and sel_rows[0][1] and sel_rows[0][1] != 'Not selected'
        # headers include a filename
        cd = r.headers.get('content-disposition', '')
        assert 'syntrix-scenario-report.csv' in cd

    def test_sample_report_with_valid_selected_plan_pdf(self):
        import requests
        payload = {
            'scenario': {'name': 'TEST_it2_sel_pdf', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]},
            'options': {'budget': 150000, 'strategies': ['supplier']},
            'selected_plan': 'supplier',
        }
        r = requests.post(f'{BASE_URL}/api/sample/report/pdf', json=payload)
        assert r.status_code == 200
        assert r.headers['content-type'].startswith('application/pdf')
        assert r.content[:4] == b'%PDF'
        cd = r.headers.get('content-disposition', '')
        assert 'syntrix-scenario-report.pdf' in cd

    def test_sample_report_bogus_selected_plan_422(self):
        import requests
        payload = {
            'scenario': {'name': 'TEST_it2_bogus', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]},
            'options': {'budget': 150000, 'strategies': ['supplier']},
            'selected_plan': 'plan-does-not-exist',
        }
        r_pdf = requests.post(f'{BASE_URL}/api/sample/report/pdf', json=payload)
        r_csv = requests.post(f'{BASE_URL}/api/sample/report/csv', json=payload)
        assert r_pdf.status_code == 422
        assert r_csv.status_code == 422

    def test_sample_report_infeasible_selected_plan_422(self):
        import requests
        # Overlapping procurement requests compete for the same supplier overtime.
        payload = {
            'scenario': {'name': 'TEST_it2_infeas', 'disruptions': [
                {'type': 'supplier_failure', 'target': 'S2'},
                {'type': 'supplier_failure', 'target': 'S2'}
            ]},
            'options': {'budget': 150000, 'strategies': ['supplier']},
            'selected_plan': 'supplier',
        }
        optimized = requests.post(f'{BASE_URL}/api/sample/optimize', json=payload)
        assert optimized.status_code == 200
        assert optimized.json()['plans'][0]['feasibility']['feasible'] is False
        r = requests.post(f'{BASE_URL}/api/sample/report/pdf', json=payload)
        assert r.status_code == 422

    def test_sample_report_invalid_format_422(self):
        import requests
        payload = {'scenario': {'name': 'TEST_it2_fmt', 'disruptions': [{'type': 'supplier_failure', 'target': 'S2'}]}}
        r = requests.post(f'{BASE_URL}/api/sample/report/xml', json=payload)
        assert r.status_code == 422


# ---------------------------------------------------------------------
# E. Transport delay propagation offsets
# ---------------------------------------------------------------------
class TestTransportDelayPropagation:
    def test_arrival_day_offset_grows_with_severity(self):
        network = synthetic_network()
        low = ScenarioInput(name='TEST_tdelay low', disruptions=[Disruption(type='transport_delay', target='L1', severity=20, start_day=3, duration=5)])
        high = ScenarioInput(name='TEST_tdelay high', disruptions=[Disruption(type='transport_delay', target='L1', severity=100, start_day=3, duration=5)])
        p_low = propagate(network, low)
        p_high = propagate(network, high)
        # Both should include a path for the origin node and extra lead time added to arrival_day
        low_days = [row['arrival_day'] for row in p_low['paths']]
        high_days = [row['arrival_day'] for row in p_high['paths']]
        assert low_days and high_days
        # Higher severity adds more lead time → equal or later arrival days
        assert max(high_days) >= max(low_days)

    def test_canonical_outcomes_unchanged(self):
        from engine import run_scenario
        from seed import canonical_scenario
        res = run_scenario(synthetic_network(), canonical_scenario())
        assert res['baseline']['kpis']['service_level'] == 100
        assert abs(res['disrupted']['kpis']['service_level'] - 92.15) < 0.5
        assert abs(res['disrupted']['conservation_error']) < 1e-3
