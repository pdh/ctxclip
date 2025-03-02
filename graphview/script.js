// Set up the color schemes
const nodeColorScale = d3
  .scaleOrdinal()
  .domain(["module", "object", "class", "function"])
  .range(["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]);

const linkColorScale = d3
  .scaleOrdinal()
  .domain(["import_object", "defines", "inherits", "calls"])
  .range(["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]);

// Set up the SVG container
const width = document.getElementById("graph-container").clientWidth;
const height = document.getElementById("graph-container").clientHeight;

let selectedNodeId = null;

let svg = d3
  .select("#graph-container")
  .append("svg")
  .attr("width", width)
  .attr("height", height);

// Create a group for the graph
let g = svg.append("g");

// Add zoom functionality
let zoom = d3
  .zoom()
  .scaleExtent([0.1, 4])
  .on("zoom", (event) => {
    g.attr("transform", event.transform);
  });

svg.call(zoom);

// Create tooltip
const tooltip = d3.select(".tooltip");

// Details panel elements
const detailsPanel = document.getElementById("details-panel");
const detailsContent = document.querySelector(".details-content");
const detailsTitle = document.getElementById("details-title");
const detailsBody = document.getElementById("details-body");
const closeDetailsBtn = document.getElementById("close-details");

// Close details panel when close button is clicked
closeDetailsBtn.addEventListener("click", () => {
  detailsPanel.classList.remove("open");
  detailsContent.classList.remove("visible");
  // Remove selected class from all nodes
  d3.selectAll(".node").classed("node-selected", false);
});

// Store the original nodes and links
let allNodes = [];
let allLinks = [];

// Track active filters
let activeNodeTypes = ["module", "object", "class", "function"];
let activeLinkTypes = ["import_object", "defines", "inherits", "calls"];

// Function to apply filters and update the graph
function applyFilters(data) {
  // Filter nodes based on active node types
  const filteredNodes = allNodes.filter((node) =>
    activeNodeTypes.includes(node.type)
  );

  // Get IDs of visible nodes
  const visibleNodeIds = new Set(filteredNodes.map((node) => node.id));

  // Filter links based on active link types and visible nodes
  const filteredLinks = allLinks.filter(
    (link) =>
      activeLinkTypes.includes(link.type) &&
      visibleNodeIds.has(link.source.id || link.source) &&
      visibleNodeIds.has(link.target.id || link.target)
  );

  // Update the graph with filtered data
  updateGraph(filteredNodes, filteredLinks, data);
}

// Function to update the graph with filtered data
function updateGraph(nodes, links, data) {
  // Remove existing elements
  g.selectAll(".nodes").remove();
  g.selectAll(".links").remove();

  // Create the simulation with filtered data
  const simulation = d3
    .forceSimulation(nodes)
    .force(
      "link",
      d3
        .forceLink(links)
        .id((d) => d.id)
        .distance(150)
    )
    .force("charge", d3.forceManyBody().strength(-400))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(60));

  // Create the links
  const link = g
    .append("g")
    .attr("class", "links")
    .selectAll("line")
    .data(links)
    .enter()
    .append("line")
    .attr("class", "link")
    .attr("stroke", (d) => linkColorScale(d.type))
    .attr("stroke-width", 2)
    .attr("marker-end", (d) => `url(#arrow-${d.type})`);

  // Create the nodes
  const node = g
    .append("g")
    .attr("class", "nodes")
    .selectAll(".node")
    .data(nodes)
    .enter()
    .append("g")
    .attr("class", "node")
    .call(
      d3
        .drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended)
    );

  // Add circles to nodes
  node
    .append("circle")
    .attr("r", (d) => {
      if (d.type === "module") return 15;
      if (d.id.includes("main.")) return 12;
      return 8;
    })
    .attr("fill", (d) => nodeColorScale(d.type));

  // Add labels to nodes
  node
    .append("text")
    .attr("dx", 15)
    .attr("dy", 4)
    .text((d) => {
      const parts = d.id.split(".");
      return parts[parts.length - 1];
    })
    .attr("fill", "#333");

  // Add hover and click effects (same as your original code)
  node
    .on("mouseover", function (event, d) {
      // Show tooltip
      tooltip
        .style("opacity", 1)
        .html(`<strong>${d.id}</strong><br>Type: ${d.type}`)
        .style("left", event.pageX + 10 + "px")
        .style("top", event.pageY - 10 + "px");

      // Highlight connected links
      link.style("stroke-opacity", (l) =>
        l.source.id === d.id || l.target.id === d.id ? 1 : 0.1
      );

      // Highlight connected nodes
      node.style("opacity", (n) =>
        n.id === d.id ||
        data.links.some(
          (l) =>
            (l.source === d.id && l.target === n.id) ||
            (l.target === d.id && l.source === n.id)
        )
          ? 1
          : 0.3
      );
    })
    .on("mouseout", function () {
      tooltip.style("opacity", 0);

      // If there's a selected node, maintain its highlighting
      if (selectedNodeId) {
        // Highlight connected links to selected node
        link.style("stroke-opacity", (l) =>
          l.source.id === selectedNodeId || l.target.id === selectedNodeId
            ? 1
            : 0.1
        );

        // Highlight selected node and its connections
        node.style("opacity", (n) =>
          n.id === selectedNodeId ||
          data.links.some(
            (l) =>
              (l.source.id === selectedNodeId && l.target.id === n.id) ||
              (l.target.id === selectedNodeId && l.source.id === n.id)
          )
            ? 1
            : 0.3
        );
      } else {
        // If no node is selected, reset all highlighting
        link.style("stroke-opacity", 0.6);
        node.style("opacity", 1);
      }
    })
    .on("click", function (event, d) {
      event.stopPropagation();

      selectedNodeId = d.id;

      // Remove selected class from all nodes and add to clicked node
      d3.selectAll(".node").classed("node-selected", false);
      d3.select(this).classed("node-selected", true);

      // Show details panel
      showNodeDetails(d, data);
    });

  // Click on background to close details panel
  svg.on("click", function () {
    selectedNodeId = null; // Reset selected node
    detailsPanel.classList.remove("open");
    detailsContent.classList.remove("visible");
    d3.selectAll(".node").classed("node-selected", false);

    // Reset all highlighting
    link.style("stroke-opacity", 0.6);
    node.style("opacity", 1);
  });

  // Update positions on each tick
  simulation.on("tick", () => {
    link
      .attr("x1", (d) => d.source.x)
      .attr("y1", (d) => d.source.y)
      .attr("x2", (d) => d.target.x)
      .attr("y2", (d) => d.target.y);

    node.attr("transform", (d) => `translate(${d.x}, ${d.y})`);
  });

  // Drag functions
  function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
  }

  function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
  }

  function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  }
}

