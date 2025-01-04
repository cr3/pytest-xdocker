"""Attr validators."""

import attr
from hamcrest import assert_that


def matches(matcher):
    """Use as attr.ib(validator=...) to matcher based validation."""
    return _MatchesValidator(matcher)


@attr.s(frozen=True, repr=False, slots=True)
class _MatchesValidator:
    matcher = attr.ib()

    def __call__(self, inst, attr, value):
        assert_that(value, self.matcher)

    def __repr__(self):
        return f"matches <{self.matcher}>"
