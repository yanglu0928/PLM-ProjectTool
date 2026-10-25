import unittest
import uuid
from unittest.mock import Mock
from types import SimpleNamespace

from plm_assistant.modules.parser.application.system_actor_binding import (
    ParserSystemActorBinding, ParserSystemActorUnavailable,
)


class ParserSystemActorBindingTests(unittest.TestCase):
    def test_fixed_identity_keeps_existing_internal_contract(self):
        value = uuid.uuid4()
        binding = ParserSystemActorBinding(system_actor_id=value)
        self.assertEqual(binding.capture(), value)
        binding.assert_same(value)

    def test_controlled_identity_loss_or_change_fails_closed(self):
        first = uuid.uuid4()
        actor = SimpleNamespace(assert_current=Mock())
        actor.assert_current.side_effect = (first, uuid.uuid4())
        binding = ParserSystemActorBinding(system_actor=actor)
        self.assertEqual(binding.capture(), first)
        with self.assertRaises(ParserSystemActorUnavailable):
            binding.assert_same(first)
        actor.assert_current.side_effect = RuntimeError("synthetic Vault loss")
        with self.assertRaises(ParserSystemActorUnavailable):
            binding.capture()

    def test_invalid_ambiguous_or_missing_source_rejected(self):
        for kwargs in ({}, {"system_actor_id": uuid.UUID(int=0)},
                       {"system_actor": object()},
                       {"system_actor_id": uuid.uuid4(),
                        "system_actor": Mock()}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ParserSystemActorBinding(**kwargs)


if __name__ == "__main__":
    unittest.main()
