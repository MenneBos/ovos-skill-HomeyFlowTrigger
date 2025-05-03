import { HomeyAPI } from 'homey-api';

const flowId = process.argv[2];

if (!flowId) {
    console.error("Geen flow-id meegegeven.");
    process.exit(1);
  }

const homeyApi = await HomeyAPI.createLocalAPI({
  address: 'http://192.168.1.170', // Vervang door IP van jouw Homey Pro
  token: 'd5af67f5-9031-4354-b03b-26c0c055b7b8:dadaf8d8-f2c2-4ef4-8a4d-ba1b07650f42:93c8ef4008ce8551c930069df7fc47d8aa6215be'         // Vervang door je lokale token
});

//const flows = await homeyApi.flow.getFlows();

try {
    await homeyApi.flow.triggerFlow({ uri: 'homey:manager:flow', id: flowId });
    console.log(`Flow met ID ${flowId} gestart.`);
  } catch (err) {
    console.error(`Kon flow ${flowId} niet starten: ${err.message}`);
    process.exit(1);
  }

process.exit();  // Ensures that the script exits properly