import { HomeyAPI } from 'homey-api';
import fs from 'fs';

// Load configuration
const config = JSON.parse(fs.readFileSync('./config.json', 'utf8'));

const searchString = process.argv[2] || "";

async function getFilteredFlows() {
  try {
    // Connect to the Homey API
    const homeyApi = await HomeyAPI.createLocalAPI({
      address: config.homey.address, // Load address from config
      token: config.homey.token      // Load token from config
    });

    // Get all flows from Homey
    const flows = await homeyApi.flow.getFlows();

    // Filter flows based on the search string
    const filteredFlows = Object.values(flows).filter(flow =>
      flow.name.toLowerCase().includes(searchString.toLowerCase())
    );

    // Format the filtered flows in the flow_mappings.json structure
    const flowMappings = {};
    filteredFlows.forEach(flow => {
      flowMappings[flow.name] = {
        id: flow.id,
        sentences: [] // Empty sentences array, as this will be populated later
      };
    });

    // Return the filtered flows to the Python script
    console.log(JSON.stringify(flowMappings));
  } catch (error) {
    console.error("❌ Error fetching or filtering flows:", error.message);
    process.exit(1); // Exit with an error code
  }
}

// Execute the function
getFilteredFlows();