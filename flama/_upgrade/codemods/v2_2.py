from flama._upgrade.migration import Migration
from flama._upgrade.operations import ArgumentToLiteral

__all__ = ["V2_2"]

V2_2 = Migration(
    target="2.2",
    source=">=2.0,<2.2",
    operations=(
        ArgumentToLiteral(
            "flama.crypto.algorithms",
            "HMACAlgorithm",
            values=(("sha256", "HS256"), ("sha384", "HS384"), ("sha512", "HS512")),
            note="`HMACAlgorithm(...)` now takes a JWA algorithm name (`HS256`, `HS384` or `HS512`) rather "
            "than a hash constructor",
        ),
    ),
)
