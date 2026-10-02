from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal
from uuid import uuid4
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

PyObjectId = Annotated[str, BeforeValidator(str)]


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: PyObjectId = Field(default_factory=lambda: str(uuid4()), alias='_id')

    def to_mongo(self):
        return self.model_dump(mode='json', by_alias=True)

    @classmethod
    def from_mongo(cls, doc):
        return cls.model_validate(doc)


class Role(str, Enum):
    ADMIN = 'ADMIN'
    ANALYST = 'ANALYST'
    VIEWER = 'VIEWER'


class Principal(BaseModel):
    id: str
    email: str
    role: Role


class Node(BaseModel):
    id: str
    name: str
    type: Literal['supplier', 'manufacturer', 'warehouse', 'customer']
    location: str
    region: str
    capacity: int = Field(ge=0)
    inventory: int = Field(ge=0)
    daily_demand: int = Field(default=0, ge=0)
    priority: int = Field(default=2, ge=1, le=3)
    unit_value: int = Field(default=850, ge=0)
    status: str = 'operational'


class Lane(BaseModel):
    id: str
    source: str
    target: str
    capacity: int = Field(ge=0)
    cost: int = Field(ge=0)
    lead_time: int = Field(ge=1)
    distance: int = Field(ge=0)
    mode: str = 'Road'
    alternate: bool = False


class Network(BaseDocument):
    name: str
    nodes: list[Node]
    lanes: list[Lane]
    products: list[dict[str, Any]]
    seed: int = 42
    synthetic: bool = True


class Disruption(BaseModel):
    type: Literal['supplier_failure', 'capacity_reduction', 'lane_closure', 'transport_delay', 'warehouse_outage', 'demand_surge', 'production_reduction'] = 'supplier_failure'
    target: str = 'S2'
    start_day: int = Field(default=3, ge=1, le=90)
    duration: int = Field(default=7, ge=1, le=90)
    severity: int = Field(default=100, ge=0, le=100)


class ScenarioInput(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    disruptions: list[Disruption] = Field(min_length=1, max_length=5)
    horizon: int = Field(default=30, ge=7, le=90)
    recovery_threshold: int = Field(default=95, ge=50, le=100)
    consecutive_days: int = Field(default=3, ge=1, le=7)

    @model_validator(mode='after')
    def within_horizon(self):
        if any(d.start_day > self.horizon for d in self.disruptions):
            raise ValueError('Disruption must start within the simulation horizon')
        self.name = self.name.strip()
        if len(self.name) < 3:
            raise ValueError('Scenario name must contain at least 3 characters')
        return self


class OptimizationInput(BaseModel):
    budget: int = Field(default=150000, ge=0, le=100000000)
    policy: Literal['business-priority', 'urgency', 'service'] = 'business-priority'
    strategies: list[Literal['supplier', 'inventory', 'rerouting', 'priority', 'combined']] = Field(default_factory=lambda: ['supplier', 'inventory', 'rerouting', 'priority', 'combined'], min_length=1, max_length=5)


class SampleOptimize(BaseModel):
    scenario: ScenarioInput
    options: OptimizationInput = Field(default_factory=OptimizationInput)
    selected_plan: str | None = None


class ScenarioDocument(BaseDocument):
    owner_id: str
    config: ScenarioInput
    impact: dict
    baseline: dict
    disrupted: dict
    plans: list[dict] = Field(default_factory=list)
    optimization_options: OptimizationInput | None = None
    selected_plan: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SelectPlan(BaseModel):
    plan_id: str
