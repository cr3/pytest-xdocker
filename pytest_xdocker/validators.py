"""Attr validators."""

from attrs import define, field
from hamcrest import assert_that


def matches(matcher):
    """Use as field(validator=...) to matcher based validation."""
    return _MatchesValidator(matcher)


@define(frozen=True, repr=False)
class _MatchesValidator:

    matcher = field()

    def __call__(self, inst, attr, value):
        assert_that(value, self.matcher)

    def __repr__(self):
        return f"matches <{self.matcher}>"
