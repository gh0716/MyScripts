from typing import Optional

from utils.dateutil import format_timestamp, parse_datetime

from . import Menu


class InputDateMenu(Menu[str]):
    def __init__(
        self,
        prompt: str = "",
        text="",
        default_ts: Optional[float] = None,
    ):
        items = []
        if default_ts is not None:
            items.append(format_timestamp(default_ts))
        items += [
            "Today",
            "Tomorrow",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        super().__init__(
            prompt=prompt,
            items=items,
            text=text,
        )


def input_date(prompt: str, default_ts: Optional[float] = None) -> Optional[float]:
    menu = InputDateMenu(
        prompt=prompt,
        default_ts=default_ts,
    )
    menu.exec()

    val = menu.get_text()
    if val is None:
        return None

    # Return none if input was cancelled
    if val is None:
        return None

    # Return 0 if the user input was empty
    if val == "":
        return 0.0

    # Parse date and time
    dt = parse_datetime(val)
    if not dt:
        return None

    # Convert to timestamp
    ts = dt.timestamp()
    return ts
