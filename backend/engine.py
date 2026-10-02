"""Deterministic aggregate-equivalent-unit engine. No statistical or AI scores.

Products/BOMs are a descriptive catalogue. Physical flows conserve equivalent units;
this is not a per-SKU BOM explosion engine. Money is INR and time is whole days.
"""
from copy import deepcopy
from collections import defaultdict
import math
import networkx as nx
from ortools.linear_solver import pywraplp
from models import ScenarioInput


def graph_for(network, include_alternates=False):
    graph = nx.DiGraph()
    for node in network.nodes:
        graph.add_node(node.id, **node.model_dump(exclude={'id'}))
    for lane in network.lanes:
        if include_alternates or not lane.alternate:
            graph.add_edge(lane.source, lane.target, **lane.model_dump(exclude={'source', 'target'}), weight=lane.cost+lane.lead_time*10)
    return graph


# 01. Structural, reference and capacity validation.
def validate_network(network):
    errors, warnings = [], []
    ids = [n.id for n in network.nodes]
    if len(ids) != len(set(ids)):
        errors.append('Duplicate node IDs')
    if len({l.id for l in network.lanes}) != len(network.lanes):
        errors.append('Duplicate lane IDs')
    for lane in network.lanes:
        if lane.source not in ids or lane.target not in ids:
            errors.append(f'{lane.id}: broken node reference')
        if lane.source == lane.target:
            errors.append(f'{lane.id}: self-loop')
    if errors:
        return {'valid': False, 'errors': errors, 'warnings': warnings}
    graph = graph_for(network)
    if not nx.is_directed_acyclic_graph(graph):
        errors.append('Primary supply network contains a cycle')
    sources = [n.id for n in network.nodes if n.type == 'supplier']
    for node in network.nodes:
        if node.type == 'customer' and not any(nx.has_path(graph, source, node.id) for source in sources):
            errors.append(f'{node.id}: unreachable demand')
        outgoing = sum(l.capacity for l in network.lanes if l.source == node.id and not l.alternate)
        if outgoing > node.capacity and node.type != 'customer':
            warnings.append(f'{node.id}: lane capacity exceeds dispatch capacity; simulation enforces node capacity')
    for product in network.products:
        if product['supplier'] not in ids or any(b['quantity'] <= 0 for b in product['bom']):
            errors.append(f"{product['id']}: invalid supplier or BOM")
    return {'valid': not errors, 'errors': errors, 'warnings': warnings}


def validate_scenario(network, scenario):
    nodes = {n.id: n for n in network.nodes}
    lanes = {l.id for l in network.lanes}
    expected = {'supplier_failure': 'supplier', 'warehouse_outage': 'warehouse', 'production_reduction': 'manufacturer', 'demand_surge': 'customer'}
    for d in scenario.disruptions:
        if d.type in ('lane_closure', 'transport_delay'):
            if d.target not in lanes:
                raise ValueError(f'Unknown transport lane: {d.target}')
        elif d.target not in nodes:
            raise ValueError(f'Unknown node: {d.target}')
        elif d.type in expected and nodes[d.target].type != expected[d.type]:
            raise ValueError(f'{d.type} requires a {expected[d.type]} target')


# 02. Downstream traversal and shortest cumulative lead-time propagation.
def propagate(network, scenario):
    graph = graph_for(network)
    affected, origins, paths = set(), set(), []
    lane_map = {l.id: l for l in network.lanes}
    for disruption in scenario.disruptions:
        if disruption.severity == 0:
            continue
        origin = lane_map[disruption.target].target if disruption.target in lane_map else disruption.target
        origins.add(origin)
        lengths, routes = nx.single_source_dijkstra(graph, origin, weight='lead_time')
        for node_id, delay in lengths.items():
            affected.add(node_id)
            paths.append({'node': node_id, 'origin': origin, 'arrival_day': disruption.start_day+delay, 'path': routes[node_id]})
    customers = [n for n in network.nodes if n.id in affected and n.type == 'customer']
    return {'affected_nodes': sorted(affected), 'origins': sorted(origins), 'paths': paths,
            'affected_customers': len(customers), 'daily_demand_exposed': sum(n.daily_demand for n in customers),
            'affected_products': [p['id'] for p in network.products if p['supplier'] in affected],
            'explanation': 'Reachability is structural exposure, not a predicted stockout. Daily simulation accounts for inventory and shipment lead times.'}


