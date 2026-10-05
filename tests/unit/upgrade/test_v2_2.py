import pathlib

import pytest

from flama._upgrade.codemods import MIGRATIONS
from flama._upgrade.codemods.v2_2 import V2_2
from flama._upgrade.source import Source


class TestCaseUpgradeV22:
    def test_registered(self) -> None:
        assert V2_2 in MIGRATIONS
        assert V2_2.target == "2.2"

    @pytest.mark.parametrize(
        ["before", "after"],
        [
            pytest.param(
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm(hashlib.sha256)\n",
                'from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm("HS256")\n',
                id="hmac_sha256_to_name",
            ),
            pytest.param(
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm(hashlib.sha384)\n",
                'from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm("HS384")\n',
                id="hmac_sha384_to_name",
            ),
            pytest.param(
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm(hashlib.sha512)\n",
                'from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm("HS512")\n',
                id="hmac_sha512_to_name",
            ),
            pytest.param(
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm(sha256)\n",
                'from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm("HS256")\n',
                id="hash_imported_directly",
            ),
        ],
    )
    def test_apply(self, before: str, after: str) -> None:
        result, _, _ = V2_2.apply(Source.parse(pathlib.Path("a.py"), before))

        assert result.text == after

    def test_hash_outside_jwa_is_flagged(self) -> None:
        before = "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm(hashlib.md5)\n"

        result, todos, changed = V2_2.apply(Source.parse(pathlib.Path("a.py"), before))

        assert changed is False
        assert result.text == before
        assert len(todos) == 1
        assert "HS256" in todos[0].message

    def test_applies_after_the_v2_relocation(self) -> None:
        before = "from flama.authentication.jwt.algorithms import HMACAlgorithm\na = HMACAlgorithm(hashlib.sha256)\n"
        expected = 'from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm("HS256")\n'

        relocated, _, _ = MIGRATIONS[0].apply(Source.parse(pathlib.Path("a.py"), before))
        result, _, _ = V2_2.apply(relocated)

        assert result.text == expected
