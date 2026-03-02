class BaseModule:
    def build(self, page, app_state):
        raise NotImplementedError

    def next_step(self, app_state):
        app_state.current_step += 1

    def prev_step(self, app_state):
        if app_state.current_step > 0:
            app_state.current_step -= 1
