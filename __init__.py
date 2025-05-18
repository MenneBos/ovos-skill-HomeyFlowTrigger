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
from difflib import get_close_matches

DEFAULT_SETTINGS = {
    "log_level": "INFO"
}

class HomeyFlowSkill(OVOSSkill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.override = True

        # Load configuration from config.json
        self.config_path = os.path.join(self.root_dir, "nodejs", "config.json")
        self.config = self._load_config()

        # Extract broker_url
        self.broker_url = self.config.get("broker", {}).get("url")
        if not self.broker_url:
            self.log.error("❌ broker_url is missing in config.json")

        # Extract values from the configuration
        self.homey_address = self.config["homey"]["address"]
        self.homey_token = self.config["homey"]["token"]
        self.broker_url = self.config["broker"]["url"]
        self.broker_login = self.config["broker"]["login"]
        self.broker_password = self.config["broker"]["password"]
        self.nodejs_start_flow = os.path.expanduser(self.config["nodejs"]["start_flow"])
        self.nodejs_get_flow = os.path.expanduser(self.config["nodejs"]["get_flow"])

    def _load_config(self):
        """Load the configuration file."""
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
                self.log.info(f"✅ Loaded config.json: {config}")
                return config
        except Exception as e:
            self.log.error(f"❌ Failed to load config.json: {e}")
            return {}

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

    def restart_ovos_service():
        try:
            subprocess.run(["systemctl", "restart", "ovos"], check=True)
            print("✅ OVOS service restarted successfully.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to restart OVOS service: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

    def _setup_mqtt(self):
        try:
            # MQTT broker details
            BROKER = self.broker_url
            PORT = 8884  # WebSocket secure port
            USERNAME = self.broker_login
            PASSWORD = self.broker_password
            TOPIC = "hello/topic"


            # Callback when the client connects to the broker
            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    self.log.info("✅ Connected to HiveMQ broker")
                    client.subscribe(TOPIC)
                else:
                    self.log.error(f"❌ Failed to connect to broker, return code {rc}")


            self.client = mqtt.Client()

            # Callback when a message is received
            def on_message(client, userdata, msg):
                try:
                    topic = msg.topic
                    payload = msg.payload.decode().strip()  # Decode the payload and strip whitespace
                    self.log.info(f"Received topic: {topic} with payload: {payload}")

                    # Handle specific topics
                    if topic == "request_flow_mappings":
                        self._send_flow_mappings()
                    elif topic == "save_flow_mappings":
                        self._save_flow_mappings(json.loads(payload))
                    elif topic == "request_flows":
                        self._request_flows(json.loads(payload))
                except Exception as e:
                    self.log.error(f"❌ Error processing MQTT message: {e}")

            # Create MQTT client
            self.client = mqtt.Client(transport="websockets")
            self.client.username_pw_set(USERNAME, PASSWORD)
            self.client.tls_set()  # Enable TLS

            # Assign callbacks
            self.client.on_connect = on_connect
            self.client.on_message = on_message 

            # Connect to the broker
            self.client.connect(BROKER, PORT)    

            # Start the MQTT loop
            self.client.loop_start()
            self.log.info("✅ MQTT client setup complete and connected to HiveMQ broker")
        except Exception as e:
            self.log.error(f"❌ Error setting up MQTT client: {e}")   

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
            args = ["node", self.nodejs_get_flow, search_string]
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
        # Extract the utterance from the message
        utterance = message.data.get("utterance", "").strip().lower()

        # Fallback to the first item in 'utterances' if 'utterance' is empty
        if not utterance and "utterances" in message.data and message.data["utterances"]:
            utterance = message.data["utterances"][0].strip().lower()

        self.log.info(f"✅ Selected utterance: '{utterance}'")

        try:
            # Load the flow_mappings.json file
            with open(self.flow_mapping_path, "r") as f:
                mappings = json.load(f)
        except Exception as e:
            self.log.error(f"❌ Kan flow_mappings.json niet laden: {e}")
            self.speak("Er ging iets mis bij het openen van de flow instellingen.")
            return

        # Flatten the sentences in flow_mappings.json for fuzzy matching
        sentence_to_flow = {}
        for flow_name, flow_data in mappings.items():
            for sentence in flow_data.get("sentences", []):
                sentence_to_flow[sentence.lower()] = flow_name

        # Use fuzzy matching to find the closest sentence
        all_sentences = list(sentence_to_flow.keys())
        closest_matches = get_close_matches(utterance, all_sentences, n=1, cutoff=0.6)

        if not closest_matches:
            self.speak(f"Ik weet niet welke flow ik moet starten voor '{utterance}'.")
            self.log.error(f"❌ Geen overeenkomende zin gevonden voor utterance: '{utterance}'")
            return

        # Get the flow name from the closest matching sentence
        closest_sentence = closest_matches[0]
        flow_name = sentence_to_flow[closest_sentence]
        flow_info = mappings[flow_name]

        flow_id = flow_info.get("id")
        if not flow_id:
            self.speak(f"Ik weet niet welke flow ik moet starten voor '{flow_name}'.")
            self.log.error(f"❌ Geen id gevonden voor flow: '{flow_name}'")
            return

        # Stel het pad in naar het Node.js-script en geef de flow-id door als argument
        args = ["node", self.nodejs_start_flow, flow_id]

        try:
            result = subprocess.run(args, capture_output=True, text=True, check=True)
            response = result.stdout.strip() or f"De flow '{flow_name}' is gestart."
            self.log.info(f"✅ {response}")
        except subprocess.CalledProcessError as e:
            response = f"Er ging iets mis bij het starten van '{flow_name}'."
            self.log.error(f"❌ Fout bij starten van flow '{flow_name}': {e.stderr}")

        self.speak(response)