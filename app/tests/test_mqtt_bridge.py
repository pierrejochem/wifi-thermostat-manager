"""Guards the paho callback-API v2 contract the bridge is built against.

paho-mqtt 2.x hands ``on_connect`` a ``ReasonCode`` plus a ``properties``
argument instead of the v1 integer ``rc``. These tests drive the callbacks the
way paho does, so a regression to a v1-shaped signature fails here rather than
silently leaving the bridge stuck at ``connected = False`` on the device.
"""
import paho.mqtt.client as mqtt
import pytest

from mqtt_client import MqttBridge


class FakeMsg:
    def __init__(self, topic: str, payload: bytes):
        self.topic = topic
        self.payload = payload


@pytest.fixture
def bridge():
    return MqttBridge(host="broker", port=1883, base_topic="wtm")


def _reason(name: str) -> mqtt.ReasonCode:
    return mqtt.ReasonCode(mqtt.PacketTypes.CONNACK, name)


def test_client_uses_callback_api_v2(bridge):
    # v1 clients are still accepted by paho 2.x but only with a
    # DeprecationWarning; assert we opted into v2 explicitly.
    assert bridge._client._callback_api_version is mqtt.CallbackAPIVersion.VERSION2


def test_on_connect_success_marks_connected_and_subscribes(bridge):
    published, subscribed = [], []
    client = type(
        "C",
        (),
        {
            "publish": lambda _s, *a, **k: published.append(a),
            "subscribe": lambda _s, t: subscribed.append(t),
        },
    )()

    bridge._on_connect(client, None, {}, _reason("Success"), None)

    assert bridge.connected is True
    assert ("wtm/bridge/availability", "online") == published[0][:2]
    assert subscribed == ["wtm/+/+/set"]


def test_on_connect_failure_leaves_bridge_disconnected(bridge):
    client = type("C", (), {"publish": lambda *a, **k: None, "subscribe": lambda *a: None})()

    bridge._on_connect(client, None, {}, _reason("Not authorized"), None)

    assert bridge.connected is False


def test_on_message_routes_command_to_handler(bridge):
    seen = []
    bridge.set_command_handler(lambda *args: seen.append(args))

    bridge._on_message(None, None, FakeMsg("wtm/abc123/target/set", b"21.5"))

    assert seen == [("abc123", "target", "21.5")]


@pytest.mark.parametrize(
    "topic",
    [
        "other/abc123/target/set",  # wrong base topic
        "wtm/abc123/target/state",  # state, not a command
        "wtm/abc123/set",           # too few segments
    ],
)
def test_on_message_ignores_unrelated_topics(bridge, topic):
    seen = []
    bridge.set_command_handler(lambda *args: seen.append(args))

    bridge._on_message(None, None, FakeMsg(topic, b"21.5"))

    assert seen == []
