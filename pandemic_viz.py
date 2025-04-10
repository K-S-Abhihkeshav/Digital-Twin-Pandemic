import base64
from mesa.visualization.modules import CanvasGrid
from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.modules import ChartModule

from mesa import Model, Agent
from mesa.space import MultiGrid
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector
import random
import math
import numpy as np
from mesa.visualization.ModularVisualization import VisualizationElement

# Import TensorFlow/Keras to load models
from tensorflow.keras.models import load_model
from tensorflow.nn import softmax

# Load your ML models (ensure the .h5 files are in your working directory)
parameter_model = load_model("./parameter_model.keras")
health_time_series_model = load_model("./health_time_series_model.keras")

def image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

human_image = image_to_base64("human.png")
heart_image = image_to_base64("heart.png")
lungs_image = image_to_base64("lungs.png")
artery_image = image_to_base64("artery.png")


# Define a softmax function to convert raw regression outputs to probabilities
# def softmax(x):
#     e_x = np.exp(x - np.max(x))
#     return e_x / e_x.sum()

# One-hot encoder for health state for the health_time_series_model.
# Expected order for the health_time_series_model is: chronic, critical, healthy, infected.
state_encoder = {
    'chronic':  [1, 0, 0, 0],
    'critical': [0, 1, 0, 0],
    'healthy': [0, 0, 1, 0],
    'infected':  [0, 0, 0, 1]
}

# state_to_target = {
#     'healthy':  [1, 0, 0, 0],
#     'infected': [0, 1, 0, 0],
#     'critical': [0, 0, 1, 0],
#     'chronic':  [0, 0, 0, 1]
# }

# Order of states as output by the parameter_model (logits in this order)
states_order_param = ["healthy", "infected", "critical", "chronic"]

def encode_state(state):
    encoding = [0] * len(states_order_param)
    encoding[states_order_param.index(state)] = 1
    return encoding
# states_order_health = ["chronic", "critical", "healthy", "infected"]

# Constants for modifying logits
VACCINE_PENALTY = 1.0       # subtract from infected logit if vaccinated
INFECTED_NEIGHBOR_BONUS = 0.5  # add per infected neighbor

# Simple death thresholds based on predicted health parameters
def check_death(agent):
    # Example thresholds: if blood pressure or heart rate fall below safe limits, mark as dead.
    if agent.is_dead == False and (agent.critical_steps > 5 or agent.health_history[-1][0] <= 60 or agent.health_history[-1][0] >= 160 or agent.health_history[-1][1] >= 105 or agent.health_history[-1][1] <= 93 or agent.health_history[-1][2] >= 30 or agent.health_history[-1][2] <= 7 or agent.health_history[-1][3] <= 25 or agent.health_history[-1][3] >= 120):
        agent.is_dead = True
        agent.state = "dead"
        agent.critical_steps = 0
        print(agent.health_history[-1])
        agent.set_dead_vitals()

class AgentDetailElement(VisualizationElement):
    local_includes = ["AgentDetailElement.js"]  # Must match actual file name

    def __init__(self):
        super().__init__()
        self.name = "AgentDetailElement"
        self.js_code = "elements.push(new AgentDetailElement());"

    def render(self, model):
        # Return a simple dict so we can see changes each step
        #print("hello")
        return model.get_agent_details()

