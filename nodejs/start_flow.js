import { HomeyAPI } from 'homey-api';
import fs from 'fs';

// Load configuration
const config = JSON.parse(fs.readFileSync('./config.json', 'utf8'));

const flowId = process.argv[2];

if (!flowId) {
    console.error("Geen flow-id meegegeven.");
    process.exit(1);
  }

  const homeyApi = await HomeyAPI.createLocalAPI({
    address: config.homey.address, // Load address from config
    token: config.homey.token      // Load token from config
});

//const flows = await homeyApi.flow.getFlows();

try {
    await homeyApi.flow.triggerFlow({ uri: 'homey:manager:flow', id: flowId });
    console.log(`Flow gestart`);
  } catch (err) {
    console.error(`Kon API niet starten: ${err.message}`);
    process.exit(1);
  }

process.exit();  // Ensures that the script exits properly