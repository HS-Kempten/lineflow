import unittest
import pygame
import simpy
from pygame import Vector2

from lineflow.simulation.movable_objects import (
    Part,
    Carrier,
)


class TestParts(unittest.TestCase):

    def setUp(self):
        self.env = simpy.Environment()

        self.specs = {
            "A1": {'assembly_condition': 5},
            "P1": {'extra_processing_time': 10, 'state': 'nok'},
        }

    def test_init(self):

        part = Part(env=self.env, name='C1-1')
        self.assertEqual(part.name, 'C1-1')

    def test_create(self):
        part = Part(env=self.env, name='C1-1')
        part.create(position=Vector2(1, 2))
        self.assertTrue(part.creation_time == 0)
        self.assertIsInstance(part._position, Vector2)

    def test_execption_on_position(self):
        part = Part(env=self.env, name='C1-1')
        with self.assertRaises(ValueError):
            part.create(position=(1, 2))

    def test_dict_like_access(self):
        specs = {"assembly_condition": 5}
        part = Part(env=self.env, name="env", specs=specs)
        self.assertEqual(part["assembly_condition"], 5)

    def test_specs_with_problematic_values(self):
        specs = {"create": 5}
        part = Part(env=self.env, name="env", specs=specs)

    def test_is_valid_for_assembly(self):
        part = Part(env=self.env, name="env", specs=self.specs)

        self.assertTrue(part.is_valid_for_assembly("A1"))

    def test_is_nok(self):
        part = Part(env=self.env, name="env", specs=self.specs)
        self.assertEqual(part.nok_probability, 0.0)


class TestCarrier(unittest.TestCase):

    def setUp(self):
        self.env = simpy.Environment()

    def test_init(self):
        Carrier(env=self.env, name='WPC1')

    def test_assemble(self):
        part = Part(env=self.env, name='C1-1')
        part.create(position=pygame.Vector2(200, 100))
        carrier = Carrier(env=self.env, name='WPC1')
        carrier.assemble(part)

        self.assertDictEqual(
            carrier.parts,
            {
                'C1-1': part
            }
        )

    def test_asemble_with_same_name(self):
        part_a = Part(env=self.env, name='C1-A')
        carrier = Carrier(env=self.env, name='WPC1')
        part_a.create(position=Vector2(1, 2))
        carrier.assemble(part_a)
        with self.assertRaises(ValueError):
            carrier.assemble(part_a)

    def test_multi_assemble(self):
        part_a = Part(env=self.env, name='C1-A')
        part_b = Part(env=self.env, name='C1-B')
        part_b.create(position=pygame.Vector2(200, 100))
        part_a.create(position=pygame.Vector2(200, 100))
        carrier = Carrier(env=self.env, name='WPC1')
        carrier.assemble(part_a)
        carrier.assemble(part_b)

        self.assertDictEqual(
            carrier.parts,
            {
                'C1-A': part_a,
                'C1-B': part_b
            }
        )

    def test_move(self):
        carrier = Carrier(env=self.env, name='WPC1')
        carrier.move(position=Vector2(1, 2))

    def test_draw(self):
        part = Part(env=self.env, name='C1-1')
        part.create(position=pygame.Vector2(200, 100))
        carrier = Carrier(env=self.env, name='WPC1')
        carrier.assemble(part)
