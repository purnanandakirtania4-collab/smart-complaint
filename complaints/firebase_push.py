import json
import os

import firebase_admin
from firebase_admin import credentials, messaging

from .models import DeviceToken


def get_firebase_app():

    try:
        return firebase_admin.get_app()

    except ValueError:
        pass

    service_account_json = os.environ.get(
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        "",
    ).strip()

    if not service_account_json:
        raise RuntimeError(
            "FIREBASE_SERVICE_ACCOUNT_JSON is missing."
        )

    service_account_info = json.loads(
        service_account_json
    )

    credential = credentials.Certificate(
        service_account_info
    )

    return firebase_admin.initialize_app(
        credential
    )


def send_push_to_user(
    user,
    title,
    message,
    data=None,
):

    get_firebase_app()

    device_tokens = (
        DeviceToken.objects
        .filter(
            user=user,
            is_active=True,
        )
    )

    sent_count = 0

    push_data = {}

    if data:
        push_data = {
            str(key): str(value)
            for key, value in data.items()
        }

    for device in device_tokens:

        try:

            firebase_message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=message,
                ),
                data=push_data,
                token=device.token,
            )

            messaging.send(
                firebase_message
            )

            sent_count += 1

        except Exception as error:

            print(
                "FCM PUSH ERROR:",
                device.id,
                error,
            )

    return sent_count