// Function to show node details in the panel
function showNodeDetails(d, data) {
  console.log("node clicked:", d);
  const checkboxesHTML = `
<div class="edge-options">
  <label><input type="checkbox" id="show-outgoing"> Show outgoing connections</label>
  <label><input type="checkbox" id="show-incoming"> Show incoming connections</label>
</div>`;
  // Set the title
  detailsTitle.textContent = d.id + d.signature;

  // Build the details content
  let content = "";

  // Basic info section
  content += `<div class="metadata-section">
        <h3>Basic Information</h3>
        <div class="metadata-item">
            <span class="metadata-label">Type:</span> ${d.type}
        </div>`;

  if (d.parent) {
    content += `<div class="metadata-item">
            <span class="metadata-label">Parent:</span> ${d.parent}
        </div>`;
  }

  if (d.path) {
    content += `<div class="metadata-item">
            <span class="metadata-label">Path:</span> ${d.path}
        </div>`;
  }

  if (d.is_public_api) {
    content += `<div class="metadata-item">
            <span class="metadata-label">Public API:</span> ${d.is_public_api}
        </div>`;
  }

  content += `</div>`;

  // Location info
  if (d.line_start && d.line_end) {
    content += `<div class="metadata-section">
            <h3>Location</h3>
            <div class="metadata-item">
                <span class="metadata-label">Lines:</span> ${d.line_start} - ${d.line_end}
            </div>
        </div>`;
  }

  // Signature and docstring
  if (d.signature || d.docstring) {
    content += `<div class="metadata-section">
            <h3>Documentation</h3>`;

    if (d.signature) {
      console.log("got signature!");
      content += `<div class="metadata-item">
                <span class="metadata-label">Signature:</span><pre>${d.signature}</pre>
            </div>`;
    }

    if (d.docstring) {
      content += `<div class="metadata-item">
                <span class="metadata-label">Docstring:</span>
                <pre>${d.docstring}</pre>
            </div>`;
    }

    content += `</div>`;
  }

  // Methods (for classes)
  if (d.methods && Array.isArray(d.methods) && d.methods.length > 0) {
    content += `<div class="metadata-section">
            <h3>Methods (${d.methods.length})</h3>
            <div class="methods-list">
                <ul>`;

    d.methods.forEach((method) => {
      content += `<li>${method}</li>`;
    });

    content += `</ul>
            </div>
        </div>`;
  }

  if (d.code && d.code !== "") {
    content += `<div class="metadata-section">
          <h3>Code</h3>
          <div class="methods-list">
            <pre>${d.code}</pre>
          </div>
      </div>`;
  }

  // Set the content
  detailsBody.innerHTML = content;
  // Insert checkboxes after the title
  if (!document.querySelector(".edge-options")) {
    detailsTitle.insertAdjacentHTML("afterend", checkboxesHTML);
  }

  // Show the panel
  detailsPanel.classList.add("open");
  detailsPanel.offsetHeight;
  setTimeout(() => {
    detailsContent.classList.add("visible");
  }, 100);

  const outgoingCheckbox = document.getElementById("show-outgoing");
  const incomingCheckbox = document.getElementById("show-incoming");

  outgoingCheckbox.addEventListener("change", function () {
    updateEdgeDetails(d, data);
  });

  incomingCheckbox.addEventListener("change", function () {
    updateEdgeDetails(d, data);
  });

  // Initial update
  updateEdgeDetails(d, data);
}