class Person(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.is_vaccinated = False
        self.critical_steps = 0
        self.critical_delay = 0
        self.is_dead = False
        self.infected_timer = 0

        if unique_id != 0:
            self.state = random.choice(["healthy", "infected", "critical", "chronic"])
            self.health_history = [
                np.array([
                    random.uniform(80,140),   # Blood Pressure
                    random.uniform(95.0, 103), # Temperature
                    random.uniform(8,23),     # Respiratory Rate
                    random.uniform(50,110)      # Heart Rate
                ]) for _ in range(5)
            ]
        
        else:
            self.state = "critical"
            self.health_history = [np.array([145, 104, 24, 115.0]) for _ in range(5)]

    def move(self):
        if self.is_dead:
            return
        x, y = self.pos
        possible_moves = [
            (x + dx, y + dy) for dx in [-1, 0, 1] for dy in [-1, 0, 1]
            if (dx != 0 or dy != 0)
            and 0 <= x + dx < self.model.grid.width
            and 0 <= y + dy < self.model.grid.height
        ]
        # Filter out positions that contain a Wall
        filtered_moves = [
            pos for pos in possible_moves
            if not any(isinstance(obj, Wall) for obj in self.model.grid.get_cell_list_contents(pos))
        ]
        if filtered_moves:
            new_position = self.random.choice(filtered_moves)
            self.model.grid.move_agent(self, new_position)

    def count_infected_neighbors(self):
        neighbors = self.model.grid.get_neighbors(self.pos, moore=True, include_center=False)
        return sum(1 for n in neighbors if isinstance(n, Person) and n.state == "infected")

    @staticmethod
    def batch_update_health_state(agents):
        seq_flat_batch = []
        infected_neighbors_batch = []
        vaccinated_batch = []

        # Collect initial data (except state encoding)
        for agent in agents:
            seq_length = min(len(agent.health_history), 20)
            seq = agent.health_history[-seq_length:]
            # if len(seq) < 5:
            #     seq = [seq[0]] * (5 - len(seq)) + seq
            seq_flat_batch.append(seq)
            infected_neighbors_batch.append(agent.count_infected_neighbors())
            vaccinated_batch.append(agent.is_vaccinated)
        # print("seq_flat_batch")
        # print(seq_flat_batch)
        seq_flat_batch = np.array(seq_flat_batch)
        infected_neighbors_batch = np.array(infected_neighbors_batch)
        vaccinated_batch = np.array(vaccinated_batch)

        # print("seq_flat_batch")
        # print(seq_flat_batch)
        # print("infected_neighbors_batch")
        # print(infected_neighbors_batch)
        # print("vaccinated_batch")
        # print(vaccinated_batch)
        # Step 1: Parameter model prediction
        parameter_logits_batch = parameter_model.predict(seq_flat_batch, verbose=0)
        
        # Adjust logits based on vaccination and infected neighbors
        for i, logits in enumerate(parameter_logits_batch):
            logits[1] += INFECTED_NEIGHBOR_BONUS * infected_neighbors_batch[i]  # Increase infected logit
            if vaccinated_batch[i]:
                logits[1] -= VACCINE_PENALTY  # Decrease infected logit if vaccinated
            parameter_logits_batch[i] = logits

        # Apply softmax to logits and determine the chosen state
        # print("parameter_logits_batch")
        # print(parameter_logits_batch)
        probs_batch = softmax(parameter_logits_batch, axis=1)
        # print("probs_batch")
        # print(probs_batch)
        probs_batch = probs_batch.numpy()
        probs_batch = probs_batch / np.sum(probs_batch, axis=1, keepdims=True)  # Ensure sum to 1
        # print("probs_batch")
        # print(probs_batch)
        if len(agents) == 1:
            chosen_states = [states_order_param[np.argmax(probs_batch[0])]]
        else:
            chosen_states = [np.random.choice(states_order_param, p=probs) for probs in probs_batch]

        # Step 2: Update agent states based on chosen states
        encoder_vector_batch = []
        for i, agent in enumerate(agents):
            agent.state = chosen_states[i]
            # if(agent.infected_timer > 4):
            #     agent.state = "critical"
            #     agent.infected_timer -= 1
            # elif(agent.state == "infected"):
            #     agent.infected_timer += 1 
            # else:
            #     agent.infected_timer = 0
            encoder_vector_batch.append(encode_state(agent.state))

        encoder_vector_batch = np.array(encoder_vector_batch)
        # print("encoder_vector_batch")
        # print(encoder_vector_batch)

        # Step 3: Health time series model prediction using updated states
        predicted_params_batch = health_time_series_model.predict([seq_flat_batch, encoder_vector_batch], verbose=0)

        # print("predicted_params_batch")
        # print(predicted_params_batch)
        # Step 4: Update agent health history and check for death
        for i, agent in enumerate(agents):
            agent.health_history.append(predicted_params_batch[i])
            
            # Check for death based on updated health parameters
            check_death(agent)

    def set_dead_vitals(self):
        self.health_history.append(np.array([0, 82, 0, 0]))

    def step(self):
        # check values of human to see if they are dead
        if self.state == "critical":
            self.critical_steps += 1
            # self.health_history[-1][1] += 0.4  # Increase temperature
            # self.critical_delay = 0
        # elif self.critical_delay < 3:
        #     self.critical_delay += 1
        else:
            self.critical_steps = 0  # reset if not critical
            # self.critical_delay = 0

        # Check if the person has been critical for more than 3 steps
        # 145, 104, 24, 115.0
        if self.is_dead:
            return
        cellmates = self.model.grid.get_cell_list_contents(self.pos)
        if any(isinstance(a, Hospital) for a in cellmates):
            self.is_vaccinated = True
        self.move()


class Hospital(Agent):
    """A hospital where people can get vaccinated."""
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)

class Wall(Agent):
    """A hospital where people can get vaccinated."""
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)

def create_enclosure(x1, y1, x2, y2, gate_positions=None):
    walls = []
    gate_positions = gate_positions or []

    # Left and right walls
    for y in range(y1, y2 + 1):
        if (x1, y) not in gate_positions:
            walls.append((x1, y))
        if (x2, y) not in gate_positions:
            walls.append((x2, y))

    # Top and bottom walls
    for x in range(x1 + 1, x2):
        if (x, y1) not in gate_positions:
            walls.append((x, y1))
        if (x, y2) not in gate_positions:
            walls.append((x, y2))

    return walls