# 03. Explainable topological criticality (not an AI score).
def criticality(network):
    graph = graph_for(network)
    centrality = nx.betweenness_centrality(graph, normalized=True)
    rows = []
    for node in network.nodes:
        downstream = nx.descendants(graph, node.id)
        demand = sum(n.daily_demand for n in network.nodes if n.id in downstream)
        alternatives = sum(1 for lane in network.lanes if lane.alternate and lane.target == node.id)
        rows.append({'id': node.id, 'name': node.name, 'type': node.type, 'location': node.location,
                     'downstream_nodes': len(downstream), 'demand_exposed': demand,
                     'betweenness': round(centrality[node.id], 5), 'alternatives': alternatives,
                     'explanation': f'{len(downstream)} downstream nodes depend on this node; {demand} units of daily demand are exposed.'})
    return sorted(rows, key=lambda n: (n['betweenness'], n['demand_exposed']), reverse=True)


# 04. Max-flow/min-cut with node splitting to enforce dispatch limits.
def bottlenecks(network):
    graph = nx.DiGraph()
    for node in network.nodes:
        graph.add_edge(node.id+':in', node.id+':out', capacity=node.capacity)
        if node.type == 'supplier':
            graph.add_edge('source', node.id+':in', capacity=node.capacity)
        if node.type == 'customer':
            graph.add_edge(node.id+':out', 'sink', capacity=node.daily_demand)
    for lane in network.lanes:
        if not lane.alternate:
            graph.add_edge(lane.source+':out', lane.target+':in', capacity=lane.capacity, lane_id=lane.id)
    flow, partition = nx.minimum_cut(graph, 'source', 'sink')
    left, right = partition
    cuts = [{'source': u.split(':')[0], 'target': v.split(':')[0], 'capacity': data['capacity'], 'lane_id': data.get('lane_id')}
            for u, v, data in graph.edges(data=True) if u in left and v in right]
    return {'max_daily_flow': flow, 'cut': cuts, 'daily_demand': sum(n.daily_demand for n in network.nodes)}


def active(disruption, day):
    return disruption.start_day <= day < disruption.start_day + disruption.duration


def daily_factors(scenario, day):
    factors, delays, surges = {}, {}, {}
    for d in scenario.disruptions:
        if not active(d, day):
            continue
        if d.type == 'transport_delay':
            delays[d.target] = max(delays.get(d.target, 0), math.ceil(d.severity/20))
        elif d.type == 'demand_surge':
            surges[d.target] = surges.get(d.target, 1)*(1+d.severity/100)
        else:
            factors[d.target] = factors.get(d.target, 1)*(1-d.severity/100)
    return factors, delays, surges


