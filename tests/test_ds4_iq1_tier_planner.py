from tools.ds4_iq1_tier_planner import (
    BLOCK_BYTES,
    CURRENT_IQ2,
    GIB,
    IQ1_ALL,
    mixed_hot_iq2_warm_iq1,
)


def test_iq1_s_effective_bpw_and_expert_size() -> None:
    assert BLOCK_BYTES["IQ1_S"] == 50
    assert BLOCK_BYTES["IQ1_S"] * 8 / 256 == 1.5625
    assert IQ1_ALL.expert_bytes == 4_915_200
    assert IQ1_ALL.expert_bytes / (1024**2) == 4.6875
    assert IQ1_ALL.all_routed_bytes / GIB == 46.875


def test_current_iq2_layout_size() -> None:
    assert CURRENT_IQ2.gate_type == "IQ2_XXS"
    assert CURRENT_IQ2.down_type == "Q2_K"
    assert CURRENT_IQ2.expert_bytes / (1024**2) == 6.75
    assert CURRENT_IQ2.all_routed_bytes / GIB == 67.5


def test_hot_iq2_plus_warm_iq1_is_larger_than_all_iq1() -> None:
    mixed = mixed_hot_iq2_warm_iq1(8)
    assert mixed["all_routed_gib"] == 47.51953125
    assert mixed["all_routed_bytes"] > IQ1_ALL.all_routed_bytes


def test_q1_0_g128_candidate_matches_1p125_bpw_accounting() -> None:
    assert BLOCK_BYTES["Q1_0_G128"] == 36
    assert BLOCK_BYTES["Q1_0_G128"] * 8 / 256 == 1.125
