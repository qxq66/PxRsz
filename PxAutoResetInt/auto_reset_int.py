class AutoResetInt:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (
                    "INT",
                    {
                        "default": 123,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "step": 1,
                        "display": "number",
                        "control_after_generate": "increment",
                        "tooltip": "Current counter value.",
                    },
                ),
                "reset_value": (
                    "INT",
                    {
                        "default": 123,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "step": 1,
                        "display": "number",
                        "tooltip": "Target value to reset to after queue is finished.",
                    },
                ),
                "reset_mode": (
                    ["Auto", "Manual"],
                    {
                        "default": "Auto",
                        "tooltip": "Auto: reset instantly when queue empties.\nManual: wait reset_delay_seconds.",
                    },
                ),
                "reset_delay_seconds": (
                    "INT",
                    {
                        "default": 3,
                        "min": 1,
                        "max": 300,
                        "step": 1,
                        "display": "number",
                        "tooltip": "Only used in Manual mode.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("value",)
    FUNCTION = "execute"
    CATEGORY = "utils"
    OUTPUT_NODE = False

    @classmethod
    def IS_CHANGED(cls, value, **kwargs):
        return value

    def execute(self, value: int, reset_value: int, reset_mode: str, reset_delay_seconds: int):
        return (value,)


NODE_CLASS_MAPPINGS = {
    "AutoResetInt": AutoResetInt,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AutoResetInt": "Auto Reset Int",
}