# 05. Integer supplier procurement with activation decisions and budget/capacity bounds.
def supplier_mip(network, scenario, budget):
    actions, logs = [], []
    node_map = {n.id: n for n in network.nodes}
    blocked = {d.target for d in scenario.disruptions if d.severity > 0}
    remaining = budget
    for d in scenario.disruptions:
        if d.type not in ('supplier_failure', 'capacity_reduction') or d.target not in node_map or node_map[d.target].type != 'supplier' or d.severity == 0:
            continue
        for lane in [l for l in network.lanes if l.source == d.target and not l.alternate]:
            need = math.ceil(node_map[d.target].capacity * .81 * d.severity/100)
            candidates = [l for l in network.lanes if l.target == lane.target and node_map[l.source].type == 'supplier' and l.source not in blocked]
            solver = pywraplp.Solver.CreateSolver('SCIP')
            solver.SetTimeLimit(2000)
            variables, costs = [], []
            for alt in candidates:
                cap = math.floor(node_map[alt.source].capacity*.75)
                units = solver.IntVar(0, cap, f'units_{alt.id}')
                enabled = solver.BoolVar(f'enable_{alt.id}')
                solver.Add(units <= cap*enabled)
                expense = units*(alt.cost+25)*d.duration + enabled*500
                variables.append((alt, units, enabled))
                costs.append(expense)
            if not variables:
                logs.append('No compatible alternate suppliers')
                continue
            shortage = solver.IntVar(0, need, 'uncovered_units')
            solver.Add(sum(v[1] for v in variables)+shortage == need)
            solver.Add(sum(costs) <= remaining)
            solver.Minimize(sum(costs)+shortage*1000000)
            status = solver.Solve()
            if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
                logs.append('Supplier procurement infeasible under budget')
                continue
            for alt, units, enabled in variables:
                quantity = round(units.solution_value())
                if quantity:
                    cost = quantity*(alt.cost+25)*d.duration+500
                    remaining -= cost
                    actions.append({'kind': 'supplier', 'source': alt.source, 'target': alt.target, 'lane': alt.id, 'quantity': quantity, 'start_day': d.start_day, 'duration': d.duration, 'cost': cost, 'description': f'Contract {quantity} extra units/day from {alt.source} with expedited lane capacity'})
            logs.append(f'SCIP: {need-round(shortage.solution_value())}/{need} lost daily units covered; budget constraint enforced')
    return actions, logs