// Function to update edge details based on checkbox state
function updateEdgeDetails(d, data) {
  const outgoingCheckbox = document.getElementById("show-outgoing");
  const incomingCheckbox = document.getElementById("show-incoming");

  // Get existing content
  let content = detailsBody.innerHTML;

  // Remove any existing edge sections
  const edgeSectionsRegex =
    /<div class="metadata-section edge-section">([\s\S]*?)<\/div>/g;
  content = content.replace(edgeSectionsRegex, "");

  // Add outgoing edges section if checked
  if (outgoingCheckbox && outgoingCheckbox.checked) {
    const outgoingEdges = findOutgoingEdges(d.id, data);
    if (outgoingEdges.length > 0) {
      content += createEdgeSection("Outgoing Connections", outgoingEdges);
    }
  }

  // Add incoming edges section if checked
  if (incomingCheckbox && incomingCheckbox.checked) {
    const incomingEdges = findIncomingEdges(d.id, data);
    if (incomingEdges.length > 0) {
      content += createEdgeSection("Incoming Connections", incomingEdges);
    }
  }

  // Update the content
  detailsBody.innerHTML = content;
}

// Function to find outgoing edges for a node
function findOutgoingEdges(nodeId, data) {
  return data.links
    .filter((link) => link.source.id === nodeId || link.source === nodeId)
    .map((link) => {
      const targetNode =
        typeof link.target === "object"
          ? link.target
          : data.nodes.find((n) => n.id === link.target);
      return {
        edge: link,
        node: targetNode,
      };
    });
}

// Function to find incoming edges for a node
function findIncomingEdges(nodeId, data) {
  return data.links
    .filter((link) => link.target.id === nodeId || link.target === nodeId)
    .map((link) => {
      const sourceNode =
        typeof link.source === "object"
          ? link.source
          : data.nodes.find((n) => n.id === link.source);
      return {
        edge: link,
        node: sourceNode,
      };
    });
}

