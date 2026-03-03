from modules.double_ratchet.module import DoubleRatchetModule


class Router:

    def __init__(self):
        self.modules = {
            "double_ratchet": DoubleRatchetModule()
        }

    def get_current_module(self, app_state):
        return self.modules[app_state.current_module]

    def export_state(self) -> dict:
        module_state = {}
        for module_name, module in self.modules.items():
            if hasattr(module, "export_state"):
                module_state[module_name] = module.export_state()
        return module_state

    def import_state(self, state: dict) -> None:
        for module_name, module_data in state.items():
            module = self.modules.get(module_name)
            if module and hasattr(module, "import_state"):
                module.import_state(module_data)
