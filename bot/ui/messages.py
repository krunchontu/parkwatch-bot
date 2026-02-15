"""Message builders for ParkWatch SG."""

from datetime import timezone

from ..utils import SGT


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

    # Convert to SGT for display; reported_at may be naive (UTC) or aware
    if reported_at.tzinfo is None:
        reported_at_sgt = reported_at.replace(tzinfo=timezone.utc).astimezone(SGT)
    else:
        reported_at_sgt = reported_at.astimezone(SGT)
    time_str = reported_at_sgt.strftime("%I:%M %p SGT")

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
    msg += "\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"

    if feedback_received:
        msg += f"\U0001f4ca Feedback: \U0001f44d {pos} / \U0001f44e {neg}\n"
        msg += "Thanks for your feedback!"
    else:
        msg += "Was this accurate? Your feedback helps!"

    return msg
