import { HomeyAPI } from 'homey-api';

const keywords = process.argv.slice(2).map(k => k.toLowerCase());

const homeyApi = await HomeyAPI.createLocalAPI({
  address: 'http://192.168.1.170', // Vervang door IP van jouw Homey Pro
  token: 'd5af67f5-9031-4354-b03b-26c0c055b7b8:dadaf8d8-f2c2-4ef4-8a4d-ba1b07650f42:93c8ef4008ce8551c930069df7fc47d8aa6215be'         // Vervang door je lokale token
});

const flows = await homeyApi.flow.getFlows();

const matchingFlow = Object.values(flows).find(flow => {
  const name = flow.name.toLowerCase();
  return keywords.every(kw => name.includes(kw));
});

if (matchingFlow) {
    await homeyApi.flow.triggerFlow({ uri: 'homey:manager:flow', id: matchingFlow.id });
    console.log(`Flow gestart: ${matchingFlow.name}`);
  } else {
    console.log("Geen flow gevonden met alle keywords: " + keywords.join(", "));
  }

process.exit();  // Ensures that the script exits properly