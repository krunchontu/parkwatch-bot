"""Message builders for ParkWatch SG."""

from ..formatting import DIVIDER, format_sgt_time


def build_alert_message(sighting, pos, neg, badge, accuracy_indicator, feedback_received=False):
    """Build the full alert message from structured sighting data.

    Single source of truth for alert format — used by both the initial
    broadcast and the feedback update path.
    """
    zone = sighting["zone"]
    reported_at = sighting["reported_at"]
    description = sighting.get("description")
    lat = sighting.get("lat")
    lng = sighting.get("lng")

    time_str = format_sgt_time(reported_at)

    msg = f"\U0001f6a8 WARDEN ALERT \u2014 {zone}\n"
    msg += f"\U0001f550 Spotted: {time_str}\n"
    if description:
        msg += f"\U0001f4dd Location: {description}\n"
    if lat and lng:
        msg += f"\U0001f310 GPS: {lat:.6f}, {lng:.6f}\n"

    if accuracy_indicator:
        msg += f"\U0001f464 Reporter: {badge} {accuracy_indicator}\n"
    else:
        msg += f"\U0001f464 Reporter: {badge}\n"

    msg += "\n\u23f0 Extend your parking now!\n"
    msg += f"\n{DIVIDER}\n"

    if feedback_received:
        msg += f"\U0001f4ca Feedback: \U0001f44d {pos} / \U0001f44e {neg}\n"
        msg += "Thanks for your feedback!"
    else:
        msg += "Was this accurate? Your feedback helps!"

    return msg
