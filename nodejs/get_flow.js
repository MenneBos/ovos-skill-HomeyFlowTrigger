import { HomeyAPI } from 'homey-api';

const searchString = process.argv[2] || "";

async function getFilteredFlows() {
  try {
    // Connect to the Homey API
    const homeyApi = await HomeyAPI.createLocalAPI({
      address: 'http://192.168.1.170', // Replace with Homey Pro's IP address
      token: 'd5af67f5-9031-4354-b03b-26c0c055b7b8:dadaf8d8-f2c2-4ef4-8a4d-ba1b07650f42:93c8ef4008ce8551c930069df7fc47d8aa6215be' // Replace with your Homey API token
    });

    // Get all flows from Homey
    const flows = await homeyApi.flows.getFlows();

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