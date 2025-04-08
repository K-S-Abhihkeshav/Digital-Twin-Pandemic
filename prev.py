from mesa.visualization.modules import CanvasGrid
from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.modules import ChartModule

from mesa import Model, Agent
from mesa.space import MultiGrid
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector
import random
import math

class Person(Agent):
    """A person in the simulation who can move, get infected, recover, die, or get vaccinated."""
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.state = "healthy"  # Can be "healthy", "infected", "recovered", "dead", "vaccinated"
        self.infection_timer = 0
        self.vaccinated = False
        
        if random.random() < 0.1:  # 10% of people start vaccinated
            self.state = "vaccinated"
            self.vaccinated = True

    def move(self):
        """Move randomly within the grid while avoiding dead people and staying within bounds."""
        x, y = self.pos
        possible_moves = [(x + dx, y + dy) for dx in [-1, 0, 1] for dy in [-1, 0, 1]
                          if (dx != 0 or dy != 0) and 0 <= x + dx < self.model.grid.width and 0 <= y + dy < self.model.grid.height]
        valid_moves = [pos for pos in possible_moves if not any(isinstance(a, Person) and a.state == "dead" for a in self.model.grid.get_cell_list_contents(pos))]
        if valid_moves:
            new_position = self.random.choice(valid_moves)
            self.model.grid.move_agent(self, new_position)
    
    def step(self):
        """Execute one step in the simulation."""
        if self.state == "infected":
            self.infection_timer += 1
            if self.infection_timer > random.randint(8, 12):  # Recovery time varies
                if random.random() < 0.2:  # 20% mortality rate
                    self.state = "dead"
                else:
                    self.state = "recovered"
        
        if self.state == "healthy":
            neighbors = self.model.grid.get_neighbors(self.pos, moore=True, include_center=True)
            infected_neighbors = [n for n in neighbors if isinstance(n, Person) and n.state == "infected"]
            if infected_neighbors and random.random() < 0.3:  # 30% base infection chance
                self.state = "infected"
        
        if self.state == "recovered":
            reinfection_prob = math.exp(-self.infection_timer / 10)  # Exponentially decreasing reinfection probability
            neighbors = self.model.grid.get_neighbors(self.pos, moore=True, include_center=True)
            infected_neighbors = [n for n in neighbors if isinstance(n, Person) and n.state == "infected"]
            if infected_neighbors and random.random() < reinfection_prob:
                self.state = "infected"
        
        if self.state not in ["dead"]:
            self.move()
        
        # Check if the agent can visit a hospital
        if self.state in ["healthy", "recovered"] and any(isinstance(a, Hospital) for a in self.model.grid.get_cell_list_contents(self.pos)):
            self.state = "vaccinated"
            self.vaccinated = True

class Hospital(Agent):
    """A hospital where people can get vaccinated."""
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)

class PandemicModel(Model):
    """The main pandemic simulation model."""
    def __init__(self, width, height, N, num_hospitals=3):
        self.grid = MultiGrid(width, height, torus=False)
        self.schedule = RandomActivation(self)

        # Create hospitals
        for i in range(num_hospitals):
            x, y = self.grid.find_empty()
            hospital = Hospital(f"H{i}", self)
            self.grid.place_agent(hospital, (x, y))
            self.schedule.add(hospital)
        
        # Create agents
        for i in range(N):
            person = Person(i, self)
            if not person.vaccinated and random.random() < 0.05:  # 5% start infected
                person.state = "infected"
            x, y = self.grid.find_empty()
            self.grid.place_agent(person, (x, y))
            self.schedule.add(person)

        self.datacollector = DataCollector(
            {"Healthy": lambda m: self.count_state(m, "healthy"),
             "Infected": lambda m: self.count_state(m, "infected"),
             "Recovered": lambda m: self.count_state(m, "recovered"),
             "Dead": lambda m: self.count_state(m, "dead"),
             "Vaccinated": lambda m: self.count_state(m, "vaccinated")}
        )

    def count_state(self, model, state):
        return sum(1 for a in self.schedule.agents if isinstance(a, Person) and a.state == state)

    def step(self):
        self.datacollector.collect(self)
        self.schedule.step()


def agent_portrayal(agent):
    if isinstance(agent, Hospital):
        return {"Shape": "rect", "Color": "white", "Filled": True, "w": 0.8, "h": 0.8, "Layer": 0, "text": str("H"), "text_color": "black"}
    elif isinstance(agent, Person):
        if agent.state == "healthy":
            color = "green"
        elif agent.state == "infected":
            color = "red"
        elif agent.state == "recovered":
            color = "blue"
        elif agent.state == "vaccinated":
            color = "pink"
        else:
            color = "black"
        return {"Shape": "circle", "Color": color, "Filled": True, "r": 0.8, "Layer": 1, "text": str(agent.unique_id), "text_color": "white"}
    return {}


grid = CanvasGrid(agent_portrayal, 20, 20, 500, 500)

chart = ChartModule([
    {"Label": "Healthy", "Color": "green"},
    {"Label": "Infected", "Color": "red"},
    {"Label": "Recovered", "Color": "blue"},
    {"Label": "Dead", "Color": "black"},
    {"Label": "Vaccinated", "Color": "pink"},
])

server = ModularServer(PandemicModel, [grid, chart], "Pandemic Digital Twin", {"width": 20, "height": 20, "N": 100, "num_hospitals": 3})
server.port = 8521
server.launch()
