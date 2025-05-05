from ovos_workshop.skills.ovos import OVOSSkill
import subprocess
import os
import json
import paho.mqtt.client as mqtt
import crypt  # For password hashing comparison

class HomeyFlowSkill(OVOSSkill):
    def initialize(self):
        self.flow_mapping_path = os.path.join(self.root_dir, "flow_mappings.json")
        self.register_intent("HomeyFlow.intent", self.handle_start_flow)
        self._setup_mqtt()

    def _setup_mqtt(self):
        self.client = mqtt.Client()
        self.client.tls_set(
            ca_certs="/etc/mosquitto/certs/ca.crt",
            certfile="/etc/mosquitto/certs/client.crt",
            keyfile="/etc/mosquitto/certs/client.key"
        )

        # Dynamically load username and password from /etc/mosquitto/passwd
        username, password = self._get_mqtt_credentials("/etc/mosquitto/passwd")
        if not username or not password:
            self.log.error("❌ Kon geen MQTT-gebruikersnaam en wachtwoord laden.")
            return

        self.client.username_pw_set(username, password)
        self.client.connect("ovos-server.local", 8883, 60)
        self.client.subscribe("homey/add_flowmap")
        self.client.subscribe("homey/remove_flowmap")
        self.client.on_message = self._on_mqtt_message
        self.client.loop_start()

    def _get_mqtt_credentials(self, passwd_file_path):
        """
        Reads the Mosquitto passwd file and extracts the first username and password.
        Assumes the password is hashed and matches the client certificate.
        """
        try:
            with open(passwd_file_path, "r") as f:
                for line in f:
                    if line.strip() and not line.startswith("#"):
                        parts = line.split(":")
                        if len(parts) == 2:
                            username = parts[0].strip()
                            hashed_password = parts[1].strip()
                            # Return the username and hashed password (if needed for validation)
                            return username, hashed_password
        except Exception as e:
            self.log.error(f"❌ Fout bij het lezen van het passwd-bestand: {e}")
        return None, None
    
    def _on_mqtt_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            utterance = payload.get("utterance")
            flow_name = payload.get("name")

            with open(self.flow_mapping_path, "r") as f:
                mappings = json.load(f)

            if topic == "homey/add_flowmap":
                self._add_flow_mapping(payload, mappings)

            elif topic == "homey/remove_flowmap":
                self._remove_flow_mapping(payload, mappings)

            elif topic == "homey/show_flowmap":
                self._update_flow_mappings(mappings)

            elif topic == "homey/delete_flowmap":
                self._delete_non_favorite_flows(mappings)

        except Exception as e:
            self.log.error(f"❌ Fout bij verwerken MQTT-bericht: {e}")
            self.speak("Er ging iets mis bij het verwerken van het MQTT-bericht.")

    def _add_flow_mapping(self, payload, mappings):
        """
        Adds a new intent sentence to the flow_name record in flow_mappings.json.
        """
        try:
            utterance = payload.get("utterance")
            flow_name = payload.get("name")

            if not utterance or not flow_name:
                self.log.error("❌ MQTT-bericht onvolledig")
                self.speak("MQTT-bericht onvolledig")
                return

            # Add the sentence to the flow_name record
            if flow_name in mappings:
                if utterance not in mappings[flow_name]["sentences"]:
                    mappings[flow_name]["sentences"].append(utterance)
                    self.log.info(f"✅ Intentzin toegevoegd aan flow: '{utterance}' -> {flow_name}")
                else:
                    self.log.warning(f"⚠️ Intentzin bestaat al voor flow: '{utterance}' -> {flow_name}")
                    self.speak("Deze intentzin bestaat al.")
                    return
            else:
                # Create a new flow_name record if it doesn't exist
                mappings[flow_name] = {
                    "flow_id": payload.get("id", "unknown"),
                    "sentences": [utterance],
                    "favorite_flow": "no"
                }
                self.log.info(f"✅ Nieuwe flow toegevoegd: '{flow_name}' met intentzin '{utterance}'")

            # Save the updated mappings to the JSON file
            with open(self.flow_mapping_path, "w") as f:
                json.dump(mappings, f, indent=2)

            # Add the sentence to the HomeyFlow.intent file
            intent_file_path = os.path.join(self.root_dir, "locale", "nl-NL", "HomeyFlow.intent")
            os.makedirs(os.path.dirname(intent_file_path), exist_ok=True)
            with open(intent_file_path, "a") as intent_file:
                intent_file.write(f"{utterance}\n")

            self.speak(f"Intentzin '{utterance}' is toegevoegd aan de flow '{flow_name}'.")

        except Exception as e:
            self.log.error(f"❌ Fout bij toevoegen van flow mapping: {e}")
            self.speak("Er ging iets mis bij het toevoegen van de flow mapping.")

    def _remove_flow_mapping(self, payload, mappings):
        """
        Removes an intent sentence from the flow_name record in flow_mappings.json
        and from the HomeyFlow.intent file.
        """
        try:
            utterance = payload.get("utterance")
            flow_name = payload.get("name")

            if not utterance or not flow_name:
                self.log.error("❌ MQTT-bericht onvolledig")
                self.speak("MQTT-bericht onvolledig")
                return

            # Remove the sentence from the flow_name record
            if flow_name in mappings:
                if utterance in mappings[flow_name]["sentences"]:
                    mappings[flow_name]["sentences"].remove(utterance)
                    self.log.info(f"✅ Intentzin verwijderd uit flow: '{utterance}' -> {flow_name}")

                    # If no sentences remain, remove the flow_name record
                    if not mappings[flow_name]["sentences"]:
                        del mappings[flow_name]
                        self.log.info(f"✅ Flow '{flow_name}' verwijderd omdat er geen intentzinnen meer zijn.")
                else:
                    self.log.warning(f"⚠️ Intentzin niet gevonden in flow: '{utterance}' -> {flow_name}")
                    self.speak("Deze intentzin is niet gevonden in de flow.")
                    return
            else:
                self.log.warning(f"⚠️ Flow niet gevonden: '{flow_name}'")
                self.speak("Deze flow is niet gevonden.")
                return

            # Save the updated mappings to the JSON file
            with open(self.flow_mapping_path, "w") as f:
                json.dump(mappings, f, indent=2)

            # Remove the sentence from the HomeyFlow.intent file
            intent_file_path = os.path.join(self.root_dir, "locale", "nl-NL", "HomeyFlow.intent")
            if os.path.exists(intent_file_path):
                with open(intent_file_path, "r") as intent_file:
                    lines = intent_file.readlines()
                with open(intent_file_path, "w") as intent_file:
                    for line in lines:
                        if line.strip() != utterance:
                            intent_file.write(line)

            self.speak(f"Intentzin '{utterance}' is verwijderd uit de flow '{flow_name}'.")

        except Exception as e:
            self.log.error(f"❌ Fout bij verwijderen van flow mapping: {e}")
            self.speak("Er ging iets mis bij het verwijderen van de flow mapping.")

    def _update_flow_mappings(self, mappings):
        """
        Updates the flow_mappings.json file with favorite flows from the Homey API.
        """
        try:
            # Run the Node.js script to fetch favorite flows
            args = ["node", os.path.join(self.root_dir, "get_favorite_flows.js")]
            result = subprocess.run(args, capture_output=True, text=True, check=True)
            favorite_flows = json.loads(result.stdout.strip())

            # Update the mappings with the favorite flows
            for flow in favorite_flows:
                flow_id = flow["id"]
                flow_name = flow["name"]

                if flow_name in mappings:
                    # Update existing flow entry
                    mappings[flow_name]["favorite_flow"] = "yes"
                else:
                    # Add new flow entry
                    mappings[flow_name] = {
                        "flow_id": flow_id,
                        "sentences": ["none"],
                        "favorite_flow": "yes"
                    }

            # Mark flows no longer favorite
            favorite_flow_names = [flow["name"] for flow in favorite_flows]
            for flow_name in list(mappings.keys()):
                if flow_name not in favorite_flow_names:
                    mappings[flow_name]["favorite_flow"] = "no"

            # Save the updated mappings to the JSON file
            with open(self.flow_mapping_path, "w") as f:
                json.dump(mappings, f, indent=2)

            self.log.info("✅ Flow mappings bijgewerkt met favoriete flows.")
            self.speak("De flow mappings zijn bijgewerkt.")

        except subprocess.CalledProcessError as e:
            self.log.error(f"❌ Fout bij ophalen van favoriete flows: {e.stderr}")
            self.speak("Er ging iets mis bij het ophalen van de favoriete flows.")
        except Exception as e:
            self.log.error(f"❌ Fout bij het bijwerken van flow mappings: {e}")
            self.speak("Er ging iets mis bij het bijwerken van de flow mappings.")

    def _delete_non_favorite_flows(self, mappings):
        """
        Deletes all flows with "favorite_flow": "no" from flow_mappings.json
        and removes their sentences from the HomeyFlow.intent file.
        """
        try:
            # Collect all sentences to be removed
            sentences_to_remove = []
            flows_to_delete = []

            for flow_name, flow_data in mappings.items():
                if flow_data.get("favorite_flow") == "no":
                    sentences_to_remove.extend(flow_data.get("sentences", []))
                    flows_to_delete.append(flow_name)

            # Remove flows from mappings
            for flow_name in flows_to_delete:
                del mappings[flow_name]
                self.log.info(f"✅ Flow '{flow_name}' verwijderd omdat het niet favoriet is.")

            # Save the updated mappings to the JSON file
            with open(self.flow_mapping_path, "w") as f:
                json.dump(mappings, f, indent=2)

            # Update the HomeyFlow.intent file
            intent_file_path = os.path.join(self.root_dir, "locale", "nl-NL", "HomeyFlow.intent")
            if os.path.exists(intent_file_path):
                with open(intent_file_path, "r") as intent_file:
                    lines = intent_file.readlines()
                with open(intent_file_path, "w") as intent_file:
                    for line in lines:
                        if line.strip() not in sentences_to_remove:
                            intent_file.write(line)

            self.speak("Alle niet-favoriete flows zijn verwijderd.")

        except Exception as e:
            self.log.error(f"❌ Fout bij verwijderen van niet-favoriete flows: {e}")
            self.speak("Er ging iets mis bij het verwijderen van niet-favoriete flows.")

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