class PandemicModel(Model):
    def __init__(self, width, height, N, num_hospitals=3):
        self.grid = MultiGrid(width, height, torus=False)
        self.schedule = RandomActivation(self)
        gate_positions = [
            (10, 13),  
            (7, 11),   
            (13, 10),  
        ]

        wall_positions = create_enclosure(7, 9, 13, 13, gate_positions)

        for idx, pos in enumerate(wall_positions):
            wall = Wall(f"W{idx}", self)
            self.grid.place_agent(wall, pos)

        for i in range(num_hospitals):
            x, y = self.grid.find_empty()
            hospital = Hospital(f"H{i}", self)
            self.grid.place_agent(hospital, (x, y))
            self.schedule.add(hospital)

        for i in range(N):
            person = Person(i, self)
            # if random.random() < 0.05:
            #     person.state = "infected"
            x, y = self.grid.find_empty()
            self.grid.place_agent(person, (x, y))
            self.schedule.add(person)

        self.datacollector = DataCollector({
            "Healthy": lambda m: sum(1 for a in m.schedule.agents if isinstance(a, Person) and a.state == "healthy" and not a.is_dead),
            "Infected": lambda m: sum(1 for a in m.schedule.agents if isinstance(a, Person) and a.state == "infected" and not a.is_dead),
            "Critical": lambda m: sum(1 for a in m.schedule.agents if isinstance(a, Person) and a.state == "critical" and not a.is_dead),
            "Chronic": lambda m: sum(1 for a in m.schedule.agents if isinstance(a, Person) and a.state == "chronic" and not a.is_dead),
            "Vaccinated": lambda m: sum(1 for a in m.schedule.agents if isinstance(a, Person) and a.is_vaccinated),
            "Dead": lambda m: sum(1 for a in m.schedule.agents if isinstance(a, Person) and a.is_dead)
        })

    def step(self):
        self.schedule.step()
        active_agents = [a for a in self.schedule.agents if isinstance(a, Person) and not a.is_dead]
        if active_agents:
            Person.batch_update_health_state(active_agents)
        self.datacollector.collect(self)
    
    def get_agent_details(self):
        details = {}
        for agent in self.schedule.agents:
            if isinstance(agent, Person):
                details[agent.unique_id] = {
                    "state": agent.state,
                    "vaccinated": agent.is_vaccinated,
                    "dead": agent.is_dead,
                    "current health": [x.tolist() for x in agent.health_history[-1]],  # converts to native types
                    "position": agent.pos,
                    "human": human_image,
                    "lungs": lungs_image,
                    "heart": heart_image,
                    "artery": artery_image,
                }
        #print("get_agent_details called:", details)  # Debug statement
        return details

def agent_portrayal(agent):
    if isinstance(agent, Hospital):
        return {"Shape": "rect", "Color": "white", "Filled": True, "w": 0.8, "h": 0.8,
                "Layer": 0, "text": "H", "text_color": "black"}
    elif isinstance(agent, Wall):
        return {"Shape": "rect", "Color": "gray", "Filled": True, "w": 1.0, "h": 1.0,
            "Layer": 0, "text": "X", "text_color": "white"}
    elif isinstance(agent, Person):
        # Dead agents get a distinct color regardless of health state.
        if agent.is_dead:
            color = "gray"
        elif agent.state == "infected":
            color = "red"
        # Vaccinated agents get a special color.
        elif agent.is_vaccinated:
            color = "pink"
        else:
            if agent.state == "healthy":
                color = "green"
            elif agent.state == "critical":
                color = "orange"
            elif agent.state == "chronic":
                color = "purple"
            else:
                color = "gray"
        return {"Shape": "circle", "Color": color, "Filled": True, "r": 0.8,
                "Layer": 1, "text": str(agent.unique_id), "text_color": "white", "id": agent.unique_id}
    return {}

grid = CanvasGrid(agent_portrayal, 20, 20, 500, 500)

chart = ChartModule([
    {"Label": "Healthy", "Color": "green"},
    {"Label": "Infected", "Color": "red"},
    {"Label": "Critical", "Color": "orange"},
    {"Label": "Chronic", "Color": "purple"},
    {"Label": "Vaccinated", "Color": "pink"},
    {"Label": "Dead", "Color": "gray"},
])

agent_detail = AgentDetailElement()
server = ModularServer(
    PandemicModel,
    [grid, chart, agent_detail],
    "Pandemic Digital Twin with ML, Vaccination, & Death",
    {"width": 20, "height": 20, "N": 30, "num_hospitals": 3}
)
server.port = 8526
server.launch()