# 06. Minimum-cost reserve inventory reallocation over real alternate lanes.
def inventory_flow(network, scenario, budget):
    impact = propagate(network, scenario)
    targets = [n for n in network.nodes if n.type == 'warehouse' and n.id in impact['affected_nodes'] and n.id != 'W5']
    if not targets:
        return [], ['No affected downstream warehouse with a reserve route']
    reserve = next(n for n in network.nodes if n.id == 'W5')
    graph = nx.DiGraph()
    graph.add_edge('source', 'W5', capacity=reserve.inventory, weight=0)
    start = min(d.start_day for d in scenario.disruptions)
    max_duration = max(d.duration for d in scenario.disruptions)
    for node in targets:
        lane = next((l for l in network.lanes if l.source == 'W5' and l.target == node.id), None)
        if lane:
            graph.add_edge('W5', node.id, capacity=min(lane.capacity*max_duration, node.capacity*2), weight=lane.cost)
            graph.add_edge(node.id, 'sink', capacity=node.capacity*2, weight=0)
    if 'sink' not in graph:
        return [], ['No reserve path exists']
    flow = nx.max_flow_min_cost(graph, 'source', 'sink', capacity='capacity', weight='weight')
    actions, remaining = [], budget
    for target, qty in flow['W5'].items():
        lane = next(l for l in network.lanes if l.source == 'W5' and l.target == target)
        qty = min(qty, remaining//lane.cost)
        if qty:
            cost = qty*lane.cost
            remaining -= cost
            actions.append({'kind': 'inventory', 'source': 'W5', 'target': target, 'lane': lane.id, 'quantity': qty, 'start_day': start, 'duration': max_duration, 'cost': cost, 'description': f'Transfer {qty} reserve units via {lane.id}; at most {lane.capacity} units/day'})
    return actions, ['Min-cost max-flow; finite reserve inventory and alternate-lane capacities enforced; budget-limited allocation']


# 07. Disruption-aware weighted shortest paths, no invented physical routes.
def reroute(network, scenario, budget):
    graph = graph_for(network, True)
    blocked = {d.target for d in scenario.disruptions if d.severity == 100 and d.type not in ('demand_surge', 'transport_delay')}
    for node_id in list(graph.nodes):
        if node_id in blocked:
            graph.remove_node(node_id)
    for source, target, data in list(graph.edges(data=True)):
        if data['id'] in blocked:
            graph.remove_edge(source, target)
    paths = []
    for target in propagate(network, scenario)['affected_nodes']:
        node = next(n for n in network.nodes if n.id == target)
        if node.type != 'customer' or target not in graph:
            continue
        candidates = []
        for source in [n.id for n in network.nodes if n.type == 'supplier' and n.id in graph]:
            try:
                path = nx.shortest_path(graph, source, target, weight='weight')
                candidates.append((nx.path_weight(graph, path, 'weight'), path))
            except nx.NetworkXNoPath:
                pass
        if candidates:
            weight, path = min(candidates)
            paths.append({'customer': target, 'path': path, 'weight': weight})
    # A route alone does not create supply: only existing alternate lanes are enabled.
    lanes = {graph[u][v]['id'] for item in paths for u, v in zip(item['path'], item['path'][1:]) if graph[u][v]['alternate']}
    actions, remaining = [], budget
    for lane_id in sorted(lanes):
        lane = next(l for l in network.lanes if l.id == lane_id)
        d = min(scenario.disruptions, key=lambda x: x.start_day)
        qty = min(lane.capacity, remaining//max(1, lane.cost*d.duration))
        if qty:
            cost = qty*lane.cost*d.duration
            actions.append({'kind': 'rerouting', 'source': lane.source, 'target': lane.target, 'lane': lane.id, 'quantity': qty, 'start_day': d.start_day, 'duration': d.duration, 'cost': cost, 'description': f'Enable alternate route {lane.source} to {lane.target}, up to {qty} units/day'})
            remaining -= cost
    return actions, paths


# 08. Deterministic fulfilment ordering.
def prioritize_orders(orders, policy):
    if policy == 'business-priority':
        return sorted(orders, key=lambda o: (o['priority'], o['due'], o['id']))
    if policy == 'service':
        return sorted(orders, key=lambda o: (o['remaining'], o['due'], o['id']))
    return sorted(orders, key=lambda o: (o['due'], o['priority'], o['id']))


# 10. Constraint validation for generated action sets.
def check_feasibility(network, actions, budget):
    violations, reserve_use, supplier_use = [], 0, defaultdict(int)
    nodes = {n.id: n for n in network.nodes}
    lanes = {l.id: l for l in network.lanes}
    if sum(a['cost'] for a in actions) > budget:
        violations.append('Recovery cost exceeds budget')
    for action in actions:
        lane = lanes.get(action['lane'])
        if not lane or lane.source != action['source'] or lane.target != action['target']:
            violations.append('Action references an unavailable lane')
            continue
        if action['kind'] == 'inventory':
            reserve_use += action['quantity']
            if action['quantity'] > lane.capacity*action['duration']:
                violations.append(f"{lane.id}: transfer cannot finish within its duration")
        elif action['kind'] == 'supplier':
            for day in range(action['start_day'], action['start_day']+action['duration']):
                supplier_use[(action['source'], day)] += action['quantity']
        elif action['quantity'] > lane.capacity:
            violations.append(f'{lane.id}: lane capacity exceeded')
    if reserve_use > nodes['W5'].inventory:
        violations.append('Reserve inventory insufficient')
    for (node_id, day), quantity in supplier_use.items():
        if quantity > math.floor(nodes[node_id].capacity*.75):
            violations.append(f'{node_id}: supplier overtime capacity exceeded on day {day}')
    return {'feasible': not violations, 'violations': violations, 'constraints': ['Recovery spend within budget', 'Reserve withdrawals limited to stock on hand', 'Supplier overtime limited to 75% of nominal capacity', 'Dispatch and lane capacities enforced each day', 'Shipments available only after lane lead time']}


# 11. Day-stepped physical flow, finite inventory and individual due-date order queues.
def simulate(network, scenario, actions=None, policy='urgency'):
    actions = actions or []
    nodes = {n.id: n for n in network.nodes}
    graph = graph_for(network)
    demand = {n.id: (n.daily_demand if n.type == 'customer' else sum(nodes[v].daily_demand for v in nx.descendants(graph, n.id))) for n in network.nodes}
    inventory = {n.id: float(n.inventory) for n in network.nodes}
    lanes = [l for l in network.lanes if not l.alternate or any(a['lane'] == l.id for a in actions)]
    shipments, orders, daily = [], [], []
    # Steady-state pipeline initialization prevents an artificial cold-start shortage.
    for lane in network.lanes:
        if lane.alternate:
            continue
        source = nodes[lane.source]
        if source.type == 'supplier':
            sources = [nodes[l.source].capacity for l in network.lanes if l.target == lane.target and not l.alternate]
            flow = demand[lane.target]*source.capacity/sum(sources)
        else:
            flow = demand[lane.target]
        for day in range(1, lane.lead_time+1):
            shipments.append({'target': lane.target, 'qty': min(flow, lane.capacity), 'arrival': day})
    initial_units = sum(inventory.values())+sum(s['qty'] for s in shipments)
    produced_total = fulfilled_total = ontime_total = demand_total = operating_cost = total_delay = 0.0
    completed_orders = delayed_orders = 0
    transfer_used = defaultdict(float)
    start_day = min(d.start_day for d in scenario.disruptions)
    for day in range(1, scenario.horizon+1):
        factors, delays, surges = daily_factors(scenario, day)
        day_actions = [a for a in actions if a['start_day'] <= day < a['start_day']+a['duration']]
        for shipment in shipments:
            if shipment['arrival'] == day:
                inventory[shipment['target']] += shipment['qty']
        shipments = [s for s in shipments if s['arrival'] > day]
        produced_today = 0
        for node in network.nodes:
            if node.type != 'supplier':
                continue
            target = next(l.target for l in network.lanes if l.source == node.id and not l.alternate)
            source_total = sum(nodes[l.source].capacity for l in network.lanes if l.target == target and not l.alternate)
            nominal = demand[target]*node.capacity/source_total
            extra = sum(a['quantity'] for a in day_actions if a['kind'] == 'supplier' and a['source'] == node.id)
            production = min(max(0, node.capacity*2-inventory[node.id]), nominal*factors.get(node.id, 1)+extra)
            inventory[node.id] += production
            produced_today += production
            operating_cost += production*120
        produced_total += produced_today
        requested_today = ontime_today = fulfilled_today = 0.0
        for node in network.nodes:
            if node.type == 'customer':
                quantity = node.daily_demand*surges.get(node.id, 1)
                orders.append({'id': f'{node.id}-{day}', 'customer': node.id, 'due': day, 'remaining': quantity, 'quantity': quantity, 'priority': node.priority})
                requested_today += quantity
        for order in prioritize_orders([o for o in orders if o['remaining'] > .0001], policy):
            customer = order['customer']
            quantity = min(inventory[customer], order['remaining'])
            inventory[customer] -= quantity
            order['remaining'] -= quantity
            fulfilled_today += quantity
            total_delay += quantity*(day-order['due'])
            if order['due'] == day:
                ontime_today += quantity
            if order['remaining'] <= .0001:
                completed_orders += 1
                if day > order['due']:
                    delayed_orders += 1
        demand_total += requested_today
        fulfilled_total += fulfilled_today
        ontime_total += ontime_today
        node_remaining = {n.id: n.capacity*factors.get(n.id, 1)+sum(a['quantity'] for a in day_actions if a['kind'] == 'supplier' and a['source'] == n.id) for n in network.nodes}
        backlog_by_customer = defaultdict(float)
        for order in orders:
            backlog_by_customer[order['customer']] += order['remaining']
        # Reserve transfers precede primary shipments; deliveries occur on a future day.
        # Dispatch downstream first so upstream replenishment sees today's withdrawals.
        # Otherwise a full warehouse suppresses replenishment immediately before it ships,
        # creating artificial alternating shortages in an undisrupted network.
        echelon_order = {node_id: i for i, node_id in enumerate(nx.topological_sort(graph))}
        ordered_lanes = sorted(lanes, key=lambda l: (l.source != 'W5', -echelon_order[l.source], nodes[l.target].priority if policy == 'business-priority' else 0, l.id))
        dispatched_today = 0
        for lane in ordered_lanes:
            lane_actions = [a for a in day_actions if a['lane'] == lane.id]
            if lane.alternate and not lane_actions:
                continue
            extra = sum(a['quantity'] for a in lane_actions if a['kind'] == 'supplier')
            capacity = lane.capacity*factors.get(lane.id, 1)+extra
            future = sum(s['qty'] for s in shipments if s['target'] == lane.target)
            wanted = max(0, demand[lane.target]*1.5+backlog_by_customer[lane.target]-inventory[lane.target]-future)
            transfer = next((a for a in lane_actions if a['kind'] == 'inventory'), None)
            if transfer:
                wanted = max(0, transfer['quantity']-transfer_used[lane.id])
            route = next((a for a in lane_actions if a['kind'] == 'rerouting'), None)
            if route:
                capacity = min(capacity, route['quantity'])
            quantity = min(inventory[lane.source], capacity, node_remaining[lane.source], wanted)
            if quantity <= .0001:
                continue
            inventory[lane.source] -= quantity
            node_remaining[lane.source] -= quantity
            dispatched_today += quantity
            if transfer:
                transfer_used[lane.id] += quantity
            shipments.append({'target': lane.target, 'qty': quantity, 'arrival': day+lane.lead_time+delays.get(lane.id, 0)})
            operating_cost += quantity*lane.cost
        backlog = sum(o['remaining'] for o in orders)
        cost = sum(a['cost'] for a in actions if a['start_day'] <= day)
        daily.append({'day': day, 'service_level': round(100*ontime_today/requested_today, 2) if requested_today else 100,
                      'cumulative_service': round(100*ontime_total/demand_total, 2), 'demand': round(requested_today, 2),
                      'fulfilled': round(fulfilled_today, 2), 'backlog': round(backlog, 2),
                      'inventory': round(sum(inventory.values()), 2), 'in_transit': round(sum(s['qty'] for s in shipments), 2),
                      'production': round(produced_today, 2), 'recovery_cost': cost,
                      'active_disruptions': sum(active(d, day) and d.severity > 0 for d in scenario.disruptions),
                      'node_inventory': {k: round(v, 2) for k, v in inventory.items()}})
    remaining_units = sum(inventory.values())+sum(s['qty'] for s in shipments)
    conservation_error = round(initial_units+produced_total-fulfilled_total-remaining_units, 5)
    kpis = calculate_kpis(daily, orders, ontime_total, fulfilled_total, demand_total, total_delay, delayed_orders, completed_orders, actions, operating_cost)
    kpis['recovery_days'] = recovery_time(daily, start_day, scenario.recovery_threshold, scenario.consecutive_days)
    return {'daily': daily, 'kpis': kpis, 'conservation_error': conservation_error,
            'model': 'Aggregate equivalent units; deterministic lead times; 1:1 production conversion; steady-state initial pipeline; recovery cost is contracted commitment, not actual marginal spend.'}


# 12. Recovery measured only after deterioration, sustained for a configurable window.
def recovery_time(daily, start_day, threshold=95, consecutive_days=3):
    impacted = [d['day'] for d in daily if d['day'] >= start_day and d['service_level'] < threshold]
    if not impacted:
        return 0
    last_bad = max(impacted)
    for index in range(last_bad, len(daily)-consecutive_days+1):
        window = daily[index:index+consecutive_days]
        if all(d['service_level'] >= threshold for d in window):
            return window[0]['day']-start_day
    return None


# 13. Metrics derived exclusively from simulation state and order fulfilment.
def calculate_kpis(daily, orders, ontime, fulfilled, demand, delay, delayed, completed, actions, operating_cost):
    unmet = sum(o['remaining'] for o in orders)
    return {'service_level': round(100*ontime/demand, 2) if demand else 100,
            'fulfillment_rate': round(100*fulfilled/demand, 2) if demand else 100,
            'unmet_demand': round(unmet, 2), 'delayed_orders': delayed+sum(o['remaining'] > .0001 for o in orders),
            'orders_at_risk': sum(o['remaining'] > .0001 for o in orders), 'total_orders': len(orders),
            'revenue_at_risk': round(unmet*850, 2), 'average_delay': round(delay/fulfilled, 2) if fulfilled else 0,
            'recovery_cost': sum(a['cost'] for a in actions), 'operating_cost': round(operating_cost, 2),
            'total_demand': round(demand, 2), 'fulfilled_units': round(fulfilled, 2),
            'peak_backlog': max(d['backlog'] for d in daily), 'minimum_service': min(d['service_level'] for d in daily),
            'perfect_order_rate': round(100*(completed-delayed)/len(orders), 2) if orders else 100}


# 09. Feasible strategy generation, evaluated through the same simulator as the baseline.
def generate_strategies(network, scenario, options):
    supplier, supplier_logs = supplier_mip(network, scenario, options.budget)
    inventory, inventory_logs = inventory_flow(network, scenario, options.budget)
    routing, paths = reroute(network, scenario, options.budget)
    combined_supplier, _ = supplier_mip(network, scenario, options.budget)
    left = options.budget-sum(a['cost'] for a in combined_supplier)
    combined_inventory, _ = inventory_flow(network, scenario, left)
    definitions = {
        'supplier': ('Alternative sourcing', 'Mixed-integer optimization', supplier, supplier_logs),
        'inventory': ('Inventory reallocation', 'Minimum-cost flow', inventory, inventory_logs),
        'rerouting': ('Logistics rerouting', 'Dijkstra shortest paths', routing, [f'{len(paths)} reachable customer routes identified']),
        'priority': ('Order prioritization', 'Deterministic order policy', [], [f'Allocation policy: {options.policy}; no extra physical capacity']),
        'combined': ('Combined recovery', 'Sourcing + reserve allocation', combined_supplier+combined_inventory, ['Supplier procurement first; remaining budget allocated to reserve flow']),
    }
    plans = []
    for key in dict.fromkeys(options.strategies):
        title, method, actions, logs = definitions[key]
        feasible = check_feasibility(network, actions, options.budget)
        simulation = simulate(network, scenario, actions, options.policy if key in ('priority', 'combined') else 'urgency')
        plans.append({'id': key, 'name': title, 'method': method, 'actions': actions, 'solver_log': logs,
                      'feasibility': feasible, 'budget': options.budget, 'paths': paths if key == 'rerouting' else [],
                      'result': simulation, 'applicable': bool(actions) or key == 'priority'})
    return pareto_compare(plans)


# 14. Non-dominated set and normalized, explainable priority recommendation.
def pareto_compare(plans, priority='balanced'):
    feasible = [p for p in plans if p['feasibility']['feasible']]
    def vector(plan):
        k = plan['result']['kpis']
        return (k['recovery_cost'], -k['service_level'], k['recovery_days'] if k['recovery_days'] is not None else 1000, k['unmet_demand'])
    for plan in plans:
        v = vector(plan)
        plan['pareto'] = plan in feasible and not any(all(a <= b for a, b in zip(vector(other), v)) and any(a < b for a, b in zip(vector(other), v)) for other in feasible)
        plan['recommended'] = False
    if feasible:
        vectors = [vector(p) for p in feasible]
        lows = [min(v[i] for v in vectors) for i in range(4)]
        highs = [max(v[i] for v in vectors) for i in range(4)]
        weights = {'cost': [1,0,0,0], 'service': [0,1,0,0], 'speed': [0,0,1,0], 'balanced': [.25,.35,.2,.2]}[priority]
        def score(plan):
            return sum(weights[i]*(v-lows[i])/(highs[i]-lows[i] or 1) for i, v in enumerate(vector(plan)))
        chosen = min(feasible, key=lambda p: (score(p), vector(p)[1], vector(p)[0]))
        chosen['recommended'] = True
        chosen['recommendation_reason'] = f'Best {priority} trade-off across feasible plans. Balanced weights: service 35%, cost 25%, recovery time 20%, unmet demand 20%.'
    return plans


def run_scenario(network, config):
    validate_scenario(network, config)
    baseline_config = config.model_copy(deep=True)
    for d in baseline_config.disruptions:
        d.severity = 0
    return {'config': config.model_dump(), 'impact': propagate(network, config),
            'baseline': simulate(network, baseline_config), 'disrupted': simulate(network, config),
            'plans': [], 'selected_plan': None}
