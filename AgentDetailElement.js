// AgentDetailElement.js
// Define a minimal VisualizationElement if not already defined.
//console.log("AgentDetailElement.js loaded");
if (typeof VisualizationElement === "undefined") {
    function VisualizationElement() {
        // Minimal stub—add methods here if needed.
        //console.log("AgentDetailElement stub called.");
    }
    VisualizationElement.prototype.render = function(data) {
        //console.log("AgentDetailElement render called2. Data:", data);
        return data;
    };
}
else{
    //console.log("VisualizationElement already defined");
}
function AgentDetailElement() {
    //console.log("AgentDetailElement constructor called");
    VisualizationElement.call(this);
    var self = this;
    this.container = document.createElement("div");
    this.container.id = "agentDetailContainer"; // add an id
    this.container.style.padding = "10px";
    this.container.style.border = "1px solid #ccc";
    this.container.style.marginTop = "10px";

    // Create the search bar input.
    this.searchBar = document.createElement("input");
    this.searchBar.setAttribute("type", "text");
    this.searchBar.setAttribute("placeholder", "Enter agent ID...");
    this.searchBar.style.marginRight = "10px";
    this.searchBar.id = "agentSearchBar";
    this.container.appendChild(this.searchBar);
    

    // Create the search button.
    this.searchButton = document.createElement("button");
    this.searchButton.innerHTML = "Search";
    this.container.appendChild(this.searchButton);

    // Create a div to display agent details.
    this.detailsDiv = document.createElement("div");
    this.detailsDiv.style.marginTop = "10px";
    this.container.appendChild(this.detailsDiv);

    // Event listener for the search button.
    this.searchButton.addEventListener("click", function() {
        var agentID = self.searchBar.value;
        self.displayAgentDetails(agentID);
    });

    // Listen for a custom event if an agent is clicked.
    document.addEventListener("agent_click", function(e) {
        var agentID = e.detail;
        self.searchBar.value = agentID;
        self.displayAgentDetails(agentID);
    });

    document.body.appendChild(this.container);
    //console.log("Container appended to DOM for debugging.");
}

// Set up inheritance.
AgentDetailElement.prototype = Object.create(VisualizationElement.prototype);
AgentDetailElement.prototype.constructor = AgentDetailElement;

// Called every step; receives data from the Python model.
AgentDetailElement.prototype.render = function(data) {
    this.agentData = data;
    //console.log("AgentDetailElement render called. Data:", data);
    
    var placeholder = document.getElementById("agent-detail-placeholder");
    if (placeholder) {
        placeholder.innerHTML = "";  // Clear old content
        placeholder.appendChild(this.container);
    } else {
        console.warn("Placeholder not found. Appending to document.body instead.");
        document.body.appendChild(this.container);
    }
    
    // Return the container's outerHTML for Mesa's update pipeline.
    return this.container.outerHTML;
};

