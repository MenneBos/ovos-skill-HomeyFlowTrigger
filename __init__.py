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
        self.intent_dir = os.path.join(self.root_dir, "locale", "nl-NL", "intent")
        #self.intent_file_path = os.path.join(self.root_dir, "HomeyFlow.intent")
        self.register_intent("HomeyFlow.intent", self.handle_start_flow)
        self._setup_mqtt()

        # Remove all existing .intent files
        self.clear_intent_files()

        # Recreate .intent files based on flow_mappings.json
        self.recreate_intent_files()

        # Register all .intent files
        self.register_all_intents()

    def clear_intent_files(self):
        """Remove all existing .intent files in the intent directory."""
        try:
            if os.path.exists(self.intent_dir):
                for intent_file in os.listdir(self.intent_dir):
                    if intent_file.endswith(".intent"):
                        intent_file_path = os.path.join(self.intent_dir, intent_file)
                        os.remove(intent_file_path)
                        self.log.info(f"✅ Verwijderd .intent-bestand: {intent_file}")
            else:
                self.log.warning(f"⚠️ Intent directory '{self.intent_dir}' bestaat niet.")
        except Exception as e:
            self.log.error(f"❌ Fout bij het verwijderen van .intent-bestanden: {e}")

    def recreate_intent_files(self):
        """Recreate .intent files based on the current flow_mappings.json."""
        try:
            # Load the flow_mappings.json file
            if os.path.exists(self.flow_mapping_path):
                with open(self.flow_mapping_path, "r") as f:
                    mappings = json.load(f)

                # Create .intent files for each flow
                for flow_name, flow_data in mappings.items():
                    self.create_intent_file(flow_name, flow_data.get("sentences", []))
            else:
                self.log.warning(f"⚠️ Flow mappings file '{self.flow_mapping_path}' bestaat niet.")
        except Exception as e:
            self.log.error(f"❌ Fout bij het opnieuw aanmaken van .intent-bestanden: {e}")

    def register_all_intents(self):
        """Register all .intent files in the intent directory."""
        try:
            if not os.path.exists(self.intent_dir):
                self.log.warning(f"⚠️ Intent directory '{self.intent_dir}' does not exist.")
                return

            for intent_file in os.listdir(self.intent_dir):
                if intent_file.endswith(".intent"):
                    intent_name = os.path.splitext(intent_file)[0]  # Remove the .intent extension
                    self.register_intent(intent_file, self.handle_start_flow)
                    self.log.info(f"✅ Intent '{intent_name}' registered.")
        except Exception as e:
            self.log.error(f"❌ Error registering intents: {e}")

    def on_settings_changed(self):
        """This method is called when the skill settings are changed."""
        LOG.info("Settings changed!")

    def restart_ovos_service():
        try:
            subprocess.run(["systemctl", "restart", "ovos"], check=True)
            print("✅ OVOS service restarted successfully.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to restart OVOS service: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

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
            payload = msg.payload.decode().strip()  # Decode the payload and strip whitespace
            if payload:  # Check if the payload is not empty
                payload = json.loads(payload)
            else:
                payload = {}  # Default to an empty dictionary if no payload is provided

            self.log.info(f"Received topic: {topic} with payload: {payload}")
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
            # Sanitize flow names in the payload
            sanitized_payload = {}
            for flow_name, flow_data in payload.items():
                # Sanitize the flow name (remove spaces, convert to lowercase, replace special characters)
                sanitized_name = flow_name.replace(" ", "_").lower()
                sanitized_payload[sanitized_name] = flow_data

            # Overwrite the flow_mappings.json file with sanitized flow names
            with open(self.flow_mapping_path, "w") as f:
                json.dump(sanitized_payload, f, indent=2)

            # Update .intent files using sanitized flow names
            self.update_intent_files(sanitized_payload)

            # Restart OVOS service to retrain Padatious
            self.restart_ovos_service()

            self.client.publish("saved_flow_mappings", json.dumps({"status": "success"}))
            self.log.info("✅ Flow mappings opgeslagen en intent-bestanden bijgewerkt.")
        except Exception as e:
            self.client.publish("saved_flow_mappings", json.dumps({"status": "failure", "error": str(e)}))
            self.log.error(f"❌ Fout bij het opslaan van flow mappings: {e}")

    def _request_flows(self, payload):
        try:
            search_string = payload.get("name", "")
            args = ["node", os.path.expanduser("~/.venvs/ovos/lib/python3.11/site-packages/ovos_skill_homeyflowtrigger/nodejs/get_flow.js"), search_string]
            self.log.info("✅ Start the subprocess for Homey API.")
            result = subprocess.run(args, capture_output=True, text=True, check=True)
            flows = json.loads(result.stdout.strip())

            # Check payload size
            payload_size = len(json.dumps(flows))
            self.log.info(f"Payload size: {payload_size} bytes")

            self.client.publish("send_flows", json.dumps(flows))
            self.log.info("✅ Flows verzonden.")
        except subprocess.CalledProcessError as e:
            self.log.error(f"❌ Fout bij ophalen van flows: {e.stderr}")
        except Exception as e:
            self.log.error(f"❌ Fout bij verwerken van flows: {e}") 

    def update_intent_files(self, mappings):
        """Update .intent files based on the current flow mappings."""
        try:
            # Ensure the intent directory exists
            os.makedirs(self.intent_dir, exist_ok=True)

            # Get the current list of .intent files
            existing_intent_files = set(os.listdir(self.intent_dir))

            # Track the intent files that should exist
            required_intent_files = set()

            for flow_name, flow_data in mappings.items():
                intent_file_name = f"{flow_name}.intent"
                required_intent_files.add(intent_file_name)

                # Write or update the .intent file
                self.create_intent_file(flow_name, flow_data.get("sentences", []))

            # Delete .intent files that are no longer needed
            for intent_file in existing_intent_files - required_intent_files:
                flow_name = os.path.splitext(intent_file)[0]
                self.delete_intent_file(flow_name)

        except Exception as e:
            self.log.error(f"❌ Fout bij het bijwerken van intent-bestanden: {e}")

    def create_intent_file(self, flow_name, sentences):
        """Create or update a .intent file for the given flow."""
        try:
            # Sanitize the flow_name to remove unwanted characters
            sanitized_flow_name = flow_name.replace("'", "").replace(" ", "_")

            # Ensure the intent directory exists
            os.makedirs(self.intent_dir, exist_ok=True)

            # Define the path for the .intent file
            intent_file_path = os.path.join(self.intent_dir, f"{sanitized_flow_name}.intent")

            # Write the sentences to the .intent file
            with open(intent_file_path, "w") as f:
                for sentence in sentences:
                    f.write(sentence + "\n")

            self.log.info(f"✅ .intent-bestand aangemaakt voor flow: {sanitized_flow_name}")
        except Exception as e:
            self.log.error(f"❌ Fout bij het aanmaken van .intent-bestand voor flow '{flow_name}': {e}")

    def delete_intent_file(self, flow_name):
        """Verwijder het .intent-bestand voor de gegeven flow."""
        try:
            intent_file_path = os.path.join(self.intent_dir, f"{flow_name}.intent")
            if os.path.exists(intent_file_path):
                os.remove(intent_file_path)
                self.log.info(f"✅ .intent-bestand verwijderd voor flow: {flow_name}")
            else:
                self.log.warning(f"⚠️ .intent-bestand voor flow '{flow_name}' niet gevonden.")
        except Exception as e:
            self.log.error(f"❌ Fout bij het verwijderen van .intent-bestand voor flow '{flow_name}': {e}")

    def restart_ovos_service(self):
        """Restart the OVOS service to retrain Padatious."""
        try:
            subprocess.run(["systemctl", "--user", "restart", "ovos.service"], check=True)
            self.log.info("✅ OVOS service succesvol herstart.")
        except subprocess.CalledProcessError as e:
            self.log.error(f"❌ Fout bij het herstarten van de OVOS-service: {e}")
        except Exception as e:
            self.log.error(f"❌ Onverwachte fout bij het herstarten van de OVOS-service: {e}")

    def handle_start_flow(self, message):
        # Use the intent type (name of the .intent file) as the flow_name
        flow_name = message.data.get("intent_type", "").strip()

        try:
            # Load the flow_mappings.json file
            with open(self.flow_mapping_path, "r") as f:
                mappings = json.load(f)
        except Exception as e:
            self.log.error(f"❌ Kan flow_mappings.json niet laden: {e}")
            self.speak("Er ging iets mis bij het openen van de flow instellingen.")
            return

        # Get the flow info directly using the flow_name
        flow_info = mappings.get(flow_name)

        if not flow_info or "flow_id" not in flow_info:
            self.speak(f"Ik weet niet welke flow ik moet starten voor '{flow_name}'.")
            self.log.error(f"❌ Geen geldige flow-info voor intent: {flow_name}")
            return

        flow_id = flow_info["flow_id"]
        self.log.info("✅ Flow name is '{flow_name}' and flow id is '{flow_id}'.")
        # Stel het pad in naar het Node.js-script en geef de flow-id door als argument
        args = ["node", os.path.expanduser("~/.venvs/ovos/lib/python3.11/site-packages/ovos_skill_homeyflowtrigger/nodejs/start_flow.js"), flow_id]

        try:
            result = subprocess.run(args, capture_output=True, text=True, check=True)
            response = result.stdout.strip() or f"De flow '{flow_name}' is gestart."
            self.log.info(f"✅ {response}")
        except subprocess.CalledProcessError as e:
            response = f"Er ging iets mis bij het starten van '{flow_name}'."
            self.log.error(f"❌ Fout bij starten van flow '{flow_name}': {e.stderr}")

        self.speak(response)