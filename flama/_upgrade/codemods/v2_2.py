from flama._upgrade.migration import Migration
from flama._upgrade.operations import Call, MapArgument, Rewrite, Symbol

__all__ = ["V2_2"]

V2_2 = Migration(
    target="2.2",
    source=">=2.0,<2.2",
    operations=(
        Rewrite(
            Call(Symbol("flama.crypto.algorithms", "HMACAlgorithm")),
            MapArgument(
                0,
                {"sha256": "HS256", "sha384": "HS384", "sha512": "HS512"},
                note="`HMACAlgorithm(...)` now takes a JWA algorithm name (`HS256`, `HS384` or `HS512`) rather "
                "than a hash constructor",
            ),
        ),
    ),
)