// Function to display details for a given agent ID.
AgentDetailElement.prototype.displayAgentDetails = function(agentID) {
    var details = this.agentData[agentID];
    if (details) {
        // Clear existing content
        this.detailsDiv.innerHTML = "";

        // Display other details as a list
        var ul = document.createElement("ul");
        let healthValues = {};  // Store health values for coloring logic
        
        for (var key in details) {
            if (details.hasOwnProperty(key) && key !== "human" && key !== "lungs" && key !== "heart" && key !== "artery") {
                var li = document.createElement("li");

                // Check if the detail is an array (e.g., health history or current health)
                if (Array.isArray(details[key])) {
                    // Special handling for "current health"
                    if (key === "current health" && details[key].length === 4) {
                        li.textContent = key + ":";
                        var subUl = document.createElement("ul");

                        var healthAttributes = ["Systolic BP", "Temperature (°F)", "Respiratory Rate", "Heart Rate"];
                        for (var i = 0; i < details[key].length; i++) {
                            var subLi = document.createElement("li");
                            subLi.textContent = healthAttributes[i] + ": " + details[key][i];
                            subUl.appendChild(subLi);
                            // Store health values for coloring logic
                            healthValues[healthAttributes[i]] = details[key][i];
                        }

                        li.appendChild(subUl);
                    } else {
                        // General handling for other arrays
                        li.textContent = key + ": [" + details[key].join(", ") + "]";
                    }
                } else {
                    li.textContent = key + ": " + details[key];
                }
                
                ul.appendChild(li);
            }
        }
        
        this.detailsDiv.appendChild(ul);
        // Function to determine color based on health values
        function getColor(value, healthyRange, badRange) {
            if ((value < healthyRange[0] && value > badRange[0]) || (value > healthyRange[1] && value < badRange[1])) return "rgba(255, 0, 0, 0.5)";  // Red (Bad)
            if (value <= badRange[0] || value >= badRange[1]) return "rgba(0, 0, 255, 0.5)";   // Blue (Critical)
            return "rgba(0, 255, 0, 0.5)";  // Green (Healthy)
        }

        // Define normal ranges
        let tempColor = getColor(healthValues["Temperature (°F)"], [97, 100.4], [95, 103]);
        let hrColor = getColor(healthValues["Heart Rate"], [60, 100], [50, 120]);
        let rrColor = getColor(healthValues["Respiratory Rate"], [12, 20], [8, 25]);
        let sbpColor = getColor(healthValues["Systolic BP"], [90, 120], [80, 140]);

        // Create a container for images
        var imageContainer = document.createElement("div");
        imageContainer.style.position = "relative";
        imageContainer.style.width = "300px"; // Set container width (same as human image width)
        imageContainer.style.height = "700px"; // Adjust height accordingly
        imageContainer.style.margin = "20px auto"; // Center align

        function createImageElement(base64Data, altText, width, height, left, top, zIndex, glowColor) {
            let wrapper = document.createElement("div");
            wrapper.style.position = "absolute";
            wrapper.style.left = left + "px";
            wrapper.style.top = top + "px";
            wrapper.style.width = width + "px";
            wrapper.style.height = height + "px";
            wrapper.style.zIndex = zIndex; // Set layer order
            wrapper.style.display = "flex";
            wrapper.style.alignItems = "center";
            wrapper.style.justifyContent = "center";

            // Create a colored layer behind the image
            let glowLayer = document.createElement("div");
            glowLayer.style.position = "absolute";
            glowLayer.style.width = "100%";
            glowLayer.style.height = "100%";
            glowLayer.style.background = glowColor;
            glowLayer.style.filter = "blur(15px)"; // Blurred glow effect
            glowLayer.style.opacity = "0.7"; // Reduce intensity

            // Create the actual image
            let img = new Image();
            img.src = "data:image/png;base64," + base64Data;
            img.alt = altText;
            img.width = width;
            img.height = height;
            img.style.position = "absolute";
            img.style.mixBlendMode = "multiply"; // Ensures glow is inside the image
            img.style.transition = "0.5s ease-in-out"; // Smooth transition

            wrapper.appendChild(glowLayer);
            wrapper.appendChild(img);
            return wrapper;
        }

        function createArteryElement(base64Data, altText, width, height, left, top, zIndex, glowColor) {
            let wrapper = document.createElement("div");
            wrapper.style.position = "absolute";
            wrapper.style.left = left + "px";
            wrapper.style.top = top + "px";
            wrapper.style.width = width + "px";
            wrapper.style.height = height + "px";
            wrapper.style.zIndex = zIndex;
            wrapper.style.display = "flex";
            wrapper.style.alignItems = "center";
            wrapper.style.justifyContent = "center";
        
            // Define glow areas inside the function
            let glowAreas = [
                // Upper chest and main arteries
                { x: width * 0.48, y: -height * 0.1, width: width * 0.16, height: height * 0.6 },
            
                // Upper arms
                { x: width * 0.2, y: height * 0.1, width: width * 0.12, height: height * 0.35 },
                { x: width * 0.8, y: height * 0.1, width: width * 0.12, height: height * 0.35 },
            
                // Lower arms and hands
                { x: width * 0.12, y: height * 0.4, width: width * 0.1, height: height * 0.2 },
                { x: width * 0.85, y: height * 0.4, width: width * 0.1, height: height * 0.2 },
            
                // Abdomen and major veins
                { x: width * 0.4, y: height * 0.45, width: width * 0.2, height: height * 0.5 },
            
                // Lower legs and feet
                { x: width * 0.38, y: height * 0.85, width: width * 0.24, height: height * 0.15 }
            ];
            
            
            
        
            // Create a container for multiple glow effects
            let glowContainer = document.createElement("div");
            glowContainer.style.position = "absolute";
            glowContainer.style.width = "100%";
            glowContainer.style.height = "100%";
            glowContainer.style.pointerEvents = "none"; // Prevents interference
        
            // Create glow effect for each specified area
            glowAreas.forEach(area => {
                let glowLayer = document.createElement("div");
                glowLayer.style.position = "absolute";
                glowLayer.style.left = area.x + "px";
                glowLayer.style.top = area.y + "px";
                glowLayer.style.width = area.width + "px";
                glowLayer.style.height = area.height + "px";
                glowLayer.style.background = glowColor;
                glowLayer.style.filter = "blur(15px)";
                glowLayer.style.opacity = "0.7";
                glowLayer.style.borderRadius = "50%"; // Circular glow spots
                glowContainer.appendChild(glowLayer);
            });
        
            // Create the actual image
            let img = new Image();
            img.src = "data:image/png;base64," + base64Data;
            img.alt = altText;
            img.width = width;
            img.height = height;
            img.style.position = "absolute";
            img.style.transition = "0.5s ease-in-out";
        
            wrapper.appendChild(glowContainer);
            wrapper.appendChild(img);
            return wrapper;
        }

        // Append images with proper positioning
        if (details.human) {
            let humanImg = createImageElement(details.human, "Human Body", 250, 700, 0, 0,1, tempColor);
            imageContainer.appendChild(humanImg);
        }
        if (details.lungs) {
            let lungsImg = createImageElement(details.lungs, "Lungs", 130, 130, 60, 120, 3, rrColor); // Adjust left and top to align
            imageContainer.appendChild(lungsImg);
        }
        if (details.heart) {
            let heartImg = createImageElement(details.heart, "Heart", 70, 70, 110, 150, 4, hrColor); // Position heart in center
            imageContainer.appendChild(heartImg);
        }
        if (details.artery) {
            let humanImg = createArteryElement(details.artery, "Artery", 250, 600, -10, 110,2, sbpColor);
            imageContainer.appendChild(humanImg);
        }

        this.detailsDiv.appendChild(imageContainer);
    } else {
        this.detailsDiv.innerHTML = "No details available for agent ID " + agentID;
    }
};




// Reset method
AgentDetailElement.prototype.reset = function() {
    //console.log("Resetting AgentDetailElement");
    this.detailsDiv.innerHTML = "";
    this.searchBar.value = "";
};

window.AgentDetailElement = AgentDetailElement;
//console.log("AgentDetailElement.js windowed");
