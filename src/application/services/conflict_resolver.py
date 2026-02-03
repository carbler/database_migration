from src.application.strategies.base_strategy import BaseStrategy
from src.application.strategies.fail_strategy import FailStrategy
from src.application.strategies.overwrite_strategy import OverwriteStrategy
from src.application.strategies.skip_strategy import SkipStrategy
from src.application.strategies.merge_strategy import MergeStrategy

class ConflictResolver:
    def __init__(self, strategy_name: str):
        self.strategy = self._get_strategy(strategy_name)

    def _get_strategy(self, name: str) -> BaseStrategy:
        strategies = {
            'fail': FailStrategy,
            'overwrite': OverwriteStrategy,
            'skip': SkipStrategy,
            'merge': MergeStrategy
        }

        strategy_class = strategies.get(name.lower())
        if not strategy_class:
            raise ValueError(f"Unknown strategy: {name}")

        return strategy_class()

    def get_strategy(self) -> BaseStrategy:
        return self.strategy
