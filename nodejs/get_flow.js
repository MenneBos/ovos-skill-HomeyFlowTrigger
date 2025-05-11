import { HomeyAPI } from 'homey-api';

const searchString = process.argv[2] || "";

HomeyAPI.createLocalAPI({
  address: 'http://192.168.1.170', // Replace with Homey Pro's IP address
  token: 'your_homey_api_token' // Replace with your Homey API token
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