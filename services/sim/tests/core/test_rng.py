"""SimRng tests (NX-100, SIM-CORE SC-5 / SC-9, ADR-0002)."""

import json
import os
import subprocess
import sys

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from nexus.core.rng import PcgStream, RngStream, SimRng

seeds = st.integers(min_value=0, max_value=2**64 - 1)
streams = st.sampled_from(list(RngStream))
counts = st.integers(min_value=0, max_value=50)


def draws(rng: SimRng, name: RngStream, n: int) -> list[int]:
    s = rng.stream(name)
    return [s.next_u64() for _ in range(n)]


def test_golden_seed_12345() -> None:
    # Pinned by running this implementation once (NX-100); not from an external reference.
    # A change here means every recorded replay breaks: needs a `golden-update` reason.
    rng = SimRng(12345)
    assert draws(rng, RngStream.COMBAT, 4) == [
        0x9F3D506061AB8E64,
        0x7164ABC4AD587592,
        0x8773F56456DB236F,
        0x79BA706EF7804B94,
    ]
    assert draws(rng, RngStream.DIRECTOR, 4) == [
        0xADDC330532E15198,
        0x8328BD72076C3046,
        0x610D8F06C8625EFB,
        0x544DBF273CE9CC49,
    ]


def test_matches_numpy_pcg64() -> None:
    np = pytest.importorskip("numpy")
    ours = SimRng(7).stream(RngStream.SPAWN)
    state = SimRng(7).to_state()["spawn"]
    bitgen = np.random.PCG64()
    bitgen.state = {
        "bit_generator": "PCG64",
        "state": {"state": int(state["state"], 16), "inc": int(state["inc"], 16)},
        "has_uint32": 0,
        "uinteger": 0,
    }
    theirs = bitgen.random_raw(8).tolist()
    assert [ours.next_u64() for _ in range(8)] == theirs


@given(seed=seeds, name=streams, n=counts)
def test_same_seed_same_draws(seed: int, name: RngStream, n: int) -> None:
    assert draws(SimRng(seed), name, n) == draws(SimRng(seed), name, n)


@given(seed=seeds, drawn=streams, other=streams, n=counts)
def test_streams_are_independent(seed: int, drawn: RngStream, other: RngStream, n: int) -> None:
    assume(drawn != other)
    busy = SimRng(seed)
    draws(busy, drawn, n)
    assert draws(busy, other, 3) == draws(SimRng(seed), other, 3)


def test_different_seeds_and_streams_differ() -> None:
    by_stream = {name: draws(SimRng(1), name, 3) for name in RngStream}
    assert len({tuple(v) for v in by_stream.values()}) == len(RngStream)
    assert draws(SimRng(1), RngStream.COMBAT, 3) != draws(SimRng(2), RngStream.COMBAT, 3)


def test_stream_is_same_object_and_unknown_names_fail() -> None:
    rng = SimRng(0)
    assert rng.stream(RngStream.COMBAT) is rng.stream("combat")
    with pytest.raises(ValueError):
        rng.stream("fow")


@given(seed=seeds, name=streams, k=counts, m=st.integers(min_value=1, max_value=20))
def test_snapshot_round_trip(seed: int, name: RngStream, k: int, m: int) -> None:
    straight = SimRng(seed)
    expected = draws(straight, name, k + m)[k:]
    rng = SimRng(seed)
    draws(rng, name, k)
    restored = SimRng.from_state(json.loads(json.dumps(rng.to_state())))
    assert draws(restored, name, m) == expected
    assert restored.to_state() == straight.to_state()


def test_to_state_is_sorted_plain_data() -> None:
    state = SimRng(3).to_state()
    assert list(state) == sorted(n.value for n in RngStream)
    assert all(len(v["state"]) == 32 and len(v["inc"]) == 32 for v in state.values())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("combat"),
        lambda d: d.update(fow=d["combat"]),
        lambda d: d["combat"].pop("inc"),
        lambda d: d["combat"].update(inc="0" * 32),
        lambda d: d["combat"].update(state="z" * 32),
        lambda d: d["combat"].update(state=5),
    ],
)
def test_from_state_rejects_bad_data(mutate: object) -> None:
    data = SimRng(3).to_state()
    mutate(data)  # type: ignore[operator]  # parametrized lambdas are untyped
    with pytest.raises(ValueError):
        SimRng.from_state(data)


@pytest.mark.parametrize("seed", [-1, 2**64, True, 1.0])
def test_bad_seed_rejected(seed: object) -> None:
    with pytest.raises(ValueError):
        SimRng(seed)  # type: ignore[arg-type]  # deliberately wrong input


@given(seed=seeds, n=st.integers(min_value=1, max_value=2**64), lo=st.integers(-1000, 1000))
def test_ranges(seed: int, n: int, lo: int) -> None:
    s = SimRng(seed).stream(RngStream.COMBAT)
    assert 0 <= s.randbelow(n) < n
    assert s.randbelow(1) == 0
    assert 0.0 <= s.random() < 1.0
    hi = lo + n % 5
    assert lo <= s.randint(lo, hi) <= hi
    assert s.randint(lo, lo) == lo


def test_randint_hits_both_ends() -> None:
    s = SimRng(9).stream(RngStream.TASKING)
    assert {s.randint(1, 3) for _ in range(200)} == {1, 2, 3}


def test_invalid_ranges_rejected() -> None:
    s = SimRng(0).stream(RngStream.COMBAT)
    for bad in (0, -1, 2**64 + 1):
        with pytest.raises(ValueError):
            s.randbelow(bad)
    with pytest.raises(ValueError):
        s.randint(2, 1)
    with pytest.raises(ValueError):
        PcgStream(0, 2)


_CHILD = (
    "from nexus.core.rng import SimRng\n"
    "r = SimRng(424242)\n"
    "print([[r.stream(n).next_u64() for _ in range(5)] for n in sorted(r.to_state())])\n"
)


def test_cross_process_hash_seed_independent() -> None:
    def run(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        return subprocess.run(  # noqa: S603  # fixed argv: this interpreter + a literal script
            [sys.executable, "-c", _CHILD], env=env, check=True, capture_output=True, text=True
        ).stdout

    assert run("1") == run("2") != ""


class _ScriptedStream(PcgStream):
    __slots__ = ("_script",)

    def __init__(self, script: list[int]) -> None:
        super().__init__(0, 1)
        self._script = iter(script)

    def next_u64(self) -> int:
        return next(self._script)


def test_randbelow_redraws_past_the_last_full_block() -> None:
    # 2**64 - 1 is past the last multiple of 3 below 2**64, so it must be redrawn.
    assert _ScriptedStream([2**64 - 1, 7]).randbelow(3) == 7 % 3


def test_edge_draws_stay_in_range() -> None:
    assert _ScriptedStream([2**64 - 1]).random() < 1.0
    assert _ScriptedStream([2**64 - 1]).randbelow(2**64) == 2**64 - 1


@pytest.mark.parametrize(
    "bad", ["0x" + "0" * 30, "A" * 32, " " + "0" * 31, "0" * 15 + "_" + "0" * 16]
)
def test_from_state_rejects_non_canonical_hex(bad: str) -> None:
    data = SimRng(1).to_state()
    data["combat"]["state"] = bad
    with pytest.raises(ValueError):
        SimRng.from_state(data)
