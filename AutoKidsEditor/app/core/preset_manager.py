from types import ModuleType

from app.presets import kids_story_v1


class PresetManager:
    _presets = {"kids_story_v1": kids_story_v1}
    DEFAULT_PRESET = "kids_story_v1"

    @classmethod
    def get_preset(cls, preset_name: str = DEFAULT_PRESET) -> ModuleType:
        try:
            return cls._presets[preset_name]
        except KeyError as error:
            raise ValueError(f"Preset desconhecido: {preset_name}") from error

    @classmethod
    def get_available_presets(cls) -> list[str]:
        return list(cls._presets)
