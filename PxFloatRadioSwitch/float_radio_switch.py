"""Float Radio Switch: bis zu 20 Float-Werte, ein Radio-Button waehlt den aktiven Wert."""

MAX_INPUTS = 20
_DEFAULTS = [0.22, 0.44, 0.66, 0.88] + [1.0] * (MAX_INPUTS - 4)


class PxFloatRadioSwitch:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            f"value_{i + 1}": ("FLOAT", {
                "default": _DEFAULTS[i], "min": -100000.0, "max": 100000.0,
                "step": 0.01, "round": 0.001,
            })
            for i in range(MAX_INPUTS)
        }
        return {
            "required": {
                "inputs": ([str(n) for n in range(2, MAX_INPUTS + 1)], {"default": "2"}),
                "selected": ("INT", {"default": 1, "min": 1, "max": MAX_INPUTS}),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("FLOAT",)
    RETURN_NAMES = ("value",)
    FUNCTION = "select"
    CATEGORY = "utils/float"
    DESCRIPTION = "Waehlt per Radio-Button einen von 2-20 Float-Werten und gibt ihn aus."

    def select(self, inputs="2", selected=1, **values):
        count = max(2, min(MAX_INPUTS, int(inputs)))
        index = max(1, min(count, int(selected)))
        value = values.get(f"value_{index}")
        if value is None:
            value = _DEFAULTS[index - 1]
        return (float(value),)


NODE_CLASS_MAPPINGS = {"PxFloatRadioSwitch": PxFloatRadioSwitch}
NODE_DISPLAY_NAME_MAPPINGS = {"PxFloatRadioSwitch": "Float Radio Switch"}
