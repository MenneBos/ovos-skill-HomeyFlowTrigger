from ovos_utils import classproperty
from ovos_utils.log import LOG
#from ovos_workshop.intents import IntentBuilder
from ovos_utils.process_utils import RuntimeRequirements
#from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills.ovos import OVOSSkill
import subprocess
import os
import json
import paho.mqtt.client as mqtt
import crypt  # For password hashing comparison

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

    def initialize(self):
        self.flow_mapping_path = os.path.join(self.root_dir, "flow_mappings.json")
        self.register_intent("HomeyFlow.intent", self.handle_start_flow)
        self._setup_mqtt()

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

    def _setup_mqtt(self):
        self.client = mqtt.Client()
        #self.client.tls_set(
        #    ca_certs="/etc/mosquitto/certs/ca.crt",
        #    certfile="/etc/mosquitto/certs/client.crt",
        #    keyfile="/etc/mosquitto/certs/client.key"
        #)

        # Dynamically load username and password from /etc/mosquitto/passwd
        #username, password = self._get_mqtt_credentials("/etc/mosquitto/passwd")
        #if not username or not password:
        #    self.log.error("❌ Kon geen MQTT-gebruikersnaam en wachtwoord laden.")
        #    return

        #self.client.username_pw_set(username, password)
        #self.client.connect("ovos-server.local", 8883, 60)
        
        self.client.connect("192.168.5.27", 1883, 60)  # Replace with your broker's IP and port
        self.client.subscribe("request_flow_mappings")
        self.client.subscribe("save_flow_mappings")
        self.client.subscribe("request_flows")
        self.client.on_message = self._on_mqtt_message
        self.client.loop_start()

        self.log.info("✅ Verbonden met MQTT-broker en wacht op berichten.")    

    #def _get_mqtt_credentials(self, passwd_file_path):
    #    """
    #    Reads the Mosquitto passwd file and extracts the first username and password.
    #    Assumes the password is hashed and matches the client certificate.
    #    """
    #    try:
    #        with open(passwd_file_path, "r") as f:
    #            for line in f:
    #                if line.strip() and not line.startswith("#"):
    #                    parts = line.split(":")
    #                    if len(parts) == 2:
    #                        username = parts[0].strip()
    #                        hashed_password = parts[1].strip()
    #                        # Return the username and hashed password (if needed for validation)
    #                        return username, hashed_password
    #    except Exception as e:
    #        self.log.error(f"❌ Fout bij het lezen van het passwd-bestand: {e}")
    #    return None, None
    
    def _on_mqtt_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            self.log.info(f"Wat is de ontavngen topic" + topic+ " met payload: " + str(payload))
             
            if topic == "request_flow_mappings":
                self._send_flow_mappings()

            elif topic == "save_flow_mappings":
                self._save_flow_mappings(payload)

            elif topic == "request_flows":
                self._request_flows(payload)

        except Exception as e:
            self.log.error(f"❌ Fout bij verwerken MQTT-bericht: {e}") 
            self.speak("Er ging iets mis bij het verwerken van het MQTT-bericht.")

    def _send_flow_mappings(self):
        try:
            with open(self.flow_mapping_path, "r") as f:
                mappings = json.load(f)
            self.client.publish("send_flow_mappings", json.dumps(mappings))
            self.log.info("✅ Flow mappings verzonden.")
        except Exception as e:
            self.log.error(f"❌ Fout bij het verzenden van flow mappings: {e}")

    def _save_flow_mappings(self, payload):
        try:
            # Overwrite the flow_mappings.json file
            with open(self.flow_mapping_path, "w") as f:
                json.dump(payload, f, indent=2)

            # Overwrite the HomeyFlow.intent file
            utterances = []
            for flow in payload.values():
                utterances.extend(flow.get("sentences", []))
            os.makedirs(os.path.dirname(self.intent_file_path), exist_ok=True)
            with open(self.intent_file_path, "w") as intent_file:
                intent_file.write("\n".join(utterances))

            self.client.publish("saved_flow_mappings", json.dumps({"status": "success"}))
            self.log.info("✅ Flow mappings opgeslagen.")
        except Exception as e:
            self.client.publish("saved_flow_mappings", json.dumps({"status": "failure", "error": str(e)}))
            self.log.error(f"❌ Fout bij het opslaan van flow mappings: {e}")

    def _request_flows(self, payload):
        try:
            search_string = payload.get("name", "")
            args = ["node", os.path.join(self.root_dir, "get_flow.js"), search_string]
            result = subprocess.run(args, capture_output=True, text=True, check=True)
            flows = json.loads(result.stdout.strip())
            self.client.publish("send_flows", json.dumps(flows))
            self.log.info("✅ Flows verzonden.")
        except subprocess.CalledProcessError as e:
            self.log.error(f"❌ Fout bij ophalen van flows: {e.stderr}")
        except Exception as e:
            self.log.error(f"❌ Fout bij verwerken van flows: {e}") 

    def handle_start_flow(self, message):
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

        args = ["node", os.path.join(self.root_dir, "start_flow_by_id.js"), flow_id]

        try:
            result = subprocess.run(args, capture_output=True, text=True, check=True)
            response = result.stdout.strip() or f"De flow {flow_name} is gestart."
            self.log.info(f"✅ {response}")
        except subprocess.CalledProcessError as e:
            response = f"Er ging iets mis bij het starten van {flow_name}."
            self.log.error(f"❌ Fout bij starten van flow-id {flow_name}: {e.stderr}")

        self.speak(response)