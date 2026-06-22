from core.kart_sandbox import kart_env


def test_kart_env_marks_network_policy():
    assert kart_env(allow_net=False)["WILLOW_KART_ALLOW_NET"] == "0"
    assert kart_env(allow_net=True)["WILLOW_KART_ALLOW_NET"] == "1"
