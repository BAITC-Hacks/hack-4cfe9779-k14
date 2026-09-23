"""Reviewable demo compatibility profiles; not approved EKT production criteria."""

# These rules apply only to the synthetic mock cable dataset. A partner must
# confirm category taxonomy and mandatory interchangeability parameters before
# any production profile is enabled.
DEMO_COMPATIBILITY_PROFILES: dict[str, dict[str, tuple[str, ...]]] = {
    "Кабель и провод": {
        "required_characteristics": ("material", "cores", "cross_section_mm2"),
        "optional_characteristics": (),
    },
}
DEMO_COMPATIBILITY_RULES_SOURCE = "demo/unconfirmed compatibility rules for mock cable data"
