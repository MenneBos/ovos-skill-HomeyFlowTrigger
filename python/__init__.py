from ovos_utils import classproperty
from ovos_utils.log import LOG
from ovos_workshop.intents import IntentBuilder
from ovos_utils.process_utils import RuntimeRequirements
from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills import OVOSSkill
import os
import subprocess

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
        self.settings.merge(DEFAULT_SETTINGS, new_only=True)
        self.settings_change_callback = self.on_settings_changed


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
    
    @intent_handler(IntentBuilder('HomeyFlow.intent').require('action').require('object').optionally('location'))
    def handle_start_flow(self, message):

        # Haal keyword(s) op uit vocab via message.utterance
        utterance = message.data.get("utterance", "").lower()
        keywords = []
        for vocab_entry in self.vocab_loader.load_vocabulary("keyword"):
            if vocab_entry.lower() in utterance:
                keywords.append(vocab_entry)
        LOG.info("Homey Flow met keywords: " + str(keywords) + " wordt gestart")

        if not keywords:
            self.log.error("Geen keywords gevonden in de utterance. Flow wordt niet gestart.")
            self.speak("Ik heb geen relevante woorden gevonden om een flow te starten.")
            return

        args = ["node", "~/my-homey-integration/start_flow.js"] + keywords
        try:
            result = subprocess.run(args, check=True, capture_output=True, text=True)
            response = result.stdout.strip() or "Ik heb geen reactie van Homey ontvangen."
        except subprocess.CalledProcessError as e:
            response = f"Er ging iets mis bij het starten van de flow."
            LOG.error(f"Homey error: {e.stderr}")
        
        self.speak(response)