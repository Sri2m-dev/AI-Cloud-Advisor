"""Append-only in-memory PUE activation configuration repository."""

from dataclasses import replace

from universal_evidence.activation.models import ConfigState


class InMemoryPueActivationRepository:
    def __init__(self) -> None:
        self._configs = {}
        self._scope_history = {}
        self._kill_switches = []

    def store(self, config):
        existing = self._configs.get(config.fingerprint)
        if existing is not None:
            return existing
        history = self._scope_history.setdefault(config.scope.key, [])
        if history:
            previous = self._configs[history[-1]]
            if previous.state is ConfigState.ACTIVE:
                self._configs[previous.fingerprint] = replace(
                    previous, state=ConfigState.SUPERSEDED
                )
        self._configs[config.fingerprint] = config
        history.append(config.fingerprint)
        return config

    def history(self, scope):
        return tuple(self._configs[item] for item in self._scope_history.get(scope.key, ()))

    def active_configs(self):
        return tuple(
            config for config in self._configs.values() if config.state is ConfigState.ACTIVE
        )

    def expire(self, activation_id):
        config = self.by_id(activation_id)
        if config is None:
            raise KeyError("activation config not found")
        expired = replace(config, state=ConfigState.EXPIRED)
        self._configs[config.fingerprint] = expired
        return expired

    def by_id(self, activation_id):
        return next(
            (config for config in self._configs.values() if config.activation_id == activation_id),
            None,
        )

    def store_kill_switch(self, config):
        existing = next(
            (item for item in self._kill_switches if item.fingerprint == config.fingerprint),
            None,
        )
        if existing is not None:
            return existing
        self._kill_switches.append(config)
        return config

    def current_kill_switch(self):
        return self._kill_switches[-1] if self._kill_switches else None

    @property
    def kill_switch_history(self):
        return tuple(self._kill_switches)
