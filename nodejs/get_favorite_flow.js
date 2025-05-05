import { HomeyAPI } from 'homey-api';

HomeyAPI.createLocalAPI({
  address: 'http://192.168.1.170', // Replace this with Homey Pro's IP address
  token: 'd5af67f5-9031-4354-b03b-26c0c055b7b8:dadaf8d8-f2c2-4ef4-8a4d-ba1b07650f42:93c8ef4008ce8551c930069df7fc47d8aa6215be' // Replace with your local token
})
  .then(homeyApi => homeyApi.flows.getFlows()) // Correct method for HomeyAPI v3
  .then(flows => {
    const favoriteFlows = Object.values(flows).filter(flow => flow.favorite); // Filter favorite flows
    const formattedFlows = favoriteFlows.map(flow => ({
      id: flow.id,
      name: flow.name
    }));
    console.log(JSON.stringify(formattedFlows)); // Output the favorite flows as JSON
  })
  .catch(error => {
    console.error("❌ Error fetching favorite flows:", error.message);
    process.exit(1);
  });