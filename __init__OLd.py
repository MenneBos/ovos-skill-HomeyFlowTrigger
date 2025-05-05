from ovos_utils import classproperty
from ovos_utils.log import LOG
from ovos_workshop.intents import IntentBuilder
from ovos_utils.process_utils import RuntimeRequirements
from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills import OVOSSkill
import os
import subprocess
import json

DEFAULT_SETTINGS = {
    "log_level": "INFO"
}

class HomeyFlowSkill(OVOSSkill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.override = True
        
    @classproperty
    def runtime_requirements(self):
        # if this isn't defined the skill will
        # only load if there is internet
        return RuntimeRequirements(
            internet_before_load=False,
            network_before_load=True,
            gui_before_load=False,
            requires_internet=False,
            requires_network=True,
            requires_gui=False,
            no_internet_fallback=True,
            no_network_fallback=True,
            no_gui_fallback=True,
        )
    
    def initialize(self,):
        self.flow_mapping_path = os.path.join(self.root_dir, "flow_mappings.json")
        self.register_intent("HomeyFlow.intent", self.handle_start_flow)

    def on_settings_changed(self):
        """This method is called when the skill settings are changed."""
        LOG.info("Settings changed!")

    @property
    def log_level(self):
        """Dynamically get the 'log_level' value from the skill settings file.
        If it doesn't exist, return the default value.
        This will reflect live changes to settings.json files (local or from backend)
        """
        return self.settings.get("log_level", "INFO")   

    def handle_start_flow(self, message):
        # Haal de intentnaam op uit het ontvangen bericht
        utterance = message.data.get("utterance", "").lower()

        try:
            with open(self.flow_mapping_path, "r") as f:
                mappings = json.load(f)
        except Exception as e:
            self.log.error(f"❌ Kan flow_mappings.json niet laden: {e}")
            self.speak("Er ging iets mis bij het openen van de flow instellingen.")
            return

        flow_info = mappings.get(utterance)
        if not flow_info or "id" not in flow_info:
            self.speak("Ik weet niet welke flow ik moet starten.")
            self.log.error(f"❌ Geen geldige flow-info voor intentzin: {utterance}")
            return
        
        flow_id = flow_info["id"]
        flow_name = flow_info.get("name", "deze flow")

        # Stel het pad in naar het Node.js-script en geef de flow-id door als argument
        args = ["node", os.path.expanduser("~/.venvs/ovos/lib/python3.11/site-packages/ovos_skill_homeyflowtrigger/nodejs/start_flow.js"), flow_id]

        try:
            result = subprocess.run(args, capture_output=True, text=True, check=True)
            response = result.stdout.strip() or "  De flow trigger is gestart, maar gaf geen antwoord terug."
        except subprocess.CalledProcessError as e:
            response = " ❌ Er ging iets mis bij het starten van de flow."
            self.log.error(f"❌ Fout bij starten van flow-id {e.stderr}")

        self.speak(response)