import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Response
from starlette.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / '.env')
from models import Network, ScenarioInput, ScenarioDocument, OptimizationInput, SampleOptimize, SelectPlan
from auth import require, auth_status
from seed import synthetic_network, canonical_scenario
from engine import run_scenario, generate_strategies, criticality, bottlenecks, validate_network
from reports import export_csv, export_pdf

logging.basicConfig(level=logging.INFO)
client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]
network = synthetic_network()
sample = None


def compute(config, options=None):
    try:
        data = run_scenario(network, config)
        if options:
            data['plans'] = generate_strategies(network, config, options)
            data['optimization_options'] = options
        return data
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@asynccontextmanager
async def lifespan(app):
    global network, sample
    await db.networks.update_one({'_id': network.id}, {'$setOnInsert': network.to_mongo()}, upsert=True)
    network = Network.from_mongo(await db.networks.find_one({'_id': network.id}))
    await db.scenarios.create_index([('owner_id', 1), ('created_at', -1)])
    sample = ScenarioDocument(id='sample-s2', owner_id='sample', **await run_in_threadpool(compute, canonical_scenario(), OptimizationInput()))
    yield
    client.close()


app = FastAPI(title='Syntrix Resilience API', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.environ['CORS_ORIGINS'].split(','), allow_credentials=True, allow_methods=['GET','POST','DELETE'], allow_headers=['Content-Type','Authorization'])
api = APIRouter(prefix='/api')


@api.get('/')
async def health():
    return {'name': 'Syntrix', 'status': 'operational', 'model': 'deterministic-aggregate'}


@api.get('/auth/status')
async def provider_status():
    return await auth_status()


@api.get('/me')
async def me(user=Depends(require('read'))):
    return user


@api.get('/sample/workspace')
async def sample_workspace():
    return {'network': network.model_dump(), 'scenario': sample.model_dump(), 'criticality': criticality(network), 'bottlenecks': bottlenecks(network), 'validation': validate_network(network)}


@api.post('/sample/simulate')
async def sample_simulate(config: ScenarioInput):
    return ScenarioDocument(owner_id='sample', **await run_in_threadpool(compute, config)).model_dump()


@api.post('/sample/optimize')
async def sample_optimize(body: SampleOptimize):
    return ScenarioDocument(owner_id='sample', **await run_in_threadpool(compute, body.scenario, body.options)).model_dump()


@api.get('/network')
async def get_network(user=Depends(require('read'))):
    return network.model_dump()


class ScenarioRepository:
    def __init__(self, user):
        self.user = user

    async def get(self, scenario_id):
        doc = await db.scenarios.find_one({'_id': scenario_id, 'owner_id': self.user.id})
        if not doc:
            raise HTTPException(404, 'Scenario not found')
        return ScenarioDocument.from_mongo(doc)

    async def list(self):
        docs = await db.scenarios.find({'owner_id': self.user.id}).sort('created_at', -1).to_list(50)
        return [ScenarioDocument.from_mongo(doc).model_dump() for doc in docs]

    async def save(self, scenario):
        await db.scenarios.replace_one({'_id': scenario.id, 'owner_id': self.user.id}, scenario.to_mongo(), upsert=True)

    async def delete(self, scenario_id):
        await self.get(scenario_id)
        await db.scenarios.delete_one({'_id': scenario_id, 'owner_id': self.user.id})


@api.get('/scenarios')
async def list_scenarios(user=Depends(require('read'))):
    return await ScenarioRepository(user).list()


@api.post('/scenarios', status_code=201)
async def create_scenario(config: ScenarioInput, user=Depends(require('simulate'))):
    scenario = ScenarioDocument(owner_id=user.id, **await run_in_threadpool(compute, config))
    await ScenarioRepository(user).save(scenario)
    return scenario.model_dump()


@api.get('/scenarios/{scenario_id}')
async def get_scenario(scenario_id: str, user=Depends(require('read'))):
    return (await ScenarioRepository(user).get(scenario_id)).model_dump()


@api.post('/scenarios/{scenario_id}/optimize')
async def optimize(scenario_id: str, options: OptimizationInput, user=Depends(require('optimize'))):
    repo = ScenarioRepository(user)
    scenario = await repo.get(scenario_id)
    scenario.plans = await run_in_threadpool(generate_strategies, network, scenario.config, options)
    scenario.optimization_options = options
    scenario.selected_plan = None
    await repo.save(scenario)
    return scenario.model_dump()


@api.post('/scenarios/{scenario_id}/select')
async def select_plan(scenario_id: str, body: SelectPlan, user=Depends(require('select'))):
    repo = ScenarioRepository(user)
    scenario = await repo.get(scenario_id)
    plan = next((p for p in scenario.plans if p['id'] == body.plan_id), None)
    if not plan or not plan['feasibility']['feasible']:
        raise HTTPException(422, 'Select an existing feasible plan')
    scenario.selected_plan = body.plan_id
    await repo.save(scenario)
    return scenario.model_dump()


@api.delete('/scenarios/{scenario_id}', status_code=204)
async def delete_scenario(scenario_id: str, user=Depends(require('delete'))):
    await ScenarioRepository(user).delete(scenario_id)


def report_response(data, format):
    if format not in ('csv', 'pdf'):
        raise HTTPException(422, 'Supported report formats: csv, pdf')
    content = export_csv(data) if format == 'csv' else export_pdf(data)
    return Response(content, media_type='text/csv' if format == 'csv' else 'application/pdf', headers={'Content-Disposition': f'attachment; filename="syntrix-scenario-report.{format}"'})


@api.post('/sample/report/{format}')
async def sample_report(format: str, body: SampleOptimize):
    data = await run_in_threadpool(compute, body.scenario, body.options)
    if body.selected_plan:
        chosen = next((p for p in data['plans'] if p['id'] == body.selected_plan and p['feasibility']['feasible']), None)
        if not chosen:
            raise HTTPException(422, 'Selected plan is not available in this report')
        data['selected_plan'] = body.selected_plan
    return await run_in_threadpool(report_response, data, format)


@api.get('/scenarios/{scenario_id}/report/{format}')
async def scenario_report(scenario_id: str, format: str, user=Depends(require('export'))):
    data = (await ScenarioRepository(user).get(scenario_id)).model_dump()
    return await run_in_threadpool(report_response, data, format)


app.include_router(api)