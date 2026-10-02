from models import Network, Node, Lane, ScenarioInput, Disruption


def synthetic_network():
    nodes, lanes = [], []
    suppliers = [
        ('Apex Components', 'Pune', 'West'), ('Bharat Semiconductors', 'Bengaluru', 'South'), ('Precision Metals', 'Nashik', 'West'),
        ('Nordic Electronics', 'Chennai', 'South'), ('Vertex Polymers', 'Coimbatore', 'South'), ('Indus Materials', 'Hosur', 'South'),
        ('Atlas Industrial', 'Gurugram', 'North'), ('Delta Microtech', 'Noida', 'North'), ('Nova Packaging', 'Jaipur', 'North'),
        ('Eastern Circuits', 'Kolkata', 'East'), ('Unity Composites', 'Bhubaneswar', 'East'), ('Pacific Parts', 'Jamshedpur', 'East')]
    for i, (name, city, region) in enumerate(suppliers):
        nodes.append(Node(id=f'S{i+1}', name=name, type='supplier', location=city, region=region, capacity=[60, 140, 60][i % 3], inventory=0))
        lanes.append(Lane(id=f'L{len(lanes)+1}', source=f'S{i+1}', target=f'M{i//3+1}', capacity=[60, 140, 60][i % 3], cost=12+i % 4*3, lead_time=1, distance=180+i*23))
    for i, (city, region) in enumerate([('Pune', 'West'), ('Chennai', 'South'), ('Manesar', 'North'), ('Kolkata', 'East')]):
        nodes.append(Node(id=f'M{i+1}', name=f'{city} Assembly', type='manufacturer', location=city, region=region, capacity=240, inventory=105))
        nodes.append(Node(id=f'W{i+1}', name=f'{city} Distribution', type='warehouse', location=city, region=region, capacity=240, inventory=105))
        lanes.append(Lane(id=f'L{len(lanes)+1}', source=f'M{i+1}', target=f'W{i+1}', capacity=240, cost=18, lead_time=1, distance=75+i*15))
    nodes.append(Node(id='W5', name='Nagpur Reserve Hub', type='warehouse', location='Nagpur', region='Central', capacity=300, inventory=900))
    cities = ['Mumbai', 'Ahmedabad', 'Surat', 'Bengaluru', 'Hyderabad', 'Kochi', 'Delhi', 'Lucknow', 'Chandigarh', 'Patna', 'Ranchi', 'Guwahati']
    for i, city in enumerate(cities):
        group = i // 3
        nodes.append(Node(id=f'C{i+1}', name=f'{city} Retail', type='customer', location=city, region=['West','South','North','East'][group], capacity=100, inventory=140, daily_demand=70, priority=i % 3+1))
        lanes.append(Lane(id=f'L{len(lanes)+1}', source=f'W{group+1}', target=f'C{i+1}', capacity=85, cost=20+i % 3*4, lead_time=1, distance=100+i*35))
    for i in range(4):
        lanes.append(Lane(id=f'L{len(lanes)+1}', source='W5', target=f'W{i+1}', capacity=120, cost=40+i*5, lead_time=1, distance=500+i*90, alternate=True))
        lanes.append(Lane(id=f'L{len(lanes)+1}', source=f'S{i*3+1}', target=f'M{(i+1)%4+1}', capacity=45, cost=35, lead_time=2, distance=750, alternate=True))
    products = [{'id': f'P{i+1:02}', 'name': f'{["Control module", "Sensor assembly", "Power unit", "Circuit board", "Display module", "Actuator"][i%6]} {100+i}', 'family': ['Industrial','Consumer','Automotive','Electronics'][i//6], 'unit_value': 850+i*25, 'supplier': f'S{i%12+1}', 'bom': [{'component': f'R{i%12+1}', 'quantity': 1}]} for i in range(24)]
    return Network(id='synthetic-network-v1', name='India Manufacturing Network', nodes=nodes, lanes=lanes, products=products)


def canonical_scenario():
    return ScenarioInput(name='Supplier S2 · 7-day shutdown', disruptions=[Disruption()])
