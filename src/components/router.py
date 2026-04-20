from modules.messaging.double_ratchet.module import DoubleRatchetModule
from modules.messaging.spqr.module import SPQRModule
from modules.key_exchange.pqxdh.module import PQXDHModule
from modules.key_exchange.x3dh.module import X3DHModule


class Router:

    def __init__(self):
        self.modules = {
            "double_ratchet": DoubleRatchetModule(),
            "spqr": SPQRModule(),
            "pqxdh": PQXDHModule(),
            "x3dh": X3DHModule(),
        }
        self.module_cards = {
            "double_ratchet": {
                "id": "double_ratchet",
                "title": "Double Ratchet",
                "subtitle": "Post-X3DH messaging",
                "description": "Interactive ratchet simulation with message timeline, attacker perspective, and send/receive step visualization.",
            },
            "spqr": {
                "id": "spqr",
                "title": "SPQR",
                "subtitle": "Sparse post-quantum messaging",
                "description": "Sparse Post-Quantum Ratchet simulation with SPQR state-machine messaging and timeline interaction.",
            },
            "x3dh": {
                "id": "x3dh",
                "title": "X3DH",
                "subtitle": "Session bootstrap",
                "description": "Three-phase model of registration, prekey-bundle processing, and initial message establishment with SK and AD checks.",
            },
            "pqxdh": {
                "id": "pqxdh",
                "title": "PQXDH",
                "subtitle": "Post-quantum session bootstrap",
                "description": "X3DH-style flow extended with signed PQ prekeys and KEM-derived shared secret contribution.",
            },
        }

    def get_current_module(self, app_state):
        return self.modules[app_state.current_module]

    def get_module_cards(self) -> list[dict]:
        return [
            self.module_cards[module_id]
            for module_id in self.modules.keys()
            if module_id in self.module_cards
        ]

    def export_state(self) -> dict:
        module_state = {}
        for module_name, module in self.modules.items():
            if hasattr(module, "export_state"):
                module_state[module_name] = module.export_state()
        return module_state

    def import_state(self, state: dict) -> None:
        if not isinstance(state, dict):
            return

        for module_name, module_data in state.items():
            module = self.modules.get(module_name)
            if module and hasattr(module, "import_state"):
                module.import_state(module_data)
