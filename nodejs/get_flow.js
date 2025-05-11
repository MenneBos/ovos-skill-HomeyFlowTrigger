import { HomeyAPI } from 'homey-api';

const searchString = process.argv[2] || "";

HomeyAPI.createLocalAPI({
  address: 'http://192.168.1.170', // Replace with Homey Pro's IP address
  token: 'd5af67f5-9031-4354-b03b-26c0c055b7b8:dadaf8d8-f2c2-4ef4-8a4d-ba1b07650f42:93c8ef4008ce8551c930069df7fc47d8aa6215be' // Replace with your Homey API token
})
  .then(homeyApi => homeyApi.flows.getFlows())
  .then(flows => {
    const filteredFlows = Object.values(flows).filter(flow =>
      flow.name.toLowerCase().includes(searchString.toLowerCase())
    );
    const formattedFlows = filteredFlows.map(flow => ({
      id: flow.id,
      name: flow.name
    }));
    console.log(JSON.stringify(formattedFlows));
  })
  .catch(error => {
    console.error("❌ Error fetching flows:", error.message);
    process.exit(1);
  });