// Function to create HTML for edge sections
function createEdgeSection(title, edges) {
  let html = `<div class="metadata-section edge-section">
      <h3>${title} (${edges.length})</h3>`;

  edges.forEach((item) => {
    const node = item.node;
    const edge = item.edge;

    html += `<div class="edge-item">
          <h4>${node.id}</h4>
          <div class="metadata-item">
              <span class="metadata-label">Type:</span> ${node.type}
          </div>
          <div class="metadata-item">
              <span class="metadata-label">Relationship:</span> ${edge.type}
          </div>`;

    if (node.docstring) {
      html += `<div class="metadata-item">
              <span class="metadata-label">Docstring:</span>
              <pre>${node.docstring.substring(0, 100)}${
        node.docstring.length > 100 ? "..." : ""
      }</pre>
          </div>`;
    }

    html += `</div>`;
  });

  html += `</div>`;
  return html;
}

// Load and process the data
function loadGraph(data) {
  console.log("loading graph");
  // Store the original data
  allNodes = [...data.nodes];
  allLinks = [...data.links];

  document.querySelectorAll(".node-type-toggle").forEach((checkbox) => {
    checkbox.addEventListener("change", function () {
      const nodeType = this.value;
      if (this.checked) {
        activeNodeTypes.push(nodeType);
      } else {
        activeNodeTypes = activeNodeTypes.filter((type) => type !== nodeType);
      }
      applyFilters(data);
    });
  });

  // Link type toggles
  document.querySelectorAll(".link-type-toggle").forEach((checkbox) => {
    checkbox.addEventListener("change", function () {
      const linkType = this.value;
      if (this.checked) {
        activeLinkTypes.push(linkType);
      } else {
        activeLinkTypes = activeLinkTypes.filter((type) => type !== linkType);
      }
      applyFilters(data);
    });
  });

  // Apply initial filters
  applyFilters(data);
};

function loadDataFromURL() {
  const url =  "./ctxclip.json"

  if (!url) {
    alert("Please enter a URL first.");
    return;
  }

  d3.json(url)
    .then(newData => {
      // Clear existing graph
      d3.select("#graph-container svg").remove();

      // Create a new SVG
      svg = d3
        .select("#graph-container")
        .append("svg")
        .attr("width", width)
        .attr("height", height);

      // Add zoom functionality
      const zoom = d3
        .zoom()
        .scaleExtent([0.1, 4])
        .on("zoom", (event) => {
          g.attr("transform", event.transform);
        });

      svg.call(zoom);

      // Create a group for the graph
      g = svg.append("g");

      // Load the new graph
      loadGraph(newData);

      // Close details panel if open
      detailsPanel.classList.remove("open");
      detailsContent.classList.remove("visible");
    })
    .catch(error => {
      console.error("Error loading data:", error);
      alert("Error loading data from URL. Please make sure it returns valid JSON.");
    });
}


// File loading functionality
document
  .getElementById("load-file-btn")
  .addEventListener("click", loadDataFromFile);

function loadDataFromFile() {
  const fileInput = document.getElementById("file-input");
  const file = fileInput.files[0];

  if (!file) {
    alert("Please select a file first.");
    return;
  }

  const reader = new FileReader();

  reader.onload = function (event) {
    try {
      const newData = JSON.parse(event.target.result);

      // Clear existing graph
      d3.select("#graph-container svg").remove();

      // Create a new SVG - make sure to assign it to the global svg variable
      svg = d3
        .select("#graph-container")
        .append("svg")
        .attr("width", width)
        .attr("height", height);

      // Add zoom functionality
      const zoom = d3
        .zoom()
        .scaleExtent([0.1, 4])
        .on("zoom", (event) => {
          g.attr("transform", event.transform);
        });

      svg.call(zoom);

      // Create a group for the graph - assign to global g variable
      g = svg.append("g");

      // Load the new graph
      loadGraph(newData);

      // Close details panel if open
      detailsPanel.classList.remove("open");
      detailsContent.classList.remove("visible");
    } catch (error) {
      console.error("Error parsing JSON file:", error);
      alert("Error loading file. Please make sure it is a valid JSON file.");
    }
  };

  reader.readAsText(file);
}


document.addEventListener("DOMContentLoaded", function () {
  loadDataFromURL();
});
