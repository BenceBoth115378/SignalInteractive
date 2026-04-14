"""Logic facade for attacker dashboard analysis.

The core implementation currently lives in view.py to avoid behavior changes
while the architecture transitions to strict logic/view separation.
"""

from modules.messaging.double_ratchet.attacker_dashboard import view as attacker_dashboard_view


def collect_attacker_secret_options(session):
    return attacker_dashboard_view.collect_attacker_secret_options(session)


def decrypt_with_attacker_selection(session, pending_messages, compromised_secrets, session_ad=b""):
    return attacker_dashboard_view.decrypt_with_attacker_selection(
        session,
        pending_messages,
        compromised_secrets,
        session_ad,
    )


def get_attacker_analysis(session, pending_messages, compromised_secrets, session_ad=b""):
    return attacker_dashboard_view.get_attacker_analysis(
        session,
        pending_messages,
        compromised_secrets,
        session_ad,
    )
